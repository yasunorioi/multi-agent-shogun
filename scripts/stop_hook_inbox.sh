#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# stop_hook_inbox.sh — Claude Code Stop Hook for inbox delivery
# ═══════════════════════════════════════════════════════════════
# When a Claude Code agent finishes its turn and is about to go idle,
# this hook:
#   1. Analyzes last_assistant_message to detect task completion/error
#   2. Auto-notifies karo via inbox_write (background, non-blocking)
#   3. Checks the agent's inbox for unread messages
#   4. If unread messages exist, BLOCKs the stop and feeds them back
#
# Environment:
#   TMUX_PANE — used to identify which agent is running
#   __STOP_HOOK_SCRIPT_DIR — override for testing (default: auto-detect)
#   __STOP_HOOK_AGENT_ID  — override for testing (default: from tmux)
# ═══════════════════════════════════════════════════════════════

set -u

# ─── SCRIPT_DIR (testable) ───
SCRIPT_DIR="${__STOP_HOOK_SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# 1. stdin読み込み（Claude Codeがstop_hook_activeなどのJSONを渡す）
INPUT=$(cat)

# 2. 無限ループ防止: stop_hook_active が true なら即座に抜ける
HOOK_ACTIVE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('stop_hook_active', False))
except:
    print('False')
" 2>/dev/null || echo "False")

if [ "$HOOK_ACTIVE" = "True" ] || [ "$HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# 3. agent_id取得（テスト用override対応）
if [ -n "${__STOP_HOOK_AGENT_ID+x}" ]; then
    AGENT_ID="$__STOP_HOOK_AGENT_ID"
elif [ -n "${TMUX_PANE:-}" ]; then
    AGENT_ID=$(tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}' 2>/dev/null || echo "")
else
    AGENT_ID=""
fi

if [ -z "$AGENT_ID" ]; then
    exit 0
fi

# 4. shogun / ohariko は常にapprove
case "$AGENT_ID" in
    shogun|ohariko)
        exit 0
        ;;
esac

# ─── 5. Analyze last_assistant_message ───
LAST_MSG=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('last_assistant_message', ''))
except:
    print('')
" 2>/dev/null || echo "")

if [ -n "$LAST_MSG" ]; then
    NOTIFY_TYPE=""
    NOTIFY_CONTENT=""

    # 完了検出パターン（日本語+英語、動詞+文脈ペアで誤検出防止）
    if echo "$LAST_MSG" | grep -qiE '任務完了|完了でござる|報告YAML.*更新|報告YAML.*記入|report.*updated|task completed|タスク完了|roju_reports.*更新'; then
        NOTIFY_TYPE="report_completed"
        NOTIFY_CONTENT="${AGENT_ID}、タスク完了検出。roju_reports確認されたし。"
    # エラー検出パターン
    elif echo "$LAST_MSG" | grep -qiE 'エラー.*中断|失敗.*中断|見つからない.*中断|abort|error.*abort|failed.*stop'; then
        NOTIFY_TYPE="error_report"
        NOTIFY_CONTENT="${AGENT_ID}、エラーで停止検出。確認されたし。"
    fi

    # 老中に自動通知（background、非ブロッキング）
    if [ -n "$NOTIFY_TYPE" ]; then
        bash "$SCRIPT_DIR/scripts/inbox_write.sh" roju_reports \
            "$NOTIFY_CONTENT" "$NOTIFY_TYPE" "$AGENT_ID" &
    fi
fi

# ─── 6. agent_idに応じたinboxファイル・未読検知 ───
INBOX_DIR="$SCRIPT_DIR/queue/inbox"
UNREAD=0

case "$AGENT_ID" in
    karo-roju)
        # 老中: roju_reports.yaml の read: false + roju_ohariko.yaml の read: false
        if [ -f "$INBOX_DIR/roju_reports.yaml" ]; then
            COUNT=$(grep -c 'read: false' "$INBOX_DIR/roju_reports.yaml" 2>/dev/null) || COUNT=0
            UNREAD=$((UNREAD + COUNT))
        fi
        if [ -f "$INBOX_DIR/roju_ohariko.yaml" ]; then
            COUNT=$(grep -c 'read: false' "$INBOX_DIR/roju_ohariko.yaml" 2>/dev/null) || COUNT=0
            UNREAD=$((UNREAD + COUNT))
        fi
        INBOX_FILES="roju_reports.yaml, roju_ohariko.yaml"
        ;;
    ashigaru[1-8])
        # 足軽/部屋子: ashigaru{N}.yaml の status: assigned
        NUM="${AGENT_ID#ashigaru}"
        INBOX_FILE="$INBOX_DIR/ashigaru${NUM}.yaml"
        if [ -f "$INBOX_FILE" ]; then
            UNREAD=$(grep -c 'status: assigned' "$INBOX_FILE" 2>/dev/null) || UNREAD=0
        fi
        INBOX_FILES="ashigaru${NUM}.yaml"
        ;;
    *)
        # 不明なagent_id → approve
        exit 0
        ;;
esac

# 7. 未読なし → approve
if [ "$UNREAD" -eq 0 ] 2>/dev/null; then
    exit 0
fi

# 8. サマリ生成（python3でYAMLパース、最大5件）
SUMMARY=$(python3 -c "
import yaml, sys, os

agent_id = '$AGENT_ID'
inbox_dir = '$INBOX_DIR'
items = []

try:
    if agent_id == 'karo-roju':
        # 老中: reports + ohariko の未読を収集
        for fname in ['roju_reports.yaml', 'roju_ohariko.yaml']:
            fpath = os.path.join(inbox_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath) as f:
                data = yaml.safe_load(f) or {}
            # reports or audit_reports
            for key in ['reports', 'audit_reports']:
                for entry in (data.get(key) or []):
                    if entry.get('read') == False:
                        summary = entry.get('summary', '').strip().split('\n')[0][:80]
                        src = entry.get('worker_id', entry.get('subtask_id', ''))
                        items.append(f'{fname}: {src} - {summary}')
            # health_reports
            for entry in (data.get('health_reports') or []):
                if entry.get('read') == False:
                    summary = entry.get('summary', '').strip().split('\n')[0][:80]
                    items.append(f'{fname}: health - {summary}')
    else:
        # 足軽/部屋子: assignedタスクを収集
        num = agent_id.replace('ashigaru', '')
        fpath = os.path.join(inbox_dir, f'ashigaru{num}.yaml')
        if os.path.exists(fpath):
            with open(fpath) as f:
                data = yaml.safe_load(f) or {}
            for task in (data.get('tasks') or []):
                if task.get('status') == 'assigned':
                    sid = task.get('subtask_id', '')
                    desc = task.get('description', '').strip().split('\n')[0][:80]
                    items.append(f'{sid}: {desc}')

    # 最大5件
    for line in items[:5]:
        print(line)
    if len(items) > 5:
        print(f'...他{len(items)-5}件')
except Exception:
    print('(YAMLの詳細取得失敗。ファイルを直接確認せよ)')
" 2>/dev/null || echo "(summary unavailable)")

# 9. JSON出力でblockを返す
REASON="inbox未読${UNREAD}件あり。queue/inbox/${INBOX_FILES}を読んで処理せよ。内容: ${SUMMARY}"
# JSONエスケープ
REASON_ESCAPED=$(echo "$REASON" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" 2>/dev/null || echo "\"inbox未読あり\"")

echo "{\"decision\": \"block\", \"reason\": ${REASON_ESCAPED}}"
