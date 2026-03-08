#!/usr/bin/env bash
# gatekeeper_f006.sh - F006 Gatekeeper: GitHub操作の事前ブロック
#
# Claude Code PreToolUse hookとして動作する。
# Bashツール実行前にF006禁止パターンをチェックし、違反コマンドをブロックする。
#
# 検出対象:
#   gh issue create / gh pr create
#   gh issue comment / gh pr comment / gh pr review
#   gh release create
#   gh api + POST + issues/pulls/comments
#
# fail-closed設計: 判定不能時はブロック側に倒す

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_CHECKER="$SCRIPT_DIR/gatekeeper_f006.py"

INPUT=$(cat)

# Python checkerを実行
RESULT=$(echo "$INPUT" | python3 "$PY_CHECKER" 2>/dev/null)
PY_EXIT=$?

# python3 実行失敗 → fail-closed (block)
if [ $PY_EXIT -ne 0 ]; then
    python3 -c "
import json
print(json.dumps({
    'decision': 'block',
    'reason': 'F006 Gatekeeper: チェックスクリプトのエラーにより安全のためブロック。'
}))
"
    exit 0
fi

# blockメッセージがあれば出力
if [ -n "$RESULT" ]; then
    echo "$RESULT"
fi

exit 0
