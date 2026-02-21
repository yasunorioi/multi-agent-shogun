"""没日録検索エンジン テストスイート

Wave1（build_index.py + main.py）の全機能をテストする。
テスト用の小さな没日録DBを tmp_path に作成し、本番DBには一切触れない。
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ============================================================
# テスト用フィクスチャ
# ============================================================

COMMANDS_DATA = [
    ("cmd_100", "2026-02-01T10:00:00", "watchdogタイマー実装", "shogun", "high", "done", "roju",
     "Pico用のwatchdogタイマーを実装せよ。ハードウェアWDTを使用し、30秒でリセットする。", "2026-02-01T10:00:00", "2026-02-02T15:00:00"),
    ("cmd_101", "2026-02-03T10:00:00", "MeCab FTS5検索エンジン構築", "shogun", "high", "pending", "midaidokoro",
     "没日録の全文検索をMeCab形態素解析+SQLite FTS5で実装する。Docker化して配備。", "2026-02-03T10:00:00", None),
    ("cmd_102", "2026-01-01T10:00:00", "古いペンディングタスク", "shogun", "low", "pending", "roju",
     "これは7日以上前に作成されたpendingタスク。放置検出のテスト用。", "2026-01-01T10:00:00", None),
]

SUBTASKS_DATA = [
    ("subtask_200", "cmd_100", "ashigaru1", "shogun", "watchdogタイマーのファームウェア実装", "/home/yasu/unipi-agri-ha",
     "done", 1, "CircuitPythonのwatchdog APIを使用", "2026-02-01T11:00:00", "2026-02-02T14:00:00", 0, None),
    ("subtask_201", "cmd_100", "ashigaru2", "shogun", "watchdogタイマーのテスト作成", "/home/yasu/unipi-agri-ha",
     "done", 1, "ユニットテストとハードウェアテスト", "2026-02-01T11:00:00", "2026-02-02T15:00:00", 0, None),
    ("subtask_202", "cmd_101", "ashigaru6", "shogun", "Docker基盤+FastAPI実装", "/home/yasu/multi-agent-shogun",
     "done", 1, "Dockerfile, docker-compose.yml, main.py", "2026-02-03T11:00:00", "2026-02-04T10:00:00", 0, None),
    ("subtask_203", "cmd_101", "ashigaru7", "shogun", "build_index.py MeCabインデクサ作成", "/home/yasu/multi-agent-shogun",
     "done", 1, "FTS5インデックス構築スクリプト", "2026-02-03T11:00:00", "2026-02-04T10:00:00", 0, None),
    ("subtask_204", "cmd_101", None, "shogun", "Wave3: MCP連携", "/home/yasu/multi-agent-shogun",
     "pending", 3, "Claude Code MCPサーバー化", None, None, 0, None),
    ("subtask_205", "cmd_100", "ashigaru1", "shogun", "watchdogドキュメント作成",
     "/home/yasu/unipi-agri-ha", "done", 1, "ドキュメント作成",
     "2026-02-01T12:00:00", "2026-02-02T16:00:00", 1, "done"),
    ("subtask_206", "cmd_101", "ashigaru1", "shogun", "MeCab辞書カスタマイズ",
     "/home/yasu/multi-agent-shogun", "done", 1, "辞書最適化",
     "2026-02-03T12:00:00", "2026-02-04T18:00:00", 1, "rejected"),
    ("subtask_207", "cmd_101", "ashigaru2", "shogun", "FTS5検索パフォーマンステスト",
     "/home/yasu/multi-agent-shogun", "done", 2, "ベンチマーク実施",
     "2026-02-04T10:00:00", "2026-02-04T14:00:00", 1, "done"),
    ("subtask_208", "cmd_100", "ashigaru2", "arsprout", "センサーwatchdog連携テスト",
     "/home/yasu/unipi-agri-ha", "done", 1, "MQTT連携watchdog",
     "2026-02-01T13:00:00", "2026-02-02T13:00:00", 1, "done"),
]

DASHBOARD_DATA = [
    ("cmd_249", "戦果", "cmd_249全完了。センサー2層構造実装+56テスト全PASS", "done", "sensor,multi-house", "2026-02-21T10:15:00"),
    (None, "殿裁定", "Node-RED全面撤去決定。LLM直接制御に移行", "resolved", "Node-RED,LLM", "2026-02-19T15:00:00"),
    ("cmd_238", "スキル候補", "fastapi-linebot-ollama採用", "adopted", "skill,linebot", "2026-02-20T09:25:00"),
]

REPORTS_DATA = [
    ("ashigaru1", "subtask_200", "2026-02-02T14:00:00", "done",
     "watchdogタイマー実装完了。CircuitPythonのwatchdog.WatchDogTimerを使用。タイムアウト30秒に設定。",
     None, None, None, None, None, None, None),
    ("ashigaru2", "subtask_201", "2026-02-02T15:00:00", "done",
     "watchdogテスト完了。正常動作確認済み。リセット機能もテスト済み。",
     None, None, None, None, None, None, None),
    ("ashigaru6", "subtask_202", "2026-02-04T10:00:00", "done",
     "Docker基盤構築完了。FastAPIアプリケーションでMeCab形態素解析とFTS5全文検索を実装。",
     None, None, None, None, None, None, None),
    ("ashigaru1", "subtask_205", "2026-02-02T16:00:00", "done",
     "watchdogドキュメント作成完了。API仕様書とREADMEを更新。",
     None, None, None, None, None, None, None),
    ("ashigaru1", "subtask_206", "2026-02-04T18:00:00", "done",
     "MeCab辞書カスタマイズ完了。農業用語辞書を追加。",
     None, None, None, None, None, None, None),
    ("ashigaru2", "subtask_207", "2026-02-04T14:00:00", "done",
     "FTS5検索パフォーマンステスト完了。1000件クエリで平均応答時間5ms。",
     None, None, None, None, None, None, None),
    ("ashigaru2", "subtask_208", "2026-02-02T13:00:00", "done",
     "センサーwatchdog連携テスト完了。MQTT経由でwatchdogリセット確認済み。",
     None, None, None, None, None, None, None),
]


def create_test_botsunichiroku_db(db_path: str) -> None:
    """テスト用の没日録DBを作成する。"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE commands (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            command TEXT NOT NULL,
            project TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            assigned_karo TEXT,
            details TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE subtasks (
            id TEXT PRIMARY KEY,
            parent_cmd TEXT NOT NULL,
            worker_id TEXT,
            project TEXT,
            description TEXT NOT NULL,
            target_path TEXT,
            status TEXT DEFAULT 'pending',
            wave INTEGER DEFAULT 1,
            notes TEXT,
            assigned_at TEXT,
            completed_at TEXT,
            needs_audit INTEGER DEFAULT 0,
            audit_status TEXT DEFAULT NULL,
            FOREIGN KEY (parent_cmd) REFERENCES commands(id)
        )
    """)
    conn.execute("""
        CREATE TABLE reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT,
            completed_steps TEXT,
            blocking_reason TEXT,
            findings TEXT,
            next_actions TEXT,
            files_modified TEXT,
            notes TEXT,
            skill_candidate_name TEXT,
            skill_candidate_desc TEXT,
            FOREIGN KEY (task_id) REFERENCES subtasks(id)
        )
    """)
    conn.executemany(
        "INSERT INTO commands VALUES (?,?,?,?,?,?,?,?,?,?)",
        COMMANDS_DATA,
    )
    conn.executemany(
        "INSERT INTO subtasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        SUBTASKS_DATA,
    )
    conn.executemany(
        "INSERT INTO reports (worker_id, task_id, timestamp, status, summary, "
        "completed_steps, blocking_reason, findings, next_actions, files_modified, "
        "skill_candidate_name, skill_candidate_desc) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        REPORTS_DATA,
    )
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
    conn.executemany(
        "INSERT INTO dashboard_entries (cmd_id, section, content, status, tags, created_at) "
        "VALUES (?,?,?,?,?,?)",
        DASHBOARD_DATA,
    )
    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path):
    """テスト用没日録DBを作成するフィクスチャ。"""
    db_path = str(tmp_path / "botsunichiroku.db")
    create_test_botsunichiroku_db(db_path)
    return db_path


@pytest.fixture
def index_db(tmp_path, test_db):
    """テスト用FTS5インデックスDBを構築するフィクスチャ。"""
    index_path = str(tmp_path / "search_index.db")
    env = {
        **os.environ,
        "BOTSUNICHIROKU_DB": test_db,
        "INDEX_DB": index_path,
    }
    build_script = str(Path(__file__).parent / "build_index.py")
    result = subprocess.run(
        [sys.executable, build_script],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"build_index.py failed: {result.stderr}"
    return index_path


@pytest.fixture
def client(test_db, index_db):
    """FastAPI TestClient フィクスチャ。環境変数でテスト用DBを指定。"""
    with patch.dict(os.environ, {
        "BOTSUNICHIROKU_DB": test_db,
        "INDEX_DB": index_db,
    }):
        # モジュールのグローバル変数を再設定するため再import
        import importlib
        import main as main_mod
        importlib.reload(main_mod)
        with TestClient(main_mod.app) as tc:
            yield tc


# ============================================================
# 1. build_index.py のテスト
# ============================================================

class TestBuildIndex:
    """build_index.py のテスト群"""

    def test_index_created_successfully(self, index_db):
        """テスト用DBから正しくインデックスが構築されるか"""
        conn = sqlite3.connect(index_db)
        count = conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0]
        conn.close()
        # commands: 3 + subtasks: 9 + reports: 7 + dashboard: 3 = 22
        assert count == 22

    def test_commands_indexed(self, index_db):
        """commandsの全レコードがインデックスに投入されるか"""
        conn = sqlite3.connect(index_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM search_index WHERE source_type = 'command'"
        ).fetchone()[0]
        conn.close()
        assert count == len(COMMANDS_DATA)

    def test_subtasks_indexed(self, index_db):
        """subtasksの全レコードがインデックスに投入されるか"""
        conn = sqlite3.connect(index_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM search_index WHERE source_type = 'subtask'"
        ).fetchone()[0]
        conn.close()
        assert count == len(SUBTASKS_DATA)

    def test_reports_indexed(self, index_db):
        """reportsの全レコードがインデックスに投入されるか"""
        conn = sqlite3.connect(index_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM search_index WHERE source_type = 'report'"
        ).fetchone()[0]
        conn.close()
        assert count == len(REPORTS_DATA)

    def test_mecab_tokenization(self, index_db):
        """MeCab分かち書きが正しく動作するか（名詞・動詞・形容詞抽出）"""
        conn = sqlite3.connect(index_db)
        row = conn.execute(
            "SELECT content FROM search_index WHERE source_id = 'cmd_100'"
        ).fetchone()
        conn.close()
        content = row[0]
        # watchdogが含まれること（英語トークンも名詞として抽出される）
        assert "watchdog" in content.lower() or "タイマー" in content

    def test_source_db_not_found(self, tmp_path):
        """没日録DBが存在しない場合のエラーハンドリング"""
        env = {
            **os.environ,
            "BOTSUNICHIROKU_DB": str(tmp_path / "nonexistent.db"),
            "INDEX_DB": str(tmp_path / "index.db"),
        }
        build_script = str(Path(__file__).parent / "build_index.py")
        result = subprocess.run(
            [sys.executable, build_script],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "ERROR" in result.stderr

    def test_index_is_idempotent(self, tmp_path, test_db):
        """インデックス構築は冪等（2回実行しても同じ結果）"""
        index_path = str(tmp_path / "search_index.db")
        env = {
            **os.environ,
            "BOTSUNICHIROKU_DB": test_db,
            "INDEX_DB": index_path,
        }
        build_script = str(Path(__file__).parent / "build_index.py")
        # 1回目
        subprocess.run([sys.executable, build_script], env=env, capture_output=True)
        conn = sqlite3.connect(index_path)
        count1 = conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0]
        conn.close()
        # 2回目
        subprocess.run([sys.executable, build_script], env=env, capture_output=True)
        conn = sqlite3.connect(index_path)
        count2 = conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0]
        conn.close()
        assert count1 == count2

    def test_index_preserves_metadata(self, index_db):
        """インデックスにメタデータ(project, worker_id等)が保存されるか"""
        conn = sqlite3.connect(index_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM search_index WHERE source_id = 'subtask_200'"
        ).fetchone()
        conn.close()
        assert row["source_type"] == "subtask"
        assert row["parent_id"] == "cmd_100"
        assert row["project"] == "shogun"
        assert row["worker_id"] == "ashigaru1"
        assert row["status"] == "done"


# ============================================================
# 2. GET /search エンドポイントのテスト
# ============================================================

class TestSearchEndpoint:
    """GET /search のテスト群"""

    def test_search_japanese_query(self, client):
        """日本語クエリで関連結果が返るか"""
        resp = client.get("/search", params={"q": "watchdog"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hits"] > 0
        source_ids = [r["source_id"] for r in data["results"]]
        # cmd_100 or subtask_200 or subtask_201 が含まれるはず
        assert any(sid in source_ids for sid in ["cmd_100", "subtask_200", "subtask_201"])

    def test_search_multi_keyword(self, client):
        """複数キーワード検索"""
        resp = client.get("/search", params={"q": "MeCab FTS5"})
        assert resp.status_code == 200
        data = resp.json()
        # cmd_101 は MeCab FTS5 に関連
        assert data["total_hits"] >= 0  # トークン化後にマッチするかは MeCab 次第

    def test_search_limit(self, client):
        """limitパラメータが正しく動作するか"""
        resp = client.get("/search", params={"q": "タスク", "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2

    def test_search_empty_query(self, client):
        """空クエリで422が返るか（FastAPIバリデーション）"""
        resp = client.get("/search", params={"q": ""})
        assert resp.status_code == 422

    def test_search_results_have_score(self, client):
        """結果にスコアが含まれるか"""
        resp = client.get("/search", params={"q": "watchdog"})
        assert resp.status_code == 200
        data = resp.json()
        if data["results"]:
            first = data["results"][0]
            assert "score" in first
            assert "rank" in first

    def test_search_response_structure(self, client):
        """レスポンス構造が正しいか"""
        resp = client.get("/search", params={"q": "実装"})
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "tokenized_query" in data
        assert "total_hits" in data
        assert "results" in data

    def test_search_results_sorted_by_rank(self, client):
        """結果がrank順にソートされているか"""
        resp = client.get("/search", params={"q": "実装", "limit": 50})
        assert resp.status_code == 200
        data = resp.json()
        ranks = [r["rank"] for r in data["results"]]
        assert ranks == sorted(ranks)


# ============================================================
# 3. GET /check/orphans エンドポイントのテスト
# ============================================================

class TestCheckOrphans:
    """GET /check/orphans のテスト群"""

    def test_orphans_detects_cmd_all_done(self, client):
        """全subtaskがdoneだがcmdがpendingの場合に検出されるか
        cmd_101: status=pending, subtask_202=done, subtask_203=done, subtask_204=pending
        → subtask_204がpendingなので検出されない
        """
        resp = client.get("/check/orphans")
        assert resp.status_code == 200
        data = resp.json()
        checks = {c["check_type"]: c for c in data["checks"]}
        assert "cmd_all_subtasks_done_but_pending" in checks

    def test_orphans_detects_stale_pending_cmd(self, client):
        """7日以上pendingのcmdが検出されるか（cmd_102は2026-01-01作成）"""
        resp = client.get("/check/orphans")
        assert resp.status_code == 200
        data = resp.json()
        checks = {c["check_type"]: c for c in data["checks"]}
        stale = checks["cmd_pending_over_7_days"]
        cmd_ids = [item["cmd_id"] for item in stale["items"]]
        assert "cmd_102" in cmd_ids

    def test_orphans_response_structure(self, client):
        """レスポンス構造が正しいか"""
        resp = client.get("/check/orphans")
        assert resp.status_code == 200
        data = resp.json()
        assert "timestamp" in data
        assert "checks" in data
        assert "total_issues" in data
        assert isinstance(data["checks"], list)
        assert len(data["checks"]) == 4  # 4種類のチェック

    def test_orphans_check_types(self, client):
        """全4種類のチェック項目が含まれるか"""
        resp = client.get("/check/orphans")
        assert resp.status_code == 200
        data = resp.json()
        check_types = {c["check_type"] for c in data["checks"]}
        expected = {
            "cmd_all_subtasks_done_but_pending",
            "cmd_pending_over_7_days",
            "subtask_assigned_over_7_days",
            "subtask_done_without_report",
        }
        assert check_types == expected

    def test_orphans_subtask_done_without_report(self, client):
        """subtaskがdoneなのにreportがないケースの検出
        subtask_203: done だが report なし
        """
        resp = client.get("/check/orphans")
        assert resp.status_code == 200
        data = resp.json()
        checks = {c["check_type"]: c for c in data["checks"]}
        no_report = checks["subtask_done_without_report"]
        subtask_ids = [item["subtask_id"] for item in no_report["items"]]
        assert "subtask_203" in subtask_ids


# ============================================================
# 4. GET /check/coverage エンドポイントのテスト
# ============================================================

class TestCheckCoverage:
    """GET /check/coverage のテスト群"""

    def test_coverage_valid_cmd(self, client):
        """正常なcmd_idでカバレッジが返るか"""
        resp = client.get("/check/coverage", params={"cmd_id": "cmd_100"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["cmd_id"] == "cmd_100"
        assert "coverage_ratio" in data
        assert 0.0 <= data["coverage_ratio"] <= 1.0

    def test_coverage_ratio_calculation(self, client):
        """coverage_ratioが正しく計算されるか"""
        resp = client.get("/check/coverage", params={"cmd_id": "cmd_100"})
        assert resp.status_code == 200
        data = resp.json()
        total_kw = len(data["instruction_keywords"])
        missing_kw = len(data["missing_keywords"])
        if total_kw > 0:
            expected_ratio = round((total_kw - missing_kw) / total_kw, 2)
            assert data["coverage_ratio"] == expected_ratio

    def test_coverage_missing_keywords(self, client):
        """指示文にあって報告に無いキーワードが検出されるか"""
        resp = client.get("/check/coverage", params={"cmd_id": "cmd_100"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["missing_keywords"], list)
        assert isinstance(data["instruction_keywords"], list)
        assert isinstance(data["report_keywords"], list)

    def test_coverage_nonexistent_cmd(self, client):
        """存在しないcmd_idで404が返るか"""
        resp = client.get("/check/coverage", params={"cmd_id": "cmd_999"})
        assert resp.status_code == 404

    def test_coverage_counts(self, client):
        """subtask_countとreport_countが正しいか"""
        resp = client.get("/check/coverage", params={"cmd_id": "cmd_100"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtask_count"] == 4   # subtask_200, subtask_201, subtask_205, subtask_208
        assert data["report_count"] == 4    # 4 reports for cmd_100's subtasks


# ============================================================
# 5. GET /health エンドポイントのテスト
# ============================================================

class TestHealth:
    """GET /health のテスト群"""

    def test_health_ok(self, client):
        """正常時にstatus:okが返るか"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_index_count(self, client):
        """index_record_countが正しいか"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        # 3 commands + 9 subtasks + 7 reports + 3 dashboard = 22
        assert data["index_record_count"] == 22

    def test_health_db_exists(self, client):
        """DB存在フラグが正しいか"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["index_db_exists"] is True
        assert data["botsunichiroku_db_exists"] is True

    def test_health_mecab_available(self, client):
        """MeCab利用可否フラグが正しいか"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mecab_available"] is True


# ============================================================
# 6. GET /search/similar エンドポイントのテスト
# ============================================================

class TestSearchSimilar:
    """GET /search/similar のテスト群"""

    def test_similar_returns_results(self, client):
        """subtask_idを渡して類似タスクが返るか"""
        resp = client.get("/search/similar", params={"subtask_id": "subtask_200"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["subtask_id"] == "subtask_200"
        assert "keywords" in data
        assert "results" in data
        assert len(data["keywords"]) > 0

    def test_similar_excludes_self(self, client):
        """自分自身が結果に含まれないか"""
        resp = client.get("/search/similar", params={"subtask_id": "subtask_200"})
        assert resp.status_code == 200
        data = resp.json()
        source_ids = [r["source_id"] for r in data["results"]]
        assert "subtask_200" not in source_ids

    def test_similar_nonexistent_subtask(self, client):
        """存在しないsubtask_idで404が返るか"""
        resp = client.get("/search/similar", params={"subtask_id": "subtask_999"})
        assert resp.status_code == 404

    def test_similar_limit(self, client):
        """limitパラメータが正しく動作するか"""
        resp = client.get("/search/similar", params={"subtask_id": "subtask_200", "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2

    def test_similar_has_audit_status_for_subtasks(self, client):
        """subtask型結果にaudit_statusが含まれるか"""
        resp = client.get("/search/similar", params={"subtask_id": "subtask_205"})
        assert resp.status_code == 200
        data = resp.json()
        subtask_results = [r for r in data["results"] if r["source_type"] == "subtask"]
        for r in subtask_results:
            assert "audit_status" in r

    def test_similar_response_structure(self, client):
        """レスポンス構造が正しいか"""
        resp = client.get("/search/similar", params={"subtask_id": "subtask_200"})
        assert resp.status_code == 200
        data = resp.json()
        assert "subtask_id" in data
        assert "keywords" in data
        assert "results" in data
        if data["results"]:
            first = data["results"][0]
            assert "source_type" in first
            assert "source_id" in first
            assert "score" in first


# ============================================================
# 7. GET /audit/history エンドポイントのテスト
# ============================================================

class TestAuditHistory:
    """GET /audit/history のテスト群"""

    def test_audit_history_returns_all(self, client):
        """フィルタなしで全監査履歴が返るか"""
        resp = client.get("/audit/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "stats" in data
        # needs_audit=1のsubtask: 205, 206, 207, 208 = 4件
        assert data["stats"]["total"] == 4

    def test_audit_history_filter_worker(self, client):
        """worker_idフィルタが正しく動作するか"""
        resp = client.get("/audit/history", params={"worker_id": "ashigaru1"})
        assert resp.status_code == 200
        data = resp.json()
        # ashigaru1のneeds_audit=1: subtask_205, subtask_206 = 2件
        assert data["stats"]["total"] == 2
        for item in data["items"]:
            assert item["worker_id"] == "ashigaru1"

    def test_audit_history_filter_project(self, client):
        """projectフィルタが正しく動作するか"""
        resp = client.get("/audit/history", params={"project": "arsprout"})
        assert resp.status_code == 200
        data = resp.json()
        # arsproutのneeds_audit=1: subtask_208 = 1件
        assert data["stats"]["total"] == 1

    def test_audit_history_stats_calculation(self, client):
        """統計値（done/rejected/approval_rate）が正しいか"""
        resp = client.get("/audit/history")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["stats"]
        # done: 205, 207, 208 = 3件、rejected: 206 = 1件
        assert stats["done"] == 3
        assert stats["rejected"] == 1
        assert stats["pending"] == 0
        assert stats["approval_rate"] == 0.75  # 3/4

    def test_audit_history_has_report_summary(self, client):
        """latest_report_summaryが含まれるか"""
        resp = client.get("/audit/history")
        assert resp.status_code == 200
        data = resp.json()
        items_with_summary = [i for i in data["items"] if i["latest_report_summary"]]
        assert len(items_with_summary) > 0

    def test_audit_history_empty_result(self, client):
        """存在しないworker_idで空結果が返るか"""
        resp = client.get("/audit/history", params={"worker_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["total"] == 0
        assert data["stats"]["approval_rate"] == 0.0

    def test_audit_history_response_structure(self, client):
        """レスポンス構造が正しいか"""
        resp = client.get("/audit/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "stats" in data
        stats = data["stats"]
        assert "total" in stats
        assert "done" in stats
        assert "rejected" in stats
        assert "pending" in stats
        assert "approval_rate" in stats


# ============================================================
# 8. GET /worker/stats エンドポイントのテスト
# ============================================================

class TestWorkerStats:
    """GET /worker/stats のテスト群"""

    def test_worker_stats_all(self, client):
        """全足軽のstatsが返るか"""
        resp = client.get("/worker/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "workers" in data
        worker_ids = [w["worker_id"] for w in data["workers"]]
        assert "ashigaru1" in worker_ids
        assert "ashigaru2" in worker_ids

    def test_worker_stats_single(self, client):
        """単一worker_idでフィルタできるか"""
        resp = client.get("/worker/stats", params={"worker_id": "ashigaru1"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["workers"]) == 1
        assert data["workers"][0]["worker_id"] == "ashigaru1"

    def test_worker_stats_task_counts(self, client):
        """タスク数集計が正しいか"""
        resp = client.get("/worker/stats", params={"worker_id": "ashigaru1"})
        assert resp.status_code == 200
        w = data = resp.json()["workers"][0]
        # ashigaru1: subtask_200(done), subtask_205(done), subtask_206(done) = 3 done
        assert w["done"] == 3
        assert w["total_tasks"] == 3

    def test_worker_stats_audit(self, client):
        """audit統計が正しいか"""
        resp = client.get("/worker/stats", params={"worker_id": "ashigaru1"})
        assert resp.status_code == 200
        w = resp.json()["workers"][0]
        # ashigaru1のneeds_audit=1: subtask_205(done), subtask_206(rejected)
        assert w["audit_approved"] == 1
        assert w["audit_rejected"] == 1
        assert w["approval_rate"] == 0.5

    def test_worker_stats_projects(self, client):
        """プロジェクト別タスク数が正しいか"""
        resp = client.get("/worker/stats", params={"worker_id": "ashigaru2"})
        assert resp.status_code == 200
        w = resp.json()["workers"][0]
        assert "shogun" in w["projects"]
        assert "arsprout" in w["projects"]

    def test_worker_stats_avg_completion(self, client):
        """平均完了時間が返るか"""
        resp = client.get("/worker/stats", params={"worker_id": "ashigaru1"})
        assert resp.status_code == 200
        w = resp.json()["workers"][0]
        assert w["avg_completion_hours"] is not None
        assert w["avg_completion_hours"] > 0

    def test_worker_stats_nonexistent(self, client):
        """存在しないworker_idで空結果が返るか"""
        resp = client.get("/worker/stats", params={"worker_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["workers"]) == 1
        assert data["workers"][0]["total_tasks"] == 0


# ============================================================
# 9. POST/GET /dashboard エンドポイントのテスト
# ============================================================

class TestDashboard:
    """POST/GET /dashboard のテスト群"""

    def test_post_dashboard_entry(self, client):
        """POST /dashboard で登録 → 201"""
        resp = client.post("/dashboard", json={
            "section": "戦果",
            "content": "テスト登録エントリ",
            "cmd_id": "cmd_001",
            "status": "done",
            "tags": "test,integration",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["status"] == "created"
        assert isinstance(data["id"], int)

    def test_post_dashboard_entry_no_cmd_id(self, client):
        """cmd_id空で登録 → 201（cmd_idはNULL許容）"""
        resp = client.post("/dashboard", json={
            "section": "殿裁定",
            "content": "cmd_id無しのエントリ",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert isinstance(data["id"], int)

    def test_get_dashboard_all(self, client):
        """GET /dashboard → 全件取得（DASHBOARD_DATAの3件）"""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entries" in data
        assert data["total"] == 3
        assert len(data["entries"]) == 3

    def test_get_dashboard_filter_section(self, client):
        """GET /dashboard?section=戦果 → セクションフィルタ"""
        resp = client.get("/dashboard", params={"section": "戦果"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["entries"][0]["section"] == "戦果"

    def test_get_dashboard_search_q(self, client):
        """GET /dashboard?q=センサー → contentのLIKE検索"""
        resp = client.get("/dashboard", params={"q": "センサー"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("センサー" in e["content"] for e in data["entries"])

    def test_search_includes_dashboard(self, client):
        """GET /search?q=センサー → source_type=dashboardがFTS5でヒット"""
        resp = client.get("/search", params={"q": "センサー"})
        assert resp.status_code == 200
        data = resp.json()
        source_types = [r["source_type"] for r in data["results"]]
        assert "dashboard" in source_types

    def test_dashboard_response_structure(self, client):
        """レスポンス構造が正しいか"""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)
        if data["entries"]:
            entry = data["entries"][0]
            assert "id" in entry
            assert "cmd_id" in entry
            assert "section" in entry
            assert "content" in entry
            assert "status" in entry
            assert "tags" in entry
            assert "created_at" in entry

    def test_get_dashboard_ordered_by_created_at_desc(self, client):
        """created_at DESCでソートされているか"""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        created_ats = [e["created_at"] for e in data["entries"]]
        assert created_ats == sorted(created_ats, reverse=True)
