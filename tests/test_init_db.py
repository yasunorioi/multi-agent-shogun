"""tests/test_init_db.py - scripts/init_db.py 統合テスト

cmd_094 subtask_211: init_db() の全機能を網羅する統合テスト。
conftest.py の共通フィクスチャ（empty_db, tmp_db_path）を使用。
"""

import sqlite3

import pytest

import init_db


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run_init_db(tmp_db_path):
    """init_db() を tmp_db_path で実行するヘルパー。"""
    original_db_path = init_db.DB_PATH
    original_db_dir = init_db.DB_DIR
    init_db.DB_PATH = tmp_db_path
    init_db.DB_DIR = tmp_db_path.parent
    try:
        init_db.init_db()
    finally:
        init_db.DB_PATH = original_db_path
        init_db.DB_DIR = original_db_dir


# ---------------------------------------------------------------------------
# DB新規作成
# ---------------------------------------------------------------------------


class TestDBCreation:
    def test_db_file_created(self, tmp_db_path):
        """新規DBが正しく作成され、指定パスにファイルが存在すること。"""
        assert not tmp_db_path.exists()
        _run_init_db(tmp_db_path)
        assert tmp_db_path.exists()
        assert tmp_db_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# テーブル作成確認（5テーブル）
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {"commands", "subtasks", "reports", "agents", "counters"}


class TestTables:
    def test_all_five_tables_exist(self, empty_db):
        """commands, subtasks, reports, agents, counters の全5テーブルが存在すること。"""
        cursor = empty_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert EXPECTED_TABLES.issubset(tables)

    def test_commands_columns(self, empty_db):
        """commandsテーブルのカラム名・型が正しいこと。"""
        cursor = empty_db.execute("PRAGMA table_info(commands)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        expected = {
            "id": "TEXT",
            "timestamp": "TEXT",
            "command": "TEXT",
            "project": "TEXT",
            "priority": "TEXT",
            "status": "TEXT",
            "assigned_karo": "TEXT",
            "details": "TEXT",
            "created_at": "TEXT",
            "completed_at": "TEXT",
        }
        assert columns == expected

    def test_subtasks_columns(self, empty_db):
        """subtasksテーブルのカラム名・型が正しいこと。"""
        cursor = empty_db.execute("PRAGMA table_info(subtasks)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        expected = {
            "id": "TEXT",
            "parent_cmd": "TEXT",
            "worker_id": "TEXT",
            "project": "TEXT",
            "description": "TEXT",
            "target_path": "TEXT",
            "status": "TEXT",
            "wave": "INTEGER",
            "notes": "TEXT",
            "needs_audit": "INTEGER",
            "audit_status": "TEXT",
            "assigned_at": "TEXT",
            "completed_at": "TEXT",
        }
        assert columns == expected

    def test_reports_columns(self, empty_db):
        """reportsテーブルのカラム名・型が正しいこと。"""
        cursor = empty_db.execute("PRAGMA table_info(reports)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        expected = {
            "id": "INTEGER",
            "worker_id": "TEXT",
            "task_id": "TEXT",
            "timestamp": "TEXT",
            "status": "TEXT",
            "summary": "TEXT",
            "completed_steps": "TEXT",
            "blocking_reason": "TEXT",
            "findings": "TEXT",
            "next_actions": "TEXT",
            "files_modified": "TEXT",
            "notes": "TEXT",
            "skill_candidate_name": "TEXT",
            "skill_candidate_desc": "TEXT",
        }
        assert columns == expected

    def test_agents_columns(self, empty_db):
        """agentsテーブルのカラム名・型が正しいこと。"""
        cursor = empty_db.execute("PRAGMA table_info(agents)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        expected = {
            "id": "TEXT",
            "role": "TEXT",
            "display_name": "TEXT",
            "model": "TEXT",
            "status": "TEXT",
            "current_task_id": "TEXT",
            "pane_target": "TEXT",
        }
        assert columns == expected

    def test_counters_columns(self, empty_db):
        """countersテーブルのカラム名・型が正しいこと。"""
        cursor = empty_db.execute("PRAGMA table_info(counters)")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        expected = {
            "name": "TEXT",
            "value": "INTEGER",
        }
        assert columns == expected


# ---------------------------------------------------------------------------
# インデックス確認（12個）
# ---------------------------------------------------------------------------

EXPECTED_INDEXES = {
    "idx_commands_status",
    "idx_commands_project",
    "idx_commands_assigned_karo",
    "idx_commands_priority",
    "idx_subtasks_status",
    "idx_subtasks_worker_id",
    "idx_subtasks_parent_cmd",
    "idx_subtasks_wave",
    "idx_reports_worker_id",
    "idx_reports_task_id",
    "idx_agents_role",
    "idx_agents_status",
}


class TestIndexes:
    def test_twelve_indexes_created(self, empty_db):
        """12個のインデックスが作成されていること。"""
        cursor = empty_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = [row["name"] for row in cursor.fetchall()]
        assert len(indexes) == 12

    def test_index_names_match(self, empty_db):
        """インデックス名の一覧が正しいこと。"""
        cursor = empty_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        index_names = {row["name"] for row in cursor.fetchall()}
        assert index_names == EXPECTED_INDEXES


# ---------------------------------------------------------------------------
# 冪等性テスト
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_double_init_no_error(self, tmp_db_path):
        """init_db() を2回実行してもエラーにならないこと。"""
        _run_init_db(tmp_db_path)
        _run_init_db(tmp_db_path)

    def test_double_init_tables_unchanged(self, tmp_db_path):
        """2回目実行後もテーブル数・データが変わらないこと。"""
        _run_init_db(tmp_db_path)
        conn = sqlite3.connect(str(tmp_db_path))
        conn.row_factory = sqlite3.Row
        tables_1 = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        agents_1 = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        counters_1 = conn.execute("SELECT COUNT(*) FROM counters").fetchone()[0]
        conn.close()

        _run_init_db(tmp_db_path)
        conn = sqlite3.connect(str(tmp_db_path))
        conn.row_factory = sqlite3.Row
        tables_2 = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        agents_2 = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        counters_2 = conn.execute("SELECT COUNT(*) FROM counters").fetchone()[0]
        conn.close()

        assert tables_1 == tables_2
        assert agents_1 == agents_2
        assert counters_1 == counters_2


# ---------------------------------------------------------------------------
# デフォルトエージェント確認（12名）
# ---------------------------------------------------------------------------


class TestDefaultAgents:
    def test_twelve_agents_inserted(self, empty_db):
        """12エージェントが挿入されること。"""
        count = empty_db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        assert count == 12

    def test_agent_id_role_display_pane(self, empty_db):
        """各エージェントの id, role, display_name, pane_target が正確であること。"""
        rows = empty_db.execute(
            "SELECT id, role, display_name, pane_target FROM agents ORDER BY id"
        ).fetchall()
        agents = {row["id"]: dict(row) for row in rows}

        # 将軍
        assert agents["shogun"]["role"] == "shogun"
        assert agents["shogun"]["display_name"] == "将軍"
        assert agents["shogun"]["pane_target"] == "shogun:main"

        # 家老
        assert agents["roju"]["role"] == "karo"
        assert agents["roju"]["display_name"] == "老中"
        assert agents["roju"]["pane_target"] == "multiagent:agents.0"

        assert agents["midaidokoro"]["role"] == "karo"
        assert agents["midaidokoro"]["display_name"] == "御台所"
        assert agents["midaidokoro"]["pane_target"] == "ooku:agents.0"

        # 足軽1-5
        for i in range(1, 6):
            key = f"ashigaru{i}"
            assert agents[key]["role"] == "ashigaru"
            assert agents[key]["display_name"] == f"足軽{i}号"
            assert agents[key]["pane_target"] == f"multiagent:agents.{i}"

        # 部屋子1-3 (ashigaru6-8)
        for i in range(6, 9):
            key = f"ashigaru{i}"
            assert agents[key]["role"] == "heyago"
            assert agents[key]["display_name"] == f"部屋子{i - 5}号"
            assert agents[key]["pane_target"] == f"ooku:agents.{i - 5}"

        # お針子
        assert agents["ohariko"]["role"] == "ohariko"
        assert agents["ohariko"]["display_name"] == "お針子"
        assert agents["ohariko"]["pane_target"] == "ooku:agents.4"

    def test_no_duplicate_on_rerun(self, tmp_db_path):
        """再実行で重複挿入されないこと（INSERT OR IGNORE）。"""
        _run_init_db(tmp_db_path)
        _run_init_db(tmp_db_path)
        conn = sqlite3.connect(str(tmp_db_path))
        count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        conn.close()
        assert count == 12


# ---------------------------------------------------------------------------
# カウンタ確認
# ---------------------------------------------------------------------------


class TestCounters:
    def test_cmd_id_initial_value(self, empty_db):
        """cmd_id カウンタの初期値が 82 であること。"""
        row = empty_db.execute(
            "SELECT value FROM counters WHERE name = 'cmd_id'"
        ).fetchone()
        assert row["value"] == 82

    def test_subtask_id_initial_value(self, empty_db):
        """subtask_id カウンタの初期値が 190 であること。"""
        row = empty_db.execute(
            "SELECT value FROM counters WHERE name = 'subtask_id'"
        ).fetchone()
        assert row["value"] == 190

    def test_counters_no_overwrite_on_rerun(self, tmp_db_path):
        """再実行でカウンタ値が上書きされないこと。"""
        _run_init_db(tmp_db_path)

        conn = sqlite3.connect(str(tmp_db_path))
        conn.execute("UPDATE counters SET value = 999 WHERE name = 'cmd_id'")
        conn.commit()
        conn.close()

        _run_init_db(tmp_db_path)

        conn = sqlite3.connect(str(tmp_db_path))
        val = conn.execute(
            "SELECT value FROM counters WHERE name = 'cmd_id'"
        ).fetchone()[0]
        conn.close()
        assert val == 999


# ---------------------------------------------------------------------------
# WALモード確認
# ---------------------------------------------------------------------------


class TestWALMode:
    def test_journal_mode_wal(self, empty_db):
        """PRAGMA journal_mode が "wal" であること。"""
        mode = empty_db.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


# ---------------------------------------------------------------------------
# 外部キー制約確認
# ---------------------------------------------------------------------------


class TestForeignKeys:
    def test_foreign_keys_enabled(self, empty_db):
        """PRAGMA foreign_keys が ON (1) であること。"""
        fk = empty_db.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_subtask_parent_cmd_fk_violation(self, empty_db):
        """subtasks.parent_cmd が commands.id を参照しており、不正値でエラーになること。"""
        with pytest.raises(sqlite3.IntegrityError):
            empty_db.execute(
                "INSERT INTO subtasks (id, parent_cmd, description) "
                "VALUES ('st_bad', 'nonexistent_cmd', 'test')"
            )

    def test_report_task_id_fk_violation(self, empty_db):
        """reports.task_id が subtasks.id を参照しており、不正値でエラーになること。"""
        with pytest.raises(sqlite3.IntegrityError):
            empty_db.execute(
                "INSERT INTO reports (worker_id, task_id, timestamp, status) "
                "VALUES ('ashigaru1', 'nonexistent_task', '2026-01-01', 'done')"
            )
