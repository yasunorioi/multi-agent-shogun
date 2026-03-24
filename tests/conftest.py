"""共通フィクスチャ - shogunシステム テストスイート用"""

import sqlite3
import sys
from pathlib import Path

import pytest

# scriptsディレクトリをパスに追加（init_db, botsunichiroku, generate_dashboard をインポート可能に）
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def tmp_db_path(tmp_path):
    """一時ディレクトリにDBパスを返す（DB未作成）。"""
    return tmp_path / "test_botsunichiroku.db"


@pytest.fixture
def empty_db(tmp_db_path):
    """空のDBを作成し、init_db.pyと同じスキーマを適用して返す。
    テストデータは投入しない。"""
    import init_db

    # init_db のグローバル変数を一時的に差し替え
    original_db_path = init_db.DB_PATH
    original_db_dir = init_db.DB_DIR
    init_db.DB_PATH = tmp_db_path
    init_db.DB_DIR = tmp_db_path.parent
    try:
        init_db.init_db()
    finally:
        init_db.DB_PATH = original_db_path
        init_db.DB_DIR = original_db_dir

    conn = sqlite3.connect(str(tmp_db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(empty_db):
    """テストデータを投入済みのDB接続を返す。
    cmd_001〜cmd_003、subtask_001〜subtask_004、report 1件を含む。"""
    conn = empty_db

    # コマンドテスト用データ
    test_commands = [
        ("cmd_001", "2026-01-01T00:00:00+00:00", "テストコマンド1", "shogun",
         "high", "done", "roju", None, "2026-01-01T00:00:00+00:00", "2026-01-01T01:00:00+00:00"),
        ("cmd_002", "2026-01-02T00:00:00+00:00", "テストコマンド2", "rotation-planner",
         "medium", "in_progress", "midaidokoro", None, "2026-01-02T00:00:00+00:00", None),
        ("cmd_003", "2026-01-03T00:00:00+00:00", "テストコマンド3", "arsprout",
         "low", "pending", "roju", None, "2026-01-03T00:00:00+00:00", None),
    ]
    conn.executemany(
        """INSERT INTO commands (id, timestamp, command, project, priority, status,
           assigned_karo, details, created_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        test_commands,
    )

    # サブタスクテスト用データ
    test_subtasks = [
        ("subtask_001", "cmd_001", "ashigaru1", "shogun", "サブタスク1",
         None, "done", 1, None, "2026-01-01T00:00:00+00:00", "2026-01-01T00:30:00+00:00"),
        ("subtask_002", "cmd_001", "ashigaru2", "shogun", "サブタスク2",
         None, "done", 1, None, "2026-01-01T00:00:00+00:00", "2026-01-01T00:45:00+00:00"),
        ("subtask_003", "cmd_002", "ashigaru6", "rotation-planner", "サブタスク3",
         "/home/yasu/rotation-planner", "in_progress", 1, None, "2026-01-02T00:00:00+00:00", None),
        ("subtask_004", "cmd_002", None, "rotation-planner", "サブタスク4（未割当）",
         None, "pending", 2, None, None, None),
    ]
    conn.executemany(
        """INSERT INTO subtasks (id, parent_cmd, worker_id, project, description,
           target_path, status, wave, notes, assigned_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        test_subtasks,
    )

    # レポートテスト用データ
    conn.execute(
        """INSERT INTO reports (worker_id, task_id, timestamp, status, summary)
           VALUES (?, ?, ?, ?, ?)""",
        ("ashigaru1", "subtask_001", "2026-01-01T00:30:00+00:00", "done", "テスト完了報告"),
    )

    conn.commit()
    return conn


@pytest.fixture
def seeded_db_path(seeded_db, tmp_db_path):
    """テストデータ投入済みDBのファイルパスを返す。
    botsunichiroku.py のDB_PATHモンキーパッチ用。"""
    return tmp_db_path
