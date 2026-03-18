#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# identity_inject.sh — コンパクション復帰時の自動身元注入
# ═══════════════════════════════════════════════════════════════
# Usage: scripts/identity_inject.sh [--agent-id ID] [--format text|json]
#
# tmux @agent_id からエージェントの役割・ペイン・割当タスクを取得し、
# 復帰用テキストを stdout に出力する。
#
# Exit codes:
#   0 = 成功（タスクあり or タスクなし両方）
#   1 = agent_id取得失敗
#   2 = エラー
#
# Environment:
#   TMUX_PANE — tmux pane識別子（自動検出用）
#   __STOP_HOOK_SCRIPT_DIR — テスト用override
#   __STOP_HOOK_AGENT_ID  — テスト用override
# ═══════════════════════════════════════════════════════════════

set -u

SCRIPT_DIR="${__STOP_HOOK_SCRIPT_DIR:-${SHOGUN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}}"

# ─── 引数パース ───
AGENT_ID=""
FORMAT="text"

while [ $# -gt 0 ]; do
    case "$1" in
        --agent-id)
            AGENT_ID="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        *)
            echo "Usage: identity_inject.sh [--agent-id ID] [--format text|json]" >&2
            exit 2
            ;;
    esac
done

# ─── agent_id取得 ───
if [ -z "$AGENT_ID" ]; then
    if [ -n "${__STOP_HOOK_AGENT_ID+x}" ]; then
        AGENT_ID="$__STOP_HOOK_AGENT_ID"
    elif [ -n "${TMUX_PANE:-}" ]; then
        AGENT_ID=$(tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}' 2>/dev/null || echo "")
    fi
fi

if [ -z "$AGENT_ID" ]; then
    echo "ERROR: agent_id を取得できない。--agent-id で指定せよ。" >&2
    exit 1
fi

# ─── HealthCheck（老中のみ） ───
if [ "$AGENT_ID" = "karo-roju" ]; then
    bash "$SCRIPT_DIR/scripts/healthcheck.sh" 2>/dev/null || true
fi

# ─── Python で身元情報を生成 ───
python3 - "$AGENT_ID" "$FORMAT" "$SCRIPT_DIR" <<'PYEOF'
import sys
import yaml
import json
import os

agent_id = sys.argv[1]
output_format = sys.argv[2]
script_dir = sys.argv[3]

# agent_id → role/pane/instructions マッピング
AGENT_MAP = {
    "shogun":    {"role": "将軍",   "pane": "shogun:main.0",       "instructions": "instructions/shogun.md"},
    "karo-roju": {"role": "老中",   "pane": "multiagent:agents.0", "instructions": "instructions/karo.md"},
    "gunshi":    {"role": "軍師",   "pane": "multiagent:agents.1", "instructions": "instructions/gunshi.md"},
    "ashigaru1": {"role": "足軽1",  "pane": "multiagent:agents.2", "instructions": "instructions/ashigaru.md"},
    "ashigaru2": {"role": "足軽2",  "pane": "multiagent:agents.3", "instructions": "instructions/ashigaru.md"},
    "ashigaru6": {"role": "部屋子1","pane": "multiagent:agents.4", "instructions": "instructions/ashigaru.md"},
    "ohariko":   {"role": "お針子", "pane": "ooku:agents.0",       "instructions": "instructions/ohariko.md"},
}

info = AGENT_MAP.get(agent_id, {
    "role": f"不明({agent_id})",
    "pane": "unknown",
    "instructions": "instructions/ashigaru.md"
})

# 報告先の決定
if agent_id in ("ashigaru1", "ashigaru2", "ashigaru6", "gunshi"):
    report_yaml = "queue/inbox/roju_reports.yaml"
elif agent_id == "ohariko":
    report_yaml = "queue/inbox/roju_ohariko.yaml"
elif agent_id == "karo-roju":
    report_yaml = "dashboard.md（将軍への報告）"
else:
    report_yaml = "N/A"

# inbox YAMLからタスク取得
tasks = []
try:
    if agent_id == "gunshi":
        inbox_path = os.path.join(script_dir, "queue", "inbox", "gunshi.yaml")
        if os.path.exists(inbox_path):
            with open(inbox_path) as f:
                data = yaml.safe_load(f) or {}
            for task in (data.get("tasks") or []):
                status = task.get("status", "")
                if status in ("assigned", "in_progress"):
                    tasks.append({
                        "subtask_id": task.get("subtask_id", ""),
                        "cmd_id": task.get("cmd_id", ""),
                        "status": status,
                        "description": (task.get("description", "") or "").strip().split("\n")[0][:100],
                        "project": task.get("project", ""),
                    })
    elif agent_id.startswith("ashigaru"):
        num = agent_id.replace("ashigaru", "")
        inbox_path = os.path.join(script_dir, "queue", "inbox", f"ashigaru{num}.yaml")
        if os.path.exists(inbox_path):
            with open(inbox_path) as f:
                data = yaml.safe_load(f) or {}
            for task in (data.get("tasks") or []):
                status = task.get("status", "")
                if status in ("assigned", "in_progress"):
                    tasks.append({
                        "subtask_id": task.get("subtask_id", ""),
                        "cmd_id": task.get("cmd_id", ""),
                        "status": status,
                        "description": (task.get("description", "") or "").strip().split("\n")[0][:100],
                        "project": task.get("project", ""),
                    })
    elif agent_id == "karo-roju":
        # 家老: 未読報告件数
        inbox_dir = os.path.join(script_dir, "queue", "inbox")
        unread_count = 0
        for fname in ["roju_reports.yaml", "roju_ohariko.yaml"]:
            fpath = os.path.join(inbox_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath) as f:
                fdata = yaml.safe_load(f) or {}
            for key in ["reports", "audit_reports"]:
                for entry in (fdata.get(key) or []):
                    if entry.get("read") is False and entry.get("subtask_id") != "stophook_notification":
                        unread_count += 1
        if unread_count > 0:
            tasks.append({
                "subtask_id": f"未読報告{unread_count}件",
                "cmd_id": "",
                "status": "pending",
                "description": "roju_reports/roju_ohariko の未読報告を処理せよ",
                "project": "",
            })
except Exception:
    pass

# 出力
if output_format == "json":
    result = {
        "agent_id": agent_id,
        "role": info["role"],
        "pane": info["pane"],
        "instructions": info["instructions"],
        "report_yaml": report_yaml,
        "tasks": tasks,
    }
    print(json.dumps(result, ensure_ascii=False))
else:
    # text形式
    print(f"汝は{info['role']}（{agent_id}）である。")
    print(f"ペイン: {info['pane']}")
    print(f"instructions: {info['instructions']}")
    print(f"報告先: {report_yaml}")
    if tasks:
        print("現在の割当タスク:")
        for t in tasks:
            cmd = f" ({t['cmd_id']})" if t["cmd_id"] else ""
            proj = f" [{t['project']}]" if t["project"] else ""
            print(f"  - {t['subtask_id']}{cmd}: {t['description']}{proj} [status: {t['status']}]")
    else:
        print("割当タスクなし。次の指示を待て。")

PYEOF
