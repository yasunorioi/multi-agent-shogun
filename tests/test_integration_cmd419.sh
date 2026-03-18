#!/usr/bin/env bash
# tests/test_integration_cmd419.sh
# cmd_419 W1-W6 統合テスト (subtask_928/cmd_419 W7-a再)
# 実行: bash tests/test_integration_cmd419.sh
# 全テスト PASS で exit 0、1件でも FAIL で exit 1

set -euo pipefail
export LANG=ja_JP.utf8
cd "$(dirname "$0")/.."

PASS=0
FAIL=0
RESULTS=()

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); RESULTS+=("PASS: $1"); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); RESULTS+=("FAIL: $1"); }

echo "========================================"
echo " cmd_419 統合テスト (subtask_928)"
echo "========================================"
echo ""

# ── 1. 既存CLIサブコマンド ─────────────────────
echo "[1] 既存CLIサブコマンド動作確認"

out=$(python3 scripts/botsunichiroku.py cmd list --status in_progress 2>&1)
if echo "$out" | grep -qE "cmd_[0-9]+"; then
  pass "cmd list --status in_progress (cmd行確認)"
else
  fail "cmd list --status in_progress"
fi

out=$(python3 scripts/botsunichiroku.py subtask list --cmd cmd_419 2>&1)
if echo "$out" | grep -q "subtask_913"; then
  pass "subtask list --cmd cmd_419 (subtask_913確認)"
else
  fail "subtask list --cmd cmd_419"
fi

out=$(python3 scripts/botsunichiroku.py report list --subtask subtask_913 2>&1)
if echo "$out" | grep -q "subtask_913"; then
  pass "report list --subtask subtask_913"
else
  fail "report list --subtask subtask_913"
fi

out=$(python3 scripts/botsunichiroku.py stats 2>&1)
if echo "$out" | grep -q "コマンド:"; then
  pass "stats (コマンド件数表示確認)"
else
  fail "stats"
fi

out=$(python3 scripts/botsunichiroku.py audit list --all 2>&1)
if echo "$out" | grep -q "subtask_"; then
  pass "audit list --all (subtask行確認)"
else
  fail "audit list --all"
fi

echo ""

# ── 2. searchサブコマンド ─────────────────────
echo "[2] searchサブコマンド動作確認"

out=$(python3 scripts/botsunichiroku.py search "WireGuard" 2>&1)
hits=$(echo "$out" | grep "Total hits:" | grep -oP '\d+' | head -1)
if [ "${hits:-0}" -ge 1 ] 2>/dev/null; then
  pass "search WireGuard (${hits}件ヒット)"
else
  fail "search WireGuard (ヒットなし)"
fi

out=$(python3 scripts/botsunichiroku.py search "MQTT" --project uecs-llm 2>&1)
hits=$(echo "$out" | grep "Total hits:" | grep -oP '\d+' | head -1)
if [ "${hits:-0}" -ge 1 ] 2>/dev/null; then
  pass "search MQTT --project uecs-llm (${hits}件ヒット)"
else
  fail "search MQTT --project uecs-llm (ヒットなし)"
fi

out=$(python3 scripts/botsunichiroku.py search --similar subtask_913 2>&1)
if echo "$out" | grep -q "Results:"; then
  pass "search --similar subtask_913 (Results行確認)"
else
  fail "search --similar subtask_913"
fi

out=$(python3 scripts/botsunichiroku.py search --enrich cmd_419 2>&1)
if echo "$out" | grep -q "Internal hits"; then
  pass "search --enrich cmd_419 (Internal hits確認)"
else
  fail "search --enrich cmd_419"
fi

echo ""

# ── 3. checkサブコマンド ──────────────────────
echo "[3] checkサブコマンド動作確認"

out=$(python3 scripts/botsunichiroku.py check orphans 2>&1)
if echo "$out" | grep -qE "ORPHANS_FOUND|ORPHANS_CLEAN"; then
  pass "check orphans (ORPHANS_FOUND/CLEAN確認)"
else
  fail "check orphans"
fi

out=$(python3 scripts/botsunichiroku.py check coverage cmd_419 2>&1)
if echo "$out" | grep -q "Coverage ratio:"; then
  pass "check coverage cmd_419 (Coverage ratio確認)"
else
  fail "check coverage cmd_419"
fi

echo ""

# ── 4. FTS5インクリメンタル更新 ──────────────
echo "[4] FTS5インクリメンタル更新テスト"

# dashboard addしてsearch_indexに即反映されるか確認
add_out=$(python3 scripts/botsunichiroku.py dashboard add test "統合テスト928_FTS5即時更新確認" --cmd cmd_419 --status active 2>&1)
entry_id=$(echo "$add_out" | grep -oP '#\K\d+')
if [ -z "$entry_id" ]; then
  fail "dashboard add (entry_id取得失敗)"
else
  pass "dashboard add (entry_id=${entry_id})"

  # 即時search確認
  search_out=$(python3 scripts/botsunichiroku.py search "統合テスト928" 2>&1)
  hits=$(echo "$search_out" | grep "Total hits:" | grep -oP '\d+' | head -1)
  if [ "${hits:-0}" -ge 1 ] 2>/dev/null; then
    pass "FTS5インクリメンタル更新: search '統合テスト928' 即時ヒット (${hits}件)"
  else
    fail "FTS5インクリメンタル更新: search '統合テスト928' ヒットなし"
  fi

  # テストデータ削除
  python3 -c "
import sqlite3
conn = sqlite3.connect('data/botsunichiroku.db')
conn.execute(\"DELETE FROM search_index WHERE source_id=?\", ('${entry_id}',))
conn.execute(\"DELETE FROM dashboard_entries WHERE id=?\", (${entry_id},))
conn.commit(); conn.close()
" 2>/dev/null && pass "テストデータ削除 (entry_id=${entry_id})"
fi

echo ""

# ── 5. 2ch DAT表示 ────────────────────────────
echo "[5] 2ch DAT表示テスト"

out=$(python3 scripts/botsunichiroku_2ch.py cmd_419 2>&1)
if echo "$out" | grep -q "管理板.*cmd_419" && echo "$out" | grep -q "◆ROJU"; then
  pass "2ch cmd_419スレッド (管理板ヘッダ+◆ROJU確認)"
else
  fail "2ch cmd_419スレッド"
fi

out=$(python3 scripts/botsunichiroku_2ch.py --board kanri --limit 5 2>&1)
if echo "$out" | grep -q "管理板.*スレッド一覧" && echo "$out" | grep -q "cmd_419"; then
  pass "--board kanri (スレッド一覧+cmd_419確認)"
else
  fail "--board kanri"
fi

out=$(python3 scripts/botsunichiroku_2ch.py --board dreams 2>&1)
if [[ "$out" == *"夢見板"* ]] && [[ "$out" == *"◆BAKU"* ]]; then
  pass "--board dreams (夢見板+◆BAKU確認)"
else
  fail "--board dreams"
fi

out=$(python3 scripts/botsunichiroku_2ch.py --board docs 2>&1)
if echo "$out" | grep -q "書庫板"; then
  pass "--board docs (書庫板ヘッダ確認)"
else
  fail "--board docs"
fi

out=$(python3 scripts/botsunichiroku_2ch.py --board diary 2>&1)
if echo "$out" | grep -q "日記板"; then
  pass "--board diary (日記板ヘッダ確認)"
else
  fail "--board diary"
fi

out=$(python3 scripts/botsunichiroku_2ch.py --board audit 2>&1)
if echo "$out" | grep -q "監査板"; then
  pass "--board audit (監査板ヘッダ確認)"
else
  fail "--board audit"
fi

echo ""

# ── 6. Docker不要確認 ────────────────────────
echo "[6] Docker不要確認"

if docker ps 2>/dev/null | grep -q kousatsu; then
  fail "kousatsuコンテナが起動中（Docker依存あり）"
else
  pass "kousatsuコンテナなし（Docker不要確認）"
fi

if curl -s --max-time 2 http://localhost:8080/health >/dev/null 2>&1; then
  fail "localhost:8080が応答（高札Docker稼働中）"
else
  pass "localhost:8080未応答（高札Dockerダウン確認）"
fi

echo ""

# ── サマリ ────────────────────────────────────
echo "========================================"
echo " テスト結果サマリ"
echo "========================================"
for r in "${RESULTS[@]}"; do
  echo "  $r"
done
echo ""
echo "  PASS: ${PASS}  FAIL: ${FAIL}"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
  echo "  NG: ${FAIL}件のテストが失敗"
  exit 1
else
  echo "  全テスト PASS"
  exit 0
fi
