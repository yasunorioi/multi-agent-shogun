#!/usr/bin/env python3
"""dat_server.py — JDim対応DATサーバー（没日録2ch閲覧用）

Python標準ライブラリのみ（http.server / socketserver）。読み取り専用。
ポート: 8823 (localhost)

使用方法:
  python3 scripts/dat_server.py        # サーバー起動
  python3 scripts/dat_server.py --port 8823

JDim接続:
  「外部板」→ http://localhost/botsunichiroku/ を追加（nginx経由）

対応板: kanri, dreams, senryaku, houkoku, ofure, zatsudan, docs, diary, audit
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ---------------------------------------------------------------------------
# パス設定
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"
DREAMS_PATH = PROJECT_ROOT / "data" / "dreams.jsonl"

PORT = 8823

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

BOARDS = ["kanri", "dreams", "senryaku", "houkoku", "ofure", "zatsudan", "docs", "diary", "audit"]

BOARD_NAMES = {
    "kanri":    "管理板 ◆老中cmd一覧",
    "dreams":   "夢見板 ◆獏の夢スレ",
    "senryaku": "戦略板 ◆軍師の分析",
    "houkoku":  "報告板 ◆足軽完了報告",
    "ofure":    "御触板 ◆老中通達",
    "zatsudan": "雑談板 ◆よろず話",
    "docs":     "書庫板 ◆文書索引",
    "diary":    "日記板 ◆エージェント日記",
    "audit":    "監査板 ◆お針子の目",
}

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

TRIPS: dict[str, str] = {
    "shogun":    "◆SHGN",
    "karo-roju": "◆ROJU",
    "roju":      "◆ROJU",
    "ashigaru1": "◆ASH1",
    "ashigaru2": "◆ASH2",
    "ashigaru3": "◆ASH3",
    "ashigaru4": "◆ASH4",
    "ashigaru5": "◆ASH5",
    "ashigaru6": "◆HYG6",
    "gunshi":    "◆GNSH",
    "ohariko":   "◆OHRK",
    "baku":      "◆BAKU",
}

NAMES: dict[str, str] = {
    "shogun":    "将軍",
    "karo-roju": "老中",
    "roju":      "老中",
    "ashigaru1": "足軽1",
    "ashigaru2": "足軽2",
    "ashigaru3": "足軽3",
    "ashigaru4": "足軽4",
    "ashigaru5": "足軽5",
    "ashigaru6": "部屋子1",
    "gunshi":    "軍師",
    "ohariko":   "お針子",
    "baku":      "獏",
}

SETTING_TXT = """\
BBS_TITLE=没日録2ch (shogun system)
BBS_COMMENT=Claude Code マルチエージェント没日録ビューア
BBS_NONAME_NAME=名無しの足軽
BBS_MAX_RES=1000
BBS_THREAD_STOP=1000
BBS_UNICODE=on
"""

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"没日録DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def fmt_ts(ts_str: str | None) -> str:
    if not ts_str:
        return "----/--/--(-) --:--:--"
    try:
        ts_clean = ts_str.split("+")[0].split("Z")[0]
        if "." in ts_clean:
            ts_clean = ts_clean.split(".")[0]
        dt = datetime.strptime(ts_clean, "%Y-%m-%dT%H:%M:%S")
        wd = WEEKDAYS[dt.weekday()]
        return dt.strftime(f"%Y/%m/%d({wd}) %H:%M:%S")
    except Exception:
        return ts_str[:19] if ts_str else "----/--/--(-) --:--:--"


def nametrip(agent_id: str | None) -> str:
    if not agent_id:
        return "名無しの足軽"
    name = NAMES.get(agent_id, agent_id)
    trip = TRIPS.get(agent_id, f"◆{agent_id[:4].upper()}")
    return f"{name} {trip}"


def dat_line(name: str, mail: str, ts: str, body: str, title: str = "") -> str:
    """DAT形式1行: 名前<>メール<>日時<>本文<>スレタイ"""
    body_esc = (body or "").replace("\r\n", "<br>").replace("\n", "<br>")
    return f"{name}<>{mail}<>{ts}<>{body_esc}<>{title}"


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
        lines.append(f"{cmd['id']}.dat<>{title} ({count})\n")
    return "".join(lines) or "main.dat<>【管理板】まだCMDなし (0)\n"


def subject_ofure() -> str:
    conn = get_conn()
    try:
        cmds = conn.execute(
            "SELECT id, command FROM commands ORDER BY id DESC LIMIT 200"
        ).fetchall()
    finally:
        conn.close()
    lines = []
    for cmd in cmds:
        title = (cmd["command"] or cmd["id"])[:60]
        lines.append(f"{cmd['id']}.dat<>{title} (1)\n")
    return "".join(lines) or "main.dat<>【御触板】まだ通達なし (0)\n"


def subject_senryaku() -> str:
    conn = get_conn()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(subtasks)").fetchall()]
        if "bloom_level" in cols:
            rows = conn.execute(
                "SELECT id, description FROM subtasks"
                " WHERE bloom_level IN ('L4','L5','L6') ORDER BY id DESC LIMIT 100"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, description FROM subtasks"
                " WHERE worker_id = 'gunshi' ORDER BY id DESC LIMIT 100"
            ).fetchall()
    finally:
        conn.close()
    lines = [f"{r['id']}.dat<>{(r['description'] or r['id'])[:50]} (1)\n" for r in rows]
    return "".join(lines) or "main.dat<>【戦略板】軍師の戦略分析一覧 (0)\n"


def subject_houkoku() -> str:
    conn = get_conn()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM subtasks WHERE status IN ('completed','done')"
        ).fetchone()[0]
    finally:
        conn.close()
    return f"main.dat<>【報告板】足軽完了報告一覧 ({total})\n"


def subject_audit() -> str:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, description, audit_status FROM subtasks"
            " WHERE needs_audit = 1 ORDER BY id DESC LIMIT 100"
        ).fetchall()
    finally:
        conn.close()
    lines = []
    for r in rows:
        label = f"[{r['audit_status'] or 'pending'}]"
        title = f"{label} {(r['description'] or r['id'])[:48]}"
        lines.append(f"{r['id']}.dat<>{title} (1)\n")
    return "".join(lines) or "main.dat<>【監査板】監査対象なし (0)\n"


def subject_diary() -> str:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='diary_entries'"
        ).fetchone()
        if not tbl:
            return "main.dat<>【日記板】diary_entries未存在 (0)\n"
        agents = conn.execute(
            "SELECT agent_id, COUNT(*) AS cnt FROM diary_entries GROUP BY agent_id ORDER BY agent_id"
        ).fetchall()
    finally:
        conn.close()
    lines = []
    for ag in agents:
        aid = ag["agent_id"]
        name = NAMES.get(aid, aid)
        lines.append(f"{aid}.dat<>{name}の日記スレ ({ag['cnt']})\n")
    return "".join(lines) or "main.dat<>【日記板】まだ記録なし (0)\n"


def subject_docs() -> str:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='doc_keywords'"
        ).fetchone()
        if not tbl:
            return "main.dat<>【書庫板】doc_keywords未存在 (0)\n"
        rows = conn.execute(
            "SELECT doc_id, COUNT(*) AS kw_cnt FROM doc_keywords"
            " GROUP BY doc_id ORDER BY doc_id DESC LIMIT 100"
        ).fetchall()
    finally:
        conn.close()
    lines = [f"{r['doc_id']}.dat<>{r['doc_id']} (kw:{r['kw_cnt']}) (1)\n" for r in rows]
    return "".join(lines) or "main.dat<>【書庫板】まだドキュメントなし (0)\n"


def subject_dreams() -> str:
    if not DREAMS_PATH.exists():
        return "main.dat<>【夢見板】まだ夢なし (0)\n"
    by_date: dict[str, list] = defaultdict(list)
    try:
        with open(DREAMS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    date = (d.get("dreamt_at") or "")[:10] or "unknown"
                    by_date[date].append(d)
    except Exception:
        return "main.dat<>【夢見板】読み込み失敗 (0)\n"
    lines = []
    for date in sorted(by_date.keys(), reverse=True)[:30]:
        count = len(by_date[date])
        lines.append(f"{date}.dat<>【夢見板】{date} の夢 ({count})\n")
    return "".join(lines) or "main.dat<>【夢見板】まだ夢なし (0)\n"


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
    lines = [f"{r['thread_id']}.dat<>{r['thread_id']} ({r['cnt']})\n" for r in rows]
    return "".join(lines) or "main.dat<>【雑談板】まだスレッドなし (0)\n"


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
    # >>1: CMD本体
    author = nametrip(cmd["assigned_karo"] or "roju")
    ts = fmt_ts(cmd["created_at"] or cmd["timestamp"])
    body = (
        f"[{cmd['project'] or '-'}] {cmd['command'] or ''}\n"
        f"priority: {cmd['priority'] or '-'} | status: {cmd['status'] or '-'}"
    )
    if cmd["details"]:
        body += "\n" + cmd["details"].strip()[:300]
    lines.append(dat_line(author, "", ts, body, title))
    # >>2+: subtasks
    for st in subtasks:
        worker = nametrip(st["worker_id"])
        ts2 = fmt_ts(st["assigned_at"])
        body2 = f"[{st['id']}] {st['description'] or ''}\nstatus: {st['status'] or '-'} | wave: {st['wave'] or '-'}"
        if st["blocked_by"]:
            body2 += f"\nblocked_by: {st['blocked_by']}"
        lines.append(dat_line(worker, "", ts2, body2))
    # reports
    for rep in reports:
        worker = nametrip(rep["worker_id"])
        ts3 = fmt_ts(rep["timestamp"])
        body3 = f"[report] {rep['task_id'] or '-'} {rep['summary'] or ''}"
        if rep["findings"]:
            body3 += f"\n{rep['findings'][:100]}"
        lines.append(dat_line(worker, "", ts3, body3))
    return "\n".join(lines) + "\n"


def dat_ofure(thread_id: str) -> str | None:
    conn = get_conn()
    try:
        cmd = conn.execute("SELECT * FROM commands WHERE id = ?", (thread_id,)).fetchone()
        if not cmd:
            return None
    finally:
        conn.close()
    title = cmd["command"] or thread_id
    author = nametrip(cmd["assigned_karo"] or "roju")
    ts = fmt_ts(cmd["created_at"] or cmd["timestamp"])
    body = (
        f"[{cmd['id']}] {cmd['command'] or ''}\n"
        f"project: {cmd['project'] or '-'} | status: {cmd['status'] or '-'} | priority: {cmd['priority'] or '-'}"
    )
    if cmd["details"]:
        body += "\n" + cmd["details"].strip()[:400]
    return dat_line(author, "", ts, body, title) + "\n"


def dat_senryaku(thread_id: str) -> str | None:
    conn = get_conn()
    try:
        st = conn.execute("SELECT * FROM subtasks WHERE id = ?", (thread_id,)).fetchone()
        if not st:
            return None
    finally:
        conn.close()
    title = (st["description"] or thread_id)[:60]
    worker = nametrip(st["worker_id"])
    ts = fmt_ts(st["assigned_at"])
    body = f"[{thread_id}] {st['description'] or ''}\nstatus: {st['status'] or '-'}"
    if st["notes"]:
        body += "\n" + st["notes"][:200]
    return dat_line(worker, "", ts, body, title) + "\n"


def dat_houkoku_main() -> str:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM subtasks WHERE status IN ('completed','done')"
            " ORDER BY completed_at DESC, id DESC LIMIT 300"
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM subtasks WHERE status IN ('completed','done')"
        ).fetchone()[0]
    finally:
        conn.close()
    title = f"【報告板】足軽完了報告 (全{total}件)"
    lines = []
    for i, st in enumerate(rows):
        worker = nametrip(st["worker_id"])
        ts = fmt_ts(st["completed_at"] or st["assigned_at"])
        body = f"[{st['id']}] {st['description'] or ''}"
        lines.append(dat_line(worker, "", ts, body, title if i == 0 else ""))
    if not lines:
        lines = [dat_line("老中 ◆ROJU", "", fmt_ts(None), "まだ完了報告なし", title)]
    return "\n".join(lines) + "\n"


def dat_audit(thread_id: str) -> str | None:
    conn = get_conn()
    try:
        st = conn.execute("SELECT * FROM subtasks WHERE id = ?", (thread_id,)).fetchone()
        if not st:
            return None
        reps = conn.execute(
            "SELECT * FROM audit_history WHERE subtask_id = ? ORDER BY id DESC LIMIT 5",
            (thread_id,),
        ).fetchall()
    finally:
        conn.close()
    title = f"[{st['audit_status'] or 'pending'}] {(st['description'] or thread_id)[:50]}"
    worker = nametrip(st["worker_id"])
    ts = fmt_ts(st["assigned_at"])
    body = f"[{thread_id}] {st['description'] or ''}\nstatus: {st['status'] or '-'} | audit: {st['audit_status'] or 'pending'}"
    lines = [dat_line(worker, "", ts, body, title)]
    for rep in reps:
        ts2 = fmt_ts(rep["timestamp"])
        verdict = rep["verdict"] or "pending"
        score = rep["score"]
        rbody = f"[監査] {verdict}({score}/15)"
        if rep["findings_summary"]:
            rbody += f"\n{rep['findings_summary'][:150]}"
        lines.append(dat_line("お針子 ◆OHRK", "", ts2, rbody))
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


def dat_docs(thread_id: str) -> str | None:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='doc_keywords'"
        ).fetchone()
        if not tbl:
            return None
        rows = conn.execute(
            "SELECT * FROM doc_keywords WHERE doc_id = ? ORDER BY keyword", (thread_id,)
        ).fetchall()
        if not rows:
            return None
    finally:
        conn.close()
    doc_type = rows[0]["doc_type"] if rows else "-"
    kws = [r["keyword"] for r in rows]
    title = thread_id
    body = f"[{thread_id}] type:{doc_type}\nKeywords: {', '.join(kws[:20])}"
    ts = fmt_ts(None)
    return dat_line("書庫 ◆DOCS", "", ts, body, title) + "\n"


def dat_dreams(thread_id: str) -> str | None:
    """thread_id = date string YYYY-MM-DD"""
    if not DREAMS_PATH.exists():
        return None
    by_date: dict[str, list] = defaultdict(list)
    try:
        with open(DREAMS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    date = (d.get("dreamt_at") or "")[:10] or "unknown"
                    by_date[date].append(d)
    except Exception:
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
# ルーティングテーブル
# ---------------------------------------------------------------------------

SUBJECT_FUNCS = {
    "kanri":    subject_kanri,
    "ofure":    subject_ofure,
    "senryaku": subject_senryaku,
    "houkoku":  subject_houkoku,
    "audit":    subject_audit,
    "diary":    subject_diary,
    "docs":     subject_docs,
    "dreams":   subject_dreams,
    "zatsudan": subject_zatsudan,
}

DAT_FUNCS = {
    "kanri":    dat_kanri,
    "ofure":    dat_ofure,
    "senryaku": dat_senryaku,
    "houkoku":  lambda tid: dat_houkoku_main() if tid == "main" else None,
    "audit":    dat_audit,
    "diary":    dat_diary,
    "docs":     dat_docs,
    "dreams":   dat_dreams,
    "zatsudan": dat_zatsudan,
}


# ---------------------------------------------------------------------------
# HTTP ハンドラ
# ---------------------------------------------------------------------------

def bbsmenu_html() -> str:
    lines = [
        "<html>",
        f"<head><meta charset='Shift_JIS'><title>没日録2ch</title></head>",
        "<body>",
        f"<b>没日録2ch (shogun system)</b><br><br>",
    ]
    for b in BOARDS:
        name = BOARD_NAMES.get(b, b)
        lines.append(f'<a href="http://localhost/botsunichiroku/{b}/">{name}</a><br>')
    lines += ["</body>", "</html>"]
    return "\n".join(lines)


class DatHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args) -> None:
        # アクセスログを標準出力に出力（簡易）
        print(f"[{self.address_string()}] {args[0]} {args[1]}")

    def send_cp932(self, text: str, content_type: str = "text/plain; charset=Shift_JIS", status: int = 200) -> None:
        data = text.encode("cp932", errors="replace")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")

        # / or /bbsmenu.html
        if path in ("", "/bbsmenu.html", "/bbsmenu.htm"):
            self.send_cp932(bbsmenu_html(), "text/html; charset=Shift_JIS")
            return

        # /SETTING.TXT
        if path.upper().endswith("SETTING.TXT"):
            self.send_cp932(SETTING_TXT)
            return

        parts = [p for p in path.split("/") if p]

        # /<board>/subject.txt
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

        # /<board>/dat/<thread_id>.dat
        if len(parts) == 3 and parts[1] == "dat" and parts[2].endswith(".dat"):
            board = parts[0]
            thread_id = parts[2][:-4]
            if board not in BOARDS:
                self.send_cp932("404 Not Found\n", status=404)
                return
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
    print(f"DATサーバー起動: http://localhost:{args.port}/")
    print(f"JDim外部板URL:   http://localhost:{args.port}/")
    print("Ctrl+C で停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバー停止")
        server.server_close()


if __name__ == "__main__":
    main()
