#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# inbox_read.sh — YAML inbox 読み取り + Drain-on-Read (v3)
# ═══════════════════════════════════════════════════════════════
# Usage:
#   scripts/inbox_read.sh <inbox_name> [options]
#
# Arguments:
#   inbox_name    読み取り対象 (roju_reports / roju_ohariko / ashigaru1 / ...)
#
# Options:
#   --unread-only     未読 (read:false) のみ表示
#   --mark-read       表示したエントリを read:true に更新
#   --drain           read:true かつ DB永続化済みエントリを削除
#   --dry-run         --drain / --mark-read の実削除をスキップして表示のみ
#   --format FORMAT   出力形式: summary|yaml|json (デフォルト: summary)
#   --no-lock         排他ロックを取得しない（テスト用）
#
# Exit codes:
#   0 = 成功 (エントリあり)
#   1 = エントリなし
#   2 = エラー
#
# セクションマッピング:
#   roju_reports  → reports
#   roju_ohariko  → audit_queue
#   ashigaru{N}   → tasks (その他も tasks)
#
# 排他制御: flock -w 5 (5秒タイムアウト、最大3回リトライ)
# atomic write: tmpfile + os.replace (部分書き込み防止)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# REPO_ROOT: リポジトリルート（inbox YAML / DB CLIの基準パス）
REPO_ROOT="${__STOP_HOOK_SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# PY_READER: inbox_read.py は常に自スクリプトと同じディレクトリ
PY_READER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/inbox_read.py"
# 環境変数 SCRIPT_DIR は Python 側に渡すリポジトリルート
SCRIPT_DIR="$REPO_ROOT"

# ─── 引数解析 ────────────────────────────────────────────────────────────────

INBOX_NAME=""
FORMAT="summary"
UNREAD_ONLY="false"
MARK_READ="false"
DRAIN="false"
DRY_RUN="false"
NO_LOCK="false"

for arg in "$@"; do
  case "$arg" in
    --unread-only) UNREAD_ONLY="true" ;;
    --mark-read)   MARK_READ="true" ;;
    --drain)       DRAIN="true" ;;
    --dry-run)     DRY_RUN="true" ;;
    --no-lock)     NO_LOCK="true" ;;
    --format=*)    FORMAT="${arg#--format=}" ;;
    --format)      : ;; # handled by next arg — not supported (use --format=xxx)
    -*)
      echo "Unknown option: $arg" >&2
      echo "Usage: $0 <inbox_name> [--unread-only] [--mark-read] [--drain] [--dry-run] [--format=summary|yaml|json]" >&2
      exit 2
      ;;
    *)
      if [ -z "$INBOX_NAME" ]; then
        INBOX_NAME="$arg"
      else
        echo "Unexpected argument: $arg" >&2
        exit 2
      fi
      ;;
  esac
done

if [ -z "$INBOX_NAME" ]; then
  echo "Usage: $0 <inbox_name> [options]" >&2
  exit 2
fi

# ─── セクションマッピング ──────────────────────────────────────────────────────

case "$INBOX_NAME" in
  roju_reports)  SECTION_KEY="reports" ;;
  roju_ohariko)  SECTION_KEY="audit_queue" ;;
  *)             SECTION_KEY="tasks" ;;
esac

INBOX_FILE="$REPO_ROOT/queue/inbox/${INBOX_NAME}.yaml"
LOCKFILE="${INBOX_FILE}.lock"

if [ ! -f "$INBOX_FILE" ]; then
  echo "ERROR: $INBOX_FILE が見つかりません" >&2
  exit 2
fi

# ─── 実行（flock排他制御）────────────────────────────────────────────────────

run_reader() {
  INBOX_FILE="$INBOX_FILE" \
  SECTION_KEY="$SECTION_KEY" \
  FORMAT="$FORMAT" \
  UNREAD_ONLY="$UNREAD_ONLY" \
  MARK_READ="$MARK_READ" \
  DRAIN="$DRAIN" \
  DRY_RUN="$DRY_RUN" \
  SCRIPT_DIR="$SCRIPT_DIR" \
  python3 "$PY_READER"
}

if [ "$NO_LOCK" = "true" ]; then
  run_reader
  exit $?
fi

# flock 排他制御 (最大3回リトライ)
attempt=0
max_attempts=3

while [ $attempt -lt $max_attempts ]; do
  if (
    flock -w 5 200 || exit 1
    run_reader
  ) 200>"$LOCKFILE"; then
    exit $?
  else
    LAST_EXIT=$?
    attempt=$((attempt + 1))
    if [ $attempt -lt $max_attempts ]; then
      sleep 1
    else
      echo "[inbox_read] flock取得失敗 ($max_attempts 回試行) for $INBOX_FILE" >&2
      exit 2
    fi
  fi
done
