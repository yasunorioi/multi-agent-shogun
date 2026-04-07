#!/bin/bash
# kanjou_auto_review.sh — 勘定吟味役の自動レビュートリガー
#
# agent-swarm notify.py の NOTIFY_EXEC から呼ばれる。
# kenshu板に1Fが投稿した時、自動でkanjou_ginmiyaku.py reviewを実行。
#
# 環境変数(notify.py exec_notify()が設定):
#   SWARM_THREAD_ID  スレッドID
#   SWARM_BOARD      板名
#   SWARM_AUTHOR     投稿者ID
#   SWARM_MESSAGE    メッセージ本文

set -euo pipefail

LOG="/tmp/kanjou_auto_review.log"
SHOGUN_DIR="/home/yasu/multi-agent-shogun"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] board=${SWARM_BOARD} thread=${SWARM_THREAD_ID} author=${SWARM_AUTHOR}" >> "$LOG"

# kenshu板の1F投稿のみ自動レビュー
if [ "${SWARM_BOARD}" = "kenshu" ]; then
    cd "$SHOGUN_DIR"
    python3 scripts/kanjou_ginmiyaku.py review --thread "${SWARM_THREAD_ID}" >> "$LOG" 2>&1 || true
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] review完了 thread=${SWARM_THREAD_ID}" >> "$LOG"
fi
