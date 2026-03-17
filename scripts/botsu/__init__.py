"""botsu — botsunichiroku.py のサブモジュール群。

共通ユーティリティをここで提供し、各サブモジュールから import する。
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent.parent  # scripts/
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"


# ---------------------------------------------------------------------------
# Notification helper
# ---------------------------------------------------------------------------

def _try_notify(message: str, title: str = "", tags: str = "") -> None:
    """通知を試みる。失敗しても握りつぶす。"""
    try:
        subprocess.Popen(
            [sys.executable, os.path.join(str(SCRIPT_DIR), "notify.py"),
             message, "--title", title, "--tags", tags],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


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
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
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
