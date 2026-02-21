"""勘定吟味役テスト — Ollama/高札API/DB全てモック"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tools.kanjou.schemas import (
    AutoJudgment,
    ChecklistCheckResult,
    FormatCheckResult,
    FormatIssue,
    IssueSeverity,
    OharikoAuditIssue,
    OharikoAuditResult,
    OharikoMetaAuditReport,
    PreAuditReport,
    PreVerdict,
    RejectionPattern,
    Recommendation,
    Severity,
    SkillCandidateEvaluation,
    SkillScores,
)
from tools.kanjou.kanjou_ginmiyaku import (
    _check_commit_prefix,
    _check_markdown_headings,
    _check_required_fields,
    _check_skill_candidate,
    _extract_json,
    check_findings_prefixes,
    check_findings_specificity,
    check_result_findings_consistency,
    determine_pre_verdict,
    load_ohariko_reports,
    rule_based_format_check,
    run_ohariko_audit,
)
from tools.kanjou.tools import DBQueryTool, FileReadTool, KousatsuAPITool


# ============================================================
# Schema Tests
# ============================================================

class TestFormatIssue:
    def test_valid(self):
        issue = FormatIssue(field="status", problem="missing", severity=IssueSeverity.error)
        assert issue.field == "status"
        assert issue.severity == IssueSeverity.error

    def test_invalid_severity(self):
        with pytest.raises(ValueError):
            FormatIssue(field="x", problem="y", severity="critical")


class TestFormatCheckResult:
    def test_default_ok(self):
        result = FormatCheckResult()
        assert result.severity == Severity.ok
        assert result.issues == []

    def test_with_issues(self):
        result = FormatCheckResult(
            issues=[FormatIssue(field="a", problem="b", severity=IssueSeverity.warn)],
            severity=Severity.warn,
        )
        assert len(result.issues) == 1


class TestChecklistCheckResult:
    def test_valid_coverage(self):
        r = ChecklistCheckResult(coverage_ratio=0.85, uncovered_items=["item_a"])
        assert r.coverage_ratio == 0.85

    def test_coverage_bounds(self):
        with pytest.raises(ValueError):
            ChecklistCheckResult(coverage_ratio=1.5)
        with pytest.raises(ValueError):
            ChecklistCheckResult(coverage_ratio=-0.1)


class TestSkillCandidateEvaluation:
    def test_valid(self):
        e = SkillCandidateEvaluation(
            skill_name="docker-pytest-runner",
            proposed_by="ashigaru1 subtask_100",
            scores=SkillScores(
                reusability=3, complexity=2, generality=3,
                independence=2, pattern_stability=2,
            ),
            total_score=12,
            auto_judgment=AutoJudgment.auto_recommend,
            rejection_pattern=RejectionPattern.none,
            recommendation=Recommendation.adopt,
            rationale="High reuse, cross-project",
        )
        assert e.total_score == 12
        assert e.auto_judgment == AutoJudgment.auto_recommend

    def test_score_bounds(self):
        with pytest.raises(ValueError):
            SkillScores(
                reusability=4, complexity=0, generality=0,
                independence=0, pattern_stability=0,
            )


class TestPreAuditReport:
    def test_minimal(self):
        r = PreAuditReport(
            subtask_id="subtask_100",
            format_check=FormatCheckResult(),
            checklist_check=ChecklistCheckResult(),
            pre_verdict=PreVerdict.likely_approved,
        )
        assert r.subtask_id == "subtask_100"
        assert r.kousatsu_ok is False
        assert r.skill_evaluation is None

    def test_json_roundtrip(self):
        r = PreAuditReport(
            subtask_id="subtask_200",
            kousatsu_ok=True,
            format_check=FormatCheckResult(
                issues=[FormatIssue(field="x", problem="y", severity=IssueSeverity.warn)],
                severity=Severity.warn,
            ),
            checklist_check=ChecklistCheckResult(coverage_ratio=0.9),
            pre_verdict=PreVerdict.needs_review,
        )
        j = r.model_dump_json()
        r2 = PreAuditReport.model_validate_json(j)
        assert r2.subtask_id == "subtask_200"
        assert r2.format_check.severity == Severity.warn


# ============================================================
# Rule-Based Format Check Tests
# ============================================================

class TestRequiredFields:
    def test_all_present(self):
        text = """
subtask_id: subtask_100
cmd_id: cmd_50
worker: ashigaru1
status: done
summary: completed task
skill_candidate: none
"""
        issues = _check_required_fields(text)
        assert len(issues) == 0

    def test_missing_fields(self):
        text = "subtask_id: subtask_100\nworker: ashigaru1\n"
        issues = _check_required_fields(text)
        missing = {i.field for i in issues}
        assert "cmd_id" in missing
        assert "status" in missing
        assert "summary" in missing
        assert "skill_candidate" in missing


class TestMarkdownHeadings:
    def test_good_headings(self):
        md = "# Title\n## Section\n### Subsection\n"
        issues = _check_markdown_headings(md)
        assert len(issues) == 0

    def test_heading_jump(self):
        md = "# Title\n### Jump\n"
        issues = _check_markdown_headings(md)
        assert len(issues) == 1
        assert "jump" in issues[0].problem.lower()


class TestCommitPrefix:
    def test_valid_prefixes(self):
        for prefix in ["feat:", "fix:", "docs:", "refactor:", "test:"]:
            assert len(_check_commit_prefix(f"{prefix} something")) == 0

    def test_invalid_prefix(self):
        issues = _check_commit_prefix("added new feature")
        assert len(issues) == 1

    def test_empty(self):
        assert len(_check_commit_prefix("")) == 0


class TestSkillCandidateCheck:
    def test_present(self):
        assert len(_check_skill_candidate("skill_candidate: none")) == 0

    def test_missing(self):
        assert len(_check_skill_candidate("no skill here")) == 1


class TestRuleBasedFormatCheck:
    def test_full_report_ok(self):
        text = """subtask_id: subtask_100
cmd_id: cmd_50
worker: ashigaru1
status: done
summary: completed
skill_candidate: docker-pytest-runner
"""
        result = rule_based_format_check(text)
        assert result.severity == Severity.ok

    def test_missing_fields_error(self):
        result = rule_based_format_check("nothing here")
        assert result.severity == Severity.error

    def test_with_markdown_files(self):
        result = rule_based_format_check(
            "subtask_id: x\ncmd_id: y\nworker: z\nstatus: done\nsummary: ok\nskill_candidate: n",
            files_content={"doc.md": "# Title\n### Bad Jump\n"},
        )
        assert result.severity == Severity.warn

    def test_with_bad_commit(self):
        result = rule_based_format_check(
            "subtask_id: x\ncmd_id: y\nworker: z\nstatus: done\nsummary: ok\nskill_candidate: n",
            commit_msgs=["added thing"],
        )
        assert result.severity == Severity.warn


# ============================================================
# Pre-Verdict Determination Tests
# ============================================================

class TestDeterminePreVerdict:
    def test_error_rejected(self):
        v = determine_pre_verdict(
            FormatCheckResult(severity=Severity.error),
            ChecklistCheckResult(),
        )
        assert v == PreVerdict.likely_rejected

    def test_low_coverage_review(self):
        v = determine_pre_verdict(
            FormatCheckResult(severity=Severity.ok),
            ChecklistCheckResult(coverage_ratio=0.5),
        )
        assert v == PreVerdict.needs_review

    def test_warn_review(self):
        v = determine_pre_verdict(
            FormatCheckResult(severity=Severity.warn),
            ChecklistCheckResult(),
        )
        assert v == PreVerdict.needs_review

    def test_all_ok_approved(self):
        v = determine_pre_verdict(
            FormatCheckResult(severity=Severity.ok),
            ChecklistCheckResult(coverage_ratio=0.9),
        )
        assert v == PreVerdict.likely_approved


# ============================================================
# JSON Extraction Tests
# ============================================================

class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_code_block(self):
        text = '```json\n{"a": 1}\n```'
        assert _extract_json(text) == {"a": 1}

    def test_invalid(self):
        with pytest.raises(ValueError):
            _extract_json("not json at all")


# ============================================================
# Tool Tests (with mocks)
# ============================================================

class TestDBQueryTool:
    def test_subtask_show_valid(self):
        db = DBQueryTool()
        with patch("tools.kanjou.tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="subtask_100 details\n", stderr=""
            )
            result = db.subtask_show("subtask_100")
            assert "subtask_100" in result

    def test_subtask_show_invalid_id(self):
        db = DBQueryTool()
        assert db.subtask_show("bad_id") is None
        assert db.subtask_show("subtask_abc") is None

    def test_report_list_valid(self):
        db = DBQueryTool()
        with patch("tools.kanjou.tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="report1\nreport2\n", stderr=""
            )
            result = db.report_list("subtask_200")
            assert "report1" in result

    def test_cmd_show_valid(self):
        db = DBQueryTool()
        with patch("tools.kanjou.tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="cmd data\n", stderr="")
            result = db.cmd_show("cmd_50")
            assert "cmd data" in result

    def test_cmd_show_invalid(self):
        db = DBQueryTool()
        assert db.cmd_show("invalid") is None

    def test_subprocess_timeout(self):
        db = DBQueryTool()
        with patch("tools.kanjou.tools.subprocess.run", side_effect=TimeoutError):
            # TimeoutError != subprocess.TimeoutExpired, so this tests FileNotFoundError path
            pass
        with patch("tools.kanjou.tools.subprocess.run") as mock_run:
            import subprocess as sp
            mock_run.side_effect = sp.TimeoutExpired(cmd="test", timeout=10)
            result = db.subtask_show("subtask_1")
            assert result is None


class TestKousatsuAPITool:
    def test_health_ok(self):
        api = KousatsuAPITool()
        with patch("tools.kanjou.tools.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            assert api.health() is True

    def test_health_fail(self):
        api = KousatsuAPITool()
        with patch("tools.kanjou.tools.httpx.get", side_effect=httpx.ConnectError("fail")):
            assert api.health() is False

    def test_search_similar(self):
        api = KousatsuAPITool()
        with patch("tools.kanjou.tools.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"results": [{"subtask_id": "subtask_50"}]},
            )
            result = api.search_similar("subtask_100")
            assert result["results"][0]["subtask_id"] == "subtask_50"

    def test_search_similar_invalid_id(self):
        api = KousatsuAPITool()
        assert api.search_similar("bad") is None

    def test_audit_history(self):
        api = KousatsuAPITool()
        with patch("tools.kanjou.tools.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"stats": {"approval_rate": 0.95}},
            )
            result = api.audit_history("ashigaru1")
            assert result["stats"]["approval_rate"] == 0.95

    def test_audit_history_invalid_worker(self):
        api = KousatsuAPITool()
        assert api.audit_history("invalid_worker") is None

    def test_check_coverage(self):
        api = KousatsuAPITool()
        with patch("tools.kanjou.tools.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"coverage_ratio": 0.85},
            )
            result = api.check_coverage("cmd_50")
            assert result["coverage_ratio"] == 0.85

    def test_timeout_fallback(self):
        api = KousatsuAPITool()
        with patch("tools.kanjou.tools.httpx.get", side_effect=httpx.TimeoutException("slow")):
            assert api.search_similar("subtask_1") is None


class TestFileReadTool:
    def test_read_valid_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        tool = FileReadTool(allowed_root=tmp_path)
        assert tool.read(str(f)) == "hello world"

    def test_read_outside_root(self, tmp_path):
        tool = FileReadTool(allowed_root=tmp_path)
        assert tool.read("/etc/passwd") is None

    def test_read_nonexistent(self, tmp_path):
        tool = FileReadTool(allowed_root=tmp_path)
        assert tool.read(str(tmp_path / "nope.txt")) is None


# ============================================================
# Import test for httpx
# ============================================================

def test_httpx_import():
    import httpx
    assert hasattr(httpx, "get")


# ============================================================
# Ohariko Meta-Audit Schema Tests
# ============================================================

class TestOharikoAuditIssue:
    def test_valid(self):
        issue = OharikoAuditIssue(
            audit_report_id="audit_report_039",
            check="prefix_format",
            problem="Invalid prefix",
            severity=IssueSeverity.warn,
        )
        assert issue.audit_report_id == "audit_report_039"
        assert issue.severity == IssueSeverity.warn


class TestOharikoAuditResult:
    def test_valid(self):
        result = OharikoAuditResult(
            audit_report_id="audit_report_039",
            subtask_id="subtask_559",
            result_match=True,
            findings_quality=Severity.ok,
            coverage_check=True,
            prefix_valid=True,
            issues=[],
            severity=Severity.ok,
        )
        assert result.audit_report_id == "audit_report_039"
        assert result.severity == Severity.ok

    def test_with_issues(self):
        result = OharikoAuditResult(
            audit_report_id="audit_report_039",
            subtask_id="subtask_559",
            result_match=False,
            findings_quality=Severity.warn,
            coverage_check=True,
            prefix_valid=False,
            issues=[
                OharikoAuditIssue(
                    audit_report_id="audit_report_039",
                    check="prefix_format",
                    problem="bad prefix",
                    severity=IssueSeverity.warn,
                )
            ],
            severity=Severity.warn,
        )
        assert len(result.issues) == 1


class TestOharikoMetaAuditReport:
    def test_minimal(self):
        r = OharikoMetaAuditReport(
            total_audited=0,
            reports=[],
            overall_severity=Severity.ok,
        )
        assert r.total_audited == 0

    def test_json_roundtrip(self):
        r = OharikoMetaAuditReport(
            total_audited=1,
            reports=[
                OharikoAuditResult(
                    audit_report_id="audit_report_039",
                    subtask_id="subtask_559",
                    result_match=True,
                    findings_quality=Severity.warn,
                    coverage_check=True,
                    prefix_valid=True,
                    issues=[
                        OharikoAuditIssue(
                            audit_report_id="audit_report_039",
                            check="specificity",
                            problem="vague finding",
                            severity=IssueSeverity.warn,
                        )
                    ],
                    qwen_review='{"quality": "mediocre", "issues": ["lazy"]}',
                    severity=Severity.warn,
                )
            ],
            overall_severity=Severity.warn,
        )
        j = r.model_dump_json()
        r2 = OharikoMetaAuditReport.model_validate_json(j)
        assert r2.total_audited == 1
        assert r2.reports[0].audit_report_id == "audit_report_039"
        assert r2.reports[0].qwen_review is not None
        assert r2.overall_severity == Severity.warn


# ============================================================
# Ohariko Meta-Audit Logic Tests
# ============================================================

class TestCheckFindingsPrefixes:
    def test_all_valid(self):
        findings = [
            "[確認OK] テスト27件全PASS",
            "[品質][中] 設計書§5のOllama記述が未更新",
            "[品質][軽微] コメント更新漏れ",
            "[高札分析] cmd_249の依存管理",
            "[鯰分析] subtask依存解析",
            "[情報] auto_reject閾値の見直し",
        ]
        invalid = check_findings_prefixes(findings)
        assert len(invalid) == 0

    def test_invalid_prefix(self):
        findings = [
            "[確認OK] テストPASS",
            "これはプレフィックスなし",
            "[不明] 不正なプレフィックス",
        ]
        invalid = check_findings_prefixes(findings)
        assert len(invalid) == 2

    def test_empty_list(self):
        assert check_findings_prefixes([]) == []

    def test_品質高(self):
        findings = ["[品質][高] 致命的な問題"]
        assert check_findings_prefixes(findings) == []


class TestResultFindingsConsistency:
    def test_approved_with_few_issues(self):
        findings = [
            "[確認OK] テストPASS",
            "[品質][中] 軽い指摘",
            "[確認OK] 設計書整合",
        ]
        ok, reason = check_result_findings_consistency("approved", findings)
        assert ok is True

    def test_approved_with_many_quality_issues(self):
        findings = [
            "[品質][中] 問題1",
            "[品質][中] 問題2",
            "[品質][高] 問題3",
        ]
        ok, reason = check_result_findings_consistency("approved", findings)
        assert ok is False
        assert "approved" in reason

    def test_rejected_with_no_quality_issues(self):
        findings = [
            "[確認OK] テストPASS",
            "[確認OK] 設計書整合",
        ]
        ok, reason = check_result_findings_consistency("rejected_trivial", findings)
        assert ok is False
        assert "rejected" in reason

    def test_rejected_with_quality_issues(self):
        findings = [
            "[品質][中] 問題発見",
            "[確認OK] テストPASS",
        ]
        ok, reason = check_result_findings_consistency("rejected_trivial", findings)
        assert ok is True

    def test_unknown_result(self):
        ok, reason = check_result_findings_consistency("unknown", ["[確認OK] ok"])
        assert ok is True


class TestCheckFindingsSpecificity:
    def test_specific_findings(self):
        findings = [
            "[品質][中] 設計書§5.1のOllama記述が未更新。agriha_control.py L200参照",
            "[品質][軽微] テスト22件はPASSだが追加推奨",
        ]
        sev, vague = check_findings_specificity(findings)
        assert sev == Severity.ok
        assert len(vague) == 0

    def test_vague_findings(self):
        findings = [
            "[品質][中] なんか問題がある",
            "[品質][中] よくない感じ",
        ]
        sev, vague = check_findings_specificity(findings)
        assert sev == Severity.error
        assert len(vague) == 2

    def test_confirmations_skipped(self):
        findings = [
            "[確認OK] テストPASS",
            "[確認OK] 設計書整合",
        ]
        sev, vague = check_findings_specificity(findings)
        assert sev == Severity.ok
        assert len(vague) == 0

    def test_mixed(self):
        findings = [
            "[確認OK] テストPASS",
            "[品質][中] 曖昧な指摘",
        ]
        sev, vague = check_findings_specificity(findings)
        assert sev == Severity.warn
        assert len(vague) == 1


class TestLoadOharikoReports:
    def test_load_from_file(self, tmp_path):
        yaml_content = """audit_reports:
  - id: audit_report_001
    subtask_id: subtask_100
    result: approved
    summary: "テスト合格"
    findings:
      - "[確認OK] テストPASS"
  - id: audit_report_002
    subtask_id: subtask_200
    result: rejected_trivial
    summary: "却下"
    findings:
      - "[品質][中] 問題あり"
"""
        f = tmp_path / "test_ohariko.yaml"
        f.write_text(yaml_content)
        reports = load_ohariko_reports(limit=5, yaml_path=f)
        assert len(reports) == 2
        assert reports[0]["id"] == "audit_report_001"

    def test_load_with_limit(self, tmp_path):
        yaml_content = """audit_reports:
  - id: r1
    subtask_id: s1
  - id: r2
    subtask_id: s2
  - id: r3
    subtask_id: s3
"""
        f = tmp_path / "test.yaml"
        f.write_text(yaml_content)
        reports = load_ohariko_reports(limit=2, yaml_path=f)
        assert len(reports) == 2

    def test_load_missing_file(self, tmp_path):
        reports = load_ohariko_reports(yaml_path=tmp_path / "nonexistent.yaml")
        assert reports == []

    def test_load_empty_yaml(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        reports = load_ohariko_reports(yaml_path=f)
        assert reports == []


class TestRunOharikoAudit:
    def test_run_with_mock_data(self, tmp_path):
        yaml_content = """audit_reports:
  - id: audit_report_001
    subtask_id: subtask_100
    result: approved
    summary: "テスト合格。27件PASS。"
    findings:
      - "[確認OK] テスト27件全PASS ✓"
      - "[品質][軽微] コメント更新漏れ。test_control.py L45参照"
"""
        f = tmp_path / "ohariko.yaml"
        f.write_text(yaml_content)

        with patch("tools.kanjou.kanjou_ginmiyaku.qwen_ohariko_review", return_value=None):
            report = run_ohariko_audit(limit=5, yaml_path=f)

        assert report.total_audited == 1
        assert report.reports[0].audit_report_id == "audit_report_001"
        assert report.reports[0].prefix_valid is True
        assert report.reports[0].result_match is True

    def test_run_empty(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("audit_reports: []")

        report = run_ohariko_audit(limit=5, yaml_path=f)
        assert report.total_audited == 0
        assert report.overall_severity == Severity.ok

    def test_run_with_qwen_poor_rating(self, tmp_path):
        yaml_content = """audit_reports:
  - id: audit_report_bad
    subtask_id: subtask_999
    result: approved
    summary: "合格"
    findings:
      - "[確認OK] OK"
"""
        f = tmp_path / "ohariko.yaml"
        f.write_text(yaml_content)

        qwen_response = '{"quality": "poor", "issues": ["lazy approval"], "missed_checks": ["tests"]}'
        with patch("tools.kanjou.kanjou_ginmiyaku.qwen_ohariko_review", return_value=qwen_response):
            report = run_ohariko_audit(limit=5, yaml_path=f)

        assert report.total_audited == 1
        assert report.reports[0].severity == Severity.error
        assert any(i.check == "qwen_review" for i in report.reports[0].issues)
