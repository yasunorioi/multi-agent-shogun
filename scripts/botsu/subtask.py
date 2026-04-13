"""subtask サブコマンド — サブタスク管理。"""

import sqlite3
import sys
from collections import deque

from . import get_connection, next_counter, now_iso, print_table, print_json, row_to_dict, fts5_upsert, vec_upsert_if_available


def _parse_blocked_by(blocked_by_str: str | None) -> list[str]:
    """Parse comma-separated blocked_by string into a list of subtask IDs."""
    if not blocked_by_str:
        return []
    return [s.strip() for s in blocked_by_str.split(",") if s.strip()]


def _detect_cycle(conn: sqlite3.Connection, start_id: str, blocked_by_ids: list[str]) -> str | None:
    """Detect circular dependencies. Returns the cycle path string if found, None otherwise."""
    for dep_id in blocked_by_ids:
        visited = set()
        queue = deque([dep_id])
        while queue:
            current = queue.popleft()
            if current == start_id:
                return f"{start_id} -> {dep_id} -> ... -> {start_id}"
            if current in visited:
                continue
            visited.add(current)
            row = conn.execute("SELECT blocked_by FROM subtasks WHERE id = ?", (current,)).fetchone()
            if row and row["blocked_by"]:
                for next_id in _parse_blocked_by(row["blocked_by"]):
                    queue.append(next_id)
    return None


def auto_unblock(conn: sqlite3.Connection, completed_id: str) -> list[str]:
    """Auto-unblock subtasks whose dependencies are all resolved.

    When a subtask is completed, find all subtasks that have it in their blocked_by.
    For each, check if ALL dependencies are now done. If so, change status from
    'blocked' to 'assigned' (if worker set) or 'pending' (if no worker).

    Returns list of unblocked subtask IDs with their new status.
    """
    unblocked = []

    rows = conn.execute(
        "SELECT id, blocked_by, worker_id, status FROM subtasks WHERE blocked_by LIKE ?",
        (f"%{completed_id}%",),
    ).fetchall()

    for row in rows:
        if row["status"] != "blocked":
            continue

        deps = _parse_blocked_by(row["blocked_by"])
        if completed_id not in deps:
            continue

        all_resolved = True
        for dep_id in deps:
            if dep_id == completed_id:
                continue
            dep_row = conn.execute(
                "SELECT status FROM subtasks WHERE id = ?", (dep_id,)
            ).fetchone()
            if not dep_row or dep_row["status"] not in ("done", "archived"):
                all_resolved = False
                break

        if all_resolved:
            new_status = "assigned" if row["worker_id"] else "pending"
            conn.execute(
                "UPDATE subtasks SET status = ? WHERE id = ?",
                (new_status, row["id"]),
            )
            worker_info = f" (worker: {row['worker_id']})" if row["worker_id"] else ""
            unblocked.append(f"{row['id']} -> {new_status}{worker_info}")

    return unblocked


def subtask_list(args) -> None:
    conn = get_connection()
    query = "SELECT id, parent_cmd, worker_id, project, status, wave, blocked_by, description FROM subtasks WHERE 1=1"
    params: list = []
    if args.cmd:
        query += " AND parent_cmd = ?"
        params.append(args.cmd)
    if args.worker:
        query += " AND worker_id = ?"
        params.append(args.worker)
    if args.status:
        query += " AND status = ?"
        params.append(args.status)
    if hasattr(args, "needs_audit") and args.needs_audit is not None:
        query += " AND needs_audit = ?"
        params.append(args.needs_audit)
    if hasattr(args, "audit_status") and args.audit_status:
        query += " AND audit_status = ?"
        params.append(args.audit_status)
    query += " ORDER BY parent_cmd DESC, wave, id"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No subtasks found.")
        return

    headers = ["ID", "CMD", "WORKER", "STATUS", "WAVE", "BLOCKED_BY", "DESCRIPTION"]
    table_rows = []
    for r in rows:
        blocked_by = r["blocked_by"] or "-"
        if len(blocked_by) > 20:
            blocked_by = blocked_by[:17] + "..."
        table_rows.append([
            r["id"],
            r["parent_cmd"],
            r["worker_id"] or "-",
            r["status"],
            str(r["wave"]),
            blocked_by,
            r["description"],
        ])
    print_table(headers, table_rows, [14, 10, 12, 14, 5, 20, 35])


def subtask_add(args) -> None:
    conn = get_connection()

    parent = conn.execute("SELECT id FROM commands WHERE id = ?", (args.cmd_id,)).fetchone()
    if not parent:
        conn.close()
        print(f"Error: parent command '{args.cmd_id}' not found.", file=sys.stderr)
        sys.exit(1)

    seq = next_counter(conn, "subtask_id")
    subtask_id = f"subtask_{seq:03d}"
    ts = now_iso()

    blocked_by_str = args.blocked_by if hasattr(args, "blocked_by") and args.blocked_by else None
    blocked_by_ids = _parse_blocked_by(blocked_by_str)

    if blocked_by_ids:
        for dep_id in blocked_by_ids:
            dep = conn.execute("SELECT id FROM subtasks WHERE id = ?", (dep_id,)).fetchone()
            if not dep:
                conn.close()
                print(f"Error: dependency subtask '{dep_id}' not found.", file=sys.stderr)
                sys.exit(1)

    assigned_at = ts if args.worker else None

    if blocked_by_ids:
        status = "blocked"
    else:
        status = "assigned" if args.worker else "pending"

    needs_audit = 1 if args.needs_audit else 0

    conn.execute(
        """INSERT INTO subtasks (id, parent_cmd, worker_id, project, description, target_path, status, wave, needs_audit, blocked_by, assigned_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (subtask_id, args.cmd_id, args.worker, args.project, args.description, args.target_path, status, args.wave, needs_audit, blocked_by_str, assigned_at),
    )
    conn.commit()
    raw_text = f"{args.description or ''}".strip()
    fts5_upsert(conn, "subtask", subtask_id, args.cmd_id, args.project or "", args.worker or "", status, raw_text)
    vec_upsert_if_available(conn, subtask_id, "subtask", raw_text, args.cmd_id, args.project or "", ts)
    conn.commit()
    conn.close()
    blocked_info = f", blocked_by={blocked_by_str}" if blocked_by_str else ""
    print(f"Created: {subtask_id} (parent={args.cmd_id}, wave={args.wave}{blocked_info})")


def subtask_update(args) -> None:
    conn = get_connection()
    updates: list[str] = []
    params: list = []

    if args.status:
        updates.append("status = ?")
        params.append(args.status)

    if args.worker:
        updates.append("worker_id = ?")
        params.append(args.worker)
        if args.status == "assigned":
            updates.append("assigned_at = ?")
            params.append(now_iso())

    if args.status and args.status in ("done", "cancelled"):
        updates.append("completed_at = ?")
        params.append(now_iso())

    if args.audit_status:
        updates.append("audit_status = ?")
        params.append(args.audit_status)

    if hasattr(args, "blocked_by") and args.blocked_by is not None:
        blocked_by_str = args.blocked_by if args.blocked_by else None
        blocked_by_ids = _parse_blocked_by(blocked_by_str)

        if blocked_by_ids:
            for dep_id in blocked_by_ids:
                dep = conn.execute("SELECT id FROM subtasks WHERE id = ?", (dep_id,)).fetchone()
                if not dep:
                    conn.close()
                    print(f"Error: dependency subtask '{dep_id}' not found.", file=sys.stderr)
                    sys.exit(1)

            cycle = _detect_cycle(conn, args.subtask_id, blocked_by_ids)
            if cycle:
                conn.close()
                print(f"Error: circular dependency detected: {cycle}", file=sys.stderr)
                sys.exit(1)

        updates.append("blocked_by = ?")
        params.append(blocked_by_str)

    if not updates:
        print("Error: no update fields specified.", file=sys.stderr)
        sys.exit(1)

    params.append(args.subtask_id)
    query = f"UPDATE subtasks SET {', '.join(updates)} WHERE id = ?"
    cursor = conn.execute(query, params)

    if cursor.rowcount == 0:
        conn.close()
        print(f"Error: subtask '{args.subtask_id}' not found.", file=sys.stderr)
        sys.exit(1)

    unblocked = []
    if args.status == "done":
        unblocked = auto_unblock(conn, args.subtask_id)

    conn.commit()

    row = conn.execute(
        "SELECT description, notes, parent_cmd, project, worker_id, status FROM subtasks WHERE id = ?",
        (args.subtask_id,),
    ).fetchone()
    if row:
        raw_text = f"{row['description'] or ''} {row['notes'] or ''}".strip()
        fts5_upsert(conn, "subtask", args.subtask_id, row["parent_cmd"] or "", row["project"] or "", row["worker_id"] or "", row["status"] or "", raw_text)
        vec_upsert_if_available(conn, args.subtask_id, "subtask", raw_text, row["parent_cmd"] or "", row["project"] or "")
        conn.commit()

    conn.close()

    changes = []
    if args.status:
        changes.append(f"status={args.status}")
    if args.audit_status:
        changes.append(f"audit_status={args.audit_status}")
    print(f"Updated: {args.subtask_id} -> {', '.join(changes)}")

    if unblocked:
        print(f"Auto-unblocked {len(unblocked)} subtask(s): {', '.join(unblocked)}")


def subtask_show(args) -> None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM subtasks WHERE id = ?", (args.subtask_id,)).fetchone()
    if not row:
        conn.close()
        print(f"Error: subtask '{args.subtask_id}' not found.", file=sys.stderr)
        sys.exit(1)

    conn.close()

    if args.json:
        print_json(row_to_dict(row))
        return

    print(f"{'ID:':<16} {row['id']}")
    print(f"{'Parent CMD:':<16} {row['parent_cmd']}")
    print(f"{'Worker:':<16} {row['worker_id'] or '-'}")
    print(f"{'Status:':<16} {row['status']}")
    print(f"{'Wave:':<16} {row['wave']}")
    print(f"{'Project:':<16} {row['project'] or '-'}")
    print(f"{'Target Path:':<16} {row['target_path'] or '-'}")
    print(f"{'Description:':<16} {row['description']}")
    print(f"{'Notes:':<16} {row['notes'] or '-'}")
    print(f"{'Blocked By:':<16} {row['blocked_by'] or '-'}")
    print(f"{'Needs Audit:':<16} {'Yes' if row['needs_audit'] else 'No'}")
    print(f"{'Audit Status:':<16} {row['audit_status'] or '-'}")
    print(f"{'Assigned:':<16} {row['assigned_at'] or '-'}")
    print(f"{'Completed:':<16} {row['completed_at'] or '-'}")
