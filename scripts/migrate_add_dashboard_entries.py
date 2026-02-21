#!/usr/bin/env python3
"""
migrate_add_dashboard_entries.py - Create dashboard_entries table in botsunichiroku.db.

Idempotent migration: safe to re-run. Uses CREATE TABLE IF NOT EXISTS.

Usage:
    python3 scripts/migrate_add_dashboard_entries.py
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cmd_id TEXT,
            section TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT,
            tags TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

    print("Migration complete: dashboard_entries table created (or already exists).")


if __name__ == "__main__":
    migrate()
