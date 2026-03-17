"""agent サブコマンド — エージェント管理。"""

import sys

from . import get_connection, print_table, print_json, row_to_dict


def agent_list(args) -> None:
    conn = get_connection()
    query = "SELECT id, role, display_name, model, status, current_task_id, pane_target FROM agents WHERE 1=1"
    params: list = []
    if args.role:
        query += " AND role = ?"
        params.append(args.role)
    query += " ORDER BY role, id"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No agents found.")
        return

    headers = ["ID", "ROLE", "NAME", "MODEL", "STATUS", "TASK", "PANE"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["role"],
            r["display_name"] or "",
            r["model"] or "",
            r["status"],
            r["current_task_id"] or "-",
            r["pane_target"] or "",
        ])
    print_table(headers, table_rows, [12, 8, 8, 7, 8, 14, 24])


def agent_update(args) -> None:
    conn = get_connection()
    updates = ["status = ?"]
    params: list = [args.status]

    if args.task is not None:
        updates.append("current_task_id = ?")
        params.append(args.task if args.task != "none" else None)

    params.append(args.agent_id)
    query = f"UPDATE agents SET {', '.join(updates)} WHERE id = ?"
    cursor = conn.execute(query, params)
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        print(f"Error: agent '{args.agent_id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"Updated: {args.agent_id} -> status={args.status}")
