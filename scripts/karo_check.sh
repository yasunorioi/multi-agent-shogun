#!/usr/bin/env bash
# karo_check.sh — 家老の「ファイル未存在」誤判定防止ツール (cmd_573 S4 / subtask_1210)
# 読み取り専用。副作用なし（ファイル/DB書き込み一切なし）
#
# 使い方:
#   bash scripts/karo_check.sh exists <keyword>   # 全サブディレクトリ横断検索
#   bash scripts/karo_check.sh path <path>         # ファイル/ディレクトリ存在確認
#   bash scripts/karo_check.sh history <pattern>   # 削除commitを追跡
#   bash scripts/karo_check.sh help                # この使い方を表示

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

cmd="${1:-help}"

case "$cmd" in

  exists)
    keyword="${2:-}"
    if [[ -z "$keyword" ]]; then
      echo "Usage: $0 exists <keyword>" >&2
      exit 1
    fi
    echo "=== [1] scripts/ 全サブディレクトリ横断検索 (*.py / *.sh) ==="
    find "$REPO_ROOT/scripts" \( -name "*.py" -o -name "*.sh" \) 2>/dev/null \
      | xargs grep -l "$keyword" 2>/dev/null \
      || echo "  (ヒットなし)"

    echo ""
    echo "=== [2] リポジトリ全体でファイル名検索 ==="
    find "$REPO_ROOT" -not -path "*/.git/*" -name "*${keyword}*" 2>/dev/null \
      || echo "  (ヒットなし)"

    echo ""
    echo "=== [3] git commit 履歴 (oneline) ==="
    git -C "$REPO_ROOT" log --all --oneline 2>/dev/null \
      | grep -i "$keyword" \
      || echo "  (ヒットなし)"
    ;;

  path)
    target="${2:-}"
    if [[ -z "$target" ]]; then
      echo "Usage: $0 path <path>" >&2
      exit 1
    fi
    # 絶対パスでなければリポジトリルートからの相対として解釈
    if [[ "$target" != /* ]]; then
      target="$REPO_ROOT/$target"
    fi

    echo "=== [1] ファイル/ディレクトリ存在確認 ==="
    if [[ -e "$target" ]]; then
      echo "  EXISTS: $target"
      ls -la "$target"
    else
      echo "  NOT FOUND: $target"
    fi

    echo ""
    echo "=== [2] git ls-files 確認 (追跡済みファイル) ==="
    rel="${target#$REPO_ROOT/}"
    git -C "$REPO_ROOT" ls-files "$rel" 2>/dev/null \
      | grep -c "" | read -r cnt || cnt=0
    git -C "$REPO_ROOT" ls-files "$rel" 2>/dev/null \
      && echo "  (上記が git 追跡済みファイル)" \
      || echo "  (git 追跡なし / 未コミット or 存在しない)"

    echo ""
    echo "=== [3] 削除ファイル追跡 (diff-filter=D) ==="
    git -C "$REPO_ROOT" log --diff-filter=D --name-only --pretty=format: -- "$rel" 2>/dev/null \
      | grep -v '^$' \
      || echo "  (削除履歴なし)"
    ;;

  history)
    pattern="${2:-}"
    if [[ -z "$pattern" ]]; then
      echo "Usage: $0 history <pattern>" >&2
      exit 1
    fi
    echo "=== [1] 削除されたファイル一覧 (diff-filter=D) ==="
    git -C "$REPO_ROOT" log --diff-filter=D --name-only --pretty=format: 2>/dev/null \
      | sort -u \
      | grep -i "$pattern" \
      || echo "  (ヒットなし)"

    echo ""
    echo "=== [2] 削除commitの詳細 ==="
    git -C "$REPO_ROOT" log --diff-filter=D --name-only --oneline 2>/dev/null \
      | grep -B1 "$pattern" \
      || echo "  (ヒットなし)"
    ;;

  help|--help|-h)
    cat <<'EOF'
karo_check.sh — 家老の「ファイル未存在」誤判定防止ツール

【使い方】
  bash scripts/karo_check.sh exists <keyword>
      scripts/ 配下の全 .py/.sh ファイルを横断検索し、keyword を含むファイルを列挙。
      git commit 履歴でも検索する。
      例: bash scripts/karo_check.sh exists crystallize

  bash scripts/karo_check.sh path <path>
      ファイル/ディレクトリの存在・git追跡状態・削除履歴を確認。
      例: bash scripts/karo_check.sh path scripts/botsu/crystallize.py

  bash scripts/karo_check.sh history <pattern>
      削除されたファイルを git log --diff-filter=D で追跡。
      例: bash scripts/karo_check.sh history crystall

  bash scripts/karo_check.sh help
      この使い方を表示。

【注意】
  - 読み取り専用。ファイル/DB書き込みは一切行わない。
  - リポジトリルートから実行することを推奨。
  - cmd_570教訓: 「ls の表面検索だけで未存在と断定するな」

【関連】
  context/karo-checklist.md  — チェックリスト文書 (第二層)
  docs/shogun/crystallize_v2_doc_design_20260502.md §4  — 三層設計背景
EOF
    ;;

  *)
    echo "Unknown command: $cmd" >&2
    echo "Run: $0 help" >&2
    exit 1
    ;;

esac
