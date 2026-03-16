#!/usr/bin/env python3
"""
diary_matome.py - 没日録2chまとめ風HTML + 2ch互換dat生成スクリプト

没日録DB（commands, subtasks, reports）+ diary_entries から:
1. 2chまとめ風HTML → data/matome/YYYY-MM-DD.html
2. 2ch互換dat → data/matome/shogun/dat/THREAD_ID.dat + subject.txt
   → 2chブラウザ(Jane Style, Siki等)で閲覧可能

Usage:
    python3 scripts/diary_matome.py [--date YYYY-MM-DD] [--cmd CMD_ID] [--all-today]
"""

import argparse
import html
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"
MATOME_DIR = PROJECT_ROOT / "data" / "matome"
# 2ch互換: /shogun/ が板、dat/ にスレdat
BOARD_DIR = MATOME_DIR / "shogun"
DAT_DIR = BOARD_DIR / "dat"

# ---------------------------------------------------------------------------
# Agent display names
# ---------------------------------------------------------------------------

AGENT_DISPLAY = {
    "roju": ("老中", "◆roju"),
    "ashigaru1": ("足軽1号", "★"),
    "ashigaru2": ("足軽2号", "★"),
    "ashigaru6": ("部屋子", "☆"),
    "gunshi": ("軍師", "◆gunshi"),
    "ohariko": ("お針子", "♥"),
}

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def get_display_name(agent_id: str) -> tuple[str, str]:
    """Return (display_name, trip) for an agent_id."""
    if agent_id in AGENT_DISPLAY:
        return AGENT_DISPLAY[agent_id]
    return (agent_id, "")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Error: database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_diary_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS diary_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL, date TEXT NOT NULL,
            cmd_id TEXT, subtask_id TEXT,
            summary TEXT NOT NULL, body TEXT NOT NULL,
            tags TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def fetch_commands_for_date(conn: sqlite3.Connection, date: str) -> list[dict]:
    rows = conn.execute(
        """SELECT DISTINCT c.id, c.command, c.project, c.status, c.created_at
           FROM commands c
           LEFT JOIN subtasks s ON s.parent_cmd = c.id
           LEFT JOIN reports r ON r.task_id = s.id
           LEFT JOIN diary_entries d ON d.cmd_id = c.id
           WHERE substr(c.created_at, 1, 10) = ?
              OR substr(s.assigned_at, 1, 10) = ?
              OR substr(s.completed_at, 1, 10) = ?
              OR substr(r.timestamp, 1, 10) = ?
              OR d.date = ?
           ORDER BY c.id""",
        (date, date, date, date, date),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_all_commands(conn: sqlite3.Connection) -> list[dict]:
    """Fetch all commands (for full dat rebuild)."""
    rows = conn.execute(
        "SELECT id, command, project, status, created_at FROM commands ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_command_by_id(conn: sqlite3.Connection, cmd_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM commands WHERE id = ?", (cmd_id,)).fetchone()
    return dict(row) if row else None


def fetch_subtasks(conn: sqlite3.Connection, cmd_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM subtasks WHERE parent_cmd = ? ORDER BY wave, id",
        (cmd_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_reports(conn: sqlite3.Connection, subtask_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM reports WHERE task_id = ? ORDER BY id",
        (subtask_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_diary_entries(conn: sqlite3.Connection, cmd_id: str | None = None, date: str | None = None) -> list[dict]:
    query = "SELECT * FROM diary_entries WHERE 1=1"
    params: list = []
    if cmd_id:
        query += " AND cmd_id = ?"
        params.append(cmd_id)
    if date:
        query += " AND date = ?"
        params.append(date)
    query += " ORDER BY id"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Common: collect posts for a command
# ---------------------------------------------------------------------------


def collect_posts(conn: sqlite3.Connection, cmd_id: str, date: str | None = None) -> list[dict]:
    """Collect all posts (reports + diary) for a command, sorted by timestamp."""
    subtasks = fetch_subtasks(conn, cmd_id)
    diary_entries = fetch_diary_entries(conn, cmd_id=cmd_id, date=date)

    posts: list[dict] = []

    for st in subtasks:
        st_id = st["id"]
        reports = fetch_reports(conn, st_id)
        for rpt in reports:
            lines = []
            if rpt.get("summary"):
                lines.append(rpt["summary"])
            if rpt.get("findings"):
                lines.append(f"findings: {rpt['findings']}")
            if rpt.get("notes"):
                lines.append(rpt["notes"])
            if not lines:
                lines.append(f"{st_id} 完了")
            lines.insert(0, f"[{st_id}] {st.get('description', '')[:60]}")
            posts.append({
                "agent_id": rpt.get("worker_id", "unknown"),
                "timestamp": rpt.get("timestamp", ""),
                "lines": lines,
                "is_diary": False,
            })

    for de in diary_entries:
        lines = [de["summary"]]
        if de.get("body"):
            lines.extend(de["body"].splitlines())
        if de.get("subtask_id"):
            lines.insert(0, f"[{de['subtask_id']}]")
        posts.append({
            "agent_id": de["agent_id"],
            "timestamp": de.get("created_at", ""),
            "lines": lines,
            "is_diary": True,
        })

    posts.sort(key=lambda p: p.get("timestamp") or "9999")
    return posts


# ---------------------------------------------------------------------------
# Timestamp formatting
# ---------------------------------------------------------------------------


def format_timestamp(ts: str | None) -> str:
    """Format ISO timestamp to 2ch-style date."""
    if not ts:
        return "不明"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        wd = WEEKDAY_JA[dt.weekday()]
        return f"{dt.year}/{dt.month:02d}/{dt.day:02d}({wd}) {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return ts[:16] if len(ts) >= 16 else ts


def format_timestamp_dat(ts: str | None) -> str:
    """Format ISO timestamp for dat file (2ch style with seconds)."""
    if not ts:
        return "1970/01/01(木) 00:00:00.00"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        wd = WEEKDAY_JA[dt.weekday()]
        return f"{dt.year}/{dt.month:02d}/{dt.day:02d}({wd}) {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}.00"
    except Exception:
        return ts[:19] if len(ts) >= 19 else ts


def ts_to_unix(ts: str | None) -> int:
    """Convert ISO timestamp to unix timestamp (for thread ID)."""
    if not ts:
        return 0
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return 0


def escape_html(text: str | None) -> str:
    if not text:
        return ""
    return html.escape(text)


# ===========================================================================
# 2ch互換 dat 生成
# ===========================================================================


def cmd_to_thread_id(cmd_id: str, created_at: str | None) -> str:
    """Generate thread ID (unix timestamp) from cmd. Falls back to hash."""
    ts = ts_to_unix(created_at)
    if ts > 0:
        return str(ts)
    # Fallback: use cmd number as pseudo-timestamp
    num = re.sub(r"[^0-9]", "", cmd_id)
    return f"1000000{num.zfill(3)}"


def make_dat_line(name: str, mail: str, date_id: str, body: str, title: str = "") -> str:
    """Build one dat line: name<>mail<>date ID<>body<>title"""
    return f"{name}<>{mail}<>{date_id}<>{body}<>{title}"


def posts_to_dat(posts: list[dict], thread_title: str) -> str:
    """Convert posts to dat file content (Shift_JIS compatible text)."""
    dat_lines = []
    for i, post in enumerate(posts):
        name_str, trip = get_display_name(post["agent_id"])
        if trip:
            name_str = f"{name_str} {trip}"

        date_str = format_timestamp_dat(post.get("timestamp"))
        agent_id = post["agent_id"]
        id_field = f"ID:{agent_id}"
        date_id = f"{date_str} {id_field}"

        # Body: join lines with <br>, ensuring NO literal newlines in body
        body_parts = []
        if post.get("is_diary"):
            body_parts.append("[日記]")
        for line in post.get("lines", []):
            # Each "line" may contain embedded newlines from DB fields
            escaped = escape_html(line)
            # Replace all newlines with <br>
            escaped = escaped.replace("\r\n", " <br> ").replace("\n", " <br> ").replace("\r", " <br> ")
            body_parts.append(escaped)
        body = " <br> ".join(body_parts)

        # Final safety: ensure no literal newlines remain in body
        body = body.replace("\n", " <br> ").replace("\r", "")

        title = thread_title if i == 0 else ""
        dat_lines.append(make_dat_line(name_str, "sage", date_id, body, title))

    return "\n".join(dat_lines) + "\n" if dat_lines else ""


def generate_dat_for_cmd(conn: sqlite3.Connection, cmd_id: str, cmd_info: dict) -> tuple[str, str, int]:
    """Generate dat content for one command.
    Returns (thread_id, dat_content, res_count)."""
    posts = collect_posts(conn, cmd_id)
    title = build_thread_title(cmd_id, cmd_info)
    thread_id = cmd_to_thread_id(cmd_id, cmd_info.get("created_at"))

    # Build >>1 from cmd details/description
    op_lines = []
    cmd_desc = cmd_info.get("command") or ""
    cmd_details = cmd_info.get("details") or ""
    cmd_status = cmd_info.get("status") or ""
    cmd_project = cmd_info.get("project") or ""
    if cmd_desc:
        op_lines.append(cmd_desc)
    if cmd_details:
        op_lines.append(cmd_details)
    if cmd_project:
        op_lines.append(f"project: {cmd_project}")
    op_lines.append(f"status: {cmd_status}")

    op_post = {
        "agent_id": "roju",
        "timestamp": cmd_info.get("created_at") or "",
        "lines": op_lines,
        "is_diary": False,
    }

    # Insert >>1 (cmd overview) at the beginning
    all_posts = [op_post] + posts
    dat_content = posts_to_dat(all_posts, title)
    return thread_id, dat_content, len(all_posts)


def build_thread_title(cmd_id: str, cmd_info: dict) -> str:
    project = cmd_info.get("project") or ""
    desc = cmd_info.get("command") or ""
    if project:
        return f"【{cmd_id}】{desc} [{project}]"
    return f"【{cmd_id}】{desc}"


def generate_subject_txt(threads: list[tuple[str, str, int]]) -> str:
    """Generate subject.txt content.
    threads: list of (thread_id, title, res_count)"""
    lines = []
    # Sort by thread_id descending (newest first)
    for tid, title, count in sorted(threads, key=lambda x: x[0], reverse=True):
        lines.append(f"{tid}.dat<>{title} ({count})")
    return "\n".join(lines) + "\n" if lines else ""


def generate_setting_txt() -> str:
    """Generate SETTING.TXT for the board."""
    return """BBS_TITLE=没日録@将軍
BBS_TITLE_PICTURE=
BBS_TITLE_COLOR=#117743
BBS_BG_COLOR=#efefef
BBS_NONAME_NAME=名無しの足軽
BBS_SUBJECT_COUNT=64
BBS_LINE_NUMBER=40
BBS_MAX_RES=1000
BBS_THREAD_TATESUGI=0
"""


def write_dat_files(conn: sqlite3.Connection, target_date: str | None = None) -> None:
    """Generate all dat files, subject.txt, and SETTING.TXT."""
    DAT_DIR.mkdir(parents=True, exist_ok=True)

    if target_date:
        commands = fetch_commands_for_date(conn, target_date)
    else:
        commands = fetch_all_commands(conn)

    # Also load existing subject.txt entries to merge
    existing_threads: dict[str, tuple[str, int]] = {}
    subject_path = BOARD_DIR / "subject.txt"
    if subject_path.exists():
        try:
            for line in subject_path.read_text(encoding="utf-8").strip().split("\n"):
                if "<>" in line:
                    tid_part, rest = line.split("<>", 1)
                    tid = tid_part.replace(".dat", "")
                    existing_threads[tid] = (rest, 0)
        except Exception:
            pass

    threads: list[tuple[str, str, int]] = []

    for cmd in commands:
        cmd_id = cmd["id"]
        thread_id, dat_content, res_count = generate_dat_for_cmd(conn, cmd_id, cmd)

        # Write dat file (Shift_JIS with fallback)
        dat_path = DAT_DIR / f"{thread_id}.dat"
        try:
            dat_path.write_text(dat_content, encoding="shift_jis", errors="replace")
        except Exception:
            dat_path.write_text(dat_content, encoding="utf-8")

        title = build_thread_title(cmd_id, cmd)
        threads.append((thread_id, title, res_count))
        # Remove from existing if we're updating
        existing_threads.pop(thread_id, None)

    # Merge remaining existing threads
    for tid, (rest, _) in existing_threads.items():
        # Parse count from "title (N)"
        m = re.search(r"\((\d+)\)$", rest)
        count = int(m.group(1)) if m else 0
        title = re.sub(r"\s*\(\d+\)$", "", rest)
        threads.append((tid, title, count))

    # Write subject.txt
    subject_content = generate_subject_txt(threads)
    try:
        subject_path.write_text(subject_content, encoding="shift_jis", errors="replace")
    except Exception:
        subject_path.write_text(subject_content, encoding="utf-8")

    # Write SETTING.TXT
    setting_path = BOARD_DIR / "SETTING.TXT"
    try:
        setting_path.write_text(generate_setting_txt(), encoding="shift_jis", errors="replace")
    except Exception:
        setting_path.write_text(generate_setting_txt(), encoding="utf-8")

    # Write bbsmenu.html (JDim等のbbsmenu用)
    bbsmenu_path = MATOME_DIR / "bbsmenu.html"
    bbsmenu_html = """<html><head><title>没日録BBS</title></head><body>
<br><br><b>没日録</b><br>
<a href="http://localhost/botsunichiroku/">没日録@将軍</a><br>
</body></html>"""
    bbsmenu_path.write_text(bbsmenu_html, encoding="utf-8")

    print(f"dat: {len(commands)} threads updated in {DAT_DIR}")


# ===========================================================================
# HTML generation (existing matome feature)
# ===========================================================================

CSS = """
body {
    background-color: #efefef;
    font-family: "MS PGothic", "IPAMonaPGothic", sans-serif;
    font-size: 14px;
    margin: 0;
    padding: 20px;
}
h1 {
    background-color: #789922;
    color: white;
    padding: 8px 16px;
    font-size: 18px;
    margin: 0 0 8px 0;
}
.thread {
    background-color: #efefef;
    margin-bottom: 24px;
}
.res {
    background-color: #f0e0d6;
    border: 1px solid #d9bfb7;
    margin: 4px 8px;
    padding: 8px;
}
.res-header {
    color: #117743;
    font-weight: bold;
    margin-bottom: 4px;
}
.res-header .name { color: #117743; font-weight: bold; }
.res-header .trip { color: #888; }
.res-header .date { color: #888; margin-left: 8px; }
.res-body {
    margin-left: 16px;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.res-body .anchor { color: #0000ff; text-decoration: none; }
.res-body .anchor:hover { text-decoration: underline; color: #ff0000; }
.diary-tag {
    background-color: #e8f5e9;
    border-left: 3px solid #4caf50;
    padding: 2px 6px;
    margin-bottom: 4px;
    font-size: 12px;
    color: #2e7d32;
}
.footer {
    text-align: center;
    color: #888;
    margin-top: 20px;
    font-size: 12px;
}
"""


def build_res_html(num: int, agent_id: str, timestamp: str, body_lines: list[str], is_diary: bool = False) -> str:
    name, trip = get_display_name(agent_id)
    date_str = format_timestamp(timestamp)
    trip_html = f' <span class="trip">{escape_html(trip)}</span>' if trip else ""

    body_html = escape_html("\n".join(body_lines))
    body_html = re.sub(
        r"&gt;&gt;(\d+)",
        r'<a class="anchor" href="#res-\1">&gt;&gt;\1</a>',
        body_html,
    )

    diary_tag = '<div class="diary-tag">📝 日記</div>' if is_diary else ""

    return f"""<div class="res" id="res-{num}">
{diary_tag}<div class="res-header">
<span class="num">{num}</span> 名前：<span class="name">{escape_html(name)}</span>{trip_html}
<span class="date">投稿日：{date_str}</span>
</div>
<div class="res-body">{body_html}</div>
</div>"""


def generate_thread_html(conn: sqlite3.Connection, cmd_id: str, cmd_info: dict, date: str | None = None) -> str:
    posts = collect_posts(conn, cmd_id, date)

    # Build >>1 from cmd info
    op_lines = []
    cmd_desc = cmd_info.get("command") or ""
    cmd_details = cmd_info.get("details") or ""
    cmd_status = cmd_info.get("status") or ""
    cmd_project = cmd_info.get("project") or ""
    if cmd_desc:
        op_lines.append(cmd_desc)
    if cmd_details:
        op_lines.append(cmd_details)
    if cmd_project:
        op_lines.append(f"project: {cmd_project}")
    op_lines.append(f"status: {cmd_status}")

    all_posts = [{"agent_id": "roju", "timestamp": cmd_info.get("created_at") or "", "lines": op_lines, "is_diary": False}] + posts

    res_blocks = []
    for i, post in enumerate(all_posts, 1):
        res_blocks.append(build_res_html(
            num=i,
            agent_id=post["agent_id"],
            timestamp=post["timestamp"],
            body_lines=post["lines"],
            is_diary=post["is_diary"],
        ))

    title = build_thread_title(cmd_id, cmd_info)

    return f"""<div class="thread">
<h1>{escape_html(title)}</h1>
{"".join(res_blocks)}
</div>"""


def generate_full_html(threads_html: str, date: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>没日録まとめ {date}</title>
<style>
{CSS}
</style>
</head>
<body>
<h1>没日録まとめ — {date}</h1>
{threads_html}
<div class="footer">Generated by diary_matome.py | multi-agent-shogun</div>
</body>
</html>"""


def generate_index() -> None:
    """Generate index.html listing all matome files."""
    MATOME_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(MATOME_DIR.glob("*.html"), reverse=True)
    files = [f for f in files if f.name != "index.html"]

    links = []
    for f in files:
        links.append(f'<li><a href="{f.name}">{f.stem}</a></li>')

    index_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>没日録まとめ</title>
<style>
body {{ background: #efefef; font-family: "MS PGothic","IPAMonaPGothic",sans-serif; padding: 20px; }}
h1 {{ background: #789922; color: white; padding: 8px 16px; font-size: 18px; }}
ul {{ list-style: none; padding: 0; }}
li {{ background: #f0e0d6; border: 1px solid #d9bfb7; margin: 4px 0; padding: 8px 12px; }}
a {{ color: #117743; text-decoration: none; font-weight: bold; }}
a:hover {{ color: #ff0000; text-decoration: underline; }}
.footer {{ text-align: center; color: #888; margin-top: 20px; font-size: 12px; }}
</style>
</head>
<body>
<h1>没日録まとめ一覧</h1>
<ul>
{"".join(links) if links else "<li>まだまとめがないでござる</li>"}
</ul>
<p><a href="shogun/">2chブラウザ用板ディレクトリ</a></p>
<div class="footer">Generated by diary_matome.py | multi-agent-shogun</div>
</body>
</html>"""

    (MATOME_DIR / "index.html").write_text(index_html, encoding="utf-8")


# ===========================================================================
# Main
# ===========================================================================


def main():
    parser = argparse.ArgumentParser(description="没日録2chまとめ風HTML + 2ch互換dat生成")
    parser.add_argument("--date", help="対象日 (YYYY-MM-DD, default: today)")
    parser.add_argument("--cmd", help="特定cmdのみ生成")
    parser.add_argument("--all-today", action="store_true", help="今日の全cmdをまとめ出力")
    parser.add_argument("--dat-only", action="store_true", help="dat生成のみ（HTML生成スキップ）")
    parser.add_argument("--full-rebuild", action="store_true", help="全cmdのdatを再生成")
    args = parser.parse_args()

    target_date = args.date or datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    ensure_diary_table(conn)

    # --- dat generation ---
    if args.full_rebuild:
        write_dat_files(conn)
    else:
        write_dat_files(conn, target_date)

    # --- HTML generation ---
    if not args.dat_only:
        if args.cmd:
            cmd_info = fetch_command_by_id(conn, args.cmd)
            if not cmd_info:
                print(f"Error: command '{args.cmd}' not found.", file=sys.stderr)
                sys.exit(1)
            threads_html = generate_thread_html(conn, args.cmd, cmd_info, date=target_date)
        else:
            commands = fetch_commands_for_date(conn, target_date)
            if not commands:
                orphan_diaries = fetch_diary_entries(conn, date=target_date)
                if not orphan_diaries:
                    print(f"No activity found for {target_date} (HTML skipped).")
                    conn.close()
                    return
                commands = []

            threads_html = ""
            for cmd in commands:
                threads_html += generate_thread_html(conn, cmd["id"], cmd, date=target_date)

        MATOME_DIR.mkdir(parents=True, exist_ok=True)
        if args.cmd:
            out_path = MATOME_DIR / f"{target_date}_{args.cmd}.html"
        else:
            out_path = MATOME_DIR / f"{target_date}.html"

        full_html = generate_full_html(threads_html, target_date)
        out_path.write_text(full_html, encoding="utf-8")
        print(f"HTML: {out_path}")

        generate_index()

    conn.close()


if __name__ == "__main__":
    main()
