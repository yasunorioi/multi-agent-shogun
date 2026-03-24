#!/usr/bin/env bats
# ═══════════════════════════════════════════════════════════════
# e2e_stop_hook.bats — Stop Hook + inbox_write E2Eテスト
# ═══════════════════════════════════════════════════════════════
# E2E-001: inbox_write.sh 基本動作
# E2E-002: 排他制御（並列2プロセス書き込み）
# E2E-003: オーバーフロー保護
# E2E-004: Stop Hook → inbox_write → karo検知フロー

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/scripts/stop_hook_inbox.sh"
INBOX_WRITE="$SCRIPT_DIR/scripts/inbox_write.sh"

setup() {
    TEST_TMP="$(mktemp -d)"
    mkdir -p "$TEST_TMP/scripts"
    mkdir -p "$TEST_TMP/queue/inbox"

    # inbox_write.shの本番コピー（SCRIPT_DIRをoverrideで使う）
    cp "$INBOX_WRITE" "$TEST_TMP/scripts/inbox_write.sh"
    chmod +x "$TEST_TMP/scripts/inbox_write.sh"
}

teardown() {
    rm -rf "$TEST_TMP"
}

# ─── E2E-001 ───
@test "E2E-001: inbox_write.sh 基本動作（roju_reports.yamlに書き込み）" {
    # 空のinboxを作成
    echo "reports: []" > "$TEST_TMP/queue/inbox/roju_reports.yaml"

    # inbox_write実行
    __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
    bash "$INBOX_WRITE" roju_reports "テスト通知メッセージ" "report_completed" "ashigaru1"

    # 書き込み確認
    [ -f "$TEST_TMP/queue/inbox/roju_reports.yaml" ]
    grep -q "stophook_notification" "$TEST_TMP/queue/inbox/roju_reports.yaml"
    grep -q "テスト通知メッセージ" "$TEST_TMP/queue/inbox/roju_reports.yaml"
    grep -q "report_completed" "$TEST_TMP/queue/inbox/roju_reports.yaml"
    grep -q "ashigaru1" "$TEST_TMP/queue/inbox/roju_reports.yaml"
    grep -q "read: false" "$TEST_TMP/queue/inbox/roju_reports.yaml"
}

# ─── E2E-002 ───
@test "E2E-002: 排他制御（並列2プロセス書き込み、データ破損なし）" {
    echo "reports: []" > "$TEST_TMP/queue/inbox/roju_reports.yaml"

    # 並列に2プロセス書き込み
    __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
    bash "$INBOX_WRITE" roju_reports "並列書き込み1" "report_completed" "ashigaru1" &
    PID1=$!

    __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
    bash "$INBOX_WRITE" roju_reports "並列書き込み2" "report_completed" "ashigaru2" &
    PID2=$!

    wait $PID1
    wait $PID2

    # YAML が壊れていないことを確認（python3でパース可能）
    python3 -c "
import yaml
with open('$TEST_TMP/queue/inbox/roju_reports.yaml') as f:
    data = yaml.safe_load(f)
assert data is not None
reports = data.get('reports', [])
assert len(reports) == 2, f'Expected 2 reports, got {len(reports)}'
print('OK: 2 reports, no corruption')
"
}

# ─── E2E-003 ───
@test "E2E-003: オーバーフロー保護（51件書き込み後、notification 50件以下）" {
    echo "reports: []" > "$TEST_TMP/queue/inbox/roju_reports.yaml"

    # 51件書き込み
    for i in $(seq 1 51); do
        __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
        bash "$INBOX_WRITE" roju_reports "通知${i}" "report_completed" "ashigaru1"
    done

    # notification件数が50以下であること
    COUNT=$(python3 -c "
import yaml
with open('$TEST_TMP/queue/inbox/roju_reports.yaml') as f:
    data = yaml.safe_load(f)
reports = data.get('reports', [])
notifications = [r for r in reports if r.get('subtask_id') == 'stophook_notification']
print(len(notifications))
")
    [ "$COUNT" -le 50 ]
}

# ─── E2E-004 ───
@test "E2E-004: Stop Hook → inbox_write → karo検知フロー" {
    # 空のinboxを準備
    echo "reports: []" > "$TEST_TMP/queue/inbox/roju_reports.yaml"
    cat > "$TEST_TMP/queue/inbox/ashigaru1.yaml" << 'YAML'
tasks:
  - subtask_id: subtask_999
    status: done
YAML

    # Stop Hook実行（完了メッセージ付き、未読inboxなし）
    __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
    __STOP_HOOK_AGENT_ID="ashigaru1" \
    run bash "$HOOK_SCRIPT" <<< '{"stop_hook_active": false, "last_assistant_message": "任務完了でござる。報告YAML更新済み。"}'

    [ "$status" -eq 0 ]
    # inbox未読なしなのでblockされない
    [ -z "$output" ]

    # background inbox_writeの完了を待つ
    sleep 2

    # inbox_writeによってroju_reports.yamlに通知が書き込まれたか確認
    grep -q "stophook_notification" "$TEST_TMP/queue/inbox/roju_reports.yaml"
    grep -q "report_completed" "$TEST_TMP/queue/inbox/roju_reports.yaml"
    grep -q "ashigaru1" "$TEST_TMP/queue/inbox/roju_reports.yaml"

    # 老中がこの未読を検知できることを確認
    __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
    __STOP_HOOK_AGENT_ID="karo-roju" \
    run bash "$HOOK_SCRIPT" <<< '{"stop_hook_active": false, "last_assistant_message": ""}'

    [ "$status" -eq 0 ]
    echo "$output" | grep -q '"block"'
}
