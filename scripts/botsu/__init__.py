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


# ---------------------------------------------------------------------------
# FTS5 helpers
# ---------------------------------------------------------------------------

try:
    import MeCab as _MeCab
    _MECAB_AVAILABLE = True
except ImportError:
    _MECAB_AVAILABLE = False

_ALLOWED_POS = {"名詞", "動詞", "形容詞"}
_fts5_tagger = None


def _fts5_tokenize(text: str) -> str:
    """MeCab分かち書き（利用可能な場合）。未インストール時はrawテキストを返す。"""
    global _fts5_tagger
    if not text:
        return ""
    if not _MECAB_AVAILABLE:
        return text
    if _fts5_tagger is None:
        try:
            _fts5_tagger = _MeCab.Tagger()
        except Exception:
            return text
    try:
        tokens = []
        node = _fts5_tagger.parseToNode(text)
        while node:
            features = node.feature.split(",")
            if features[0] in _ALLOWED_POS:
                surface = node.surface.strip()
                if surface:
                    tokens.append(surface)
            node = node.next
        result = " ".join(tokens)
        return result if result.strip() else text
    except Exception:
        return text


def fts5_upsert(
    conn: sqlite3.Connection,
    source_type: str,
    source_id: str,
    parent_id: str,
    project: str,
    worker_id: str,
    status: str,
    raw_text: str,
) -> None:
    """search_index FTS5テーブルをインクリメンタル更新する。

    search_indexが存在しない場合は何もしない（エラーにしない）。
    MeCab利用可能なら分かち書き後投入、不可ならrawテキストをそのまま投入。
    冪等設計: DELETE WHERE source_id=? → INSERT。
    呼び出し元でconn.commit()が必要。
    """
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'"
    ).fetchone()
    if not exists:
        return
    content = _fts5_tokenize(raw_text)
    conn.execute("DELETE FROM search_index WHERE source_id = ?", (source_id,))
    conn.execute(
        "INSERT INTO search_index"
        " (source_type, source_id, parent_id, project, worker_id, status, content)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source_type, source_id, parent_id, project, worker_id, status, content),
    )
