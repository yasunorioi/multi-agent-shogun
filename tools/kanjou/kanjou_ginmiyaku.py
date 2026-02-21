#!/usr/bin/env python3
"""勘定吟味役（かんじょうぎんみやく）— Phase 0-1 メインスクリプト

Phase 0: Ollama + Qwen2.5-Coder 疎通確認
Phase 1: FormatChecker（ルールベース + Qwen補完）

Usage:
    python3 tools/kanjou/kanjou_ginmiyaku.py --phase0
    python3 tools/kanjou/kanjou_ginmiyaku.py --audit subtask_560
    python3 tools/kanjou/kanjou_ginmiyaku.py --help
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Optional

import httpx

import yaml

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
from pathlib import Path

from tools.kanjou.tools import DBQueryTool, FileReadTool, KousatsuAPITool

# ---------- Config ----------

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"
OLLAMA_TIMEOUT = 30.0


# ---------- Phase 0: Ollama疎通確認 ----------

def phase0() -> bool:
    """Ollama + Qwen2.5-Coder 疎通確認."""
    print("[Phase 0] Ollama疎通確認...")
    print(f"  Model: {OLLAMA_MODEL}")
    print(f"  URL:   {OLLAMA_BASE}/api/chat")

    try:
        r = httpx.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a code reviewer. Always respond in JSON only.",
                    },
                    {
                        "role": "user",
                        "content": (
                            'Review this Python function and return JSON: '
                            '{"issues": [], "quality": "good"|"bad"}\n\n'
                            'def add(a, b):\n    return a + b'
                        ),
                    },
                ],
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code != 200:
            print(f"  [FAIL] HTTP {r.status_code}: {r.text[:200]}")
            return False

        data = r.json()
        content = data.get("message", {}).get("content", "")
        print(f"  [OK] Response received ({len(content)} chars)")
        print(f"  Model response: {content[:300]}")

        # JSON解析可能かチェック
        try:
            _extract_json(content)
            print("  [OK] JSON parseable")
        except ValueError:
            print("  [WARN] Response is not valid JSON (may still be usable)")

        return True

    except httpx.ConnectError:
        print(f"  [FAIL] Cannot connect to Ollama at {OLLAMA_BASE}")
        print("  Hint: Start Ollama with 'ollama serve' and pull model with:")
        print(f"        ollama pull {OLLAMA_MODEL}")
        return False
    except httpx.TimeoutException:
        print(f"  [FAIL] Timeout ({OLLAMA_TIMEOUT}s)")
        return False


# ---------- Phase 1: Format Check ----------

# Required YAML report fields
REQUIRED_REPORT_FIELDS = ["subtask_id", "cmd_id", "worker", "status", "summary", "skill_candidate"]

# Valid commit prefixes
VALID_COMMIT_PREFIXES = ["feat:", "fix:", "docs:", "refactor:", "test:", "chore:", "style:", "perf:", "ci:"]


def _check_required_fields(report_text: str) -> list[FormatIssue]:
    """Check required fields in a YAML report."""
    issues = []
    for field in REQUIRED_REPORT_FIELDS:
        # Look for "field:" or "field :" pattern
        pattern = rf"(?:^|\n)\s*{re.escape(field)}\s*:"
        if not re.search(pattern, report_text):
            issues.append(FormatIssue(
                field=field,
                problem=f"Required field '{field}' not found in report",
                severity=IssueSeverity.error,
            ))
    return issues


def _check_markdown_headings(content: str) -> list[FormatIssue]:
    """Check Markdown heading structure."""
    issues = []
    lines = content.split("\n")
    prev_level = 0
    for i, line in enumerate(lines, 1):
        m = re.match(r"^(#{1,6})\s", line)
        if m:
            level = len(m.group(1))
            # Heading level should not jump more than 1 level
            if prev_level > 0 and level > prev_level + 1:
                issues.append(FormatIssue(
                    field=f"line:{i}",
                    problem=f"Heading jump from h{prev_level} to h{level}",
                    severity=IssueSeverity.warn,
                ))
            prev_level = level
    return issues


def _check_commit_prefix(commit_msg: str) -> list[FormatIssue]:
    """Check commit message prefix."""
    issues = []
    if commit_msg and not any(commit_msg.startswith(p) for p in VALID_COMMIT_PREFIXES):
        issues.append(FormatIssue(
            field="commit_message",
            problem=f"Commit message lacks valid prefix (expected: {', '.join(VALID_COMMIT_PREFIXES)})",
            severity=IssueSeverity.warn,
        ))
    return issues


def _check_skill_candidate(report_text: str) -> list[FormatIssue]:
    """Check skill_candidate field existence."""
    issues = []
    if "skill_candidate" not in report_text:
        issues.append(FormatIssue(
            field="skill_candidate",
            problem="skill_candidate field missing in report",
            severity=IssueSeverity.warn,
        ))
    return issues


def rule_based_format_check(
    report_text: str,
    files_content: dict[str, str] | None = None,
    commit_msgs: list[str] | None = None,
) -> FormatCheckResult:
    """Rule-based format checking (no LLM required)."""
    all_issues: list[FormatIssue] = []

    # 1. Required fields in YAML report
    all_issues.extend(_check_required_fields(report_text))

    # 2. skill_candidate check
    all_issues.extend(_check_skill_candidate(report_text))

    # 3. Markdown heading structure for any .md files
    if files_content:
        for path, content in files_content.items():
            if path.endswith(".md"):
                all_issues.extend(_check_markdown_headings(content))

    # 4. Commit message prefix
    if commit_msgs:
        for msg in commit_msgs:
            all_issues.extend(_check_commit_prefix(msg))

    # Determine overall severity
    has_error = any(i.severity == IssueSeverity.error for i in all_issues)
    has_warn = any(i.severity == IssueSeverity.warn for i in all_issues)

    if has_error:
        severity = Severity.error
    elif has_warn:
        severity = Severity.warn
    else:
        severity = Severity.ok

    return FormatCheckResult(issues=all_issues, severity=severity)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response text (may be wrapped in markdown code blocks)."""
    # Try direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Cannot extract JSON from: {text[:200]}")


def qwen_supplemental_check(report_text: str) -> list[FormatIssue]:
    """Call Qwen2.5-Coder for supplemental format issue detection."""
    try:
        r = httpx.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a code/document format reviewer. "
                            "Respond ONLY in JSON. No explanation text.\n"
                            "Output schema: {\"issues\": [{\"field\": str, \"problem\": str, \"severity\": \"warn\"|\"error\"}]}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Check this report for format issues NOT covered by these rules:\n"
                            "- Required YAML fields (subtask_id, cmd_id, worker, status, summary, skill_candidate)\n"
                            "- Markdown heading levels\n"
                            "- Commit message prefix\n\n"
                            "Look for: inconsistent naming, broken links, malformed YAML, "
                            "encoding issues, duplicate sections.\n\n"
                            f"Report content:\n{report_text[:2000]}"
                        ),
                    },
                ],
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code != 200:
            return []

        data = r.json()
        content = data.get("message", {}).get("content", "")
        parsed = _extract_json(content)

        issues = []
        for item in parsed.get("issues", []):
            sev = item.get("severity", "warn")
            if sev not in ("warn", "error"):
                sev = "warn"
            issues.append(FormatIssue(
                field=item.get("field", "unknown"),
                problem=item.get("problem", "unknown issue"),
                severity=IssueSeverity(sev),
            ))
        return issues

    except (httpx.ConnectError, httpx.TimeoutException, ValueError, KeyError):
        return []


# ---------- Phase 1: Full Audit Pipeline ----------

def collect_info(subtask_id: str) -> dict:
    """Collect info from DB + Kousatsu API + files."""
    db = DBQueryTool()
    kousatsu = KousatsuAPITool()

    info: dict = {
        "subtask_id": subtask_id,
        "subtask_detail": db.subtask_show(subtask_id),
        "reports": db.report_list(subtask_id),
        "kousatsu_ok": kousatsu.health(),
        "similar_tasks": None,
        "audit_history": None,
    }

    if info["kousatsu_ok"]:
        info["similar_tasks"] = kousatsu.search_similar(subtask_id)
        # Extract worker from subtask detail
        worker_match = re.search(r"worker[:\s]+(\w+)", info.get("subtask_detail") or "")
        if worker_match:
            info["audit_history"] = kousatsu.audit_history(worker_match.group(1))

    return info


def determine_pre_verdict(
    format_result: FormatCheckResult,
    checklist_result: ChecklistCheckResult,
) -> PreVerdict:
    """Determine pre-verdict based on format and checklist results."""
    if format_result.severity == Severity.error:
        return PreVerdict.likely_rejected

    # Coverage below threshold
    if checklist_result.coverage_ratio is not None and checklist_result.coverage_ratio < 0.7:
        return PreVerdict.needs_review

    if format_result.severity == Severity.warn:
        return PreVerdict.needs_review

    return PreVerdict.likely_approved


def run_audit(subtask_id: str) -> PreAuditReport:
    """Run Phase 1 audit for a subtask."""
    print(f"[Phase 1] Auditing {subtask_id}...")

    # Step 1: Collect information
    print("  [1/4] Collecting info from DB + Kousatsu API...")
    info = collect_info(subtask_id)
    print(f"  Kousatsu API: {'OK' if info['kousatsu_ok'] else 'NG (fallback mode)'}")

    # Step 2: Rule-based format check
    print("  [2/4] Rule-based format check...")
    report_text = info.get("reports") or ""
    format_result = rule_based_format_check(report_text)
    print(f"  Format: {format_result.severity.value} ({len(format_result.issues)} issues)")

    # Step 3: Qwen supplemental check
    print("  [3/4] Qwen supplemental check...")
    qwen_issues = qwen_supplemental_check(report_text)
    if qwen_issues:
        print(f"  Qwen found {len(qwen_issues)} additional issues")
        format_result.issues.extend(qwen_issues)
        # Recalculate severity
        has_error = any(i.severity == IssueSeverity.error for i in format_result.issues)
        has_warn = any(i.severity == IssueSeverity.warn for i in format_result.issues)
        if has_error:
            format_result.severity = Severity.error
        elif has_warn:
            format_result.severity = Severity.warn
    else:
        print("  Qwen: no additional issues (or Ollama unavailable)")

    # Step 4: Build checklist result
    print("  [4/4] Building checklist check result...")
    checklist_result = ChecklistCheckResult(
        similar_tasks=info.get("similar_tasks", {}).get("results", []) if isinstance(info.get("similar_tasks"), dict) else [],
    )

    # Extract worker approval rate from audit history
    audit_hist = info.get("audit_history")
    if isinstance(audit_hist, dict):
        stats = audit_hist.get("stats", {})
        checklist_result.worker_approval_rate = stats.get("approval_rate")

    # Determine pre-verdict
    pre_verdict = determine_pre_verdict(format_result, checklist_result)

    report = PreAuditReport(
        subtask_id=subtask_id,
        kousatsu_ok=info["kousatsu_ok"],
        format_check=format_result,
        checklist_check=checklist_result,
        pre_verdict=pre_verdict,
    )

    return report


# ---------- Phase 2: Ohariko Meta-Audit ----------

OHARIKO_YAML = Path("/home/yasu/multi-agent-shogun/queue/inbox/roju_ohariko.yaml")

# Valid finding prefixes
VALID_FINDING_PREFIXES = [
    "[確認OK]",
    "[品質][軽微]",
    "[品質][中]",
    "[品質][高]",
    "[高札分析]",
    "[鯰分析]",
    "[情報]",
]


def load_ohariko_reports(limit: int = 5, yaml_path: Path | None = None) -> list[dict]:
    """Load audit_reports from roju_ohariko.yaml."""
    path = yaml_path or OHARIKO_YAML
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return []
    reports = data.get("audit_reports", [])
    if not isinstance(reports, list):
        return []
    return reports[:limit]


def check_findings_prefixes(findings: list[str]) -> list[str]:
    """Check that each finding starts with a valid prefix.

    Returns list of findings with invalid prefixes.
    """
    invalid = []
    for f in findings:
        f_stripped = f.strip()
        if not any(f_stripped.startswith(p) for p in VALID_FINDING_PREFIXES):
            invalid.append(f_stripped)
    return invalid


def check_result_findings_consistency(
    result: str, findings: list[str]
) -> tuple[bool, str]:
    """Check consistency between result field and findings content.

    Returns (is_consistent, reason).
    """
    quality_issues = [
        f for f in findings
        if any(f.strip().startswith(p) for p in ("[品質][中]", "[品質][高]"))
    ]
    num_quality = len(quality_issues)

    if result == "approved" and num_quality >= 3:
        return False, f"approved but {num_quality} medium/high quality issues found"

    if result in ("rejected_trivial", "rejected_judgment") and num_quality == 0:
        confirmations = [f for f in findings if f.strip().startswith("[確認OK]")]
        if len(confirmations) == len(findings):
            return False, "rejected but all findings are confirmations with no quality issues"

    return True, "consistent"


def check_findings_specificity(findings: list[str]) -> tuple[Severity, list[str]]:
    """Check that findings contain specific evidence (filenames, line numbers, counts).

    Returns (severity, list_of_vague_findings).
    """
    # Patterns indicating specificity
    specificity_patterns = [
        re.compile(r"\b\w+\.\w{1,5}\b"),      # filename.ext
        re.compile(r"\b[Ll]ine\s*:?\s*\d+|L\d{2,}"),  # line reference
        re.compile(r"\d+\s*(件|テスト|PASS|行|項目|ファイル|tests?)"),  # counts
        re.compile(r"§\d"),                    # section reference
        re.compile(r"\b(ch|v)\d"),             # channel/version reference
    ]

    vague = []
    for f in findings:
        f_stripped = f.strip()
        # Skip pure confirmations — they are inherently specific enough
        if f_stripped.startswith("[確認OK]"):
            continue
        # Check for quality issues that lack specifics
        if not any(p.search(f_stripped) for p in specificity_patterns):
            vague.append(f_stripped)

    if len(vague) == 0:
        return Severity.ok, []
    elif len(vague) <= 1:
        return Severity.warn, vague
    else:
        return Severity.error, vague


def qwen_ohariko_review(audit_report: dict) -> Optional[str]:
    """Ask Qwen to review an ohariko audit report for quality."""
    report_id = audit_report.get("id", "unknown")
    result = audit_report.get("result", "unknown")
    summary = audit_report.get("summary", "")
    findings = audit_report.get("findings", [])
    findings_text = "\n".join(f"  - {f}" for f in findings)

    prompt = (
        f"This is an audit report (id: {report_id}) with result: {result}.\n"
        f"Summary: {summary[:500]}\n"
        f"Findings:\n{findings_text[:1500]}\n\n"
        "Evaluate this audit quality. Return JSON only:\n"
        '{"quality": "good"|"mediocre"|"poor", '
        '"issues": ["issue1", ...], '
        '"missed_checks": ["check1", ...]}'
    )

    try:
        r = httpx.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a meta-auditor reviewing an AI auditor's work. "
                            "Be strict and unforgiving. Check for: lazy approvals, "
                            "vague findings, missing critical checks, inconsistent judgments. "
                            "Respond ONLY in JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return data.get("message", {}).get("content", "")
    except (httpx.ConnectError, httpx.TimeoutException):
        return None


def run_ohariko_audit(
    limit: int = 5, yaml_path: Path | None = None
) -> OharikoMetaAuditReport:
    """Run meta-audit on ohariko's audit reports."""
    print(f"[Meta-Audit] お針子監査の監査を開始 (limit={limit})...")

    reports = load_ohariko_reports(limit, yaml_path)
    if not reports:
        print("  [WARN] No audit reports found.")
        return OharikoMetaAuditReport(
            total_audited=0, reports=[], overall_severity=Severity.ok
        )

    print(f"  Found {len(reports)} audit reports to review.")

    results: list[OharikoAuditResult] = []

    for report in reports:
        report_id = report.get("id", "unknown")
        subtask_id = report.get("subtask_id", "unknown")
        result_field = report.get("result", "")
        findings = report.get("findings", [])

        print(f"\n  --- Reviewing {report_id} ({subtask_id}) ---")
        issues: list[OharikoAuditIssue] = []

        # Check 1: Findings prefix format
        invalid_prefixes = check_findings_prefixes(findings)
        prefix_valid = len(invalid_prefixes) == 0
        if not prefix_valid:
            for inv in invalid_prefixes:
                issues.append(OharikoAuditIssue(
                    audit_report_id=report_id,
                    check="prefix_format",
                    problem=f"Invalid prefix: {inv[:80]}",
                    severity=IssueSeverity.warn,
                ))
        print(f"    Prefix check: {'OK' if prefix_valid else f'{len(invalid_prefixes)} invalid'}")

        # Check 2: Result-findings consistency
        is_consistent, reason = check_result_findings_consistency(result_field, findings)
        if not is_consistent:
            issues.append(OharikoAuditIssue(
                audit_report_id=report_id,
                check="result_consistency",
                problem=reason,
                severity=IssueSeverity.error,
            ))
        print(f"    Consistency:   {'OK' if is_consistent else reason}")

        # Check 3: Findings specificity
        specificity_sev, vague_list = check_findings_specificity(findings)
        if vague_list:
            for v in vague_list:
                issues.append(OharikoAuditIssue(
                    audit_report_id=report_id,
                    check="findings_specificity",
                    problem=f"Vague finding: {v[:80]}",
                    severity=IssueSeverity.warn,
                ))
        print(f"    Specificity:   {specificity_sev.value} ({len(vague_list)} vague)")

        # Check 4: Qwen review
        print("    Qwen review:   ", end="")
        qwen_result = qwen_ohariko_review(report)
        if qwen_result:
            print(f"received ({len(qwen_result)} chars)")
            try:
                qwen_parsed = _extract_json(qwen_result)
                if qwen_parsed.get("quality") == "poor":
                    issues.append(OharikoAuditIssue(
                        audit_report_id=report_id,
                        check="qwen_review",
                        problem=f"Qwen rated quality as poor: {qwen_parsed.get('issues', [])}",
                        severity=IssueSeverity.error,
                    ))
            except ValueError:
                pass  # Non-parseable Qwen output — skip
        else:
            print("skipped (Ollama unavailable)")

        # Determine per-report severity
        has_error = any(i.severity == IssueSeverity.error for i in issues)
        has_warn = any(i.severity == IssueSeverity.warn for i in issues)
        if has_error:
            severity = Severity.error
        elif has_warn:
            severity = Severity.warn
        else:
            severity = Severity.ok

        results.append(OharikoAuditResult(
            audit_report_id=report_id,
            subtask_id=subtask_id,
            result_match=is_consistent,
            findings_quality=specificity_sev,
            coverage_check=True,  # Placeholder — full coverage check needs subtask description
            prefix_valid=prefix_valid,
            issues=issues,
            qwen_review=qwen_result,
            severity=severity,
        ))

    # Overall severity
    if any(r.severity == Severity.error for r in results):
        overall = Severity.error
    elif any(r.severity == Severity.warn for r in results):
        overall = Severity.warn
    else:
        overall = Severity.ok

    meta_report = OharikoMetaAuditReport(
        total_audited=len(results),
        reports=results,
        overall_severity=overall,
    )

    print(f"\n[Meta-Audit] Complete: {len(results)} reports audited, overall={overall.value}")
    return meta_report


# ---------- CLI ----------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="kanjou_ginmiyaku",
        description="勘定吟味役 — 自動監査ツール (Phase 0-2)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--phase0", action="store_true", help="Ollama疎通確認 (Phase 0)")
    group.add_argument("--audit", metavar="SUBTASK_ID", help="subtask監査 (Phase 1)")
    group.add_argument("--audit-ohariko", action="store_true", help="お針子監査の監査 (Phase 2)")

    parser.add_argument("--limit", type=int, default=5, help="対象件数 (--audit-ohariko用)")

    args = parser.parse_args()

    if args.phase0:
        ok = phase0()
        return 0 if ok else 1

    if args.audit:
        subtask_id = args.audit
        if not re.match(r"^subtask_\d+$", subtask_id):
            print(f"[ERROR] Invalid subtask_id: {subtask_id} (expected: subtask_NNN)", file=sys.stderr)
            return 2

        report = run_audit(subtask_id)
        print("\n--- PreAuditReport ---")
        print(report.model_dump_json(indent=2))
        return 0

    if args.audit_ohariko:
        meta_report = run_ohariko_audit(limit=args.limit)
        print("\n--- OharikoMetaAuditReport ---")
        print(meta_report.model_dump_json(indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
