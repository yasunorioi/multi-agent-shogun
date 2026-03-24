#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# launch_mbp.sh — MBP城 (shogun-mbp) tmux起動スクリプト
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   MBP上で直接実行:
#     bash scripts/launch_mbp.sh
#
#   Linux(デスクトップPC)からSSH経由で実行:
#     bash scripts/launch_mbp.sh --remote
#
# tmuxセッション構成 (shogun-mbp):
#   ペイン0: ollama serve  (起動完了確認後にqwen3:70bロード状態表示)
#   ペイン1: claude code   (足軽浪人。CLAUDE.md読み込み対応)
#   ペイン2: 予備          (ベンチマーク実行用)
#
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── 定数 ────────────────────────────────────────────────────────────────────
SESSION="shogun-mbp"
MBP_HOST="yasu@mbp.local"
MODEL="qwen3:70b"
OLLAMA_PORT=11434
OLLAMA_WAIT_SEC=60   # ollama起動待ちタイムアウト（秒）

# macOS (Apple Silicon) brewパス
BREW_BIN="/opt/homebrew/bin"

# ── カラー出力 ───────────────────────────────────────────────────────────────
_info()    { echo "[launch_mbp] $*"; }
_warn()    { echo "[launch_mbp] WARNING: $*" >&2; }
_error()   { echo "[launch_mbp] ERROR: $*" >&2; }
_fatal()   { _error "$*"; exit 1; }

# ── リモート実行判定 ─────────────────────────────────────────────────────────
_is_local() {
    # --remote フラグが渡された場合はリモート扱い
    for arg in "$@"; do
        [ "$arg" = "--remote" ] && return 1
    done
    # macOSかつmbp.localか確認
    if [ "$(uname -s)" = "Darwin" ]; then
        return 0  # macOS上 → ローカル
    fi
    return 1  # Linux等 → リモート
}

# ── SSH経由でMBP上でスクリプトを実行 ────────────────────────────────────────
_run_remote() {
    _info "SSH経由でMBP城を構築します: $MBP_HOST"

    # SSH疎通確認
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$MBP_HOST" "echo ok" &>/dev/null; then
        _fatal "$MBP_HOST に接続できません。WireGuard VPN / ネットワークを確認してください。"
    fi

    # このスクリプト自身をMBPに転送して実行（--remoteなしで＝ローカルモード）
    local script_path
    script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
    _info "スクリプトを転送中: $MBP_HOST:/tmp/launch_mbp.sh"
    scp -q "$script_path" "$MBP_HOST:/tmp/launch_mbp.sh"
    ssh -t "$MBP_HOST" "bash /tmp/launch_mbp.sh"
}

# ── ollama インストール確認 ───────────────────────────────────────────────────
_check_ollama() {
    # PATH優先、なければBrewパスを確認
    if command -v ollama &>/dev/null; then
        OLLAMA_BIN="$(command -v ollama)"
    elif [ -x "${BREW_BIN}/ollama" ]; then
        OLLAMA_BIN="${BREW_BIN}/ollama"
        export PATH="${BREW_BIN}:${PATH}"
    else
        _error "ollamaが見つかりません。"
        echo "  インストール方法:"
        echo "    brew install ollama"
        echo "  または:"
        echo "    https://ollama.com/download/mac"
        exit 1
    fi
    _info "ollama: $OLLAMA_BIN"
}

# ── qwen3:70bモデル確認 ──────────────────────────────────────────────────────
_check_model() {
    local models
    # ollamaが起動中なら直接確認、そうでなければ一時起動して確認
    if curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" &>/dev/null; then
        models=$(curl -s "http://localhost:${OLLAMA_PORT}/api/tags")
    else
        # 一時的に起動して確認
        _info "モデル確認のためollamaを一時起動..."
        "$OLLAMA_BIN" serve &>/dev/null &
        local tmp_pid=$!
        sleep 3
        models=$(curl -s "http://localhost:${OLLAMA_PORT}/api/tags" 2>/dev/null || echo "")
        kill $tmp_pid 2>/dev/null || true
        wait $tmp_pid 2>/dev/null || true
    fi

    if echo "$models" | grep -q "\"$MODEL\""; then
        _info "モデル確認OK: $MODEL"
    else
        _warn "モデル '$MODEL' がpullされていません。"
        echo ""
        echo "  pullコマンド:"
        echo "    ollama pull $MODEL"
        echo ""
        echo "  ※ qwen3:70bは約40GB。高速回線でのpullを推奨します。"
        echo "  ※ pullなしでも起動を続行できます（モデルなしでollamaのみ起動）。"
        echo ""
        echo "  続行しますか? [Y/n]"
        read -r ans
        case "$ans" in
            n|N) _info "中断しました。ollama pull $MODEL 後に再実行してください。"; exit 0 ;;
            *)   _warn "モデル未pullのまま続行します。" ;;
        esac
    fi
}

# ── ollama起動完了待ち ────────────────────────────────────────────────────────
_wait_ollama_ready() {
    _info "ollama起動待ち (最大${OLLAMA_WAIT_SEC}秒)..."
    local i=0
    while [ $i -lt $OLLAMA_WAIT_SEC ]; do
        if curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" &>/dev/null; then
            _info "ollama起動完了 (${i}秒)"
            return 0
        fi
        sleep 1
        i=$((i + 1))
        # 5秒ごとに進捗表示
        if [ $((i % 5)) -eq 0 ]; then
            _info "  ...待機中 ${i}秒経過"
        fi
    done
    _warn "ollama起動タイムアウト (${OLLAMA_WAIT_SEC}秒)。ペイン0を確認してください。"
    return 1
}

# ── claude codeのパス取得 ─────────────────────────────────────────────────────
_find_claude() {
    if command -v claude &>/dev/null; then
        echo "$(command -v claude)"
    elif [ -x "${BREW_BIN}/claude" ]; then
        echo "${BREW_BIN}/claude"
    elif [ -x "${HOME}/.claude/bin/claude" ]; then
        echo "${HOME}/.claude/bin/claude"
    elif [ -x "${HOME}/.local/bin/claude" ]; then
        echo "${HOME}/.local/bin/claude"
    else
        _warn "claudeコマンドが見つかりません。ペイン1でclaude codeを手動起動してください。"
        echo "claude"  # フォールバック: PATHに期待
    fi
}

# ── tmuxセッション構築 ────────────────────────────────────────────────────────
_launch_tmux() {
    local claude_bin
    claude_bin="$(_find_claude)"
    _info "claude: $claude_bin"

    # 既存セッション確認
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        _info "セッション '$SESSION' は既に存在します。アタッチします。"
        echo "  切断: tmux detach (Prefix+d)"
        echo "  終了: tmux kill-session -t $SESSION"
        tmux attach-session -t "$SESSION"
        return 0
    fi

    _info "MBP城を構築します..."

    # ── ペイン0: ollama serve ──
    tmux new-session -d -s "$SESSION" -x 220 -y 60 \; \
        send-keys "echo '═══ ペイン0: ollama serve ═══' && $OLLAMA_BIN serve 2>&1 | tee /tmp/ollama_mbp.log" Enter

    # ollama起動完了を待ってからペイン分割
    if _wait_ollama_ready; then
        # qwen3:70bロード状態を確認してペイン0に表示
        local tags
        tags=$(curl -s "http://localhost:${OLLAMA_PORT}/api/tags" 2>/dev/null)
        if echo "$tags" | grep -q "\"$MODEL\""; then
            tmux send-keys -t "${SESSION}:0.0" "" ""  # ペイン0はollamaが占有中のためnoop
            _info "モデル $MODEL はロード可能な状態です。"
        fi
    fi

    # ── ペイン1: claude code ──
    tmux split-window -t "${SESSION}:0" -v -p 40
    tmux send-keys -t "${SESSION}:0.1" \
        "echo '═══ ペイン1: claude code (足軽浪人) ═══' && cd \"\${SHOGUN_ROOT:-\$HOME}\" && $claude_bin --effort low" Enter

    # ── ペイン2: 予備（ベンチマーク用） ──
    tmux split-window -t "${SESSION}:0" -v -p 50
    tmux send-keys -t "${SESSION}:0.2" \
        "echo '═══ ペイン2: 予備・ベンチマーク用 ═══'" Enter

    # ペイン1をフォーカス（claude codeが主役）
    tmux select-pane -t "${SESSION}:0.1"

    _info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    _info "MBP城 起動完了！"
    _info "  セッション: $SESSION"
    _info "  接続: tmux attach-session -t $SESSION"
    _info "  ペイン0: ollama serve (localhost:$OLLAMA_PORT)"
    _info "  ペイン1: claude code"
    _info "  ペイン2: 予備（ベンチマーク用）"
    _info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tmux attach-session -t "$SESSION"
}

# ── メイン ───────────────────────────────────────────────────────────────────
main() {
    # tmuxが未インストールの場合は先にチェック
    if ! command -v tmux &>/dev/null; then
        _fatal "tmuxがインストールされていません。: brew install tmux"
    fi

    # リモート実行モード判定
    if ! _is_local "$@"; then
        _run_remote
        exit 0
    fi

    # ローカル (MBP上) での実行
    _info "MBP城 起動シーケンス開始"
    _check_ollama
    _check_model
    _launch_tmux
}

main "$@"
