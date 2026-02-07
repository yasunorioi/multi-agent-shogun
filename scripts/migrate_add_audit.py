#!/usr/bin/env python3
"""
migrate_add_audit.py - Add audit columns to subtasks table.

Adds needs_audit and audit_status columns to the existing subtasks table.
Idempotent: safe to re-run (checks for existing columns before ALTER TABLE).

Usage:
    python3 scripts/migrate_add_audit.py
"""

import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"


def get_existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names for a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Add audit columns if they don't exist. Returns list of added columns."""
    existing = get_existing_columns(conn, "subtasks")
    added = []

    if "needs_audit" not in existing:
        conn.execute("ALTER TABLE subtasks ADD COLUMN needs_audit INTEGER DEFAULT 0")
        added.append("needs_audit")

    if "audit_status" not in existing:
        conn.execute("ALTER TABLE subtasks ADD COLUMN audit_status TEXT DEFAULT NULL")
        added.append("audit_status")

    if added:
        conn.commit()

    return added


def main() -> None:
    if not DB_PATH.exists():
        print(f"Error: database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python3 scripts/init_db.py' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    added = migrate(conn)
    conn.close()

    if added:
        print(f"Migration complete: added columns {', '.join(added)} to subtasks table.")
    else:
        print("No migration needed: columns already exist.")


if __name__ == "__main__":
    main()
