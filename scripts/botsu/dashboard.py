"""dashboard サブコマンド — ダッシュボードエントリ管理。"""

from . import get_connection, now_iso, print_table, fts5_upsert


def dashboard_add(args) -> None:
    conn = get_connection()
    ts = now_iso()
    cursor = conn.execute(
        "INSERT INTO dashboard_entries (cmd_id, section, content, status, tags, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (args.cmd, args.section, args.content, args.status, args.tags, ts),
    )
    entry_id = cursor.lastrowid
    raw_text = " ".join(filter(None, [args.section, args.content]))
    fts5_upsert(
        conn,
        source_type="dashboard",
        source_id=str(entry_id),
        parent_id=args.cmd or "",
        project="",
        worker_id=args.tags or "",
        status=args.status or "",
        raw_text=raw_text,
    )
    conn.commit()
    conn.close()
    print(f"Created: dashboard entry #{entry_id}")


def dashboard_list(args) -> None:
    conn = get_connection()
    query = "SELECT id, cmd_id, section, content, status, tags, created_at FROM dashboard_entries WHERE 1=1"
    params: list = []
    if args.section:
        query += " AND section = ?"
        params.append(args.section)
    if args.cmd:
        query += " AND cmd_id = ?"
        params.append(args.cmd)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("No dashboard entries found.")
        return

    headers = ["ID", "CMD", "SECTION", "STATUS", "TAGS", "CONTENT", "CREATED"]
    table_rows = []
    for r in rows:
        content = r["content"] or ""
        content_short = content[:40] if len(content) > 40 else content
        table_rows.append([
            str(r["id"]),
            r["cmd_id"] or "-",
            r["section"],
            r["status"] or "-",
            r["tags"] or "-",
            content_short,
            r["created_at"],
        ])
    print_table(headers, table_rows, [5, 10, 12, 10, 16, 40, 20])


def dashboard_search(args) -> None:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, cmd_id, section, content, status, tags, created_at FROM dashboard_entries WHERE content LIKE ? ORDER BY id DESC",
        (f"%{args.keyword}%",),
    ).fetchall()
    conn.close()

    if not rows:
        print(f"No entries found for keyword: {args.keyword}")
        return

    headers = ["ID", "CMD", "SECTION", "STATUS", "TAGS", "CONTENT", "CREATED"]
    table_rows = []
    for r in rows:
        content = r["content"] or ""
        content_short = content[:40] if len(content) > 40 else content
        table_rows.append([
            str(r["id"]),
            r["cmd_id"] or "-",
            r["section"],
            r["status"] or "-",
            r["tags"] or "-",
            content_short,
            r["created_at"],
        ])
    print_table(headers, table_rows, [5, 10, 12, 10, 16, 40, 20])
