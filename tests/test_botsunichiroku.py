"""tests/test_botsunichiroku.py - botsunichiroku.py ユニットテスト

scripts/botsunichiroku.py (没日録CLI) の全サブコマンドを網羅テスト。
conftest.py の共通フィクスチャ (empty_db, seeded_db, seeded_db_path, tmp_db_path) を使用。
"""

import json
import sqlite3

import pytest

import botsunichiroku


# ---------------------------------------------------------------------------
# Fixtures (テストファイル固有)
# ---------------------------------------------------------------------------


@pytest.fixture
def cli(monkeypatch, seeded_db_path):
    """DB_PATH をテストデータ投入済み DB にパッチ。"""
    monkeypatch.setattr(botsunichiroku, "DB_PATH", seeded_db_path)
    return botsunichiroku


@pytest.fixture
def cli_empty(monkeypatch, empty_db, tmp_db_path):
    """DB_PATH をスキーマのみ（テストデータなし）DB にパッチ。"""
    monkeypatch.setattr(botsunichiroku, "DB_PATH", tmp_db_path)
    return botsunichiroku


def run_cli(argv, capsys):
    """argparse パース → 関数実行 → captured stdout/stderr を返す。"""
    parser = botsunichiroku.build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return capsys.readouterr()


# ===========================================================================
# cmd サブコマンド
# ===========================================================================


class TestCmdAdd:
    def test_basic(self, cli, capsys):
        """cmd add: 必須引数のみで新規コマンド作成"""
        out = run_cli(["cmd", "add", "テスト新規コマンド"], capsys)
        assert "Created: cmd_083" in out.out

    def test_all_options(self, cli, capsys):
        """cmd add: 全オプション指定"""
        out = run_cli([
            "cmd", "add", "全オプション付きコマンド",
            "--project", "shogun", "--priority", "high", "--karo", "roju",
        ], capsys)
        assert "Created: cmd_083" in out.out

    def test_counter_increment(self, cli, capsys):
        """cmd add: カウンタが連番インクリメントされること"""
        run_cli(["cmd", "add", "コマンド1"], capsys)
        out = run_cli(["cmd", "add", "コマンド2"], capsys)
        assert "Created: cmd_084" in out.out


class TestCmdList:
    def test_all(self, cli, capsys):
        """cmd list: 全件取得"""
        out = run_cli(["cmd", "list"], capsys)
        assert "cmd_001" in out.out
        assert "cmd_002" in out.out
        assert "cmd_003" in out.out

    def test_status_filter(self, cli, capsys):
        """cmd list: --status フィルタ"""
        out = run_cli(["cmd", "list", "--status", "done"], capsys)
        assert "cmd_001" in out.out
        assert "cmd_002" not in out.out

    def test_project_filter(self, cli, capsys):
        """cmd list: --project フィルタ"""
        out = run_cli(["cmd", "list", "--project", "arsprout"], capsys)
        assert "cmd_003" in out.out
        assert "cmd_001" not in out.out

    def test_json_output(self, cli, capsys):
        """cmd list: --json でJSON配列を出力"""
        out = run_cli(["cmd", "list", "--json"], capsys)
        data = json.loads(out.out)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_empty_result(self, cli_empty, capsys):
        """cmd list: コマンド0件"""
        out = run_cli(["cmd", "list"], capsys)
        assert "No commands found." in out.out


class TestCmdUpdate:
    def test_status_change(self, cli, capsys):
        """cmd update: ステータス変更"""
        out = run_cli(["cmd", "update", "cmd_003", "--status", "in_progress"], capsys)
        assert "Updated: cmd_003" in out.out
        assert "status=in_progress" in out.out

    def test_done_sets_completed_at(self, cli, capsys, seeded_db_path):
        """cmd update: done 時に completed_at が自動設定される"""
        run_cli(["cmd", "update", "cmd_003", "--status", "done"], capsys)
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT completed_at FROM commands WHERE id = 'cmd_003'").fetchone()
        conn.close()
        assert row["completed_at"] is not None

    def test_not_found(self, cli):
        """cmd update: 存在しない cmd_id で SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args(["cmd", "update", "cmd_999", "--status", "done"])
            args.func(args)


class TestCmdShow:
    def test_basic(self, cli, capsys):
        """cmd show: 正常表示（subtasks 含む）"""
        out = run_cli(["cmd", "show", "cmd_001"], capsys)
        assert "cmd_001" in out.out
        assert "テストコマンド1" in out.out
        assert "Subtasks (2)" in out.out

    def test_json_output(self, cli, capsys):
        """cmd show: --json で subtasks 配列を含む"""
        out = run_cli(["cmd", "show", "cmd_001", "--json"], capsys)
        data = json.loads(out.out)
        assert data["id"] == "cmd_001"
        assert "subtasks" in data
        assert len(data["subtasks"]) == 2

    def test_not_found(self, cli):
        """cmd show: 存在しない cmd_id で SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args(["cmd", "show", "cmd_999"])
            args.func(args)


# ===========================================================================
# subtask サブコマンド
# ===========================================================================


class TestSubtaskAdd:
    def test_basic(self, cli, capsys):
        """subtask add: 必須引数のみ（pending, worker なし）"""
        out = run_cli(["subtask", "add", "cmd_001", "テストサブタスク"], capsys)
        assert "Created: subtask_191" in out.out
        assert "parent=cmd_001" in out.out

    def test_all_options(self, cli, capsys, seeded_db_path):
        """subtask add: 全オプション指定で assigned 状態になる"""
        out = run_cli([
            "subtask", "add", "cmd_002", "全オプションサブタスク",
            "--worker", "ashigaru3", "--wave", "2",
            "--project", "shogun", "--target-path", "/tmp/test",
        ], capsys)
        assert "Created: subtask_191" in out.out
        assert "wave=2" in out.out
        # worker 指定時は assigned 状態かつ assigned_at が設定される
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status, assigned_at FROM subtasks WHERE id = 'subtask_191'").fetchone()
        conn.close()
        assert row["status"] == "assigned"
        assert row["assigned_at"] is not None

    def test_parent_not_found(self, cli):
        """subtask add: 存在しない親コマンドで SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args(["subtask", "add", "cmd_999", "desc"])
            args.func(args)


class TestSubtaskList:
    def test_all(self, cli, capsys):
        """subtask list: 全件取得"""
        out = run_cli(["subtask", "list"], capsys)
        assert "subtask_001" in out.out
        assert "subtask_004" in out.out

    def test_cmd_filter(self, cli, capsys):
        """subtask list: --cmd フィルタ"""
        out = run_cli(["subtask", "list", "--cmd", "cmd_001"], capsys)
        assert "subtask_001" in out.out
        assert "subtask_003" not in out.out

    def test_worker_filter(self, cli, capsys):
        """subtask list: --worker フィルタ"""
        out = run_cli(["subtask", "list", "--worker", "ashigaru6"], capsys)
        assert "subtask_003" in out.out
        assert "subtask_001" not in out.out

    def test_status_filter(self, cli, capsys):
        """subtask list: --status フィルタ"""
        out = run_cli(["subtask", "list", "--status", "pending"], capsys)
        assert "subtask_004" in out.out
        assert "subtask_001" not in out.out

    def test_json_output(self, cli, capsys):
        """subtask list: --json でJSON配列"""
        out = run_cli(["subtask", "list", "--json"], capsys)
        data = json.loads(out.out)
        assert isinstance(data, list)
        assert len(data) == 4


class TestSubtaskUpdate:
    def test_status_change(self, cli, capsys):
        """subtask update: ステータス変更"""
        out = run_cli(["subtask", "update", "subtask_004", "--status", "assigned"], capsys)
        assert "Updated: subtask_004" in out.out

    def test_with_worker(self, cli, capsys, seeded_db_path):
        """subtask update: --worker 指定でワーカー割当"""
        run_cli([
            "subtask", "update", "subtask_004",
            "--status", "assigned", "--worker", "ashigaru3",
        ], capsys)
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT worker_id, assigned_at FROM subtasks WHERE id = 'subtask_004'").fetchone()
        conn.close()
        assert row["worker_id"] == "ashigaru3"
        assert row["assigned_at"] is not None

    def test_done_sets_completed_at(self, cli, capsys, seeded_db_path):
        """subtask update: done 時に completed_at 自動設定"""
        run_cli(["subtask", "update", "subtask_003", "--status", "done"], capsys)
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT completed_at FROM subtasks WHERE id = 'subtask_003'").fetchone()
        conn.close()
        assert row["completed_at"] is not None

    def test_not_found(self, cli):
        """subtask update: 存在しない subtask_id で SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args(["subtask", "update", "subtask_999", "--status", "done"])
            args.func(args)


class TestSubtaskShow:
    def test_basic(self, cli, capsys):
        """subtask show: 正常表示"""
        out = run_cli(["subtask", "show", "subtask_003"], capsys)
        assert "subtask_003" in out.out
        assert "サブタスク3" in out.out
        assert "ashigaru6" in out.out

    def test_json_output(self, cli, capsys):
        """subtask show: --json 出力"""
        out = run_cli(["subtask", "show", "subtask_003", "--json"], capsys)
        data = json.loads(out.out)
        assert data["id"] == "subtask_003"
        assert data["worker_id"] == "ashigaru6"
        assert data["project"] == "rotation-planner"

    def test_not_found(self, cli):
        """subtask show: 存在しない subtask_id で SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args(["subtask", "show", "subtask_999"])
            args.func(args)


# ===========================================================================
# report サブコマンド
# ===========================================================================


class TestReportAdd:
    def test_basic(self, cli, capsys):
        """report add: 必須引数のみ"""
        out = run_cli([
            "report", "add", "subtask_001", "ashigaru1",
            "--status", "done", "--summary", "テスト完了",
        ], capsys)
        assert "Created: report #" in out.out

    def test_with_json_fields(self, cli, capsys, seeded_db_path):
        """report add: --findings --files-modified --skill-name --skill-desc"""
        run_cli([
            "report", "add", "subtask_002", "ashigaru2",
            "--status", "done", "--summary", "全項目テスト完了",
            "--findings", '["発見1", "発見2"]',
            "--files-modified", '["file1.py", "file2.py"]',
            "--skill-name", "test-skill",
            "--skill-desc", "テストスキル説明",
        ], capsys)
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT findings, files_modified, skill_candidate_name FROM reports WHERE worker_id = 'ashigaru2'"
        ).fetchone()
        conn.close()
        assert "発見1" in row["findings"]
        assert row["skill_candidate_name"] == "test-skill"

    def test_subtask_not_found(self, cli):
        """report add: 存在しない subtask_id で SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args([
                "report", "add", "subtask_999", "ashigaru1",
                "--status", "done", "--summary", "test",
            ])
            args.func(args)


class TestReportList:
    def test_all(self, cli, capsys):
        """report list: 全件取得"""
        out = run_cli(["report", "list"], capsys)
        assert "subtask_001" in out.out

    def test_subtask_filter(self, cli, capsys):
        """report list: --subtask フィルタ"""
        out = run_cli(["report", "list", "--subtask", "subtask_001"], capsys)
        assert "subtask_001" in out.out

    def test_worker_filter(self, cli, capsys):
        """report list: --worker フィルタ"""
        out = run_cli(["report", "list", "--worker", "ashigaru1"], capsys)
        assert "ashigaru1" in out.out

    def test_json_output(self, cli, capsys):
        """report list: --json 出力"""
        out = run_cli(["report", "list", "--json"], capsys)
        data = json.loads(out.out)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_empty_result(self, cli, capsys):
        """report list: 結果0件"""
        out = run_cli(["report", "list", "--worker", "nobody"], capsys)
        assert "No reports found." in out.out


# ===========================================================================
# agent サブコマンド
# ===========================================================================


class TestAgentList:
    def test_all(self, cli, capsys):
        """agent list: 全件取得（12エージェント）"""
        out = run_cli(["agent", "list"], capsys)
        assert "shogun" in out.out
        assert "ashigaru1" in out.out
        assert "ohariko" in out.out

    def test_role_filter(self, cli, capsys):
        """agent list: --role フィルタ"""
        out = run_cli(["agent", "list", "--role", "karo"], capsys)
        assert "roju" in out.out
        # karo ロールのみ表示（ashigaru は非表示）
        assert "ashigaru1" not in out.out

    def test_json_output(self, cli, capsys):
        """agent list: --json でJSON配列"""
        out = run_cli(["agent", "list", "--json"], capsys)
        data = json.loads(out.out)
        assert isinstance(data, list)
        assert len(data) == 12


class TestAgentUpdate:
    def test_status_change(self, cli, capsys):
        """agent update: ステータス変更"""
        out = run_cli(["agent", "update", "ashigaru1", "--status", "busy"], capsys)
        assert "Updated: ashigaru1" in out.out

    def test_with_task(self, cli, capsys, seeded_db_path):
        """agent update: --task でタスクID設定"""
        run_cli(["agent", "update", "ashigaru1", "--status", "busy", "--task", "subtask_001"], capsys)
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT current_task_id FROM agents WHERE id = 'ashigaru1'").fetchone()
        conn.close()
        assert row["current_task_id"] == "subtask_001"

    def test_clear_task(self, cli, capsys, seeded_db_path):
        """agent update: --task none でタスクIDクリア"""
        # まず設定
        run_cli(["agent", "update", "ashigaru1", "--status", "busy", "--task", "subtask_001"], capsys)
        # クリア
        run_cli(["agent", "update", "ashigaru1", "--status", "idle", "--task", "none"], capsys)
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT current_task_id FROM agents WHERE id = 'ashigaru1'").fetchone()
        conn.close()
        assert row["current_task_id"] is None

    def test_not_found(self, cli):
        """agent update: 存在しない agent_id で SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args(["agent", "update", "nobody", "--status", "idle"])
            args.func(args)


# ===========================================================================
# counter サブコマンド
# ===========================================================================


class TestCounterNext:
    def test_cmd_id(self, cli, capsys):
        """counter next: cmd_id インクリメント（82→83）"""
        out = run_cli(["counter", "next", "cmd_id"], capsys)
        assert "cmd_083" in out.out

    def test_subtask_id(self, cli, capsys):
        """counter next: subtask_id インクリメント（190→191）"""
        out = run_cli(["counter", "next", "subtask_id"], capsys)
        assert "subtask_191" in out.out

    def test_not_found(self, cli):
        """counter next: 存在しないカウンタで SystemExit"""
        with pytest.raises(SystemExit):
            parser = botsunichiroku.build_parser()
            args = parser.parse_args(["counter", "next", "nonexistent"])
            args.func(args)


class TestCounterShow:
    def test_basic(self, cli, capsys):
        """counter show: テーブル出力"""
        out = run_cli(["counter", "show"], capsys)
        assert "cmd_id" in out.out
        assert "subtask_id" in out.out

    def test_json_output(self, cli, capsys):
        """counter show: --json 出力"""
        out = run_cli(["counter", "show", "--json"], capsys)
        data = json.loads(out.out)
        assert isinstance(data, list)
        names = {item["name"] for item in data}
        assert "cmd_id" in names
        assert "subtask_id" in names


# ===========================================================================
# stats サブコマンド
# ===========================================================================


class TestStats:
    def test_text_output(self, cli, capsys):
        """stats: テキスト出力"""
        out = run_cli(["stats"], capsys)
        assert "没日録" in out.out
        assert "コマンド" in out.out
        assert "サブタスク" in out.out

    def test_json_output(self, cli, capsys):
        """stats: --json で構造化データ"""
        out = run_cli(["stats", "--json"], capsys)
        data = json.loads(out.out)
        assert data["commands"]["total"] == 3
        assert data["subtasks"]["total"] == 4
        assert "agents" in data
        assert "by_project" in data
        assert "by_karo" in data


# ===========================================================================
# archive サブコマンド
# ===========================================================================


class TestArchive:
    def test_dry_run(self, cli, capsys):
        """archive: --dry-run でアーカイブ対象確認（変更なし）"""
        out = run_cli(["archive", "--days", "0", "--dry-run"], capsys)
        assert "dry-run" in out.out
        assert "cmd_001" in out.out

    def test_execute(self, cli, capsys, seeded_db_path):
        """archive: 実行で done→archived に変更"""
        run_cli(["archive", "--days", "0"], capsys)
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        cmd = conn.execute("SELECT status FROM commands WHERE id = 'cmd_001'").fetchone()
        sub = conn.execute("SELECT status FROM subtasks WHERE id = 'subtask_001'").fetchone()
        conn.close()
        assert cmd["status"] == "archived"
        assert sub["status"] == "archived"

    def test_no_targets(self, cli_empty, capsys):
        """archive: アーカイブ対象0件"""
        out = run_cli(["archive", "--days", "7"], capsys)
        assert "0件" in out.out


# ===========================================================================
# ヘルパー関数テスト
# ===========================================================================


class TestHelpers:
    def test_now_iso(self):
        """now_iso: ISO 8601形式の文字列"""
        ts = botsunichiroku.now_iso()
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_row_to_dict(self, seeded_db_path):
        """row_to_dict: sqlite3.Row → dict 変換"""
        conn = sqlite3.connect(str(seeded_db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM commands WHERE id = 'cmd_001'").fetchone()
        conn.close()
        d = botsunichiroku.row_to_dict(row)
        assert isinstance(d, dict)
        assert d["id"] == "cmd_001"

    def test_print_table(self, capsys):
        """print_table: ヘッダー + データ行を出力"""
        botsunichiroku.print_table(["COL_A", "COL_B"], [["val1", "val2"]])
        out = capsys.readouterr()
        assert "COL_A" in out.out
        assert "val1" in out.out

    def test_print_table_auto_width(self, capsys):
        """print_table: widths 省略時は自動計算"""
        botsunichiroku.print_table(["X", "Y"], [["long_value_here", "short"]])
        out = capsys.readouterr()
        assert "long_value_here" in out.out

    def test_build_parser_cmd(self):
        """build_parser: cmd list パース"""
        parser = botsunichiroku.build_parser()
        args = parser.parse_args(["cmd", "list", "--status", "done", "--json"])
        assert args.entity == "cmd"
        assert args.action == "list"
        assert args.status == "done"
        assert args.json is True

    def test_build_parser_subtask(self):
        """build_parser: subtask add パース"""
        parser = botsunichiroku.build_parser()
        args = parser.parse_args([
            "subtask", "add", "cmd_001", "desc",
            "--worker", "ashigaru1", "--wave", "2",
        ])
        assert args.entity == "subtask"
        assert args.cmd_id == "cmd_001"
        assert args.worker == "ashigaru1"
        assert args.wave == 2

    def test_get_connection_missing_db(self, monkeypatch, tmp_path):
        """get_connection: DB ファイルが存在しない場合 SystemExit"""
        monkeypatch.setattr(botsunichiroku, "DB_PATH", tmp_path / "nonexistent.db")
        with pytest.raises(SystemExit):
            botsunichiroku.get_connection()
