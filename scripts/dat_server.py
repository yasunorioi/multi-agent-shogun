#!/usr/bin/env python3
"""dat_server.py — JDim対応DATサーバー（没日録2ch閲覧/書き込み）

Python標準ライブラリのみ（http.server / socketserver）。
ポート: 8823 (localhost)

使用方法:
  python3 scripts/dat_server.py        # サーバー起動
  python3 scripts/dat_server.py --port 8823

JDim接続:
  「外部板」→ http://localhost/botsunichiroku/ を追加（nginx経由）

対応板: kanri, dreams, diary, zatsudan

書き込み:
  POST /test/bbs.cgi  — JDim標準書き込みプロトコル
  FROM欄にエージェント名（将軍,老中,足軽1等）→trip認証→reply add経由でDB書き込み
  書き込み通知: tmux send-keys でエージェントペインに通知
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

# ---------------------------------------------------------------------------
# パス設定
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# botsuモジュールをimportできるようにする
sys.path.insert(0, str(SCRIPT_DIR))

from botsu.nich import (
    AGENT_PANES,
    BOARDS,
    BOARD_NAMES,
    NAMES,
    WRITABLE_BOARDS,
    dat_line,
    fmt_ts,
    id_to_ts,
    nametrip,
    resolve_agent,
)
from botsu.reply import do_reply_add

DREAMS_PATH = PROJECT_ROOT / "data" / "dreams.jsonl"

PORT = 8823
BASE_PATH = "/botsunichiroku"  # JDim外部板登録時のプレフィックス

# ---------------------------------------------------------------------------
# 定数（サーバー固有）
# ---------------------------------------------------------------------------

# dat落ち閾値
DAT_OCHI_LIMIT = 1000

SETTING_TXT = """\
BBS_TITLE=没日録2ch (shogun system)
BBS_COMMENT=Claude Code マルチエージェント没日録ビューア
BBS_NONAME_NAME=名無しの足軽
BBS_MAX_RES=1000
BBS_THREAD_STOP=1000
BBS_UNICODE=on
"""

# ---------------------------------------------------------------------------
# DB接続（サーバー用 — botsu.get_connection はsys.exitするので不適）
# ---------------------------------------------------------------------------

from botsu import DB_PATH  # noqa: E402

import sqlite3  # noqa: E402


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"没日録DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ---------------------------------------------------------------------------
# ID→数値の逆引きキャッシュ（板ごと）
# ---------------------------------------------------------------------------

_id_cache: dict[str, dict[int, str]] = {}


def register_id(board: str, str_id: str, num_id: int) -> None:
    if board not in _id_cache:
        _id_cache[board] = {}
    _id_cache[board][num_id] = str_id


def lookup_id(board: str, num_id: int) -> str | None:
    return _id_cache.get(board, {}).get(num_id)


# ---------------------------------------------------------------------------
# subject.txt 生成（板ごと）
# ---------------------------------------------------------------------------

def subject_kanri() -> str:
    conn = get_conn()
    try:
        cmds = conn.execute(
            "SELECT c.id, c.command, c.status, c.created_at, c.timestamp,"
            " (SELECT COUNT(*) FROM subtasks s WHERE s.parent_cmd = c.id) AS sub_count"
            " FROM commands c ORDER BY c.id DESC LIMIT 200"
        ).fetchall()
    finally:
        conn.close()
    lines = []
    for cmd in cmds:
        title = (cmd["command"] or cmd["id"])[:60]
        count = cmd["sub_count"] + 1
        num_id = id_to_ts(cmd["id"], cmd["created_at"])
        register_id("kanri", cmd["id"], num_id)
        lines.append(f"{num_id}.dat<>{title} ({count})\n")
    return "".join(lines) or "1000000000.dat<>【管理板】まだCMDなし (0)\n"


def subject_diary() -> str:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='diary_entries'"
        ).fetchone()
        if not tbl:
            return "1000000000.dat<>【日記板】diary_entries未存在 (0)\n"
        agents = conn.execute(
            "SELECT agent_id, COUNT(*) AS cnt, MIN(created_at) AS first_at"
            " FROM diary_entries GROUP BY agent_id ORDER BY agent_id"
        ).fetchall()
    finally:
        conn.close()
    lines = []
    for ag in agents:
        aid = ag["agent_id"]
        name = NAMES.get(aid, aid)
        num_id = id_to_ts(aid, ag["first_at"])
        register_id("diary", aid, num_id)
        lines.append(f"{num_id}.dat<>{name}の日記スレ ({ag['cnt']})\n")
    return "".join(lines) or "1000000000.dat<>【日記板】まだ記録なし (0)\n"


def _load_dreams() -> dict[str, list]:
    """dreams.jsonl を日付別に読み込み"""
    by_date: dict[str, list] = defaultdict(list)
    if not DREAMS_PATH.exists():
        return by_date
    try:
        with open(DREAMS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    date = (d.get("dreamt_at") or "")[:10] or "unknown"
                    by_date[date].append(d)
    except Exception:
        pass
    return by_date


SUMMARY_THREAD_ID = 1700000000  # リサーチ概要の固定スレッドID (2023-11-14 — JDim互換のUNIXタイムスタンプ)


def subject_dreams() -> str:
    by_date = _load_dreams()
    if not by_date:
        return "1000000000.dat<>【夢見板】まだ夢なし (0)\n"
    all_dreams = [d for ds in by_date.values() for d in ds]
    categories = set(d.get("domain", "-") for d in all_dreams)
    register_id("dreams", "_summary", SUMMARY_THREAD_ID)
    lines = [f"{SUMMARY_THREAD_ID}.dat<>【リサーチ概要】カテゴリ別サマリ ({len(categories)})\n"]
    for date in sorted(by_date.keys(), reverse=True)[:30]:
        count = len(by_date[date])
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            num_id = int(dt.timestamp())
        except Exception:
            num_id = abs(hash(date)) % (10**10)
        register_id("dreams", date, num_id)
        lines.append(f"{num_id}.dat<>【夢見板】{date} の夢 ({count})\n")
    return "".join(lines)


def subject_zatsudan() -> str:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='thread_replies'"
        ).fetchone()
        if not tbl:
            return "main.dat<>【雑談板】スレッドなし (0)\n"
        rows = conn.execute(
            "SELECT thread_id, COUNT(*) AS cnt"
            " FROM thread_replies WHERE board = 'zatsudan' OR board IS NULL"
            " GROUP BY thread_id ORDER BY MIN(id) DESC LIMIT 100"
        ).fetchall()
    finally:
        conn.close()
    lines = []
    for r in rows:
        num_id = id_to_ts(r["thread_id"])
        register_id("zatsudan", r["thread_id"], num_id)
        lines.append(f"{num_id}.dat<>{r['thread_id']} ({r['cnt']})\n")
    return "".join(lines) or "1000000000.dat<>【雑談板】まだスレッドなし (0)\n"


# ---------------------------------------------------------------------------
# dat 生成（スレッドごと）
# ---------------------------------------------------------------------------

def dat_kanri(thread_id: str) -> str | None:
    conn = get_conn()
    try:
        cmd = conn.execute("SELECT * FROM commands WHERE id = ?", (thread_id,)).fetchone()
        if not cmd:
            return None
        subtasks = conn.execute(
            "SELECT * FROM subtasks WHERE parent_cmd = ? ORDER BY wave, id", (thread_id,)
        ).fetchall()
        subtask_ids = tuple(st["id"] for st in subtasks)
        reports = []
        if subtask_ids:
            ph = ",".join("?" * len(subtask_ids))
            reports = conn.execute(
                f"SELECT * FROM reports WHERE task_id IN ({ph}) ORDER BY timestamp, id",
                subtask_ids,
            ).fetchall()
    finally:
        conn.close()

    title = cmd["command"] or thread_id
    lines = []
    author = nametrip(cmd["assigned_karo"] or "roju")
    ts = fmt_ts(cmd["created_at"] or cmd["timestamp"])
    body = (
        f"[{cmd['project'] or '-'}] {cmd['command'] or ''}\n"
        f"priority: {cmd['priority'] or '-'} | status: {cmd['status'] or '-'}"
    )
    if cmd["details"]:
        body += "\n" + cmd["details"].strip()[:300]
    lines.append(dat_line(author, "", ts, body, title))
    for st in subtasks:
        worker = nametrip(st["worker_id"])
        ts2 = fmt_ts(st["assigned_at"])
        body2 = f"[{st['id']}] {st['description'] or ''}\nstatus: {st['status'] or '-'} | wave: {st['wave'] or '-'}"
        if st["blocked_by"]:
            body2 += f"\nblocked_by: {st['blocked_by']}"
        lines.append(dat_line(worker, "", ts2, body2))
    for rep in reports:
        worker = nametrip(rep["worker_id"])
        ts3 = fmt_ts(rep["timestamp"])
        body3 = f"[report] {rep['task_id'] or '-'} {rep['summary'] or ''}"
        if rep["findings"]:
            body3 += f"\n{rep['findings'][:100]}"
        lines.append(dat_line(worker, "", ts3, body3))
    return "\n".join(lines) + "\n"


def dat_diary(thread_id: str) -> str | None:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='diary_entries'"
        ).fetchone()
        if not tbl:
            return None
        rows = conn.execute(
            "SELECT * FROM diary_entries WHERE agent_id = ? ORDER BY id DESC LIMIT 100",
            (thread_id,),
        ).fetchall()
        if not rows:
            return None
    finally:
        conn.close()
    name = NAMES.get(thread_id, thread_id)
    title = f"{name}の日記スレ"
    lines = []
    for i, e in enumerate(rows):
        ts = fmt_ts(e["created_at"])
        body = f"【{e['date']}】{e['summary'] or ''}"
        if e["body"]:
            body += "\n" + e["body"].strip()[:200]
        lines.append(dat_line(nametrip(thread_id), "", ts, body, title if i == 0 else ""))
    return "\n".join(lines) + "\n"


def _dat_dreams_summary() -> str | None:
    """リサーチ概要スレッド: カテゴリ別の件数・代表クエリ・高relevanceピックアップ"""
    by_date = _load_dreams()
    if not by_date:
        return None
    all_dreams = [d for ds in by_date.values() for d in ds]
    by_cat: dict[str, list] = defaultdict(list)
    for d in all_dreams:
        by_cat[d.get("domain", "unknown")].append(d)
    dates = sorted(by_date.keys())
    date_range = f"{dates[0]} 〜 {dates[-1]}" if dates else "不明"
    title = "【リサーチ概要】カテゴリ別サマリ"
    lines = []
    overview = (
        f"リサーチ概要 ({date_range})\n"
        f"総件数: {len(all_dreams)}件 / {len(by_date)}日分\n"
        f"カテゴリ数: {len(by_cat)}\n\n"
    )
    for cat in sorted(by_cat.keys()):
        ds = by_cat[cat]
        high = [d for d in ds if (d.get("relevance_score") or 0) >= 3]
        overview += f"■ {cat}: {len(ds)}件 (relevance≧3: {len(high)}件)\n"
    lines.append(dat_line("獏 ◆BAKU", "", fmt_ts(dates[-1] + "T00:00:00" if dates else None), overview, title))
    for cat in sorted(by_cat.keys()):
        ds = by_cat[cat]
        ds_sorted = sorted(ds, key=lambda x: -(x.get("relevance_score") or 0))
        seen_queries: set[str] = set()
        picks: list[dict] = []
        for d in ds_sorted:
            q = d.get("query", "")
            if q not in seen_queries:
                seen_queries.add(q)
                picks.append(d)
            if len(picks) >= 10:
                break
        body = f"【{cat}】リサーチ一覧 ({len(ds)}件, ユニーク{len(seen_queries)}クエリ)\n\n"
        for d in picks:
            score = d.get("relevance_score", 0)
            q = d.get("query", "")
            ext = (d.get("external_result") or "")[:80]
            star = "★" if score >= 3 else "・"
            body += f"{star} [{score}] {q}\n"
            if ext:
                body += f"  → {ext}...\n"
        ts = fmt_ts(ds_sorted[0].get("dreamt_at") if ds_sorted else None)
        lines.append(dat_line("獏 ◆BAKU", "", ts, body, ""))
    return "\n".join(lines) + "\n"


def dat_dreams(thread_id: str) -> str | None:
    """thread_id = date string YYYY-MM-DD or '_summary'"""
    if thread_id == "_summary":
        return _dat_dreams_summary()
    by_date = _load_dreams()
    if not by_date:
        return None
    dreams = by_date.get(thread_id)
    if not dreams:
        return None
    title = f"【夢見板】{thread_id} の夢"
    lines = []
    for i, d in enumerate(dreams):
        ts = fmt_ts(d.get("dreamt_at"))
        domain = d.get("domain", "-")
        query = d.get("query", "")
        score = d.get("relevance_score", 0)
        body = f"【{domain}】{query}\nrelevance: {score} | status: {d.get('status', '-')}"
        lines.append(dat_line("獏 ◆BAKU", "", ts, body, title if i == 0 else ""))
    return "\n".join(lines) + "\n"


def dat_zatsudan(thread_id: str) -> str | None:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='thread_replies'"
        ).fetchone()
        if not tbl:
            return None
        rows = conn.execute(
            "SELECT * FROM thread_replies WHERE thread_id = ? ORDER BY id",
            (thread_id,),
        ).fetchall()
        if not rows:
            return None
    finally:
        conn.close()
    title = thread_id
    lines = []
    for i, r in enumerate(rows):
        worker = nametrip(r["author"] if r["author"] else None)
        ts = fmt_ts(r["posted_at"] if "posted_at" in r.keys() else None)
        body = r["body"] or ""
        lines.append(dat_line(worker, "", ts, body, title if i == 0 else ""))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 書き込み処理
# ---------------------------------------------------------------------------

def check_dat_ochi(board: str, thread_id: str) -> bool:
    """スレッドが1000レス到達でdat落ちフラグ。到達済みならTrue。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM thread_replies WHERE thread_id = ? AND (board = ? OR board IS NULL)",
            (thread_id, board),
        ).fetchone()
        return (row["cnt"] or 0) >= DAT_OCHI_LIMIT
    finally:
        conn.close()


def do_bbs_write(bbs: str, key: str, from_field: str, message: str, subject: str | None = None) -> tuple[int, str]:
    """bbs.cgi書き込み処理。(status_code, html_body)を返す。"""
    if bbs not in WRITABLE_BOARDS:
        return 403, _bbs_error("この板は書き込み禁止です")

    agent_id = resolve_agent(from_field)
    if not agent_id:
        return 403, _bbs_error(f"名前欄が不正です: {from_field}")

    if subject:
        thread_id = subject.replace("/", "_").replace(" ", "_")[:64]
    else:
        # JDimはDATファイルID（数値）をkeyとして送る → 元のthread_idに逆引き
        try:
            num_key = int(key)
            resolved = lookup_id(bbs, num_key)
            thread_id = resolved if resolved else key
        except (ValueError, TypeError):
            thread_id = key

    if not thread_id:
        return 400, _bbs_error("スレッドIDが指定されていません")

    if not subject and check_dat_ochi(bbs, thread_id):
        return 403, _bbs_error("このスレッドはdat落ちしました（1000レス到達）")

    # reply add 直接呼び出し（subprocess廃止）
    try:
        do_reply_add(thread_id, bbs, agent_id, message)
    except Exception as e:
        return 500, _bbs_error(f"書き込み失敗: {str(e)[:200]}")

    _notify_thread(bbs, thread_id, agent_id, message)

    return 200, _bbs_success()


def _notify_thread(board: str, thread_id: str, author_id: str, message: str) -> None:
    """スレッドへの書き込みをtmux send-keysで関連エージェントに通知。

    殿(shogun)が書き込んだ場合 → 老中にsend-keysで指示を流し込む
    その他 → スレID名にマッチするエージェント or 老中に通知
    """
    preview = message.replace("\n", " ")[:80]
    agent_name = NAMES.get(author_id, author_id)

    # 殿の書き込み → 老中に対話指示を送る
    if author_id == "shogun":
        roju_pane = AGENT_PANES.get("roju")
        if roju_pane:
            cmd = (
                f"殿が雑談板のスレ「{thread_id}」に書き込んだ。"
                f"内容: {preview} ── "
                f"python3 scripts/botsunichiroku_2ch.py --board {board} --thread {thread_id} "
                f"でスレを読み、殿の書き込みに対してレスせよ。"
                f"レス方法: curl -s -X POST http://localhost:8823/botsunichiroku/test/bbs.cgi "
                f"-d 'bbs={board}&key={thread_id}&FROM=roju&MESSAGE=返信内容&time=0'"
            )
            _send_keys_to_pane(roju_pane, cmd)
        return

    # エージェントの書き込み → 殿に通知 + スレID名にマッチするエージェントに通知
    notify_msg = f"[2ch] {board}/{thread_id} に {agent_name} が書き込み: {preview}"

    # 殿に通知（家臣の書き込みを殿が追えるように）
    shogun_pane = AGENT_PANES.get("shogun")
    if shogun_pane:
        _send_keys_to_pane(shogun_pane, notify_msg)

    for agent_id, pane in AGENT_PANES.items():
        if agent_id == author_id or agent_id == "shogun":
            continue
        agent_name_lower = NAMES.get(agent_id, agent_id).lower()
        if agent_id in thread_id.lower() or agent_name_lower in thread_id.lower():
            _send_keys_to_pane(pane, notify_msg)
            return

    # デフォルト: 老中に通知
    if author_id != "roju" and author_id != "karo-roju":
        roju_pane = AGENT_PANES.get("roju")
        if roju_pane:
            _send_keys_to_pane(roju_pane, notify_msg)


def _send_keys_to_pane(pane: str, message: str) -> None:
    """tmux send-keys でメッセージを送信（2段階: テキスト + Enter）。"""
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, message[:500]],
            capture_output=True, timeout=3,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "Enter"],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass


def _bbs_success() -> str:
    return (
        "<html><head><title>書きこみました</title></head>"
        "<body>書きこみが終わりました。<br><br>"
        "画面を切り替えるまでしばらくお待ちください。</body></html>"
    )


def _bbs_error(msg: str) -> str:
    return (
        f"<html><head><title>ＥＲＲＯＲ！</title></head>"
        f"<body>ERROR: {msg}<br><br>"
        f"画面を切り替えるまでしばらくお待ちください。</body></html>"
    )


# ---------------------------------------------------------------------------
# ルーティングテーブル
# ---------------------------------------------------------------------------

SUBJECT_FUNCS = {
    "kanri":    subject_kanri,
    "dreams":   subject_dreams,
    "diary":    subject_diary,
    "zatsudan": subject_zatsudan,
}

DAT_FUNCS = {
    "kanri":    dat_kanri,
    "dreams":   dat_dreams,
    "diary":    dat_diary,
    "zatsudan": dat_zatsudan,
}


# ---------------------------------------------------------------------------
# HTTP ハンドラ
# ---------------------------------------------------------------------------

def bbsmenu_html(port: int = PORT) -> str:
    """JDim互換bbsmenu。HREFは直接アクセス用（nginx不要）。"""
    categories = {
        "没日録": ["kanri", "diary"],
        "リサーチ": ["dreams"],
        "交流": ["zatsudan"],
    }
    base = f"http://localhost:{port}{BASE_PATH}"
    lines = [
        "<HTML>",
        "<HEAD>",
        '<META http-equiv="Content-Type" content="text/html; charset=Shift_JIS">',
        "<TITLE>BBS MENU for 没日録2ch</TITLE>",
        "</HEAD>",
        "<BODY>",
    ]
    for cat, boards_in_cat in categories.items():
        lines.append(f"<BR><BR><B>{cat}</B><BR>")
        for b in boards_in_cat:
            name = BOARD_NAMES.get(b, b)
            lines.append(f'<A HREF={base}/{b}/>{name}</A><br>')
    lines += ["</BODY>", "</HTML>"]
    return "\n".join(lines)


class DatHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args) -> None:
        print(f"[{self.address_string()}] {args[0]} {args[1]}")

    def send_cp932(self, text: str, content_type: str = "text/plain; charset=Shift_JIS", status: int = 200) -> None:
        data = text.encode("cp932", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def _strip_base(path: str) -> str:
        """BASE_PATHプレフィックスがあれば剥がす。"""
        if path.startswith(BASE_PATH + "/"):
            return path[len(BASE_PATH):]
        if path == BASE_PATH:
            return "/"
        return path

    def do_POST(self) -> None:
        path = self._strip_base(self.path.split("?")[0]).rstrip("/")

        if path in ("/test/bbs.cgi", "/bbs.cgi"):
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 65536:
                self.send_cp932(_bbs_error("投稿が大きすぎます"), "text/html; charset=Shift_JIS", 413)
                return
            raw = self.rfile.read(content_length)
            # JDimはcp932でURLエンコードして送るので、バイト列のままparse_qsに渡す
            raw_params = parse_qs(raw, keep_blank_values=True)

            def _dec(key: bytes, default: str = "") -> str:
                vals = raw_params.get(key, [b""])
                v = vals[0]
                # UTF-8を先に試す（curl/CLI経由）。失敗時にcp932（JDim経由）
                try:
                    return v.decode("utf-8").strip()
                except UnicodeDecodeError:
                    try:
                        return v.decode("cp932").strip()
                    except UnicodeDecodeError:
                        return v.decode("latin-1").strip()

            bbs = _dec(b"bbs")
            key = _dec(b"key")
            from_field = _dec(b"FROM")
            mail = _dec(b"mail")
            message = _dec(b"MESSAGE")
            subject = _dec(b"subject") or None
            time_val = _dec(b"time")

            if not message:
                self.send_cp932(_bbs_error("本文が空です"), "text/html; charset=Shift_JIS", 400)
                return

            status, html = do_bbs_write(bbs, key, from_field, message, subject)
            self.send_cp932(html, "text/html; charset=Shift_JIS", status)
            return

        self.send_cp932("404 Not Found\n", status=404)

    def do_GET(self) -> None:
        path = self._strip_base(self.path.split("?")[0]).rstrip("/")

        if path in ("", "/bbsmenu.html", "/bbsmenu.htm"):
            self.send_cp932(bbsmenu_html(self.server.server_port), "text/html; charset=Shift_JIS")
            return

        if path.upper().endswith("SETTING.TXT"):
            self.send_cp932(SETTING_TXT)
            return

        parts = [p for p in path.split("/") if p]

        # JDim外部板: プレフィックス自体を板として登録された場合
        # /subject.txt → 全板カテゴリ一覧を返す
        if len(parts) == 1 and parts[0].lower() == "subject.txt":
            lines = []
            for board in BOARDS:
                name = BOARD_NAMES.get(board, board)
                lines.append(f"{board}.dat<>{name} (0)\n")
            self.send_cp932("".join(lines))
            return

        # /dat/<board>.dat → bbsmenuをdat形式で返す（JDim板トップ互換）
        if len(parts) == 2 and parts[0] == "dat" and parts[1].endswith(".dat"):
            board = parts[1][:-4]
            if board in BOARDS:
                name = BOARD_NAMES.get(board, board)
                content = dat_line(
                    "老中 ◆ROJU", "", fmt_ts(None),
                    f"板トップ: {name}\nsubject.txt → /{board}/subject.txt",
                    name,
                )
                self.send_cp932(content + "\n")
                return

        if len(parts) == 1 and parts[0] in BOARDS:
            self.send_cp932(f"<html><body>{parts[0]}</body></html>\n", "text/html; charset=Shift_JIS")
            return

        if len(parts) == 2 and parts[1].lower() == "subject.txt":
            board = parts[0]
            if board not in BOARDS:
                self.send_cp932("404 Not Found\n", status=404)
                return
            try:
                content = SUBJECT_FUNCS[board]()
            except Exception as e:
                content = f"Error: {e}\n"
            self.send_cp932(content)
            return

        if len(parts) == 3 and parts[1] == "dat" and parts[2].endswith(".dat"):
            board = parts[0]
            num_id_str = parts[2][:-4]
            if board not in BOARDS:
                self.send_cp932("404 Not Found\n", status=404)
                return
            try:
                num_id = int(num_id_str)
                thread_id = lookup_id(board, num_id) or num_id_str
            except ValueError:
                thread_id = num_id_str
            if thread_id == num_id_str and board in SUBJECT_FUNCS:
                try:
                    SUBJECT_FUNCS[board]()
                    thread_id = lookup_id(board, int(num_id_str)) or num_id_str
                except Exception:
                    pass
            try:
                content = DAT_FUNCS[board](thread_id)
            except Exception as e:
                content = None
                print(f"[ERROR] dat {board}/{thread_id}: {e}")
            if content is None:
                self.send_cp932("404 Not Found\n", status=404)
                return
            self.send_cp932(content)
            return

        # test/read.cgi/{board}/{thread_id} ルート（JDim互換 read.cgi形式）
        if len(parts) == 4 and parts[0] == "test" and parts[1] == "read.cgi":
            board = parts[2]
            num_id_str = parts[3]
            if board not in BOARDS:
                self.send_cp932("404 Not Found\n", status=404)
                return
            try:
                num_id = int(num_id_str)
                thread_id = lookup_id(board, num_id) or num_id_str
            except ValueError:
                thread_id = num_id_str
            if thread_id == num_id_str and board in SUBJECT_FUNCS:
                try:
                    SUBJECT_FUNCS[board]()
                    thread_id = lookup_id(board, int(num_id_str)) or num_id_str
                except Exception:
                    pass
            try:
                content = DAT_FUNCS[board](thread_id)
            except Exception as e:
                content = None
                print(f"[ERROR] dat {board}/{thread_id}: {e}")
            if content is None:
                self.send_cp932("404 Not Found\n", status=404)
                return
            self.send_cp932(content)
            return

        self.send_cp932("404 Not Found\n", status=404)


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="JDim対応DATサーバー（没日録2ch閲覧用）")
    parser.add_argument("--port", type=int, default=PORT, help=f"ポート番号 (デフォルト: {PORT})")
    args = parser.parse_args()

    server = HTTPServer(("localhost", args.port), DatHandler)
    print(f"DATサーバー起動: http://localhost:{args.port}{BASE_PATH}/")
    print(f"JDim外部板URL:   http://localhost:{args.port}{BASE_PATH}/")
    print(f"bbsmenu:         http://localhost:{args.port}{BASE_PATH}/bbsmenu.html")
    print("Ctrl+C で停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバー停止")
        server.server_close()


if __name__ == "__main__":
    main()
