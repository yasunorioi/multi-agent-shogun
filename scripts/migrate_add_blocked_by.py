#!/usr/bin/env python3
"""
migrate_add_blocked_by.py - Add blocked_by column to subtasks table.

Idempotent migration: safe to re-run. Only adds the column if it doesn't exist.

Usage:
    python3 scripts/migrate_add_blocked_by.py
"""

import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"


def migrate() -> None:
    if not DB_PATH.exists():
        print(f"Error: database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python3 scripts/init_db.py' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    # Check if column already exists
    cursor = conn.execute("PRAGMA table_info(subtasks)")
    columns = {row[1] for row in cursor.fetchall()}

    if "blocked_by" in columns:
        print("Column 'blocked_by' already exists in subtasks table. Nothing to do.")
        conn.close()
        return

    # Add the column
    conn.execute("ALTER TABLE subtasks ADD COLUMN blocked_by TEXT")
    conn.commit()
    conn.close()

    print("Migration complete: added 'blocked_by' column to subtasks table.")


if __name__ == "__main__":
    migrate()
