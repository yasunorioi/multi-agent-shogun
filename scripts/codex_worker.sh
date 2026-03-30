#!/usr/bin/env bash
# scripts/codex_worker.sh — Codex足軽ワーカー
#
# notify_exec フックから呼び出される。環境変数でコンテキストを受け取る。
#
# 環境変数:
#   SWARM_THREAD_ID — 任務スレッドID（必須）
#   SWARM_BOARD     — 板名（デフォルト: ninmu）
#   SWARM_AUTHOR    — 投稿者 (roju)
#   SWARM_MESSAGE   — 投稿本文（タスク指示）
#
# 二重起動防止: flock で /tmp/codex_worker_<thread_id>.lock を排他制御

set -euo pipefail

# ─── 設定 ─────────────────────────────────────────────────
CODEX_MODEL="${CODEX_MODEL:-gpt-4.1}"
WORKDIR="${CODEX_WORKDIR:-/home/yasu/multi-agent-shogun}"
AGENT_SWARM_DIR="/home/yasu/agent-swarm"
AGENT_ID="codex_ashigaru"

# ─── APIキー読み込み ───────────────────────────────────────
source_key() {
    local envfile="${HOME}/.config/env/openai.env"
    if [[ -f "$envfile" ]]; then
        # 形式: OPEN_AI="sk-proj-..." または OPEN_AI=sk-proj-...
        local raw
        raw=$(grep '^OPEN_AI=' "$envfile" 2>/dev/null | head -1) || true
        if [[ -n "$raw" ]]; then
            # ダブルクォート除去
            export CODEX_API_KEY
            CODEX_API_KEY=$(echo "$raw" | cut -d= -f2- | tr -d '"'"'")
        fi
    fi
}

# ─── BBS POST ヘルパー ─────────────────────────────────────
post_reply() {
    local thread_id="$1" board="$2" body="$3"
    python3 "${AGENT_SWARM_DIR}/server/cli.py" reply add \
        "$thread_id" \
        --agent "$AGENT_ID" \
        --board "$board" \
        --body "$body" \
        2>/dev/null || true  # BBS POST失敗はワーカー失敗にしない
}

# ─── メイン ───────────────────────────────────────────────
main() {
    local thread_id="${SWARM_THREAD_ID:?SWARM_THREAD_ID is required}"
    local board="${SWARM_BOARD:-ninmu}"
    local message="${SWARM_MESSAGE:?SWARM_MESSAGE is required}"

    # ログディレクトリ作成
    local logdir="${WORKDIR}/logs/codex"
    mkdir -p "$logdir"
    local logfile="${logdir}/$(date +%Y%m%d_%H%M%S)_${thread_id}.log"

    # stdout/stderr をログファイルにリダイレクト（notify.pyのopen()は既にリダイレクト済みだが念のため）
    exec >> "$logfile" 2>&1

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] codex_worker start: thread=${thread_id} board=${board}"

    # 二重起動防止（flock）
    local lockfile="/tmp/codex_worker_${thread_id}.lock"
    exec 9>"$lockfile"
    if ! flock -n 9; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 既に実行中 (thread=${thread_id})。スキップ。"
        exit 0
    fi

    # APIキー取得
    source_key
    if [[ -z "${CODEX_API_KEY:-}" ]]; then
        echo "[ERROR] CODEX_API_KEY未設定"
        post_reply "$thread_id" "$board" \
            "[error] Codex足軽: CODEX_API_KEY未設定。~/.config/env/openai.env を確認せよ。"
        exit 1
    fi

    # タスク抽出: "@codex_ashigaru " 以降をタスクとして扱う
    local task
    task=$(printf '%s' "$message" | sed 's/.*@codex_ashigaru[[:space:]]*//')
    [[ -z "$task" ]] && task="$message"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] task: ${task:0:200}"

    # 着手報告
    post_reply "$thread_id" "$board" \
        "[status: in_progress] Codex足軽着手。model=${CODEX_MODEL} thread=${thread_id}"

    # codex exec 実行
    local result_file="/tmp/codex_result_${thread_id}.txt"
    cd "$WORKDIR"

    local exit_code=0
    codex exec \
        --full-auto \
        --model "$CODEX_MODEL" \
        --ephemeral \
        -o "$result_file" \
        "$task" || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        # 成功報告
        local result
        result=$(head -c 1800 "$result_file" 2>/dev/null || echo "(出力なし)")
        post_reply "$thread_id" "$board" \
            "[report] Codex足軽完了 (thread=${thread_id})
${result}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完了"
    else
        # 失敗報告
        post_reply "$thread_id" "$board" \
            "[error] Codex足軽失敗 (thread=${thread_id} exit=${exit_code})。ログ: ${logfile}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 失敗: exit=${exit_code}"
    fi

    rm -f "$result_file"

    # ロック解放（fd 9 は exit 時に自動クローズ）
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] codex_worker end"
}

main "$@"
