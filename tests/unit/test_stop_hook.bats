#!/usr/bin/env bats
# ═══════════════════════════════════════════════════════════════
# test_stop_hook.bats — stop_hook_inbox.sh ユニットテスト
# ═══════════════════════════════════════════════════════════════
# 本番スクリプトをenv var overrideで呼び出してテストする。
#   __STOP_HOOK_SCRIPT_DIR → テスト用一時ディレクトリ
#   __STOP_HOOK_AGENT_ID   → tmux agent_id のモック
#
# テスト一覧:
#   T-001: stop_hook_active=true → exit 0
#   T-002: TMUX_PANE空 + __STOP_HOOK_AGENT_ID未設定 → exit 0
#   T-003: agent_id=shogun → exit 0
#   T-004: agent_id=ohariko → exit 0
#   T-005: 完了メッセージ → inbox_write呼び出し(report_completed)
#   T-006: エラーメッセージ → inbox_write呼び出し(error_report)
#   T-007: 中立メッセージ → inbox_write呼ばれない
#   T-008: karo-roju + 未読あり → block JSON
#   T-009: ashigaru1 + assigned あり → block JSON
#   T-010: ashigaru1 + assigned なし → exit 0

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/scripts/stop_hook_inbox.sh"

setup() {
    TEST_TMP="$(mktemp -d)"
    mkdir -p "$TEST_TMP/scripts"
    mkdir -p "$TEST_TMP/queue/inbox"

    # Mock inbox_write.sh — 引数をファイルにログ
    cat > "$TEST_TMP/scripts/inbox_write.sh" << 'MOCK'
#!/bin/bash
echo "$@" >> "$(dirname "$0")/../inbox_write_calls.log"
MOCK
    chmod +x "$TEST_TMP/scripts/inbox_write.sh"
}

teardown() {
    rm -rf "$TEST_TMP"
}

# Helper: 本番hookスクリプトをテストoverride付きで実行
run_hook() {
    local json="$1"
    local agent_id="${2:-ashigaru1}"
    __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
    __STOP_HOOK_AGENT_ID="$agent_id" \
    run bash "$HOOK_SCRIPT" <<< "$json"
}

# Helper: agent_id空で実行
run_hook_no_agent() {
    local json="$1"
    __STOP_HOOK_SCRIPT_DIR="$TEST_TMP" \
    __STOP_HOOK_AGENT_ID="" \
    run bash "$HOOK_SCRIPT" <<< "$json"
}

# ─── T-001 ───
@test "T-001: stop_hook_active=true → exit 0（全処理スキップ）" {
    run_hook '{"stop_hook_active": true, "last_assistant_message": "任務完了"}'
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# ─── T-002 ───
@test "T-002: agent_id空 → exit 0" {
    run_hook_no_agent '{"stop_hook_active": false}'
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# ─── T-003 ───
@test "T-003: agent_id=shogun → exit 0" {
    run_hook '{"stop_hook_active": false, "last_assistant_message": "任務完了"}' "shogun"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# ─── T-004 ───
@test "T-004: agent_id=ohariko → exit 0" {
    run_hook '{"stop_hook_active": false, "last_assistant_message": "監査完了"}' "ohariko"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# ─── T-005 ───
@test "T-005: 完了メッセージ → inbox_write呼び出し(report_completed)" {
    run_hook '{"stop_hook_active": false, "last_assistant_message": "任務完了でござる。報告YAML更新済み。"}'
    [ "$status" -eq 0 ]
    # background processの完了を待つ
    sleep 1
    [ -f "$TEST_TMP/inbox_write_calls.log" ]
    grep -q "roju_reports" "$TEST_TMP/inbox_write_calls.log"
    grep -q "report_completed" "$TEST_TMP/inbox_write_calls.log"
    grep -q "ashigaru1" "$TEST_TMP/inbox_write_calls.log"
}

# ─── T-006 ───
@test "T-006: エラーメッセージ → inbox_write呼び出し(error_report)" {
    run_hook '{"stop_hook_active": false, "last_assistant_message": "ファイルが見つからない。エラーで中断する。"}'
    [ "$status" -eq 0 ]
    sleep 1
    [ -f "$TEST_TMP/inbox_write_calls.log" ]
    grep -q "roju_reports" "$TEST_TMP/inbox_write_calls.log"
    grep -q "error_report" "$TEST_TMP/inbox_write_calls.log"
}

# ─── T-007 ───
@test "T-007: 中立メッセージ → inbox_write呼ばれない" {
    run_hook '{"stop_hook_active": false, "last_assistant_message": "待機する。次の指示を待つ。"}'
    [ "$status" -eq 0 ]
    sleep 1
    [ ! -f "$TEST_TMP/inbox_write_calls.log" ]
}

# ─── T-008 ───
@test "T-008: karo-roju + 未読あり → block JSON" {
    cat > "$TEST_TMP/queue/inbox/roju_reports.yaml" << 'YAML'
reports:
  - subtask_id: subtask_999
    worker: ashigaru1
    status: completed
    summary: "テスト報告"
    read: false
YAML
    run_hook '{"stop_hook_active": false, "last_assistant_message": ""}' "karo-roju"
    [ "$status" -eq 0 ]
    echo "$output" | grep -q '"decision"'
    echo "$output" | grep -q '"block"'
}

# ─── T-009 ───
@test "T-009: ashigaru1 + assigned あり → block JSON" {
    cat > "$TEST_TMP/queue/inbox/ashigaru1.yaml" << 'YAML'
tasks:
  - subtask_id: subtask_999
    cmd_id: cmd_999
    status: assigned
    notes: "テストタスク"
YAML
    run_hook '{"stop_hook_active": false, "last_assistant_message": ""}' "ashigaru1"
    [ "$status" -eq 0 ]
    echo "$output" | grep -q '"decision"'
    echo "$output" | grep -q '"block"'
}

# ─── T-010 ───
@test "T-010: ashigaru1 + assigned なし → exit 0" {
    cat > "$TEST_TMP/queue/inbox/ashigaru1.yaml" << 'YAML'
tasks:
  - subtask_id: subtask_999
    cmd_id: cmd_999
    status: done
    notes: "完了済みタスク"
YAML
    run_hook '{"stop_hook_active": false, "last_assistant_message": ""}' "ashigaru1"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}
