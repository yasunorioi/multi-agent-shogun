"""diary サブコマンド — AI日記管理。"""

import sqlite3
import sys
from datetime import datetime

from . import get_connection, now_iso, print_table, print_json, row_to_dict, fts5_upsert


DIARY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS diary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    date TEXT NOT NULL,
    cmd_id TEXT,
    subtask_id TEXT,
    summary TEXT NOT NULL,
    body TEXT NOT NULL,
    tags TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

DIARY_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_diary_agent ON diary_entries(agent_id)",
    "CREATE INDEX IF NOT EXISTS idx_diary_date ON diary_entries(date)",
    "CREATE INDEX IF NOT EXISTS idx_diary_cmd ON diary_entries(cmd_id)",
]


def ensure_diary_table(conn: sqlite3.Connection) -> None:
    """Create diary_entries table if it doesn't exist."""
    conn.execute(DIARY_TABLE_SQL)
    for idx_sql in DIARY_INDEXES_SQL:
        conn.execute(idx_sql)


def diary_add(args) -> None:
    conn = get_connection()
    ensure_diary_table(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO diary_entries (agent_id, date, cmd_id, subtask_id, summary, body, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (args.agent_id, today, args.cmd, args.subtask, args.summary, args.body, args.tags, now_iso()),
    )
    row = conn.execute("SELECT last_insert_rowid()").fetchone()
    diary_id = row[0]
    raw_text = " ".join(filter(None, [args.summary, args.body]))
    fts5_upsert(
        conn,
        source_type="diary",
        source_id=str(diary_id),
        parent_id=args.cmd or args.subtask or "",
        project="",
        worker_id=args.agent_id or "",
        status="",
        raw_text=raw_text,
    )
    conn.commit()
    conn.close()
    print(f"Created: diary entry #{diary_id}")


def diary_list(args) -> None:
    conn = get_connection()
    ensure_diary_table(conn)
    query = "SELECT id, agent_id, date, cmd_id, subtask_id, summary, tags, created_at FROM diary_entries WHERE 1=1"
    params: list = []
    if args.agent:
        query += " AND agent_id = ?"
        params.append(args.agent)
    if args.date:
        query += " AND date = ?"
        params.append(args.date)
    if args.cmd:
        query += " AND cmd_id = ?"
        params.append(args.cmd)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No diary entries found.")
        return

    headers = ["ID", "AGENT", "DATE", "CMD", "SUBTASK", "SUMMARY", "TAGS"]
    table_rows = []
    for r in rows:
        table_rows.append([
            str(r["id"]),
            r["agent_id"],
            r["date"],
            r["cmd_id"] or "-",
            r["subtask_id"] or "-",
            (r["summary"] or "")[:40],
            r["tags"] or "-",
        ])
    print_table(headers, table_rows, [5, 12, 12, 10, 14, 40, 16])


def diary_show(args) -> None:
    conn = get_connection()
    ensure_diary_table(conn)
    row = conn.execute("SELECT * FROM diary_entries WHERE id = ?", (args.diary_id,)).fetchone()
    conn.close()

    if not row:
        print(f"Error: diary entry #{args.diary_id} not found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print_json(row_to_dict(row))
        return

    d = row_to_dict(row)
    print(f"=== Diary Entry #{d['id']} ===")
    print(f"  Agent:    {d['agent_id']}")
    print(f"  Date:     {d['date']}")
    print(f"  Cmd:      {d.get('cmd_id') or '-'}")
    print(f"  Subtask:  {d.get('subtask_id') or '-'}")
    print(f"  Tags:     {d.get('tags') or '-'}")
    print(f"  Created:  {d['created_at']}")
    print(f"  Summary:  {d['summary']}")
    print(f"  Body:")
    for line in d["body"].splitlines():
        print(f"    {line}")


def diary_today(args) -> None:
    conn = get_connection()
    ensure_diary_table(conn)
    today = datetime.now().strftime("%Y-%m-%d")
    query = "SELECT id, agent_id, date, cmd_id, subtask_id, summary, body, tags, created_at FROM diary_entries WHERE date = ?"
    params: list = [today]
    if args.agent:
        query += " AND agent_id = ?"
        params.append(args.agent)
    query += " ORDER BY id ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print(f"No diary entries for today ({today}).")
        return

    for r in rows:
        d = row_to_dict(r)
        print(f"--- #{d['id']} [{d['agent_id']}] {d.get('cmd_id') or ''} {d['created_at']} ---")
        print(f"  {d['summary']}")
        for line in d["body"].splitlines():
            print(f"    {line}")
        print()
