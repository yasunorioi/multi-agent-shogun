#!/usr/bin/env python3
"""
policy_checker.py — Phase 1 PreToolUse Policy Checker
AgentSpec DSL inspired, Claude Code hooks compatible.

設計原則:
- fail-open (エラー時は通過。gatekeeper_f006.shがfail-closedで兜)
- ms級オーバーヘッド (正規表現マッチのみ、LLM呼び出しなし)
- TraceRecord原型をJSONLログ出力

設計書: docs/shogun/quality_guardrails_design_v2.md §2.2
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime

LOG_PATH = os.path.expanduser("~/multi-agent-shogun/logs/policy_violations.jsonl")


def get_agent_id() -> str:
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return "unknown"
    try:
        r = subprocess.run(
            ["tmux", "display-message", "-t", pane, "-p", "#{@agent_id}"],
            capture_output=True, text=True, timeout=2
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def log_violation(agent_id: str, rule_id: str, target: str, decision: str) -> None:
    """TraceRecord原型をJSONLログに記録"""
    record = {
        "trace_id": f"tr_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "phase": "runtime",
        "agent": agent_id,
        "verdict": decision,
        "rule_id": rule_id,
        "target": target[:200],  # 長すぎるコマンドは切り詰め
        "timestamp": datetime.now().isoformat()
    }
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # ログ書き込み失敗は無視（fail-open）


# === ルール定義 ===
# (trigger_tool, check_fn, decision, rule_id, reason)
UNIVERSAL_RULES = [
    (
        "Bash",
        lambda cmd, _: bool(re.search(r'tmux\s+send-keys\s+.*-t\s+shogun', cmd)),
        "deny", "F001",
        "将軍への直接send-keys禁止。老中経由で報告せよ。",
    ),
    (
        "Bash",
        lambda cmd, _: bool(re.search(r'while\s+true|sleep\s+\d+\s*&&\s*tmux', cmd, re.S)),
        "deny", "F004",
        "ポーリング禁止。イベント駆動で動け。",
    ),
    (
        "Bash",
        lambda cmd, _: bool(re.search(r'cat\s+/dev/tty(ACM|USB)', cmd)),
        "deny", "SERIAL",
        "シリアルデバイス直接cat禁止。tmuxペインが破壊される。",
    ),
]

ROLE_RULES: dict[str, list] = {
    "gunshi": [
        (
            "Edit",
            lambda _, path: bool(re.search(r'queue/inbox/ashigaru', path)),
            "deny", "F003",
            "軍師が足軽inboxに書き込み禁止。分析結果は老中に返せ。",
        ),
        (
            "Write",
            lambda _, path: bool(re.search(r'queue/inbox/ashigaru', path)),
            "deny", "F003",
            "軍師が足軽inboxに書き込み禁止。分析結果は老中に返せ。",
        ),
    ],
    "ohariko": [
        (
            "Edit",
            lambda _, path: (
                not re.search(r'queue/inbox/(roju_ohariko|ohariko)', path)
                and bool(re.search(r'queue/inbox/', path))
            ),
            "deny", "OHARIKO_SCOPE",
            "お針子は自分のinbox以外のYAMLを書き換えるな。",
        ),
    ],
}


def main() -> None:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        sys.exit(0)  # fail-open: パースエラーは通過

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    command = tool_input.get("command", "")
    file_path = tool_input.get("file_path", "")

    agent_id = get_agent_id()

    # 全エージェント共通ルール + role別ルール
    all_rules = UNIVERSAL_RULES + ROLE_RULES.get(agent_id, [])

    for trigger, check_fn, decision, rule_id, reason in all_rules:
        if trigger != tool_name:
            continue
        target = command if tool_name == "Bash" else file_path
        if check_fn(target, file_path):
            log_violation(agent_id, rule_id, target, decision)
            out = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": f"[{agent_id}] [{rule_id}] {reason}"
                }
            }
            print(json.dumps(out, ensure_ascii=False))
            return
    # マッチなし: 出力なし(通過)
    sys.exit(0)


if __name__ == "__main__":
    main()
