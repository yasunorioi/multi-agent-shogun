#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# inbox_write.sh — YAML inbox への安全書き込みユーティリティ
# ═══════════════════════════════════════════════════════════════
# Usage: bash scripts/inbox_write.sh <target_inbox> <content> [type] [from]
# Example: bash scripts/inbox_write.sh roju_reports "ashigaru1完了" report_completed ashigaru1
#
# 書き込み先: queue/inbox/{target_inbox}.yaml の reports:[] セクション
# 排他制御: flock -w 5（5秒タイムアウト、最大3回リトライ）
# atomic write: tmpfile + os.replace（部分読み取り防止）
# オーバーフロー保護: stophook_notification type の50件超を刈り込み
#
# Environment:
#   __STOP_HOOK_SCRIPT_DIR — override for testing (default: auto-detect)
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="${__STOP_HOOK_SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TARGET="$1"
CONTENT="$2"
TYPE="${3:-wake_up}"
FROM="${4:-unknown}"

INBOX="$SCRIPT_DIR/queue/inbox/${TARGET}.yaml"
LOCKFILE="${INBOX}.lock"

# Validate arguments
if [ -z "$TARGET" ] || [ -z "$CONTENT" ]; then
    echo "Usage: inbox_write.sh <target_inbox> <content> [type] [from]" >&2
    exit 1
fi

# Initialize inbox if not exists
if [ ! -f "$INBOX" ]; then
    mkdir -p "$(dirname "$INBOX")"
    echo "reports: []" > "$INBOX"
fi

TIMESTAMP=$(date "+%Y-%m-%dT%H:%M:%S")

# Atomic write with flock (3 retries)
attempt=0
max_attempts=3

while [ $attempt -lt $max_attempts ]; do
    if (
        flock -w 5 200 || exit 1

        python3 -c "
import yaml, sys, os, tempfile

inbox_path = '$INBOX'
timestamp = '$TIMESTAMP'
content = '''$CONTENT'''
msg_type = '$TYPE'
from_agent = '$FROM'

try:
    with open(inbox_path) as f:
        data = yaml.safe_load(f)

    if not data:
        data = {}
    if not data.get('reports'):
        data['reports'] = []

    new_entry = {
        'subtask_id': 'stophook_notification',
        'worker': from_agent,
        'status': 'notification',
        'reported_at': timestamp,
        'summary': content,
        'type': msg_type,
        'read': False
    }
    data['reports'].append(new_entry)

    # Overflow protection: keep max 50 stophook_notification entries
    notifications = [r for r in data['reports'] if r.get('subtask_id') == 'stophook_notification']
    if len(notifications) > 50:
        others = [r for r in data['reports'] if r.get('subtask_id') != 'stophook_notification']
        # Keep newest 50 notifications (by position = by time)
        kept_notifs = notifications[-50:]
        data['reports'] = others + kept_notifs

    # Atomic write: tmp file + rename
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(inbox_path), suffix='.tmp')
    try:
        with os.fdopen(tmp_fd, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, indent=2)
        os.replace(tmp_path, inbox_path)
    except:
        os.unlink(tmp_path)
        raise

except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" || exit 1

    ) 200>"$LOCKFILE"; then
        exit 0
    else
        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            sleep 1
        else
            echo "[inbox_write] Failed to acquire lock after $max_attempts attempts for $INBOX" >&2
            exit 1
        fi
    fi
done
