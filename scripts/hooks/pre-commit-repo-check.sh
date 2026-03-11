#!/usr/bin/env bash
# pre-commit-repo-check.sh
# リポ誤爆防止フック: コミット先リポが割当タスクのプロジェクトと一致するか検証する
#
# 登録方法:
#   ln -sf /home/yasu/multi-agent-shogun/scripts/hooks/pre-commit-repo-check.sh \
#       /path/to/target-repo/.git/hooks/pre-commit
#   ※ 各リポの .git/hooks/pre-commit にシンボリックリンクを張る
#
# スキップ方法（緊急時）:
#   SKIP_REPO_CHECK=1 git commit -m "..."
#
# 設計方針:
#   - bash スクリプト1本。外部依存なし（grep/sed/awk のみ）
#   - 判定不能（inbox読めない、project不明等）の場合は commit を許可（false positive 回避）
#   - multi-agent-shogun リポ自体はチェック対象外（全プロジェクト共用）
#   - agent_id 取得失敗時もチェックスキップ

set -euo pipefail

SHOGUN_DIR="/home/yasu/multi-agent-shogun"
PROJECTS_YAML="${SHOGUN_DIR}/config/projects.yaml"
INBOX_DIR="${SHOGUN_DIR}/queue/inbox"

# 現在のリポのルートパスを取得（失敗時はスキップ）
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

# multi-agent-shogun リポ自体はチェック対象外（全プロジェクトで共用されるため）
[[ "$REPO_ROOT" == "$SHOGUN_DIR" ]] && exit 0

# projects.yaml が存在しない場合はスキップ
[[ ! -f "$PROJECTS_YAML" ]] && exit 0

# ─────────────────────────────────────────
# Step 1: agent_id 取得（環境変数 → tmux ペイン変数の順）
# ─────────────────────────────────────────
AGENT_ID="${AGENT_ID:-}"

if [[ -z "$AGENT_ID" ]] && [[ -n "${TMUX_PANE:-}" ]]; then
  AGENT_ID="$(tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}' 2>/dev/null)" || true
fi

# agent_id が取得できない場合はチェックスキップ
[[ -z "$AGENT_ID" ]] && exit 0

# ─────────────────────────────────────────
# Step 2: inbox YAML から現在進行中タスクの project を取得
# ─────────────────────────────────────────
INBOX_YAML="${INBOX_DIR}/${AGENT_ID}.yaml"

[[ ! -f "$INBOX_YAML" ]] && exit 0

# タスク項目は ^- で始まる（列0のダッシュ）
# フィールドは 2スペースインデント（notes の内容は 4スペース以上なので混入しない）
PROJECT="$(awk '
  /^- / {
    if ((blk_status == "in_progress" || blk_status == "assigned") && blk_project != "") {
      print blk_project
    }
    blk_status = ""; blk_project = ""
  }
  /^  status: / { blk_status = $2 }
  /^  project: / { blk_project = $2 }
  END {
    if ((blk_status == "in_progress" || blk_status == "assigned") && blk_project != "") {
      print blk_project
    }
  }
' "$INBOX_YAML" | tail -1)"

# project が取得できない場合はスキップ
[[ -z "$PROJECT" ]] && exit 0

# ─────────────────────────────────────────
# Step 3: projects.yaml から project の path を検索
# キー名一致 または パスの basename 一致で検索
# ─────────────────────────────────────────
EXPECTED_PATH="$(awk -v proj="$PROJECT" '
  # プロジェクトのトップレベルキー（2スペースインデント）を検出
  /^  [a-zA-Z]/ {
    key = $0
    gsub(/^  |:.*/, "", key)
    in_proj = (key == proj)
  }

  # キー名一致の場合: 4スペースインデントの path フィールドを取得
  in_proj && /^    path: / {
    val = $0
    gsub(/^    path: */, "", val)
    print val
    exit
  }

  # キー名不一致の場合: path の basename が project と一致するか確認
  !in_proj && /^    path: / {
    val = $0
    gsub(/^    path: */, "", val)
    n = split(val, a, "/")
    if (a[n] == proj) {
      print val
      exit
    }
  }
' "$PROJECTS_YAML")"

# expected_path が取得できない場合はスキップ（未登録プロジェクト等）
[[ -z "$EXPECTED_PATH" ]] && exit 0

# ─────────────────────────────────────────
# Step 4: 現在のリポパスと期待パスを比較
# ─────────────────────────────────────────
if [[ "$REPO_ROOT" != "$EXPECTED_PATH" ]]; then
  CURRENT_REMOTE="$(git remote get-url origin 2>/dev/null || echo "不明")"

  echo ""
  echo "⚠  リポ誤爆検出: project=${PROJECT} のタスクだが現在のリポが異なる"
  echo "   現在のリポ: ${REPO_ROOT}"
  echo "   リモートURL: ${CURRENT_REMOTE}"
  echo "   期待リポ:   ${EXPECTED_PATH}"
  echo "   正しいリポでコミットしているか確認せよ。"
  echo "   強制する場合: SKIP_REPO_CHECK=1 git commit ..."
  echo ""

  # 緊急スキップ
  [[ "${SKIP_REPO_CHECK:-}" == "1" ]] && exit 0

  exit 1
fi

exit 0
