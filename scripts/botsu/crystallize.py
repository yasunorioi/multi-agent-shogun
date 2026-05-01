"""crystallize — cmd完了時の自動結晶化機構 v2 (cmd_517 hybrid).

cmd_update(status='done') 時に呼ばれ、以下を実行:
1. cmds/subtasks/git logからダイジェスト生成
2. agent-swarm DAT スレ "cmd_XXX" (board=crystals) に >>1-5 を5レス連投
3. ${SHOGUN_CRYSTALS_DIR}/{project}.md に目次行をappend

graceful degradation: 失敗時はwarn のみ。cmd完了処理を阻害しない。
冪等性: 同cmd再実行で重複しない。
"""

import fcntl
import logging
import os
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from . import get_connection

logger = logging.getLogger(__name__)


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _truncate(text: str, n: int) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[:n] + "..."


def _fetch_cmd_info(cmd_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, command, details, project, status, created_at, completed_at"
            " FROM commands WHERE id = ?",
            (cmd_id,),
        ).fetchone()
        if not row:
            return None
        subtasks = conn.execute(
            "SELECT id, status, description FROM subtasks WHERE parent_cmd = ? ORDER BY id",
            (cmd_id,),
        ).fetchall()
        return {
            "id": row["id"],
            "command": row["command"] or "",
            "details": row["details"] or "",
            "project": row["project"] or "shogun",
            "status": row["status"] or "",
            "created_at": row["created_at"] or "",
            "completed_at": row["completed_at"] or "",
            "subtasks": [dict(s) for s in subtasks],
        }
    finally:
        conn.close()


def _git_log_summary(since: str, until: str) -> str:
    if not since:
        return "(取得失敗)"
    cwd = os.environ.get("SHOGUN_ROOT", "/home/yasu/multi-agent-shogun")
    try:
        cmd = ["git", "log", f"--since={since}", "--pretty=format:%h %s", "-n", "5"]
        if until:
            cmd.insert(2, f"--until={until}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, cwd=cwd)
        if result.returncode != 0:
            return "(取得失敗)"
        return result.stdout.strip() or "(コミットなし)"
    except Exception:
        return "(取得失敗)"


def _build_templates(info: dict) -> list[str]:
    cmd_id = info["id"]
    project = info["project"]

    q_body = info["command"]
    if info["details"]:
        q_body = q_body + " / " + info["details"].replace("\n", " ")
    body1 = f">>1 問い [project: {project}]\n{_truncate(q_body, 300)}"

    done_subs = [s for s in info["subtasks"] if s["status"] == "done"]
    if done_subs:
        lines = []
        for s in done_subs[:5]:
            desc = (s["description"] or "").split("\n")[0]
            lines.append(f"- {s['id']}: {_truncate(desc, 100)}")
        body2 = ">>2 結果\n" + "\n".join(lines)
    else:
        body2 = ">>2 結果\n(完了サブタスクなし)"

    body3 = ">>3 変更点\n" + _truncate(_git_log_summary(info["created_at"], info["completed_at"]), 500)

    body4 = ">>4 学び\n(空欄)"

    body5 = (f">>5 関連\nproject={project}, completed_at={info['completed_at']}")

    return [body1, body2, body3, body4, body5]


def _swarm_post_python(thread_id: str, board: str, bodies: list[str]) -> bool:
    """agent-swarm botsu.reply.do_reply_add 直叩き (notify=False)。

    sys.path競合(unknown_unknowns #8)対策: sys.modules 退避で shogun側 botsu と分離。
    """
    swarm_path = _env("SWARM_SERVER_PATH", "/home/yasu/agent-swarm/server")
    if not os.path.isdir(swarm_path):
        return False

    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "botsu" or k.startswith("botsu.")}
    sys.path.insert(0, swarm_path)
    try:
        from botsu.reply import do_reply_add  # type: ignore
        for body in bodies:
            do_reply_add(thread_id, board, "shogun", body, notify=False)
        return True
    except Exception as e:
        logger.warning(f"swarm Python direct call failed: {e}")
        return False
    finally:
        for k in [k for k in list(sys.modules) if k == "botsu" or k.startswith("botsu.")]:
            del sys.modules[k]
        for k, v in saved.items():
            sys.modules[k] = v
        try:
            sys.path.remove(swarm_path)
        except ValueError:
            pass


def _swarm_post_http(thread_id: str, board: str, bodies: list[str]) -> bool:
    base = _env("SWARM_DAT_URL", "http://localhost:8824")
    url = f"{base}/bbs/test/bbs.cgi"
    for body in bodies:
        try:
            data = urllib.parse.urlencode({
                "bbs": board, "key": thread_id, "FROM": "shogun",
                "MESSAGE": body, "time": "0",
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as e:
            logger.warning(f"HTTP POST failed for {thread_id}: {e}")
            return False
    return True


def _dat_already_exists(thread_id: str, board: str) -> bool:
    db_path = _env("SWARM_DB", "/home/yasu/agent-swarm/data/swarm.db")
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM thread_replies WHERE thread_id = ? AND board = ? LIMIT 1",
                (thread_id, board),
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except Exception:
        return False


def _md_append(project: str, cmd_id: str, info: dict) -> bool:
    crystals_dir = Path(_env("SHOGUN_CRYSTALS_DIR", "/home/yasu/agent-swarm/crystals"))
    crystals_dir.mkdir(parents=True, exist_ok=True)
    md_path = crystals_dir / f"{project}.md"

    if md_path.exists():
        with open(md_path, "r", encoding="utf-8") as f:
            if f"### {cmd_id}:" in f.read():
                return True

    completed_date = (info["completed_at"] or "")[:10]
    q_excerpt = _truncate(info["command"].replace("\n", " "), 80)
    base = _env("SWARM_DAT_URL", "http://localhost:8824")
    board = _env("SWARM_BOARD", "crystals")
    dat_url = f"{base}/bbs/test/read.cgi/{board}/{cmd_id}"

    block = (
        f"\n### {cmd_id}: {q_excerpt} ({completed_date}) [→ DAT #{cmd_id}]\n"
        f"- **問い**: {q_excerpt}\n"
        f"- **DAT**: {dat_url}\n"
    )

    with open(md_path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(block)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return True


def crystallize_cmd(cmd_id: str) -> dict:
    """cmd_id を結晶化。返り値: {posted, md_appended, skipped, reason}"""
    if _env("SHOGUN_CRYSTALS_DISABLE", "0") == "1":
        return {"posted": False, "md_appended": False, "skipped": True, "reason": "disabled"}

    info = _fetch_cmd_info(cmd_id)
    if not info:
        return {"posted": False, "md_appended": False, "skipped": True, "reason": "cmd_not_found"}

    bodies = _build_templates(info)
    board = _env("SWARM_BOARD", "crystals")

    if _dat_already_exists(cmd_id, board):
        posted = True
    else:
        posted = _swarm_post_python(cmd_id, board, bodies) or _swarm_post_http(cmd_id, board, bodies)

    md_appended = False
    try:
        md_appended = _md_append(info["project"], cmd_id, info)
    except Exception as e:
        logger.warning(f"MD append failed for {cmd_id}: {e}")

    return {
        "posted": posted,
        "md_appended": md_appended,
        "skipped": False,
        "reason": "ok" if (posted and md_appended) else "partial",
    }


# ====== プロジェクトテンプレ機構(cmd_571追加) ======

TEMPLATE_REPLY_DEFINITIONS: dict[int, tuple[str, str]] = {
    1:  ("project_overview", "プロジェクト概要"),
    2:  ("architecture",     "アーキテクチャ図"),
    3:  ("components",       "主要構成要素"),
    4:  ("data_flow",        "データフロー"),
    5:  ("gotchas",          "既知の癖・地雷"),
    6:  ("file_index",       "重要ファイルパス索引"),
    7:  ("env_vars",         "環境変数・設定値"),
    8:  ("metrics",          "メトリクス・ヘルスチェック"),
    9:  ("external_links",   "外部接続点"),
    10: ("glossary",         "用語集・命名由来"),
}


def _existing_template_nums(thread_id: str, board: str) -> set[int]:
    """thread_replies から `<!-- TEMPLATE:N -->` を持つレスの N を抽出。"""
    db_path = _env("SWARM_DB", "/home/yasu/agent-swarm/data/swarm.db")
    if not os.path.exists(db_path):
        return set()
    nums: set[int] = set()
    try:
        conn = sqlite3.connect(db_path)
        try:
            for (body,) in conn.execute(
                "SELECT body FROM thread_replies WHERE thread_id=? AND board=?",
                (thread_id, board),
            ):
                m = re.search(r"<!-- TEMPLATE:(\d+) -->", body or "")
                if m:
                    nums.add(int(m.group(1)))
        finally:
            conn.close()
    except Exception:
        pass
    return nums


def init_project_template(
    project: str,
    scaffolds: dict[int, str] | None = None,
    dry_run: bool = False,
) -> dict:
    """`project_{project}` スレを初期化し >>1-10 テンプレを投稿する。

    scaffolds: {n: "本文"} で各レスを任意指定。未指定はプレースホルダを投稿。
    冪等性: 既存 <!-- TEMPLATE:N --> があるレスはスキップ。
    dry_run=True: 投稿せず posted リストのみ返す（テスト用）。
    """
    thread_id = f"project_{project}"
    board = _env("SWARM_BOARD", "crystals")
    scaffolds = scaffolds or {}

    existing = _existing_template_nums(thread_id, board)
    posted: list[int] = []
    for n, (_slug, label) in TEMPLATE_REPLY_DEFINITIONS.items():
        if n in existing:
            continue
        body = scaffolds.get(n) or f"<!-- TEMPLATE:{n} -->\n>>{n} {label}\n(未記入)"
        if "<!-- TEMPLATE:" not in body:
            body = f"<!-- TEMPLATE:{n} -->\n{body}"
        if dry_run:
            posted.append(n)
            continue
        ok = _swarm_post_python(thread_id, board, [body]) or _swarm_post_http(thread_id, board, [body])
        if ok:
            posted.append(n)
    return {"thread_id": thread_id, "posted": posted}


def update_template_reply(
    project: str,
    reply_no: int,
    body: str,
    dry_run: bool = False,
) -> dict:
    """テンプレレスを更新する（実態は新規 INSERT・最新版優先方式）。

    INSERT-only: thread_replies への UPDATE/DELETE は行わない。
    dry_run=True: 投稿せず updated=True を返す（テスト用）。
    """
    if reply_no not in TEMPLATE_REPLY_DEFINITIONS:
        return {"updated": False, "reason": "invalid_reply_no"}
    thread_id = f"project_{project}"
    board = _env("SWARM_BOARD", "crystals")
    if "<!-- TEMPLATE:" not in body:
        body = f"<!-- TEMPLATE:{reply_no} -->\n{body}"
    if dry_run:
        return {"updated": True, "thread_id": thread_id, "reply_no": reply_no, "dry_run": True}
    ok = _swarm_post_python(thread_id, board, [body]) or _swarm_post_http(thread_id, board, [body])
    return {"updated": ok, "thread_id": thread_id, "reply_no": reply_no}
