"""karo_audit_judge — needs_audit 自動判定ロジック (cmd_573 S7).

【判定優先度】
  1. 手動指定 (needs_audit=true/false 明示) → 絶対優先
  2. judge_needs_audit() で True 判定 → 自動付与推奨
  3. それ以外 → False (既定)

【運用フロー (老中側)】
  from scripts.karo_audit_judge import judge_needs_audit

  # subtask 割当時に呼ぶ
  flagged, reasons = judge_needs_audit(
      description=subtask["description"],
      target_path=subtask.get("target_path"),
  )
  # 手動指定が優先 — needs_audit フィールドが明示されていればそちらを使う
  if "needs_audit" not in subtask:
      subtask["needs_audit"] = flagged

【自動統合は本スクリプト単独では行わない】
  scripts/botsu/cmd.py (subtask add) への組込は別 cmd で殿確認後に実施。
  本スクリプトはライブラリとして独立させ、テスト容易性を保つ。
"""

import re

# ---------------------------------------------------------------------------
# ヒューリスティック定義
# ---------------------------------------------------------------------------

_KEYWORD_PATTERN = re.compile(
    r"crystallize|結晶化|没日録|botsunichiroku|swarm\.db|thread_replies"
    r"|forbidden_actions|F00[1-9]|instructions/|context/karo-",
    re.IGNORECASE,
)

_AUDIT_PATHS = (
    "scripts/botsu/",
    "scripts/karo_",
    "instructions/",
    "agent-swarm/",
    "data/botsunichiroku.db",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def judge_needs_audit(
    description: str,
    target_path: str | None = None,
) -> tuple[bool, list[str]]:
    """subtask の説明とパスから needs_audit=true が適切か判定する。

    Returns:
        (flagged, reasons)
        flagged: True なら needs_audit=true を推奨
        reasons: フラグを立てた理由のリスト（デバッグ・説明用）
    """
    reasons: list[str] = []

    m = _KEYWORD_PATTERN.search(description or "")
    if m:
        reasons.append(f"keyword match: '{m.group()}' in description")

    path = target_path or ""
    for audit_path in _AUDIT_PATHS:
        if audit_path in path:
            reasons.append(f"path match: '{audit_path}' in target_path")
            break

    return bool(reasons), reasons
