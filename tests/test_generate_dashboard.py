"""tests/test_generate_dashboard.py - generate_dashboard.py のユニットテスト"""

import sys

import pytest

import generate_dashboard as gd


# ============================================================
# ローカルフィクスチャ
# ============================================================


@pytest.fixture
def skills_dir(tmp_path):
    """一時スキルディレクトリを作成"""
    d = tmp_path / "skills"
    d.mkdir()
    return d


@pytest.fixture
def patch_skills_dir(monkeypatch, skills_dir):
    """SKILLS_DIR をテスト用ディレクトリに差し替え"""
    monkeypatch.setattr(gd, "SKILLS_DIR", skills_dir)
    return skills_dir


# ============================================================
# get_action_required
# ============================================================


class TestGetActionRequired:
    def test_empty_db(self, empty_db):
        result = gd.get_action_required(empty_db)
        assert result == []

    def test_seeded_no_critical_high(self, seeded_db):
        """seeded_dbにはcritical/highの未完了cmdがない"""
        result = gd.get_action_required(seeded_db)
        assert result == []

    def test_with_critical_cmd(self, seeded_db):
        """critical pendingコマンドが取得される"""
        seeded_db.execute(
            """INSERT INTO commands
               (id, timestamp, command, project, priority, status, assigned_karo, created_at)
               VALUES ('cmd_100', '2026-02-01T00:00:00', 'Critical task', 'shogun',
                       'critical', 'pending', 'roju', '2026-02-01T00:00:00')"""
        )
        seeded_db.commit()
        result = gd.get_action_required(seeded_db)
        assert len(result) == 1
        assert result[0]["id"] == "cmd_100"
        assert result[0]["priority"] == "critical"

    def test_priority_ordering(self, seeded_db):
        """criticalがhighより先に返る"""
        seeded_db.execute(
            """INSERT INTO commands
               (id, timestamp, command, project, priority, status, assigned_karo, created_at)
               VALUES ('cmd_100', '2026-02-01T00:00:00', 'High task', 'shogun',
                       'high', 'pending', 'roju', '2026-02-01T00:00:00')"""
        )
        seeded_db.execute(
            """INSERT INTO commands
               (id, timestamp, command, project, priority, status, assigned_karo, created_at)
               VALUES ('cmd_101', '2026-02-01T00:00:00', 'Critical task', 'shogun',
                       'critical', 'in_progress', 'roju', '2026-02-01T00:00:00')"""
        )
        seeded_db.commit()
        result = gd.get_action_required(seeded_db)
        assert len(result) == 2
        assert result[0]["priority"] == "critical"
        assert result[1]["priority"] == "high"


# ============================================================
# get_skill_candidates
# ============================================================


class TestGetSkillCandidates:
    def test_empty(self, seeded_db):
        """seeded_dbのレポートにスキル候補がない"""
        result = gd.get_skill_candidates(seeded_db)
        assert result == []

    def test_with_candidate(self, seeded_db):
        """スキル候補付きレポートを取得"""
        seeded_db.execute(
            """UPDATE reports
               SET skill_candidate_name='test-skill',
                   skill_candidate_desc='A useful skill'
               WHERE task_id='subtask_001'"""
        )
        seeded_db.commit()
        result = gd.get_skill_candidates(seeded_db)
        assert len(result) == 1
        assert result[0]["name"] == "test-skill"
        assert result[0]["description"] == "A useful skill"
        assert result[0]["cmd"] == "cmd_001"


# ============================================================
# get_in_progress_cmds
# ============================================================


class TestGetInProgressCmds:
    def test_empty_db(self, empty_db):
        result = gd.get_in_progress_cmds(empty_db)
        assert result == []

    def test_seeded_subtask_counts(self, seeded_db):
        """cmd_002のサブタスク集計が正しい（total=2, done=0, active=1）"""
        result = gd.get_in_progress_cmds(seeded_db)
        assert len(result) == 1
        cmd = result[0]
        assert cmd["id"] == "cmd_002"
        assert cmd["subtask_total"] == 2
        assert cmd["subtask_done"] == 0
        # active = assigned + in_progress のみ（pendingは含まない）
        assert cmd["subtask_active"] == 1


# ============================================================
# get_recent_done_cmds
# ============================================================


class TestGetRecentDoneCmds:
    def test_empty_db(self, empty_db):
        result = gd.get_recent_done_cmds(empty_db)
        assert result == []

    def test_seeded(self, seeded_db):
        """cmd_001（done）が取得される"""
        result = gd.get_recent_done_cmds(seeded_db)
        assert len(result) == 1
        assert result[0]["id"] == "cmd_001"
        assert result[0]["completed_at"] is not None

    def test_limit_restricts_results(self, seeded_db):
        """limit=0で空を返す"""
        result = gd.get_recent_done_cmds(seeded_db, limit=0)
        assert result == []

    def test_ordering_by_completed_at(self, seeded_db):
        """completed_at降順でソート"""
        seeded_db.execute(
            """INSERT INTO commands
               (id, timestamp, command, project, priority, status, assigned_karo,
                created_at, completed_at)
               VALUES ('cmd_100', '2026-02-01T00:00:00', 'Newer done', 'shogun',
                       'low', 'done', 'roju',
                       '2026-02-01T00:00:00', '2026-02-01T12:00:00')"""
        )
        seeded_db.commit()
        result = gd.get_recent_done_cmds(seeded_db, limit=10)
        assert len(result) == 2
        assert result[0]["id"] == "cmd_100"  # newer first
        assert result[1]["id"] == "cmd_001"


# ============================================================
# _extract_skill_overview
# ============================================================


class TestExtractSkillOverview:
    def test_overview_section(self, tmp_path):
        """## Overview セクションから1行目を抽出"""
        f = tmp_path / "skill.md"
        f.write_text("# Skill\n\n## Overview\n\nThis is great.\nSecond.\n\n## Usage\n")
        assert gd._extract_skill_overview(f) == "This is great."

    def test_h1_fallback(self, tmp_path):
        """Overviewなし → H1タイトルにフォールバック"""
        f = tmp_path / "skill.md"
        f.write_text("# My Cool Skill - A description\n\nBody text.")
        assert gd._extract_skill_overview(f) == "My Cool Skill"

    def test_truncates_at_80(self, tmp_path):
        """80文字で切り詰め"""
        f = tmp_path / "skill.md"
        long = "A" * 100
        f.write_text(f"# T\n\n## Overview\n\n{long}\n")
        assert len(gd._extract_skill_overview(f)) == 80

    def test_skips_core_capability_line(self, tmp_path):
        """**Core Capability 行をスキップして次の行を使う"""
        f = tmp_path / "skill.md"
        f.write_text("# T\n\n## Overview\n\n**Core Capability**: foo\nActual.\n")
        assert gd._extract_skill_overview(f) == "Actual."

    def test_file_not_readable(self, tmp_path):
        """存在しないファイル → 空文字列"""
        assert gd._extract_skill_overview(tmp_path / "nonexistent.md") == ""


# ============================================================
# get_skills_from_filesystem
# ============================================================


class TestGetSkillsFromFilesystem:
    def test_no_directory(self, monkeypatch, tmp_path):
        """ディレクトリ不在で空リスト"""
        monkeypatch.setattr(gd, "SKILLS_DIR", tmp_path / "nonexistent")
        assert gd.get_skills_from_filesystem() == []

    def test_with_md_files(self, patch_skills_dir):
        """スキルファイルをname順に取得"""
        (patch_skills_dir / "alpha.md").write_text("# Alpha Skill\n\nBody.")
        (patch_skills_dir / "beta.md").write_text("# B\n\n## Overview\n\nBeta overview.\n")
        result = gd.get_skills_from_filesystem()
        assert len(result) == 2
        assert result[0]["name"] == "alpha"
        assert result[1]["name"] == "beta"
        assert result[1]["overview"] == "Beta overview."

    def test_ignores_non_md(self, patch_skills_dir):
        """.md以外のファイルは無視"""
        (patch_skills_dir / "skill.md").write_text("# Skill\n")
        (patch_skills_dir / "notes.txt").write_text("not a skill")
        (patch_skills_dir / "data.json").write_text("{}")
        assert len(gd.get_skills_from_filesystem()) == 1


# ============================================================
# generate_dashboard（統合テスト）
# ============================================================


class TestGenerateDashboard:
    def test_all_sections_present(self, seeded_db, patch_skills_dir):
        """全セクション見出しが含まれる"""
        content = gd.generate_dashboard(seeded_db)
        expected = [
            "📊 戦況報告",
            "📜 殿の方針",
            "🚨 要対応",
            "🔄 進行中",
            "✅ 本日の戦果",
            "🎯 スキル化候補",
            "🛠️ 生成されたスキル",
            "⏸️ 待機中",
            "❓ 伺い事項",
        ]
        for section in expected:
            assert section in content, f"Missing section: {section}"

    def test_has_timestamp(self, seeded_db, patch_skills_dir):
        """最終更新タイムスタンプが含まれる"""
        content = gd.generate_dashboard(seeded_db)
        assert "最終更新:" in content

    def test_ends_with_newline(self, seeded_db, patch_skills_dir):
        """末尾が改行で終わる"""
        content = gd.generate_dashboard(seeded_db)
        assert content.endswith("\n")


# ============================================================
# _render_action_required
# ============================================================


class TestRenderActionRequired:
    def test_security_warning_always_present(self, seeded_db, patch_skills_dir):
        """セキュリティ警告は常に表示"""
        content = gd._render_action_required(seeded_db)
        assert "セキュリティ" in content
        assert "PrivateKey" in content

    def test_no_unapproved_shows_none_message(self, seeded_db, patch_skills_dir):
        """未承認スキルなし → 「なし」メッセージ"""
        content = gd._render_action_required(seeded_db)
        assert "なし（スキル化候補は全件対応済み）" in content

    def test_unapproved_skill_listed(self, seeded_db, patch_skills_dir):
        """未承認スキルがテーブル表示される"""
        seeded_db.execute(
            """UPDATE reports
               SET skill_candidate_name='new-skill',
                   skill_candidate_desc='Desc'
               WHERE task_id='subtask_001'"""
        )
        seeded_db.commit()
        content = gd._render_action_required(seeded_db)
        assert "new-skill" in content
        assert "承認待ち" in content


# ============================================================
# _render_in_progress
# ============================================================


class TestRenderInProgress:
    def test_empty_shows_none(self, empty_db):
        content = gd._render_in_progress(empty_db)
        assert "なし" in content

    def test_shows_cmd_and_subtasks(self, seeded_db):
        """cmd_002とサブタスク詳細が表示"""
        content = gd._render_in_progress(seeded_db)
        assert "cmd_002" in content
        assert "テストコマンド2" in content
        assert "rotation-planner" in content
        assert "subtask_003" in content


# ============================================================
# _render_recent_done
# ============================================================


class TestRenderRecentDone:
    def test_empty_shows_placeholder(self, empty_db):
        content = gd._render_recent_done(empty_db)
        assert "なし" in content

    def test_time_formatting(self, seeded_db):
        """completed_atからHH:MMを抽出"""
        content = gd._render_recent_done(seeded_db)
        assert "cmd_001" in content
        assert "01:00" in content

    def test_none_completed_at(self, seeded_db):
        """completed_at=Noneでもエラーにならない"""
        seeded_db.execute(
            """INSERT INTO commands
               (id, timestamp, command, project, priority, status, assigned_karo,
                created_at, completed_at)
               VALUES ('cmd_100', '2026-02-01T00:00:00', 'No time', 'shogun',
                       'low', 'done', 'roju', '2026-02-01T00:00:00', NULL)"""
        )
        seeded_db.commit()
        content = gd._render_recent_done(seeded_db)
        assert "cmd_100" in content
        assert "No time" in content


# ============================================================
# _render_skill_candidates
# ============================================================


class TestRenderSkillCandidates:
    def test_all_approved(self, seeded_db, patch_skills_dir):
        """候補なし → 全件スキル化完了メッセージ"""
        content = gd._render_skill_candidates(seeded_db)
        assert "全件スキル化完了" in content

    def test_unapproved_shown(self, seeded_db, patch_skills_dir):
        """未承認スキルをテーブル表示"""
        seeded_db.execute(
            """UPDATE reports
               SET skill_candidate_name='pending-skill',
                   skill_candidate_desc='Needs approval'
               WHERE task_id='subtask_001'"""
        )
        seeded_db.commit()
        content = gd._render_skill_candidates(seeded_db)
        assert "pending-skill" in content
        assert "Needs approval" in content


# ============================================================
# _render_skills_list
# ============================================================


class TestRenderSkillsList:
    def test_empty_dir(self, patch_skills_dir):
        content = gd._render_skills_list()
        assert "計0件" in content
        assert "なし" in content

    def test_with_skills(self, patch_skills_dir):
        (patch_skills_dir / "my-skill.md").write_text("# My Skill\n\nBody.")
        content = gd._render_skills_list()
        assert "計1件" in content
        assert "my-skill" in content
        assert "My Skill" in content


# ============================================================
# main（CLI）
# ============================================================


class TestMain:
    def test_dry_run(self, monkeypatch, seeded_db_path, tmp_path, capsys):
        """--dry-runでstdoutに出力、ファイル書き込みなし"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        output = tmp_path / "dashboard.md"
        monkeypatch.setattr(gd, "DB_PATH", seeded_db_path)
        monkeypatch.setattr(gd, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(gd, "DASHBOARD_PATH", output)
        monkeypatch.setattr(sys, "argv", ["generate_dashboard.py", "--dry-run"])
        gd.main()
        captured = capsys.readouterr()
        assert "📊 戦況報告" in captured.out
        assert not output.exists()

    def test_output_file(self, monkeypatch, seeded_db_path, tmp_path):
        """--outputでファイルに書き込み"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        output = tmp_path / "test_dashboard.md"
        monkeypatch.setattr(gd, "DB_PATH", seeded_db_path)
        monkeypatch.setattr(gd, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(sys, "argv",
                            ["generate_dashboard.py", "--output", str(output)])
        gd.main()
        assert output.exists()
        content = output.read_text()
        assert "📊 戦況報告" in content
