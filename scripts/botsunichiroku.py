#!/usr/bin/env python3
"""
botsunichiroku.py - CLI tool for the multi-agent-shogun SQLite database (没日録).

Provides subcommands to manage commands, subtasks, reports, agents, and counters
stored in data/botsunichiroku.db.

Usage:
    python3 scripts/botsunichiroku.py cmd list [--status STATUS] [--project PROJECT] [--json]
    python3 scripts/botsunichiroku.py cmd add "description" [--project PROJECT] [--priority PRIORITY] [--karo roju|midaidokoro]
    python3 scripts/botsunichiroku.py cmd update CMD_ID --status STATUS
    python3 scripts/botsunichiroku.py cmd show CMD_ID [--json]

    python3 scripts/botsunichiroku.py subtask list [--cmd CMD_ID] [--worker WORKER] [--status STATUS] [--needs-audit 0|1] [--audit-status STATUS] [--json]
    python3 scripts/botsunichiroku.py subtask add CMD_ID "description" [--worker WORKER] [--wave N] [--project PROJECT] [--target-path PATH] [--needs-audit] [--blocked-by ID1,ID2]
    python3 scripts/botsunichiroku.py subtask update SUBTASK_ID [--status STATUS] [--worker WORKER] [--audit-status {pending,in_progress,done}] [--blocked-by ID1,ID2]
    python3 scripts/botsunichiroku.py subtask show SUBTASK_ID [--json]

    python3 scripts/botsunichiroku.py report add TASK_ID WORKER_ID --status STATUS --summary "text" [--findings JSON] [--files-modified JSON] [--skill-name NAME] [--skill-desc DESC]
    python3 scripts/botsunichiroku.py report list [--subtask SUBTASK_ID] [--worker WORKER_ID] [--status STATUS] [--json]

    python3 scripts/botsunichiroku.py agent list [--role ROLE] [--json]
    python3 scripts/botsunichiroku.py agent update AGENT_ID --status STATUS [--task TASK_ID]

    python3 scripts/botsunichiroku.py counter next NAME
    python3 scripts/botsunichiroku.py counter show [--json]

    python3 scripts/botsunichiroku.py audit list [--all] [--json]

    python3 scripts/botsunichiroku.py stats [--json]
    python3 scripts/botsunichiroku.py archive [--days N] [--dry-run]

    python3 scripts/botsunichiroku.py dashboard add SECTION CONTENT [--cmd CMD_ID] [--tags TAG1,TAG2] [--status STATUS]
    python3 scripts/botsunichiroku.py dashboard list [--section SECTION] [--limit N] [--cmd CMD_ID]
    python3 scripts/botsunichiroku.py dashboard search KEYWORD

    python3 scripts/botsunichiroku.py diary add AGENT_ID --summary "要約" --body "本文" [--cmd CMD_ID] [--subtask SUBTASK_ID] [--tags tag1,tag2]
    python3 scripts/botsunichiroku.py diary list [--agent AGENT_ID] [--date YYYY-MM-DD] [--cmd CMD_ID] [--limit N] [--json]
    python3 scripts/botsunichiroku.py diary show DIARY_ID [--json]
    python3 scripts/botsunichiroku.py diary today [--agent AGENT_ID]

    python3 scripts/botsunichiroku.py kenchi add ID NAME --category CATEGORY --description DESC --path PATH [--depends-on DEPS] [--called-by CALLERS] [--notes NOTES]
    python3 scripts/botsunichiroku.py kenchi list [--category CATEGORY] [--json]
    python3 scripts/botsunichiroku.py kenchi show ID [--json]
    python3 scripts/botsunichiroku.py kenchi update ID [--name NAME] [--description DESC] [--depends-on DEPS] [--called-by CALLERS] [--notes NOTES]
    python3 scripts/botsunichiroku.py kenchi search KEYWORD [--json]
    python3 scripts/botsunichiroku.py kenchi delete ID
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _try_notify(message: str, title: str = "", tags: str = "") -> None:
    """通知を試みる。失敗しても握りつぶす。"""
    try:
        subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(__file__), "notify.py"),
             message, "--title", title, "--tags", tags],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

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
    conn.close()
    print(f"Created: {cmd_id}")

    # --- 高札v2: 自動enrich ---
    enrich_text = f"{args.description} {details or ''}"
    enrich_payload = json.dumps({
        "cmd_id": cmd_id,
        "text": enrich_text,
        "project": args.project,
    })
    try:
        subprocess.Popen(
            ["curl", "-s", "-X", "POST", "http://localhost:8080/enrich",
             "-H", "Content-Type: application/json",
             "-d", enrich_payload],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # 高札APIダウンでもcmd add自体は正常完了

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


# ---------------------------------------------------------------------------
# Subtask subcommands
# ---------------------------------------------------------------------------


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
        # Truncate long blocked_by for table display
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


def _parse_blocked_by(blocked_by_str: str | None) -> list[str]:
    """Parse comma-separated blocked_by string into a list of subtask IDs."""
    if not blocked_by_str:
        return []
    return [s.strip() for s in blocked_by_str.split(",") if s.strip()]


def _detect_cycle(conn: sqlite3.Connection, start_id: str, blocked_by_ids: list[str]) -> str | None:
    """Detect circular dependencies. Returns the cycle path string if found, None otherwise."""
    # BFS from each dependency to see if any path leads back to start_id
    from collections import deque
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

    # Find all subtasks that reference completed_id in their blocked_by
    rows = conn.execute(
        "SELECT id, blocked_by, worker_id, status FROM subtasks WHERE blocked_by LIKE ?",
        (f"%{completed_id}%",),
    ).fetchall()

    for row in rows:
        if row["status"] != "blocked":
            continue

        deps = _parse_blocked_by(row["blocked_by"])
        if completed_id not in deps:
            continue  # false positive from LIKE match

        # Check if ALL dependencies are done
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

    # Handle blocked_by dependencies
    blocked_by_str = args.blocked_by if hasattr(args, "blocked_by") and args.blocked_by else None
    blocked_by_ids = _parse_blocked_by(blocked_by_str)

    if blocked_by_ids:
        # Verify all dependency subtasks exist
        for dep_id in blocked_by_ids:
            dep = conn.execute("SELECT id FROM subtasks WHERE id = ?", (dep_id,)).fetchone()
            if not dep:
                conn.close()
                print(f"Error: dependency subtask '{dep_id}' not found.", file=sys.stderr)
                sys.exit(1)

        # Cycle detection (check if any dependency eventually points back to this new subtask)
        # Since this is a new subtask, we only need to check if deps create a cycle among themselves
        # No cycle possible for a brand new ID, but we validate the dependency chain is valid

    assigned_at = ts if args.worker else None

    # If blocked_by is specified, force status=blocked regardless of worker
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
            # Verify dependencies exist
            for dep_id in blocked_by_ids:
                dep = conn.execute("SELECT id FROM subtasks WHERE id = ?", (dep_id,)).fetchone()
                if not dep:
                    conn.close()
                    print(f"Error: dependency subtask '{dep_id}' not found.", file=sys.stderr)
                    sys.exit(1)

            # Cycle detection
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

    # Auto-unblock dependent subtasks when status changes to done
    unblocked = []
    if args.status == "done":
        unblocked = auto_unblock(conn, args.subtask_id)

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
    _try_notify(f"📋 report #{report_id} ({args.status}) — {args.summary[:50]}",
                title=f"subtask {args.task_id}", tags=args.status)


def report_list(args) -> None:
    conn = get_connection()
    query = "SELECT id, task_id, worker_id, status, summary, timestamp FROM reports WHERE 1=1"
    params: list = []

    if args.subtask:
        query += " AND task_id = ?"
        params.append(args.subtask)
    if args.worker:
        query += " AND worker_id = ?"
        params.append(args.worker)
    if args.status:
        query += " AND status = ?"
        params.append(args.status)

    query += " ORDER BY id DESC LIMIT 20"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No reports found.")
        return

    headers = ["ID", "SUBTASK", "WORKER", "STATUS", "SUMMARY", "CREATED"]
    table_rows = []
    for r in rows:
        summary = r["summary"] or ""
        summary_short = summary[:40] if len(summary) > 40 else summary
        table_rows.append([
            str(r["id"]),
            r["task_id"],
            r["worker_id"],
            r["status"],
            summary_short,
            r["timestamp"],
        ])
    print_table(headers, table_rows, [6, 14, 12, 10, 40, 20])


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
# Audit subcommand
# ---------------------------------------------------------------------------


def audit_list(args) -> None:
    conn = get_connection()
    if args.all:
        query = """SELECT id, parent_cmd, worker_id, status, audit_status, needs_audit, description
                   FROM subtasks WHERE needs_audit = 1
                   ORDER BY parent_cmd DESC, id"""
    else:
        query = """SELECT id, parent_cmd, worker_id, status, audit_status, needs_audit, description
                   FROM subtasks WHERE needs_audit = 1 AND (audit_status IS NULL OR audit_status = 'pending')
                   ORDER BY parent_cmd DESC, id"""
    rows = conn.execute(query).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        if args.all:
            print("No audit items found.")
        else:
            print("No pending audits.")
        return

    headers = ["ID", "CMD", "WORKER", "STATUS", "AUDIT", "DESCRIPTION"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["parent_cmd"],
            r["worker_id"] or "-",
            r["status"],
            r["audit_status"] or "pending",
            r["description"],
        ])
    print_table(headers, table_rows, [14, 10, 12, 14, 10, 40])


# ---------------------------------------------------------------------------
# Stats subcommand
# ---------------------------------------------------------------------------


def stats_show(args) -> None:
    conn = get_connection()

    # Command counts by status
    cmd_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM commands GROUP BY status"
    ).fetchall()
    cmd_counts = {r["status"]: r["cnt"] for r in cmd_rows}
    cmd_total = sum(cmd_counts.values())

    # Subtask counts by status
    sub_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM subtasks GROUP BY status"
    ).fetchall()
    sub_counts = {r["status"]: r["cnt"] for r in sub_rows}
    sub_total = sum(sub_counts.values())

    # Agent utilisation (busy / total ashigaru+heyago)
    agent_total = conn.execute(
        "SELECT COUNT(*) FROM agents WHERE role IN ('ashigaru', 'heyago')"
    ).fetchone()[0]
    agent_busy = conn.execute(
        "SELECT COUNT(*) FROM agents WHERE role IN ('ashigaru', 'heyago') AND status = 'busy'"
    ).fetchone()[0]

    # Commands completed in last 24 hours
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_done = conn.execute(
        "SELECT COUNT(*) FROM commands WHERE status IN ('done', 'archived') AND completed_at >= ?",
        (cutoff_24h,),
    ).fetchone()[0]

    # Commands by project
    proj_rows = conn.execute(
        "SELECT COALESCE(project, '(none)') as proj, COUNT(*) as cnt FROM commands GROUP BY project ORDER BY cnt DESC"
    ).fetchall()

    # Commands by assigned_karo
    karo_rows = conn.execute(
        "SELECT COALESCE(assigned_karo, '(none)') as karo, COUNT(*) as cnt FROM commands GROUP BY assigned_karo ORDER BY cnt DESC"
    ).fetchall()

    conn.close()

    if args.json:
        data = {
            "commands": {"total": cmd_total, "by_status": cmd_counts},
            "subtasks": {"total": sub_total, "by_status": sub_counts},
            "agents": {"total": agent_total, "busy": agent_busy},
            "recent_24h_done": recent_done,
            "by_project": {r["proj"]: r["cnt"] for r in proj_rows},
            "by_karo": {r["karo"]: r["cnt"] for r in karo_rows},
        }
        print_json(data)
        return

    # Text output
    cmd_status_str = " | ".join(
        f"{s}: {cmd_counts.get(s, 0)}"
        for s in ("pending", "in_progress", "done", "cancelled", "archived")
    )
    sub_status_str = " | ".join(
        f"{s}: {sub_counts.get(s, 0)}"
        for s in ("pending", "assigned", "in_progress", "done", "blocked", "archived")
    )
    proj_str = " | ".join(f"{r['proj']}={r['cnt']}" for r in proj_rows)
    karo_str = " | ".join(f"{r['karo']}={r['cnt']}" for r in karo_rows)

    pct = (agent_busy * 100 // agent_total) if agent_total > 0 else 0

    print("═══════════════════════════════════════")
    print("  没日録 統計情報")
    print("═══════════════════════════════════════")
    print(f"  コマンド: {cmd_total}件")
    print(f"    {cmd_status_str}")
    print(f"  サブタスク: {sub_total}件")
    print(f"    {sub_status_str}")
    print(f"  足軽稼働率: {agent_busy}/{agent_total} ({pct}%)")
    print(f"  直近24h完了: {recent_done}件")
    print(f"  プロジェクト別: {proj_str}")
    print(f"  家老別: {karo_str}")
    print("═══════════════════════════════════════")


# ---------------------------------------------------------------------------
# Archive subcommand
# ---------------------------------------------------------------------------


def archive_run(args) -> None:
    conn = get_connection()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

    # Find target commands
    target_cmds = conn.execute(
        "SELECT id FROM commands WHERE status = 'done' AND completed_at IS NOT NULL AND completed_at < ?",
        (cutoff,),
    ).fetchall()
    cmd_ids = [r["id"] for r in target_cmds]

    if not cmd_ids:
        conn.close()
        print(f"アーカイブ対象: 0件（{args.days}日以上前に完了したcmdなし）")
        return

    # Count related subtasks
    placeholders = ",".join("?" for _ in cmd_ids)
    sub_count = conn.execute(
        f"SELECT COUNT(*) FROM subtasks WHERE parent_cmd IN ({placeholders}) AND status = 'done'",
        cmd_ids,
    ).fetchone()[0]

    if args.dry_run:
        print(f"[dry-run] アーカイブ対象: commands {len(cmd_ids)}件, subtasks {sub_count}件（{args.days}日以上前に完了）")
        print(f"[dry-run] 対象cmd: {', '.join(cmd_ids[:10])}{'...' if len(cmd_ids) > 10 else ''}")
        conn.close()
        return

    # Update commands
    conn.execute(
        f"UPDATE commands SET status = 'archived' WHERE id IN ({placeholders})",
        cmd_ids,
    )

    # Update related subtasks
    conn.execute(
        f"UPDATE subtasks SET status = 'archived' WHERE parent_cmd IN ({placeholders}) AND status = 'done'",
        cmd_ids,
    )

    conn.commit()
    conn.close()
    print(f"アーカイブ対象: {len(cmd_ids)}件（{args.days}日以上前に完了）")
    print(f"更新完了: commands {len(cmd_ids)}件, subtasks {sub_count}件 → archived")


# ---------------------------------------------------------------------------
# Diary subcommands
# ---------------------------------------------------------------------------

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
    conn.commit()
    # Get lastrowid
    row = conn.execute("SELECT last_insert_rowid()").fetchone()
    diary_id = row[0]
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


# ---------------------------------------------------------------------------
# Kenchi (検地帳) subcommands — 藩のリソース台帳
# ---------------------------------------------------------------------------

KENCHI_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS kenchi (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT NOT NULL,
    path        TEXT NOT NULL,
    depends_on  TEXT,
    called_by   TEXT,
    added_at    TEXT NOT NULL,
    updated_at  TEXT,
    notes       TEXT
)
"""

KENCHI_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_kenchi_category ON kenchi(category)",
    "CREATE INDEX IF NOT EXISTS idx_kenchi_name ON kenchi(name)",
]


def ensure_kenchi_table(conn: sqlite3.Connection) -> None:
    """Create kenchi table if it doesn't exist."""
    conn.execute(KENCHI_TABLE_SQL)
    for idx_sql in KENCHI_INDEXES_SQL:
        conn.execute(idx_sql)


def kenchi_add(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)

    # Check for duplicates
    existing = conn.execute("SELECT id FROM kenchi WHERE id = ?", (args.id,)).fetchone()
    if existing:
        conn.close()
        print(f"Error: kenchi '{args.id}' already exists. Use 'kenchi update' to modify.", file=sys.stderr)
        sys.exit(1)

    ts = now_iso()
    conn.execute(
        "INSERT INTO kenchi (id, name, category, description, path, depends_on, called_by, added_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (args.id, args.name, args.category, args.description, args.path, args.depends_on, args.called_by, ts, args.notes),
    )
    conn.commit()
    conn.close()
    print(f"Created: kenchi '{args.id}' ({args.category})")


def kenchi_list(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    query = "SELECT id, name, category, description, path, depends_on, called_by, added_at, updated_at FROM kenchi WHERE 1=1"
    params: list = []

    if args.category:
        query += " AND category = ?"
        params.append(args.category)

    query += " ORDER BY category, id"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No kenchi entries found.")
        return

    headers = ["ID", "NAME", "CATEGORY", "DESCRIPTION", "PATH"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["name"],
            r["category"],
            (r["description"] or "")[:40],
            r["path"],
        ])
    print_table(headers, table_rows, [28, 20, 10, 40, 30])


def kenchi_show(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    row = conn.execute("SELECT * FROM kenchi WHERE id = ?", (args.id,)).fetchone()
    conn.close()

    if not row:
        print(f"Error: kenchi '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print_json(row_to_dict(row))
        return

    d = row_to_dict(row)
    print(f"=== 検地帳: {d['id']} ===")
    print(f"  Name:        {d['name']}")
    print(f"  Category:    {d['category']}")
    print(f"  Description: {d['description']}")
    print(f"  Path:        {d['path']}")
    print(f"  Depends on:  {d.get('depends_on') or '-'}")
    print(f"  Called by:    {d.get('called_by') or '-'}")
    print(f"  Added:       {d['added_at']}")
    print(f"  Updated:     {d.get('updated_at') or '-'}")
    print(f"  Notes:       {d.get('notes') or '-'}")


def kenchi_update(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)

    existing = conn.execute("SELECT id FROM kenchi WHERE id = ?", (args.id,)).fetchone()
    if not existing:
        conn.close()
        print(f"Error: kenchi '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    updates = []
    params: list = []

    if args.name:
        updates.append("name = ?")
        params.append(args.name)
    if args.category:
        updates.append("category = ?")
        params.append(args.category)
    if args.description:
        updates.append("description = ?")
        params.append(args.description)
    if args.path:
        updates.append("path = ?")
        params.append(args.path)
    if args.depends_on is not None:
        updates.append("depends_on = ?")
        params.append(args.depends_on)
    if args.called_by is not None:
        updates.append("called_by = ?")
        params.append(args.called_by)
    if args.notes is not None:
        updates.append("notes = ?")
        params.append(args.notes)

    if not updates:
        conn.close()
        print("Nothing to update.")
        return

    updates.append("updated_at = ?")
    params.append(now_iso())
    params.append(args.id)

    conn.execute(f"UPDATE kenchi SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    print(f"Updated: kenchi '{args.id}'")


def kenchi_search(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    keyword = f"%{args.keyword}%"
    rows = conn.execute(
        "SELECT id, name, category, description, path, depends_on, called_by, added_at FROM kenchi WHERE id LIKE ? OR name LIKE ? OR description LIKE ? OR notes LIKE ? ORDER BY category, id",
        (keyword, keyword, keyword, keyword),
    ).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print(f"No kenchi entries found for: {args.keyword}")
        return

    headers = ["ID", "NAME", "CATEGORY", "DESCRIPTION", "PATH"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["name"],
            r["category"],
            (r["description"] or "")[:40],
            r["path"],
        ])
    print_table(headers, table_rows, [28, 20, 10, 40, 30])


def kenchi_delete(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    cursor = conn.execute("DELETE FROM kenchi WHERE id = ?", (args.id,))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        print(f"Error: kenchi '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"Deleted: kenchi '{args.id}'")


# ---------------------------------------------------------------------------
# Dashboard subcommands
# ---------------------------------------------------------------------------


def dashboard_add(args) -> None:
    conn = get_connection()
    ts = now_iso()
    cursor = conn.execute(
        "INSERT INTO dashboard_entries (cmd_id, section, content, status, tags, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (args.cmd, args.section, args.content, args.status, args.tags, ts),
    )
    conn.commit()
    entry_id = cursor.lastrowid
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
    p.add_argument("--karo", choices=["roju", "midaidokoro"], help="Assign to specific karo")
    p.add_argument("--file", dest="details_file", help="Read details from file")
    p.add_argument("--stdin", dest="details_stdin", action="store_true", help="Read details from stdin")
    p.set_defaults(func=cmd_add)

    # cmd update
    p = cmd_sub.add_parser("update", help="Update command status")
    p.add_argument("cmd_id", help="Command ID (e.g., cmd_083)")
    p.add_argument("--status", required=True, choices=["pending", "acknowledged", "in_progress", "done", "cancelled", "archived"], help="New status")
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
    p.add_argument("--needs-audit", type=int, choices=[0, 1], help="Filter by needs_audit (0 or 1)")
    p.add_argument("--audit-status", choices=["pending", "in_progress", "done", "rejected"], help="Filter by audit status")
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
    p.add_argument("--needs-audit", action="store_true", help="Mark as requiring ohariko audit")
    p.add_argument("--blocked-by", help="Comma-separated subtask IDs this task depends on (e.g., subtask_200,subtask_201). Forces status=blocked.")
    p.set_defaults(func=subtask_add)

    # subtask update
    p = subtask_sub.add_parser("update", help="Update subtask status")
    p.add_argument("subtask_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("--status", choices=["pending", "assigned", "in_progress", "done", "blocked", "cancelled", "archived"], help="New status")
    p.add_argument("--worker", help="Assign/reassign to worker")
    p.add_argument("--audit-status", choices=["pending", "in_progress", "done"], help="Set audit status")
    p.add_argument("--blocked-by", help="Set/update blocked_by dependencies (comma-separated subtask IDs, or empty string to clear)")
    p.set_defaults(func=subtask_update)

    # subtask show
    p = subtask_sub.add_parser("show", help="Show subtask details")
    p.add_argument("subtask_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=subtask_show)

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

    # report list
    p = report_sub.add_parser("list", help="List reports")
    p.add_argument("--subtask", help="Filter by subtask ID")
    p.add_argument("--worker", help="Filter by worker ID")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=report_list)

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

    # === audit ===
    audit_parser = top_sub.add_parser("audit", help="Manage audits")
    audit_sub = audit_parser.add_subparsers(dest="action", required=True)

    # audit list
    p = audit_sub.add_parser("list", help="List audit items (default: pending only)")
    p.add_argument("--all", action="store_true", help="Show all audit items (not just pending)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=audit_list)

    # === stats ===
    p = top_sub.add_parser("stats", help="Show database statistics")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=stats_show)

    # === archive ===
    p = top_sub.add_parser("archive", help="Archive old completed commands")
    p.add_argument("--days", type=int, default=7, help="Archive commands completed more than N days ago (default: 7)")
    p.add_argument("--dry-run", action="store_true", help="Show what would be archived without making changes")
    p.set_defaults(func=archive_run)

    # === dashboard ===
    dashboard_parser = top_sub.add_parser("dashboard", help="Manage dashboard entries")
    dashboard_sub = dashboard_parser.add_subparsers(dest="action", required=True)

    # dashboard add
    p = dashboard_sub.add_parser("add", help="Add a dashboard entry")
    p.add_argument("section", help="Section name (e.g., 戦果, スキル候補, findings, 殿裁定, ブロック事項)")
    p.add_argument("content", help="Entry content text")
    p.add_argument("--cmd", help="Related command ID (e.g., cmd_249)", default=None)
    p.add_argument("--tags", help="Comma-separated tags (e.g., OTA,Arduino)", default=None)
    p.add_argument("--status", help="Entry status (e.g., done, adopted, rejected, resolved, frozen)", default=None)
    p.set_defaults(func=dashboard_add)

    # dashboard list
    p = dashboard_sub.add_parser("list", help="List dashboard entries")
    p.add_argument("--section", help="Filter by section name", default=None)
    p.add_argument("--limit", type=int, default=20, help="Max entries to show (default: 20)")
    p.add_argument("--cmd", help="Filter by command ID", default=None)
    p.set_defaults(func=dashboard_list)

    # dashboard search
    p = dashboard_sub.add_parser("search", help="Search dashboard entries by keyword")
    p.add_argument("keyword", help="Keyword to search in content")
    p.set_defaults(func=dashboard_search)

    # === diary ===
    diary_parser = top_sub.add_parser("diary", help="Manage diary entries (思考記録)")
    diary_sub = diary_parser.add_subparsers(dest="action", required=True)

    # diary add
    p = diary_sub.add_parser("add", help="Add a diary entry")
    p.add_argument("agent_id", help="Agent ID (e.g., ashigaru1, roju)")
    p.add_argument("--summary", required=True, help="1-line summary")
    p.add_argument("--body", required=True, help="Body text (思考過程・判断理由)")
    p.add_argument("--cmd", help="Related command ID (e.g., cmd_414)", default=None)
    p.add_argument("--subtask", help="Related subtask ID", default=None)
    p.add_argument("--tags", help="Comma-separated tags", default=None)
    p.set_defaults(func=diary_add)

    # diary list
    p = diary_sub.add_parser("list", help="List diary entries")
    p.add_argument("--agent", help="Filter by agent ID")
    p.add_argument("--date", help="Filter by date (YYYY-MM-DD)")
    p.add_argument("--cmd", help="Filter by command ID")
    p.add_argument("--limit", type=int, default=20, help="Max entries (default: 20)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=diary_list)

    # diary show
    p = diary_sub.add_parser("show", help="Show diary entry details")
    p.add_argument("diary_id", type=int, help="Diary entry ID")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=diary_show)

    # diary today
    p = diary_sub.add_parser("today", help="Show today's diary entries (コンパクション復帰用)")
    p.add_argument("--agent", help="Filter by agent ID")
    p.set_defaults(func=diary_today)

    # === kenchi (検地帳) ===
    kenchi_parser = top_sub.add_parser("kenchi", help="検地帳 — リソース台帳管理")
    kenchi_sub = kenchi_parser.add_subparsers(dest="action", required=True)

    # kenchi add
    p = kenchi_sub.add_parser("add", help="Register a resource")
    p.add_argument("id", help="Resource ID (e.g. scripts/notify.py)")
    p.add_argument("name", help="Human-readable name")
    p.add_argument("--category", required=True, choices=["script", "config", "api", "lib", "db", "doc", "infra"], help="Resource category")
    p.add_argument("--description", required=True, help="What it does")
    p.add_argument("--path", required=True, help="File path")
    p.add_argument("--depends-on", help="Dependencies (JSON array or comma-separated)")
    p.add_argument("--called-by", help="Callers (JSON array or comma-separated)")
    p.add_argument("--notes", help="Additional notes")
    p.set_defaults(func=kenchi_add)

    # kenchi list
    p = kenchi_sub.add_parser("list", help="List resources")
    p.add_argument("--category", help="Filter by category")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=kenchi_list)

    # kenchi show
    p = kenchi_sub.add_parser("show", help="Show resource details")
    p.add_argument("id", help="Resource ID")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=kenchi_show)

    # kenchi update
    p = kenchi_sub.add_parser("update", help="Update a resource")
    p.add_argument("id", help="Resource ID")
    p.add_argument("--name", help="New name")
    p.add_argument("--category", help="New category")
    p.add_argument("--description", help="New description")
    p.add_argument("--path", help="New path")
    p.add_argument("--depends-on", help="New dependencies")
    p.add_argument("--called-by", help="New callers")
    p.add_argument("--notes", help="New notes")
    p.set_defaults(func=kenchi_update)

    # kenchi search
    p = kenchi_sub.add_parser("search", help="Search resources by keyword")
    p.add_argument("keyword", help="Search keyword")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=kenchi_search)

    # kenchi delete
    p = kenchi_sub.add_parser("delete", help="Delete a resource")
    p.add_argument("id", help="Resource ID")
    p.set_defaults(func=kenchi_delete)

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
