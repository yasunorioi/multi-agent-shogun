#!/usr/bin/env python3
"""
init_db.py - Initialize the SQLite database for the multi-agent-shogun system.

Creates the database at data/botsunichiroku.db (没日録) with all required tables,
indexes, default agents, and counters. Safe to re-run: only creates tables/rows
that don't already exist.

Usage:
    python3 scripts/init_db.py
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_DIR = PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "botsunichiroku.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

TABLES_SQL = {
    "commands": """
        CREATE TABLE IF NOT EXISTS commands (
            id TEXT PRIMARY KEY,               -- e.g. "cmd_082"
            timestamp TEXT NOT NULL,            -- ISO 8601
            command TEXT NOT NULL,              -- short description
            project TEXT,                       -- e.g. "arsprout", "rotation-planner", "shogun"
            priority TEXT DEFAULT 'medium',     -- critical / high / medium / low
            status TEXT DEFAULT 'pending',      -- pending / acknowledged / in_progress / done / cancelled
            assigned_karo TEXT,                 -- "roju" or "midaidokoro"
            details TEXT,                       -- full task description
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """,
    "subtasks": """
        CREATE TABLE IF NOT EXISTS subtasks (
            id TEXT PRIMARY KEY,               -- e.g. "subtask_190"
            parent_cmd TEXT NOT NULL,           -- FK to commands.id
            worker_id TEXT,                     -- e.g. "ashigaru1"
            project TEXT,
            description TEXT NOT NULL,
            target_path TEXT,                   -- working directory for the task
            status TEXT DEFAULT 'pending',      -- pending / assigned / in_progress / done / blocked / cancelled
            wave INTEGER DEFAULT 1,            -- Wave number (1, 2, 3)
            notes TEXT,                        -- additional context
            needs_audit INTEGER DEFAULT 0,  -- 1=お針子監査対象
            audit_status TEXT DEFAULT NULL, -- NULL/pending/in_progress/done
            assigned_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (parent_cmd) REFERENCES commands(id)
        )
    """,
    "reports": """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            task_id TEXT NOT NULL,              -- FK to subtasks.id
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,               -- done / blocked / error
            summary TEXT,
            completed_steps TEXT,               -- JSON array
            blocking_reason TEXT,
            findings TEXT,                      -- JSON array
            next_actions TEXT,                  -- JSON array
            files_modified TEXT,                -- JSON array
            notes TEXT,
            skill_candidate_name TEXT,
            skill_candidate_desc TEXT,
            FOREIGN KEY (task_id) REFERENCES subtasks(id)
        )
    """,
    "agents": """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,               -- e.g. "shogun", "roju", "midaidokoro", "ashigaru1"
            role TEXT NOT NULL,                 -- "shogun" / "karo" / "ashigaru"
            display_name TEXT,                  -- e.g. "老中", "御台所", "足軽1号"
            model TEXT,                         -- e.g. "opus", "sonnet"
            status TEXT DEFAULT 'idle',         -- idle / busy / error / offline
            current_task_id TEXT,
            pane_target TEXT                    -- tmux pane target e.g. "multiagent:agents.0"
        )
    """,
    "counters": """
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0
        )
    """,
}

# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_commands_status ON commands(status)",
    "CREATE INDEX IF NOT EXISTS idx_commands_project ON commands(project)",
    "CREATE INDEX IF NOT EXISTS idx_commands_assigned_karo ON commands(assigned_karo)",
    "CREATE INDEX IF NOT EXISTS idx_commands_priority ON commands(priority)",
    "CREATE INDEX IF NOT EXISTS idx_subtasks_status ON subtasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_subtasks_worker_id ON subtasks(worker_id)",
    "CREATE INDEX IF NOT EXISTS idx_subtasks_parent_cmd ON subtasks(parent_cmd)",
    "CREATE INDEX IF NOT EXISTS idx_subtasks_wave ON subtasks(wave)",
    "CREATE INDEX IF NOT EXISTS idx_reports_worker_id ON reports(worker_id)",
    "CREATE INDEX IF NOT EXISTS idx_reports_task_id ON reports(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_agents_role ON agents(role)",
    "CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)",
]

# ---------------------------------------------------------------------------
# Default data
# ---------------------------------------------------------------------------

DEFAULT_AGENTS = [
    # (id, role, display_name, model, status, current_task_id, pane_target)
    ("shogun", "shogun", "将軍", "opus", "idle", None, "shogun:main"),
    ("roju", "karo", "老中", "opus", "idle", None, "multiagent:agents.0"),
    ("midaidokoro", "karo", "御台所", "opus", "idle", None, "ooku:agents.0"),
    ("ashigaru1", "ashigaru", "足軽1号", "sonnet", "idle", None, "multiagent:agents.1"),
    ("ashigaru2", "ashigaru", "足軽2号", "sonnet", "idle", None, "multiagent:agents.2"),
    ("ashigaru3", "ashigaru", "足軽3号", "sonnet", "idle", None, "multiagent:agents.3"),
    ("ashigaru4", "ashigaru", "足軽4号", "sonnet", "idle", None, "multiagent:agents.4"),
    ("ashigaru5", "ashigaru", "足軽5号", "sonnet", "idle", None, "multiagent:agents.5"),
    ("ashigaru6", "heyago", "部屋子1号", "sonnet", "idle", None, "ooku:agents.1"),
    ("ashigaru7", "heyago", "部屋子2号", "sonnet", "idle", None, "ooku:agents.2"),
    ("ashigaru8", "heyago", "部屋子3号", "sonnet", "idle", None, "ooku:agents.3"),
    ("ohariko", "ohariko", "お針子", "sonnet", "idle", None, "ooku:agents.4"),
]

DEFAULT_COUNTERS = [
    # (name, value) -- start values based on existing YAML data
    ("cmd_id", 82),
    ("subtask_id", 190),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create and initialize the 没日録 (botsunichiroku) database."""

    # Ensure data/ directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)

    db_existed = DB_PATH.exists()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    created_tables: list[str] = []
    existing_tables: list[str] = []

    # -- Detect which tables already exist --------------------------------
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    pre_existing = {row[0] for row in cursor.fetchall()}

    # -- Create tables ----------------------------------------------------
    for table_name, ddl in TABLES_SQL.items():
        if table_name in pre_existing:
            existing_tables.append(table_name)
        else:
            created_tables.append(table_name)
        conn.execute(ddl)

    # -- Create indexes ---------------------------------------------------
    for idx_sql in INDEXES_SQL:
        conn.execute(idx_sql)

    # -- Seed default agents (INSERT OR IGNORE for safe re-run) -----------
    agents_inserted = 0
    for agent in DEFAULT_AGENTS:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO agents
                (id, role, display_name, model, status, current_task_id, pane_target)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            agent,
        )
        agents_inserted += cursor.rowcount

    # -- Seed counters (INSERT OR IGNORE for safe re-run) -----------------
    counters_inserted = 0
    for counter_name, counter_value in DEFAULT_COUNTERS:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO counters (name, value) VALUES (?, ?)",
            (counter_name, counter_value),
        )
        counters_inserted += cursor.rowcount

    conn.commit()

    # -- Verify -----------------------------------------------------------
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    all_tables = [row[0] for row in cursor.fetchall()]

    cursor = conn.execute("SELECT COUNT(*) FROM agents")
    agent_count = cursor.fetchone()[0]

    cursor = conn.execute("SELECT name, value FROM counters ORDER BY name")
    counter_rows = cursor.fetchall()

    cursor = conn.execute("PRAGMA journal_mode")
    journal_mode = cursor.fetchone()[0]

    conn.close()

    # -- Summary ----------------------------------------------------------
    print("=" * 60)
    print("  multi-agent-shogun DB initialization")
    print("=" * 60)
    print(f"  Database : {DB_PATH}")
    print(f"  WAL mode : {journal_mode}")
    print(f"  DB existed before : {db_existed}")
    print()
    if created_tables:
        print(f"  Tables created ({len(created_tables)}):")
        for t in created_tables:
            print(f"    + {t}")
    if existing_tables:
        print(f"  Tables already existed ({len(existing_tables)}):")
        for t in existing_tables:
            print(f"    - {t}")
    print()
    print(f"  All tables: {', '.join(all_tables)}")
    print(f"  Agents: {agent_count} rows ({agents_inserted} newly inserted)")
    print(f"  Counters: {len(counter_rows)} rows ({counters_inserted} newly inserted)")
    for name, value in counter_rows:
        print(f"    {name} = {value}")
    print()
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    init_db()
