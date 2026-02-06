#!/usr/bin/env python3
"""
botsunichiroku.py - CLI tool for the multi-agent-shogun SQLite database (没日録).

Provides subcommands to manage commands, subtasks, reports, agents, and counters
stored in data/botsunichiroku.db.

Usage:
    python3 scripts/botsunichiroku.py cmd list [--status STATUS] [--project PROJECT] [--json]
    python3 scripts/botsunichiroku.py cmd add "description" [--project PROJECT] [--priority PRIORITY] [--karo roju|ooku]
    python3 scripts/botsunichiroku.py cmd update CMD_ID --status STATUS
    python3 scripts/botsunichiroku.py cmd show CMD_ID [--json]

    python3 scripts/botsunichiroku.py subtask list [--cmd CMD_ID] [--worker WORKER] [--status STATUS] [--json]
    python3 scripts/botsunichiroku.py subtask add CMD_ID "description" [--worker WORKER] [--wave N] [--project PROJECT] [--target-path PATH]
    python3 scripts/botsunichiroku.py subtask update SUBTASK_ID --status STATUS [--worker WORKER]

    python3 scripts/botsunichiroku.py report add TASK_ID WORKER_ID --status STATUS --summary "text" [--findings JSON] [--files-modified JSON] [--skill-name NAME] [--skill-desc DESC]

    python3 scripts/botsunichiroku.py agent list [--role ROLE] [--json]
    python3 scripts/botsunichiroku.py agent update AGENT_ID --status STATUS [--task TASK_ID]

    python3 scripts/botsunichiroku.py counter next NAME
    python3 scripts/botsunichiroku.py counter show [--json]
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def get_connection() -> sqlite3.Connection:
    """Open a connection to botsunichiroku.db with WAL mode and foreign keys."""
    if not DB_PATH.exists():
        print(f"Error: database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python3 scripts/init_db.py' first.", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def next_counter(conn: sqlite3.Connection, name: str) -> int:
    """Atomically increment the named counter and return the new value."""
    cursor = conn.execute(
        "UPDATE counters SET value = value + 1 WHERE name = ?", (name,)
    )
    if cursor.rowcount == 0:
        print(f"Error: counter '{name}' not found.", file=sys.stderr)
        sys.exit(1)
    row = conn.execute(
        "SELECT value FROM counters WHERE name = ?", (name,)
    ).fetchone()
    conn.commit()
    return row["value"]


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_table(headers: list[str], rows: list[list[str]], widths: list[int] | None = None) -> None:
    """Print a fixed-width table to stdout."""
    if not widths:
        # Auto-compute widths based on content
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        # Cap individual columns at 60 chars
        widths = [min(w, 60) for w in widths]

    fmt = "  ".join(f"{{:<{w}}}" for w in widths)

    print(fmt.format(*[h[:w] for h, w in zip(headers, widths)]))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        cells = [str(c)[:w] for c, w in zip(row, widths)]
        print(fmt.format(*cells))


def print_json(data) -> None:
    """Print data as formatted JSON."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# Command (cmd) subcommands
# ---------------------------------------------------------------------------


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
    conn = get_connection()
    seq = next_counter(conn, "cmd_id")
    cmd_id = f"cmd_{seq:03d}"
    ts = now_iso()
    conn.execute(
        """INSERT INTO commands (id, timestamp, command, project, priority, status, assigned_karo, created_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (cmd_id, ts, args.description, args.project, args.priority, args.karo, ts),
    )
    conn.commit()
    conn.close()
    print(f"Created: {cmd_id}")


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

    # Also fetch subtasks for this command
    subtasks = conn.execute(
        "SELECT id, worker_id, status, wave, description FROM subtasks WHERE parent_cmd = ? ORDER BY wave, id",
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
    print(f"{'Details:':<16} {row['details'] or '-'}")
    print(f"{'Created:':<16} {row['created_at']}")
    print(f"{'Completed:':<16} {row['completed_at'] or '-'}")

    if subtasks:
        print(f"\nSubtasks ({len(subtasks)}):")
        headers = ["ID", "WORKER", "STATUS", "WAVE", "DESCRIPTION"]
        table_rows = []
        for s in subtasks:
            table_rows.append([
                s["id"],
                s["worker_id"] or "-",
                s["status"],
                str(s["wave"]),
                s["description"],
            ])
        print_table(headers, table_rows, [14, 12, 14, 5, 50])


# ---------------------------------------------------------------------------
# Subtask subcommands
# ---------------------------------------------------------------------------


def subtask_list(args) -> None:
    conn = get_connection()
    query = "SELECT id, parent_cmd, worker_id, project, status, wave, description FROM subtasks WHERE 1=1"
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
    query += " ORDER BY parent_cmd DESC, wave, id"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No subtasks found.")
        return

    headers = ["ID", "CMD", "WORKER", "STATUS", "WAVE", "PROJECT", "DESCRIPTION"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["parent_cmd"],
            r["worker_id"] or "-",
            r["status"],
            str(r["wave"]),
            r["project"] or "",
            r["description"],
        ])
    print_table(headers, table_rows, [14, 10, 12, 14, 5, 15, 40])


def subtask_add(args) -> None:
    conn = get_connection()

    # Verify parent command exists
    parent = conn.execute("SELECT id FROM commands WHERE id = ?", (args.cmd_id,)).fetchone()
    if not parent:
        conn.close()
        print(f"Error: parent command '{args.cmd_id}' not found.", file=sys.stderr)
        sys.exit(1)

    seq = next_counter(conn, "subtask_id")
    subtask_id = f"subtask_{seq:03d}"
    ts = now_iso()

    assigned_at = ts if args.worker else None
    status = "assigned" if args.worker else "pending"

    conn.execute(
        """INSERT INTO subtasks (id, parent_cmd, worker_id, project, description, target_path, status, wave, assigned_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (subtask_id, args.cmd_id, args.worker, args.project, args.description, args.target_path, status, args.wave, assigned_at),
    )
    conn.commit()
    conn.close()
    print(f"Created: {subtask_id} (parent={args.cmd_id}, wave={args.wave})")


def subtask_update(args) -> None:
    conn = get_connection()
    updates = ["status = ?"]
    params: list = [args.status]

    if args.worker:
        updates.append("worker_id = ?")
        params.append(args.worker)
        if args.status == "assigned":
            updates.append("assigned_at = ?")
            params.append(now_iso())

    if args.status in ("done", "cancelled"):
        updates.append("completed_at = ?")
        params.append(now_iso())

    params.append(args.subtask_id)
    query = f"UPDATE subtasks SET {', '.join(updates)} WHERE id = ?"
    cursor = conn.execute(query, params)
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        print(f"Error: subtask '{args.subtask_id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"Updated: {args.subtask_id} -> status={args.status}")


# ---------------------------------------------------------------------------
# Report subcommands
# ---------------------------------------------------------------------------


def report_add(args) -> None:
    conn = get_connection()

    # Verify task exists
    task = conn.execute("SELECT id FROM subtasks WHERE id = ?", (args.task_id,)).fetchone()
    if not task:
        conn.close()
        print(f"Error: subtask '{args.task_id}' not found.", file=sys.stderr)
        sys.exit(1)

    ts = now_iso()
    conn.execute(
        """INSERT INTO reports (worker_id, task_id, timestamp, status, summary, findings, files_modified, skill_candidate_name, skill_candidate_desc)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            args.worker_id,
            args.task_id,
            ts,
            args.status,
            args.summary,
            args.findings,
            args.files_modified,
            args.skill_name,
            args.skill_desc,
        ),
    )
    conn.commit()
    report_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    print(f"Created: report #{report_id} (task={args.task_id}, worker={args.worker_id})")


# ---------------------------------------------------------------------------
# Agent subcommands
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Counter subcommands
# ---------------------------------------------------------------------------


def counter_next(args) -> None:
    conn = get_connection()
    val = next_counter(conn, args.name)
    conn.close()

    # Format output based on counter name
    if args.name == "cmd_id":
        print(f"cmd_{val:03d}")
    elif args.name == "subtask_id":
        print(f"subtask_{val:03d}")
    else:
        print(f"{args.name} = {val}")


def counter_show(args) -> None:
    conn = get_connection()
    rows = conn.execute("SELECT name, value FROM counters ORDER BY name").fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No counters found.")
        return

    headers = ["NAME", "VALUE", "NEXT_ID"]
    table_rows = []
    for r in rows:
        name = r["name"]
        val = r["value"]
        # Show what the next generated ID would be
        if name == "cmd_id":
            next_id = f"cmd_{val + 1:03d}"
        elif name == "subtask_id":
            next_id = f"subtask_{val + 1:03d}"
        else:
            next_id = str(val + 1)
        table_rows.append([name, str(val), next_id])
    print_table(headers, table_rows, [14, 8, 16])


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="botsunichiroku",
        description="CLI tool for the multi-agent-shogun database (没日録 botsunichiroku.db)",
    )
    top_sub = parser.add_subparsers(dest="entity", required=True, help="Entity to manage")

    # === cmd ===
    cmd_parser = top_sub.add_parser("cmd", help="Manage commands")
    cmd_sub = cmd_parser.add_subparsers(dest="action", required=True)

    # cmd list
    p = cmd_sub.add_parser("list", help="List commands")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--project", help="Filter by project")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_list)

    # cmd add
    p = cmd_sub.add_parser("add", help="Add a new command")
    p.add_argument("description", help="Short description of the command")
    p.add_argument("--project", help="Project name (e.g., arsprout, shogun)")
    p.add_argument("--priority", default="medium", choices=["critical", "high", "medium", "low"], help="Priority level")
    p.add_argument("--karo", choices=["roju", "ooku"], help="Assign to specific karo")
    p.set_defaults(func=cmd_add)

    # cmd update
    p = cmd_sub.add_parser("update", help="Update command status")
    p.add_argument("cmd_id", help="Command ID (e.g., cmd_083)")
    p.add_argument("--status", required=True, choices=["pending", "acknowledged", "in_progress", "done", "cancelled"], help="New status")
    p.set_defaults(func=cmd_update)

    # cmd show
    p = cmd_sub.add_parser("show", help="Show command details")
    p.add_argument("cmd_id", help="Command ID (e.g., cmd_083)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_show)

    # === subtask ===
    subtask_parser = top_sub.add_parser("subtask", help="Manage subtasks")
    subtask_sub = subtask_parser.add_subparsers(dest="action", required=True)

    # subtask list
    p = subtask_sub.add_parser("list", help="List subtasks")
    p.add_argument("--cmd", help="Filter by parent command ID")
    p.add_argument("--worker", help="Filter by worker ID")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=subtask_list)

    # subtask add
    p = subtask_sub.add_parser("add", help="Add a new subtask")
    p.add_argument("cmd_id", help="Parent command ID (e.g., cmd_083)")
    p.add_argument("description", help="Subtask description")
    p.add_argument("--worker", help="Assign to worker (e.g., ashigaru1)")
    p.add_argument("--wave", type=int, default=1, help="Wave number (default: 1)")
    p.add_argument("--project", help="Project name")
    p.add_argument("--target-path", help="Target working directory")
    p.set_defaults(func=subtask_add)

    # subtask update
    p = subtask_sub.add_parser("update", help="Update subtask status")
    p.add_argument("subtask_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("--status", required=True, choices=["pending", "assigned", "in_progress", "done", "blocked", "cancelled"], help="New status")
    p.add_argument("--worker", help="Assign/reassign to worker")
    p.set_defaults(func=subtask_update)

    # === report ===
    report_parser = top_sub.add_parser("report", help="Manage reports")
    report_sub = report_parser.add_subparsers(dest="action", required=True)

    # report add
    p = report_sub.add_parser("add", help="Add a report")
    p.add_argument("task_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("worker_id", help="Worker ID (e.g., ashigaru1)")
    p.add_argument("--status", required=True, choices=["done", "blocked", "error"], help="Report status")
    p.add_argument("--summary", required=True, help="Summary text")
    p.add_argument("--findings", help="Findings as JSON array string")
    p.add_argument("--files-modified", help="Modified files as JSON array string")
    p.add_argument("--skill-name", help="Skill candidate name")
    p.add_argument("--skill-desc", help="Skill candidate description")
    p.set_defaults(func=report_add)

    # === agent ===
    agent_parser = top_sub.add_parser("agent", help="Manage agents")
    agent_sub = agent_parser.add_subparsers(dest="action", required=True)

    # agent list
    p = agent_sub.add_parser("list", help="List agents")
    p.add_argument("--role", choices=["shogun", "karo", "ashigaru"], help="Filter by role")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=agent_list)

    # agent update
    p = agent_sub.add_parser("update", help="Update agent status")
    p.add_argument("agent_id", help="Agent ID (e.g., ashigaru1)")
    p.add_argument("--status", required=True, choices=["idle", "busy", "error", "offline"], help="New status")
    p.add_argument("--task", help="Current task ID (use 'none' to clear)")
    p.set_defaults(func=agent_update)

    # === counter ===
    counter_parser = top_sub.add_parser("counter", help="Manage counters")
    counter_sub = counter_parser.add_subparsers(dest="action", required=True)

    # counter next
    p = counter_sub.add_parser("next", help="Atomically increment and return next value")
    p.add_argument("name", help="Counter name (e.g., cmd_id, subtask_id)")
    p.set_defaults(func=counter_next)

    # counter show
    p = counter_sub.add_parser("show", help="Show all counters")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=counter_show)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
