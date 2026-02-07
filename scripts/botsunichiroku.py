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

    python3 scripts/botsunichiroku.py subtask list [--cmd CMD_ID] [--worker WORKER] [--status STATUS] [--json]
    python3 scripts/botsunichiroku.py subtask add CMD_ID "description" [--worker WORKER] [--wave N] [--project PROJECT] [--target-path PATH] [--needs-audit]
    python3 scripts/botsunichiroku.py subtask update SUBTASK_ID [--status STATUS] [--worker WORKER] [--audit-status {pending,in_progress,done}]
    python3 scripts/botsunichiroku.py subtask show SUBTASK_ID [--json]

    python3 scripts/botsunichiroku.py report add TASK_ID WORKER_ID --status STATUS --summary "text" [--findings JSON] [--files-modified JSON] [--skill-name NAME] [--skill-desc DESC]
    python3 scripts/botsunichiroku.py report list [--subtask SUBTASK_ID] [--worker WORKER_ID] [--status STATUS] [--json]

    python3 scripts/botsunichiroku.py agent list [--role ROLE] [--json]
    python3 scripts/botsunichiroku.py agent update AGENT_ID --status STATUS [--task TASK_ID]

    python3 scripts/botsunichiroku.py counter next NAME
    python3 scripts/botsunichiroku.py counter show [--json]

    python3 scripts/botsunichiroku.py stats [--json]
    python3 scripts/botsunichiroku.py archive [--days N] [--dry-run]
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
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

    needs_audit = 1 if args.needs_audit else 0

    conn.execute(
        """INSERT INTO subtasks (id, parent_cmd, worker_id, project, description, target_path, status, wave, needs_audit, assigned_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (subtask_id, args.cmd_id, args.worker, args.project, args.description, args.target_path, status, args.wave, needs_audit, assigned_at),
    )
    conn.commit()
    conn.close()
    print(f"Created: {subtask_id} (parent={args.cmd_id}, wave={args.wave})")


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

    if not updates:
        print("Error: no update fields specified.", file=sys.stderr)
        sys.exit(1)

    params.append(args.subtask_id)
    query = f"UPDATE subtasks SET {', '.join(updates)} WHERE id = ?"
    cursor = conn.execute(query, params)
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        print(f"Error: subtask '{args.subtask_id}' not found.", file=sys.stderr)
        sys.exit(1)

    changes = []
    if args.status:
        changes.append(f"status={args.status}")
    if args.audit_status:
        changes.append(f"audit_status={args.audit_status}")
    print(f"Updated: {args.subtask_id} -> {', '.join(changes)}")


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
    p.set_defaults(func=subtask_add)

    # subtask update
    p = subtask_sub.add_parser("update", help="Update subtask status")
    p.add_argument("subtask_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("--status", choices=["pending", "assigned", "in_progress", "done", "blocked", "cancelled", "archived"], help="New status")
    p.add_argument("--worker", help="Assign/reassign to worker")
    p.add_argument("--audit-status", choices=["pending", "in_progress", "done"], help="Set audit status")
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

    # === stats ===
    p = top_sub.add_parser("stats", help="Show database statistics")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=stats_show)

    # === archive ===
    p = top_sub.add_parser("archive", help="Archive old completed commands")
    p.add_argument("--days", type=int, default=7, help="Archive commands completed more than N days ago (default: 7)")
    p.add_argument("--dry-run", action="store_true", help="Show what would be archived without making changes")
    p.set_defaults(func=archive_run)

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
