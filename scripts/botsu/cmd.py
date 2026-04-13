"""cmd サブコマンド — コマンド管理。"""

import sys

from . import get_connection, next_counter, now_iso, print_table, print_json, row_to_dict, _try_notify, fts5_upsert, vec_upsert_if_available


def cmd_list(args) -> None:
    conn = get_connection()
    query = "SELECT id, timestamp, command, project, priority, status, assigned_karo FROM commands WHERE 1=1"
    params: list = []
    if args.status:
        query += " AND status = ?"
        params.append(args.status)
    if args.project:
        query += " AND project = ?"
        params.append(args.project)
    query += " ORDER BY id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No commands found.")
        return

    headers = ["ID", "STATUS", "PRIORITY", "PROJECT", "KARO", "COMMAND"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"] or "",
            r["status"] or "",
            r["priority"] or "",
            r["project"] or "",
            r["assigned_karo"] or "",
            r["command"] or "",
        ])
    print_table(headers, table_rows, [10, 14, 8, 18, 6, 50])


def cmd_add(args) -> None:
    details = None
    if args.details_file:
        import os
        if not os.path.exists(args.details_file):
            print(f"Error: file '{args.details_file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.details_file) as f:
            details = f.read()
    elif args.details_stdin:
        details = sys.stdin.read()

    conn = get_connection()
    seq = next_counter(conn, "cmd_id")
    cmd_id = f"cmd_{seq:03d}"
    ts = now_iso()
    conn.execute(
        """INSERT INTO commands (id, timestamp, command, project, priority, status, assigned_karo, created_at, details)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
        (cmd_id, ts, args.description, args.project, args.priority, args.karo, ts, details),
    )
    conn.commit()
    raw_text = f"{args.description} {details or ''}".strip()
    fts5_upsert(conn, "command", cmd_id, "", args.project or "", args.karo or "", "pending", raw_text)
    vec_upsert_if_available(conn, cmd_id, "command", raw_text, "", args.project or "", ts)
    conn.commit()
    conn.close()
    print(f"Created: {cmd_id}")

    # --- 高札v2: 自動enrich (CLI直接呼び出し、Docker不要) ---
    try:
        from botsu.search import enrich_data as _enrich_data
        _enrich_data(cmd_id)
    except Exception:
        pass

    _try_notify(f"📌 {cmd_id} 登録: {args.description[:60]}", title="New Command", tags="cmd_add")


def cmd_update(args) -> None:
    conn = get_connection()
    updates = ["status = ?"]
    params: list = [args.status]

    if args.status in ("done", "cancelled"):
        updates.append("completed_at = ?")
        params.append(now_iso())

    params.append(args.cmd_id)
    query = f"UPDATE commands SET {', '.join(updates)} WHERE id = ?"
    cursor = conn.execute(query, params)
    conn.commit()

    if cursor.rowcount > 0:
        row = conn.execute(
            "SELECT command, details, project, assigned_karo FROM commands WHERE id = ?",
            (args.cmd_id,),
        ).fetchone()
        if row:
            raw_text = f"{row['command'] or ''} {row['details'] or ''}".strip()
            fts5_upsert(conn, "command", args.cmd_id, "", row["project"] or "", row["assigned_karo"] or "", args.status, raw_text)
            vec_upsert_if_available(conn, args.cmd_id, "command", raw_text, "", row["project"] or "")
            conn.commit()

    conn.close()

    if cursor.rowcount == 0:
        print(f"Error: command '{args.cmd_id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"Updated: {args.cmd_id} -> status={args.status}")


def cmd_show(args) -> None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM commands WHERE id = ?", (args.cmd_id,)).fetchone()
    if not row:
        conn.close()
        print(f"Error: command '{args.cmd_id}' not found.", file=sys.stderr)
        sys.exit(1)

    subtasks = conn.execute(
        "SELECT id, worker_id, status, wave, blocked_by, description FROM subtasks WHERE parent_cmd = ? ORDER BY wave, id",
        (args.cmd_id,),
    ).fetchall()
    conn.close()

    if args.json:
        d = row_to_dict(row)
        d["subtasks"] = [row_to_dict(s) for s in subtasks]
        print_json(d)
        return

    print(f"{'ID:':<16} {row['id']}")
    print(f"{'Command:':<16} {row['command']}")
    print(f"{'Status:':<16} {row['status']}")
    print(f"{'Priority:':<16} {row['priority']}")
    print(f"{'Project:':<16} {row['project'] or '-'}")
    print(f"{'Assigned Karo:':<16} {row['assigned_karo'] or '-'}")
    if row['details']:
        print(f"{'Details:':<16}")
        print(row['details'])
    else:
        print(f"{'Details:':<16} -")
    print(f"{'Created:':<16} {row['created_at']}")
    print(f"{'Completed:':<16} {row['completed_at'] or '-'}")

    if subtasks:
        print(f"\nSubtasks ({len(subtasks)}):")
        headers = ["ID", "WORKER", "STATUS", "WAVE", "BLOCKED_BY", "DESCRIPTION"]
        table_rows = []
        for s in subtasks:
            blocked_by = s["blocked_by"] or "-"
            if len(blocked_by) > 20:
                blocked_by = blocked_by[:17] + "..."
            table_rows.append([
                s["id"],
                s["worker_id"] or "-",
                s["status"],
                str(s["wave"]),
                blocked_by,
                s["description"],
            ])
        print_table(headers, table_rows, [14, 12, 14, 5, 20, 40])
