#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# shutsujin_departure.sh — 出陣時環境変数セットアップ
# ═══════════════════════════════════════════════════════════════
# worktreeモードで足軽が作業する際に、DB/YAML/contextへの
# 絶対パス参照を保証するための基盤環境変数を設定する。
#
# Usage: source scripts/shutsujin_departure.sh
#        または tmux環境変数として set-environment で設定
# ═══════════════════════════════════════════════════════════════

export SHOGUN_ROOT=/home/yasu/multi-agent-shogun
