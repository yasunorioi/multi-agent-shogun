#!/usr/bin/env python3
"""
migrate_yaml_to_db.py - Migrate existing YAML queue data into SQLite.

Reads the YAML files used by the multi-agent-shogun system and inserts
historical data into data/botsunichiroku.db (没日録).

Sources:
  - queue/shogun_to_karo.yaml  -> commands table
  - queue/tasks/ashigaru*.yaml -> subtasks table
  - queue/reports/ashigaru*_report.yaml -> reports table

Safe to re-run: uses INSERT OR IGNORE so duplicate primary keys are skipped.

Usage:
    python3 scripts/migrate_yaml_to_db.py
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from glob import glob
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def safe_yaml_load(filepath: str) -> dict | list | None:
    """Load a YAML file, handling common formatting quirks.

    Some report files use '|\\' (pipe-backslash) instead of '|' for block
    scalars, which PyYAML rejects.  We try the file as-is first, then fall
    back to sanitising '|\\' -> '|' before re-parsing.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        # Fix pipe-backslash block scalars:  "|\" or ">\" at end-of-value
        sanitised = re.sub(r"(\||\>)\\(\s*\n)", r"\1\2", raw)
        try:
            return yaml.safe_load(sanitised)
        except yaml.YAMLError as e:
            raise e

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"

SHOGUN_TO_KARO = PROJECT_ROOT / "queue" / "shogun_to_karo.yaml"
TASKS_DIR = PROJECT_ROOT / "queue" / "tasks"
REPORTS_DIR = PROJECT_ROOT / "queue" / "reports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_str(value) -> str | None:
    """Convert a value to string, returning None for None/empty."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def safe_json_list(value) -> str | None:
    """Convert a list (or string) to a JSON array string for storage."""
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return json.dumps([str(value)], ensure_ascii=False)


def extract_cmd_number(cmd_id: str) -> int:
    """Extract the numeric part from 'cmd_NNN'."""
    m = re.search(r"(\d+)", str(cmd_id))
    return int(m.group(1)) if m else 0


def extract_subtask_number(task_id: str) -> int:
    """Extract the numeric part from 'subtask_NNN'."""
    m = re.search(r"(\d+)", str(task_id))
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# 1. Migrate commands from shogun_to_karo.yaml
# ---------------------------------------------------------------------------

def migrate_commands(conn: sqlite3.Connection) -> int:
    """Parse queue/shogun_to_karo.yaml and insert commands."""
    if not SHOGUN_TO_KARO.exists():
        print(f"  WARNING: {SHOGUN_TO_KARO} not found, skipping commands.")
        return 0

    print(f"  Reading {SHOGUN_TO_KARO} ...")
    data = safe_yaml_load(str(SHOGUN_TO_KARO))

    if not data or "queue" not in data:
        print("  WARNING: No 'queue' key found in shogun_to_karo.yaml.")
        return 0

    queue = data["queue"]
    if not isinstance(queue, list):
        print("  WARNING: 'queue' is not a list.")
        return 0

    inserted = 0
    max_cmd_num = 0

    for cmd in queue:
        if not isinstance(cmd, dict):
            continue

        cmd_id = safe_str(cmd.get("id"))
        if not cmd_id:
            continue

        # Track highest command number
        num = extract_cmd_number(cmd_id)
        if num > max_cmd_num:
            max_cmd_num = num

        timestamp = safe_str(cmd.get("timestamp", ""))
        command_text = safe_str(cmd.get("command", ""))
        project = safe_str(cmd.get("project"))
        priority = safe_str(cmd.get("priority", "medium"))
        status = safe_str(cmd.get("status", "pending"))
        details = safe_str(cmd.get("details"))
        assigned_karo = safe_str(cmd.get("assigned_karo") or cmd.get("assigned_to"))

        # Use timestamp as created_at; if status is done, also set completed_at
        created_at = timestamp or datetime.now().isoformat()
        completed_at = timestamp if status == "done" else None

        try:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO commands
                    (id, timestamp, command, project, priority, status,
                     assigned_karo, details, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cmd_id,
                    timestamp or "",
                    command_text or "",
                    project,
                    priority,
                    status,
                    assigned_karo,
                    details,
                    created_at,
                    completed_at,
                ),
            )
            inserted += cursor.rowcount
        except sqlite3.Error as e:
            print(f"  ERROR inserting {cmd_id}: {e}")

    return inserted


# ---------------------------------------------------------------------------
# 2. Migrate subtasks from queue/tasks/ashigaru*.yaml
# ---------------------------------------------------------------------------

def migrate_subtasks(conn: sqlite3.Connection) -> int:
    """Parse queue/tasks/ashigaru*.yaml and insert non-idle subtasks."""
    pattern = str(TASKS_DIR / "ashigaru*.yaml")
    files = sorted(glob(pattern))

    if not files:
        print(f"  WARNING: No task files found matching {pattern}")
        return 0

    inserted = 0

    for filepath in files:
        # Extract worker_id from filename: ashigaru1.yaml -> ashigaru1
        basename = Path(filepath).stem  # e.g. "ashigaru1"
        worker_id = basename

        print(f"  Reading {filepath} ...")
        try:
            data = safe_yaml_load(filepath)
        except Exception as e:
            print(f"  ERROR parsing {filepath}: {e}")
            continue

        if not data or "task" not in data:
            continue

        task = data["task"]
        if not isinstance(task, dict):
            continue

        status = safe_str(task.get("status", "idle"))

        # Skip idle tasks (no real assignment)
        if status == "idle":
            continue

        task_id = safe_str(task.get("task_id"))
        if not task_id:
            continue

        parent_cmd = safe_str(task.get("parent_cmd"))
        project = safe_str(task.get("project"))
        description = safe_str(task.get("description", ""))
        target_path = safe_str(task.get("target_path"))
        priority = safe_str(task.get("priority"))
        wave = task.get("wave")
        notes = safe_str(task.get("notes"))
        timestamp = safe_str(task.get("timestamp"))

        assigned_at = timestamp
        completed_at = timestamp if status == "done" else None

        try:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO subtasks
                    (id, parent_cmd, worker_id, project, description,
                     target_path, status, wave, notes, assigned_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    parent_cmd or "",
                    worker_id,
                    project,
                    description or "",
                    target_path,
                    status,
                    wave if isinstance(wave, int) else 1,
                    notes,
                    assigned_at,
                    completed_at,
                ),
            )
            inserted += cursor.rowcount
        except sqlite3.Error as e:
            print(f"  ERROR inserting subtask {task_id}: {e}")

    return inserted


# ---------------------------------------------------------------------------
# 3. Migrate reports from queue/reports/ashigaru*_report.yaml
# ---------------------------------------------------------------------------

def ensure_subtask_exists(
    conn: sqlite3.Connection,
    task_id: str,
    parent_cmd: str | None,
    worker_id: str | None,
    timestamp: str | None,
) -> None:
    """Create a placeholder subtask row if it doesn't exist yet.

    Reports reference subtask IDs, but the corresponding task file may now
    show status=idle (meaning the subtask was completed and cleared).
    We create a minimal 'done' entry so the FK constraint is satisfied.
    """
    existing = conn.execute(
        "SELECT id FROM subtasks WHERE id = ?", (task_id,)
    ).fetchone()
    if existing:
        return

    conn.execute(
        """
        INSERT OR IGNORE INTO subtasks
            (id, parent_cmd, worker_id, project, description,
             target_path, status, wave, notes, assigned_at, completed_at)
        VALUES (?, ?, ?, NULL, ?, NULL, 'done', 1, 'Auto-created from report migration', ?, ?)
        """,
        (
            task_id,
            parent_cmd or "",
            worker_id,
            f"(migrated from report, original task cleared)",
            timestamp,
            timestamp,
        ),
    )


def migrate_reports(conn: sqlite3.Connection) -> int:
    """Parse queue/reports/ashigaru*_report.yaml and insert non-empty reports."""
    pattern = str(REPORTS_DIR / "ashigaru*_report.yaml")
    files = sorted(glob(pattern))

    if not files:
        print(f"  WARNING: No report files found matching {pattern}")
        return 0

    inserted = 0

    for filepath in files:
        print(f"  Reading {filepath} ...")
        try:
            data = safe_yaml_load(filepath)
        except Exception as e:
            print(f"  ERROR parsing {filepath}: {e}")
            continue

        if not data or not isinstance(data, dict):
            continue

        worker_id = safe_str(data.get("worker_id"))
        task_id = safe_str(data.get("task_id"))
        timestamp = safe_str(data.get("timestamp"))
        status = safe_str(data.get("status"))

        # Skip empty/idle reports
        if not task_id or not status:
            continue

        # Extract result fields
        result = data.get("result", {}) or {}
        if not isinstance(result, dict):
            result = {}

        summary = safe_str(result.get("summary"))
        completed_steps = safe_json_list(result.get("completed_steps"))
        blocking_reason = safe_str(
            result.get("blocking_reason")
        )
        findings = safe_json_list(result.get("findings"))
        next_actions = safe_json_list(
            result.get("next_actions_proposal") or result.get("next_actions")
        )
        files_modified = safe_json_list(
            result.get("files_modified") or result.get("files_created")
        )
        notes = safe_str(result.get("notes"))

        # Extract skill_candidate info
        skill_data = data.get("skill_candidate", {}) or {}
        if not isinstance(skill_data, dict):
            skill_data = {}

        skill_name = None
        skill_desc = None
        if skill_data.get("found"):
            skill_name = safe_str(skill_data.get("name"))
            skill_desc = safe_str(skill_data.get("description"))

        # Extract parent_cmd if available (some reports have it at top level)
        parent_cmd = safe_str(data.get("parent_cmd"))

        try:
            # Ensure the referenced subtask exists (may have been cleared
            # to idle after the report was written).
            ensure_subtask_exists(conn, task_id, parent_cmd, worker_id, timestamp)

            # Use a query that checks for duplicates by worker_id + task_id
            # since reports.id is AUTOINCREMENT, we can't use INSERT OR IGNORE
            # on the primary key. Instead, check if a report for this
            # worker+task already exists.
            existing = conn.execute(
                "SELECT id FROM reports WHERE worker_id = ? AND task_id = ?",
                (worker_id, task_id),
            ).fetchone()

            if existing:
                continue  # Already migrated

            cursor = conn.execute(
                """
                INSERT INTO reports
                    (worker_id, task_id, timestamp, status, summary,
                     completed_steps, blocking_reason, findings,
                     next_actions, files_modified, notes,
                     skill_candidate_name, skill_candidate_desc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    worker_id or "",
                    task_id,
                    timestamp or "",
                    status,
                    summary,
                    completed_steps,
                    blocking_reason,
                    findings,
                    next_actions,
                    files_modified,
                    notes,
                    skill_name,
                    skill_desc,
                ),
            )
            inserted += cursor.rowcount
        except sqlite3.Error as e:
            print(f"  ERROR inserting report for {worker_id}/{task_id}: {e}")

    return inserted


# ---------------------------------------------------------------------------
# 4. Update counters
# ---------------------------------------------------------------------------

def update_counters(conn: sqlite3.Connection) -> None:
    """Set counters to be one past the highest existing id."""
    # Find highest cmd_id
    row = conn.execute(
        "SELECT id FROM commands ORDER BY id"
    ).fetchall()

    max_cmd = 0
    for (cid,) in row:
        num = extract_cmd_number(cid)
        if num > max_cmd:
            max_cmd = num

    # Find highest subtask_id
    row = conn.execute(
        "SELECT id FROM subtasks ORDER BY id"
    ).fetchall()

    max_sub = 0
    for (sid,) in row:
        num = extract_subtask_number(sid)
        if num > max_sub:
            max_sub = num

    # Also consider the existing counter values (don't go backwards)
    existing_cmd = conn.execute(
        "SELECT value FROM counters WHERE name = 'cmd_id'"
    ).fetchone()
    existing_sub = conn.execute(
        "SELECT value FROM counters WHERE name = 'subtask_id'"
    ).fetchone()

    new_cmd_counter = max(max_cmd + 1, (existing_cmd[0] if existing_cmd else 0))
    new_sub_counter = max(max_sub + 1, (existing_sub[0] if existing_sub else 0))

    conn.execute(
        "UPDATE counters SET value = ? WHERE name = 'cmd_id'",
        (new_cmd_counter,),
    )
    conn.execute(
        "UPDATE counters SET value = ? WHERE name = 'subtask_id'",
        (new_sub_counter,),
    )

    print(f"  Counters updated:")
    print(f"    cmd_id    = {new_cmd_counter} (highest cmd: cmd_{max_cmd:03d})")
    print(f"    subtask_id = {new_sub_counter} (highest subtask: subtask_{max_sub})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Run 'python3 scripts/init_db.py' first.")
        sys.exit(1)

    print("=" * 60)
    print("  YAML -> SQLite Migration (没日録)")
    print("=" * 60)
    print(f"  Database: {DB_PATH}")
    print()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    # Disable FK constraints during migration since historical data may
    # reference subtasks/commands that were cleared from the YAML files.
    # The subtasks table has FK to commands, and reports has FK to subtasks.
    # Completed tasks get cleared to "idle" in the YAML, losing the reference.
    conn.execute("PRAGMA foreign_keys=OFF")

    # --- Migrate commands ---
    print("[1/4] Migrating commands from shogun_to_karo.yaml ...")
    cmd_count = migrate_commands(conn)
    conn.commit()
    print(f"  -> {cmd_count} commands inserted.\n")

    # --- Migrate subtasks ---
    print("[2/4] Migrating subtasks from queue/tasks/ ...")
    sub_count = migrate_subtasks(conn)
    conn.commit()
    print(f"  -> {sub_count} subtasks inserted.\n")

    # --- Migrate reports ---
    print("[3/4] Migrating reports from queue/reports/ ...")
    rep_count = migrate_reports(conn)
    conn.commit()
    print(f"  -> {rep_count} reports inserted.\n")

    # --- Update counters ---
    print("[4/4] Updating counters ...")
    update_counters(conn)
    conn.commit()
    print()

    # --- Verification ---
    total_cmds = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    total_subs = conn.execute("SELECT COUNT(*) FROM subtasks").fetchone()[0]
    total_reps = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

    print("=" * 60)
    print("  Migration Summary")
    print("=" * 60)
    print(f"  Commands inserted this run : {cmd_count}")
    print(f"  Subtasks inserted this run : {sub_count}")
    print(f"  Reports  inserted this run : {rep_count}")
    print()
    print(f"  Total commands in DB       : {total_cmds}")
    print(f"  Total subtasks in DB       : {total_subs}")
    print(f"  Total reports  in DB       : {total_reps}")
    print()

    # Show status breakdown
    print("  Command status breakdown:")
    for row in conn.execute(
        "SELECT status, COUNT(*) FROM commands GROUP BY status ORDER BY status"
    ):
        print(f"    {row[0]}: {row[1]}")
    print()

    # FK integrity check (informational)
    conn.execute("PRAGMA foreign_keys=ON")
    fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_errors:
        print(f"  NOTE: {len(fk_errors)} FK reference(s) to missing parent rows")
        print("  (Expected for historical data where tasks were cleared to idle)")
        for err in fk_errors[:5]:
            print(f"    table={err[0]}, rowid={err[1]}, parent={err[2]}, fkid={err[3]}")
        if len(fk_errors) > 5:
            print(f"    ... and {len(fk_errors) - 5} more")
    else:
        print("  FK integrity: OK")
    print()

    print("  Done.")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
