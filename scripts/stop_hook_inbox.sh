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

# 4. shogun は常にapprove。ohariko は (A) rejected_trivial 自動差し戻し後にapprove
case "$AGENT_ID" in
    shogun)
        exit 0
        ;;
    ohariko)
        # (A) rejected_trivial 自動差し戻し（老中不介入）
        # roju_ohariko.yaml の rejected_trivial かつ auto_requeued 未処理エントリを足軽に自動再割当
        python3 -c "
import yaml, os, tempfile, subprocess, sys
from datetime import datetime

script_dir = '$SCRIPT_DIR'
inbox_dir = os.path.join(script_dir, 'queue', 'inbox')
ohariko_path = os.path.join(inbox_dir, 'roju_ohariko.yaml')

if not os.path.exists(ohariko_path):
    sys.exit(0)

with open(ohariko_path) as f:
    data = yaml.safe_load(f) or {}

pane_map = {
    'ashigaru1': 'multiagent:agents.1',
    'ashigaru2': 'multiagent:agents.2',
    'ashigaru3': 'multiagent:agents.3',
    'ashigaru4': 'multiagent:agents.4',
    'ashigaru6': 'multiagent:agents.3',
}

modified = False
for entry in (data.get('audit_requests') or []):
    if (entry.get('judgement') == 'rejected_trivial'
            and not entry.get('auto_requeued')
            and entry.get('worker', '').startswith('ashigaru')
            and entry.get('subtask_id')):

        worker     = entry['worker']
        subtask_id = entry['subtask_id']
        cmd_id     = entry.get('cmd_id', '')
        recommend  = entry.get('recommendation', entry.get('summary', '指摘事項を修正せよ'))
        score      = entry.get('score', '?')

        num = worker.replace('ashigaru', '')
        worker_inbox = os.path.join(inbox_dir, f'ashigaru{num}.yaml')
        if not os.path.exists(worker_inbox):
            continue

        with open(worker_inbox) as f:
            wdata = yaml.safe_load(f) or {}

        existing_retries = sum(
            1 for t in (wdata.get('tasks') or [])
            if t.get('retry_of') == subtask_id
        )
        retry_count = existing_retries + 1

        # retry上限(2回)超過 → エスカレーション（自動ループ停止）
        if retry_count > 2:
            entry['auto_requeued'] = 'escalated'
            modified = True
            continue

        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        retry_task = {
            'subtask_id'  : f'{subtask_id}_retry_{retry_count}',
            'cmd_id'      : cmd_id,
            'assigned_by' : 'ohariko_auto',
            'assigned_at' : now,
            'status'      : 'assigned',
            'retry_count' : retry_count,
            'retry_of'    : subtask_id,
            'description' : f'【自動差し戻し rejected_trivial {score}点 retry_{retry_count}】\n{recommend}',
        }

        if 'tasks' not in wdata:
            wdata['tasks'] = []
        wdata['tasks'].append(retry_task)

        # Atomic write: worker inbox 更新
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(worker_inbox), suffix='.tmp')
        try:
            with os.fdopen(tmp_fd, 'w') as f:
                yaml.dump(wdata, f, default_flow_style=False,
                          allow_unicode=True, indent=2)
            os.replace(tmp_path, worker_inbox)
        except Exception as e:
            try: os.unlink(tmp_path)
            except: pass
            print(f'[auto_requeue] ERROR writing {worker}: {e}', file=sys.stderr)
            continue

        entry['auto_requeued']    = True
        entry['auto_requeued_at'] = now
        modified = True

        # ashigaruをtmux send-keysで起こす
        pane = pane_map.get(worker)
        if pane:
            subprocess.run(
                ['tmux', 'send-keys', '-t', pane,
                 f'{worker}、rejected_trivial自動差し戻し（retry_{retry_count}）。inbox確認されよ。'],
                check=False)
            subprocess.run(
                ['tmux', 'send-keys', '-t', pane, 'Enter'],
                check=False)

# roju_ohariko.yaml に auto_requeued フラグを保存
if modified:
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(ohariko_path), suffix='.tmp')
    try:
        with os.fdopen(tmp_fd, 'w') as f:
            yaml.dump(data, f, default_flow_style=False,
                      allow_unicode=True, indent=2)
        os.replace(tmp_path, ohariko_path)
    except Exception as e:
        try: os.unlink(tmp_path)
        except: pass
        print(f'[auto_requeue] ERROR saving ohariko: {e}', file=sys.stderr)
" 2>/dev/null
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
    # karo-roju自身は自分のinbox(roju_reports)に書き込まない
    # 理由: 自分のinboxに自分で通知→直後にunreadとして検出→blockのレースコンディション
    if [ -n "$NOTIFY_TYPE" ] && [ "$AGENT_ID" != "karo-roju" ]; then
        bash "$SCRIPT_DIR/scripts/inbox_write.sh" roju_reports \
            "$NOTIFY_CONTENT" "$NOTIFY_TYPE" "$AGENT_ID" &
    fi

    # (B) お針子auto-trigger: report_completed + needs_audit=true → ohariko.yaml に自動監査依頼
    if [ "$NOTIFY_TYPE" = "report_completed" ] && [ "$AGENT_ID" != "karo-roju" ]; then
        _AGENT_ID_B="$AGENT_ID"
        _SCRIPT_DIR_B="$SCRIPT_DIR"
        python3 -c "
import yaml, os, subprocess, sys, tempfile

script_dir = '$_SCRIPT_DIR_B'
worker     = '$_AGENT_ID_B'
inbox_dir  = os.path.join(script_dir, 'queue', 'inbox')
reports_path  = os.path.join(inbox_dir, 'roju_reports.yaml')
ohariko_path  = os.path.join(inbox_dir, 'ohariko.yaml')

if not os.path.exists(reports_path):
    sys.exit(0)

with open(reports_path) as f:
    rdata = yaml.safe_load(f) or {}

# 最新の未処理 needs_audit=true エントリを探す（このworker限定）
target = None
for entry in reversed(rdata.get('reports') or []):
    if (entry.get('worker') == worker
            and entry.get('needs_audit')
            and not entry.get('audit_triggered')):
        target = entry
        break

if not target:
    sys.exit(0)

subtask_id = target.get('subtask_id', '')
cmd_id     = target.get('cmd_id', '')
summary    = target.get('summary', '')

# ohariko.yaml に audit_request を書き込む
subprocess.run([
    'bash', os.path.join(script_dir, 'scripts', 'inbox_write.sh'),
    'ohariko',
    f'{subtask_id} の監査を依頼する（auto-trigger by stop_hook）。担当: {worker}。cmd: {cmd_id}。{summary[:60]}',
    'audit_request', 'stop_hook_auto'
], check=False)

# audit_triggered フラグを立てて roju_reports.yaml を更新
target['audit_triggered'] = True
tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(reports_path), suffix='.tmp')
try:
    with os.fdopen(tmp_fd, 'w') as f:
        yaml.dump(rdata, f, default_flow_style=False, allow_unicode=True, indent=2)
    os.replace(tmp_path, reports_path)
except Exception as e:
    try: os.unlink(tmp_path)
    except: pass
    print(f'[auto_trigger] ERROR: {e}', file=sys.stderr)
" 2>/dev/null &
    fi
fi

# ─── 5.5 コンパクション復帰検出 → identity情報注入 ───
# summaryの特徴的パターンでコンパクションを推定し、身元情報をblock理由に含める
if echo "$LAST_MSG" | grep -qiE 'エージェントの役割|コンパクション復帰|Summary生成時の必須事項|summary.*generated'; then
    IDENTITY=$(bash "$SCRIPT_DIR/scripts/identity_inject.sh" --agent-id "$AGENT_ID" 2>/dev/null || echo "")
    if [ -n "$IDENTITY" ]; then
        REASON="コンパクション復帰検出。${IDENTITY}"
        REASON_ESCAPED=$(echo "$REASON" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))" 2>/dev/null || echo "\"コンパクション復帰検出\"")
        echo "{\"decision\": \"block\", \"reason\": ${REASON_ESCAPED}}"
        exit 0
    fi
fi

# ─── 6. agent_idに応じたinboxファイル・未読検知 ───
INBOX_DIR="$SCRIPT_DIR/queue/inbox"
UNREAD=0

case "$AGENT_ID" in
    karo-roju)
        # 老中: roju_reports.yaml + roju_ohariko.yaml の実報告（stophook_notification除外）をカウント
        # stophook_notificationはinformationalな通知でkaro-rojuをblockすべきではない
        COUNT=$(python3 -c "
import yaml, os, sys
inbox_dir = '$INBOX_DIR'
count = 0
for fname in ['roju_reports.yaml', 'roju_ohariko.yaml']:
    fpath = os.path.join(inbox_dir, fname)
    if not os.path.exists(fpath):
        continue
    try:
        with open(fpath) as f:
            data = yaml.safe_load(f) or {}
        for key in ['reports', 'audit_reports', 'health_reports', 'preemptive_assignments']:
            for entry in (data.get(key) or []):
                if entry.get('read') == False and entry.get('subtask_id') != 'stophook_notification':
                    count += 1
    except Exception:
        pass
print(count)
" 2>/dev/null) || COUNT=0
        UNREAD=$((UNREAD + COUNT))
        INBOX_FILES="roju_reports.yaml, roju_ohariko.yaml"
        ;;
    ashigaru[1-8])
        # 足軽/部屋子: ashigaru{N}.yaml の tasks[].status == "assigned" をYAMLパースでカウント
        # NOTE: grep 'status: assigned' はfull_summary/description内の文字列を誤検知するため廃止
        NUM="${AGENT_ID#ashigaru}"
        INBOX_FILE="$INBOX_DIR/ashigaru${NUM}.yaml"
        if [ -f "$INBOX_FILE" ]; then
            UNREAD=$(python3 -c "
import yaml, sys
try:
    with open('$INBOX_FILE') as f:
        data = yaml.safe_load(f) or {}
    count = sum(1 for t in (data.get('tasks') or []) if t.get('status') == 'assigned')
    print(count)
except Exception:
    print(0)
" 2>/dev/null) || UNREAD=0
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
