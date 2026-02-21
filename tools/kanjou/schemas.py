"""勘定吟味役 — Pydantic v2 スキーマ定義

設計書 §4.2 / §5.2 の JSON Schema を Pydantic モデルに変換。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------- Enums ----------

class Severity(str, Enum):
    ok = "ok"
    warn = "warn"
    error = "error"


class IssueSeverity(str, Enum):
    warn = "warn"
    error = "error"


class PreVerdict(str, Enum):
    likely_approved = "likely_approved"
    needs_review = "needs_review"
    likely_rejected = "likely_rejected"


class AutoJudgment(str, Enum):
    auto_reject = "auto_reject"
    needs_review = "needs_review"
    auto_recommend = "auto_recommend"


class RejectionPattern(str, Enum):
    too_simple = "too_simple"
    project_specific = "project_specific"
    config_varies = "config_varies"
    merged_into_other = "merged_into_other"
    scope_too_narrow = "scope_too_narrow"
    none = "none"


class Recommendation(str, Enum):
    adopt = "adopt"
    reject = "reject"
    hold = "hold"
    needs_human = "needs_human"


# ---------- Format Check ----------

class FormatIssue(BaseModel):
    field: str
    problem: str
    severity: IssueSeverity


class FormatCheckResult(BaseModel):
    issues: list[FormatIssue] = Field(default_factory=list)
    severity: Severity = Severity.ok


# ---------- Checklist Check ----------

class ChecklistCheckResult(BaseModel):
    coverage_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    uncovered_items: list[str] = Field(default_factory=list)
    similar_tasks: list[dict] = Field(default_factory=list)
    worker_approval_rate: Optional[float] = None


# ---------- Skill Candidate Evaluation ----------

class SkillScores(BaseModel):
    reusability: int = Field(..., ge=0, le=3)
    complexity: int = Field(..., ge=0, le=3)
    generality: int = Field(..., ge=0, le=3)
    independence: int = Field(..., ge=0, le=2)
    pattern_stability: int = Field(..., ge=0, le=2)


class SkillCandidateEvaluation(BaseModel):
    skill_name: str
    proposed_by: str
    line_count: Optional[int] = Field(None, ge=0)
    scores: SkillScores
    total_score: int = Field(..., ge=0, le=13)
    auto_judgment: AutoJudgment
    rejection_pattern: RejectionPattern = RejectionPattern.none
    recommendation: Recommendation
    rationale: str = ""


# ---------- PreAuditReport (top-level output) ----------

class PreAuditReport(BaseModel):
    subtask_id: str
    kousatsu_ok: bool = False
    format_check: FormatCheckResult
    checklist_check: ChecklistCheckResult
    skill_evaluation: Optional[SkillCandidateEvaluation] = None
    pre_verdict: PreVerdict


# ---------- Ohariko Meta-Audit (お針子監査の監査) ----------

class OharikoAuditIssue(BaseModel):
    audit_report_id: str
    check: str
    problem: str
    severity: IssueSeverity


class OharikoAuditResult(BaseModel):
    audit_report_id: str
    subtask_id: str
    result_match: bool
    findings_quality: Severity
    coverage_check: bool
    prefix_valid: bool
    issues: list[OharikoAuditIssue] = Field(default_factory=list)
    qwen_review: Optional[str] = None
    severity: Severity


class OharikoMetaAuditReport(BaseModel):
    """お針子監査の監査結果（メタ監査）"""
    total_audited: int
    reports: list[OharikoAuditResult] = Field(default_factory=list)
    overall_severity: Severity
