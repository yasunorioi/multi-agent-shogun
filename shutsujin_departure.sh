#!/bin/bash
# 🏯 multi-agent-shogun 出陣スクリプト（毎日の起動用）
# Daily Deployment Script for Multi-Agent Orchestration System
#
# 使用方法:
#   ./shutsujin_departure.sh           # 全エージェント起動（前回の状態を維持）
#   ./shutsujin_departure.sh -c        # キューをリセットして起動（クリーンスタート）
#   ./shutsujin_departure.sh -c -d     # キュー + DB を初期化して起動（フルクリーン）
#   ./shutsujin_departure.sh -d        # DBのみ初期化して起動
#   ./shutsujin_departure.sh -i        # 省力起動（将軍+老中のみ、足軽等は待機）
#   ./shutsujin_departure.sh -s        # セットアップのみ（Claude起動なし）
#   ./shutsujin_departure.sh -h        # ヘルプ表示

set -e

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 言語設定を読み取り（デフォルト: ja）
LANG_SETTING="ja"
if [ -f "./config/settings.yaml" ]; then
    LANG_SETTING=$(grep "^language:" ./config/settings.yaml 2>/dev/null | awk '{print $2}' || echo "ja")
fi

# シェル設定を読み取り（デフォルト: bash）
SHELL_SETTING="bash"
if [ -f "./config/settings.yaml" ]; then
    SHELL_SETTING=$(grep "^shell:" ./config/settings.yaml 2>/dev/null | awk '{print $2}' || echo "bash")
fi

# 色付きログ関数（戦国風）
log_info() {
    echo -e "\033[1;33m【報】\033[0m $1"
}

log_success() {
    echo -e "\033[1;32m【成】\033[0m $1"
}

log_war() {
    echo -e "\033[1;31m【戦】\033[0m $1"
}

# ═══════════════════════════════════════════════════════════════════════════════
# プロンプト生成関数（bash/zsh対応）
# ───────────────────────────────────────────────────────────────────────────────
# 使用法: generate_prompt "ラベル" "色" "シェル"
# 色: red, green, blue, magenta, cyan, yellow
# ═══════════════════════════════════════════════════════════════════════════════
generate_prompt() {
    local label="$1"
    local color="$2"
    local shell_type="$3"

    if [ "$shell_type" == "zsh" ]; then
        # zsh用: %F{color}%B...%b%f 形式
        echo "(%F{${color}}%B${label}%b%f) %F{green}%B%~%b%f%# "
    else
        # bash用: \[\033[...m\] 形式
        local color_code
        case "$color" in
            red)     color_code="1;31" ;;
            green)   color_code="1;32" ;;
            yellow)  color_code="1;33" ;;
            blue)    color_code="1;34" ;;
            magenta) color_code="1;35" ;;
            cyan)    color_code="1;36" ;;
            *)       color_code="1;37" ;;  # white (default)
        esac
        echo "(\[\033[${color_code}m\]${label}\[\033[0m\]) \[\033[1;32m\]\w\[\033[0m\]\$ "
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# オプション解析
# ═══════════════════════════════════════════════════════════════════════════════
SETUP_ONLY=false
OPEN_TERMINAL=false
CLEAN_MODE=false
CLEAN_DB_MODE=false
KESSEN_MODE=false
IDLE_MODE=false
SHELL_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--setup-only)
            SETUP_ONLY=true
            shift
            ;;
        -c|--clean)
            CLEAN_MODE=true
            shift
            ;;
        -d|--clean-db)
            CLEAN_DB_MODE=true
            shift
            ;;
        -k|--kessen)
            KESSEN_MODE=true
            shift
            ;;
        -i|--idle)
            IDLE_MODE=true
            shift
            ;;
        -t|--terminal)
            OPEN_TERMINAL=true
            shift
            ;;
        -shell|--shell)
            if [[ -n "$2" && "$2" != -* ]]; then
                SHELL_OVERRIDE="$2"
                shift 2
            else
                echo "エラー: -shell オプションには bash または zsh を指定してください"
                exit 1
            fi
            ;;
        -h|--help)
            echo ""
            echo "🏯 multi-agent-shogun 出陣スクリプト"
            echo ""
            echo "使用方法: ./shutsujin_departure.sh [オプション]"
            echo ""
            echo "オプション:"
            echo "  -c, --clean         キューとダッシュボードをリセットして起動（クリーンスタート）"
            echo "                      未指定時は前回の状態を維持して起動"
            echo "  -d, --clean-db      没日録DB(SQLite)も初期化（--cleanと併用推奨）"
            echo "                      単独使用時はDBのみ初期化（キューは維持）"
            echo "  -k, --kessen        決戦の陣（全員Opus Thinkingで起動）"
            echo "                      未指定時は平時の陣（足軽1-3=Sonnet, 部屋子1-2=Opus, お針子=Sonnet）"
            echo "  -i, --idle          省力起動（将軍+老中のみClaude起動、他はペイン作成のみ）"
            echo "                      足軽・部屋子・お針子はタスク発生時に worker_ctl.sh で起動"
            echo ""
            echo "  体制:"
            echo "    老中（roju）:  全プロジェクト統括"
            echo "    足軽（ashigaru）: 老中配下の実働部隊（1名）"
            echo "    部屋子（heyago）: 老中直轄の調査実働部隊（1名）"
            echo "    お針子（ohariko）: 監査・予測・先行割当"
            echo "  -s, --setup-only    tmuxセッションのセットアップのみ（Claude起動なし）"
            echo "  -t, --terminal      Windows Terminal で新しいタブを開く"
            echo "  -shell, --shell SH  シェルを指定（bash または zsh）"
            echo "                      未指定時は config/settings.yaml の設定を使用"
            echo "  -h, --help          このヘルプを表示"
            echo ""
            echo "例:"
            echo "  ./shutsujin_departure.sh              # 前回の状態を維持して出陣"
            echo "  ./shutsujin_departure.sh -c           # クリーンスタート（キューリセット）"
            echo "  ./shutsujin_departure.sh -c -d        # フルクリーン（キュー + DB初期化）"
            echo "  ./shutsujin_departure.sh -d           # DBのみ初期化（キューは維持）"
            echo "  ./shutsujin_departure.sh -s           # セットアップのみ（手動でClaude起動）"
            echo "  ./shutsujin_departure.sh -t           # 全エージェント起動 + ターミナルタブ展開"
            echo "  ./shutsujin_departure.sh -shell bash  # bash用プロンプトで起動"
            echo "  ./shutsujin_departure.sh -k           # 決戦の陣（全足軽Opus Thinking）"
            echo "  ./shutsujin_departure.sh -i             # 省力起動（将軍+老中のみ）"
            echo "  ./shutsujin_departure.sh -c -k         # クリーンスタート＋決戦の陣"
            echo "  ./shutsujin_departure.sh -shell zsh   # zsh用プロンプトで起動"
            echo ""
            echo "モデル構成:"
            echo "  将軍:    Opus（thinking無効）"
            echo "  老中:    Opus Thinking"
            echo "  足軽1:   Sonnet Thinking"
            echo "  部屋子1: Opus Thinking"
            echo "  お針子:  Sonnet Thinking"
            echo ""
            echo "陣形:"
            echo "  平時の陣（デフォルト）: 足軽1=Sonnet, 部屋子1=Opus, お針子=Sonnet"
            echo "  決戦の陣（--kessen）:   全員=Opus Thinking"
            echo ""
            echo "エイリアス:"
            echo "  csst  → cd /mnt/c/tools/multi-agent-shogun && ./shutsujin_departure.sh"
            echo "  css   → tmux attach-session -t shogun"
            echo "  csm   → tmux attach-session -t multiagent"
            echo ""
            exit 0
            ;;
        *)
            echo "不明なオプション: $1"
            echo "./shutsujin_departure.sh -h でヘルプを表示"
            exit 1
            ;;
    esac
done

# シェル設定のオーバーライド（コマンドラインオプション優先）
if [ -n "$SHELL_OVERRIDE" ]; then
    if [[ "$SHELL_OVERRIDE" == "bash" || "$SHELL_OVERRIDE" == "zsh" ]]; then
        SHELL_SETTING="$SHELL_OVERRIDE"
    else
        echo "エラー: -shell オプションには bash または zsh を指定してください（指定値: $SHELL_OVERRIDE）"
        exit 1
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 出陣バナー表示（CC0ライセンスASCIIアート使用）
# ───────────────────────────────────────────────────────────────────────────────
# 【著作権・ライセンス表示】
# 忍者ASCIIアート: syntax-samurai/ryu - CC0 1.0 Universal (Public Domain)
# 出典: https://github.com/syntax-samurai/ryu
# "all files and scripts in this repo are released CC0 / kopimi!"
# ═══════════════════════════════════════════════════════════════════════════════
show_battle_cry() {
    clear

    # タイトルバナー（色付き）
    echo ""
    echo -e "\033[1;31m╔══════════════════════════════════════════════════════════════════════════════════╗\033[0m"
    echo -e "\033[1;31m║\033[0m \033[1;33m███████╗██╗  ██╗██╗   ██╗████████╗███████╗██╗   ██╗     ██╗██╗███╗   ██╗\033[0m \033[1;31m║\033[0m"
    echo -e "\033[1;31m║\033[0m \033[1;33m██╔════╝██║  ██║██║   ██║╚══██╔══╝██╔════╝██║   ██║     ██║██║████╗  ██║\033[0m \033[1;31m║\033[0m"
    echo -e "\033[1;31m║\033[0m \033[1;33m███████╗███████║██║   ██║   ██║   ███████╗██║   ██║     ██║██║██╔██╗ ██║\033[0m \033[1;31m║\033[0m"
    echo -e "\033[1;31m║\033[0m \033[1;33m╚════██║██╔══██║██║   ██║   ██║   ╚════██║██║   ██║██   ██║██║██║╚██╗██║\033[0m \033[1;31m║\033[0m"
    echo -e "\033[1;31m║\033[0m \033[1;33m███████║██║  ██║╚██████╔╝   ██║   ███████║╚██████╔╝╚█████╔╝██║██║ ╚████║\033[0m \033[1;31m║\033[0m"
    echo -e "\033[1;31m║\033[0m \033[1;33m╚══════╝╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝  ╚════╝ ╚═╝╚═╝  ╚═══╝\033[0m \033[1;31m║\033[0m"
    echo -e "\033[1;31m╠══════════════════════════════════════════════════════════════════════════════════╣\033[0m"
    echo -e "\033[1;31m║\033[0m       \033[1;37m出陣じゃーーー！！！\033[0m    \033[1;36m⚔\033[0m    \033[1;35m天下布武！\033[0m                          \033[1;31m║\033[0m"
    echo -e "\033[1;31m╚══════════════════════════════════════════════════════════════════════════════════╝\033[0m"
    echo ""

    # ═══════════════════════════════════════════════════════════════════════════
    # 足軽隊列（オリジナル）
    # ═══════════════════════════════════════════════════════════════════════════
    echo -e "\033[1;34m  ╔═════════════════════════════════════════════════════════════════════════════╗\033[0m"
    echo -e "\033[1;34m  ║\033[0m            \033[1;37m【 足軽・部屋子・お針子 隊列 ・ 三 名 配 備 】\033[0m              \033[1;34m║\033[0m"
    echo -e "\033[1;34m  ╚═════════════════════════════════════════════════════════════════════════════╝\033[0m"

    cat << 'ASHIGARU_EOF'

       /\      /\      /\
      /||\    /||\    /||\
     /_||\   /_||\   /_||\
       ||      ||      ||
      /||\    /||\    /||\
      /  \    /  \    /  \
     [足1]   [部1]   [針]

ASHIGARU_EOF

    echo -e "                    \033[1;36m「「「 はっ！！ 出陣いたす！！ 」」」\033[0m"
    echo ""

    # ═══════════════════════════════════════════════════════════════════════════
    # システム情報
    # ═══════════════════════════════════════════════════════════════════════════
    echo -e "\033[1;33m  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\033[0m"
    echo -e "\033[1;33m  ┃\033[0m  \033[1;37m🏯 multi-agent-shogun\033[0m  〜 \033[1;36m戦国マルチエージェント統率システム\033[0m 〜           \033[1;33m┃\033[0m"
    echo -e "\033[1;33m  ┃\033[0m                                                                           \033[1;33m┃\033[0m"
    echo -e "\033[1;33m  ┃\033[0m  \033[1;35m将軍\033[0m:統括 \033[1;31m老中\033[0m:全PJ統括 \033[1;34m足軽\033[0m×1 \033[1;36m部屋子\033[0m×1 \033[1;33mお針子\033[0m×1       \033[1;33m┃\033[0m"
    echo -e "\033[1;33m  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\033[0m"
    echo ""
}

# バナー表示実行
show_battle_cry

echo -e "  \033[1;33m天下布武！陣立てを開始いたす\033[0m (Setting up the battlefield)"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: 既存セッションクリーンアップ
# ═══════════════════════════════════════════════════════════════════════════════
log_info "🧹 既存の陣を撤収中..."
tmux kill-session -t multiagent 2>/dev/null && log_info "  └─ multiagent陣、撤収完了" || log_info "  └─ multiagent陣は存在せず"
tmux kill-session -t ooku 2>/dev/null && log_info "  └─ ooku陣、撤収完了" || log_info "  └─ ooku陣は存在せず"
tmux kill-session -t shogun 2>/dev/null && log_info "  └─ shogun本陣、撤収完了" || log_info "  └─ shogun本陣は存在せず"

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1.5: 前回記録のバックアップ（--clean時のみ、内容がある場合）
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$CLEAN_MODE" = true ] || [ "$CLEAN_DB_MODE" = true ]; then
    BACKUP_DIR="./logs/backup_$(date '+%Y%m%d_%H%M%S')"
    NEED_BACKUP=false

    if [ "$CLEAN_MODE" = true ] && [ -f "./dashboard.md" ]; then
        if grep -q "cmd_" "./dashboard.md" 2>/dev/null; then
            NEED_BACKUP=true
        fi
    fi

    if [ "$CLEAN_DB_MODE" = true ] && [ -f "./data/botsunichiroku.db" ]; then
        NEED_BACKUP=true
    fi

    if [ "$NEED_BACKUP" = true ]; then
        mkdir -p "$BACKUP_DIR" || true
        if [ "$CLEAN_MODE" = true ]; then
            cp "./dashboard.md" "$BACKUP_DIR/" 2>/dev/null || true
            cp -r "./queue/reports" "$BACKUP_DIR/" 2>/dev/null || true
            cp -r "./queue/tasks" "$BACKUP_DIR/" 2>/dev/null || true
            cp "./queue/shogun_to_karo.yaml" "$BACKUP_DIR/" 2>/dev/null || true
            cp "./queue/shogun_to_roju.yaml" "$BACKUP_DIR/" 2>/dev/null || true
            cp "./queue/shogun_to_ooku.yaml" "$BACKUP_DIR/" 2>/dev/null || true
        fi
        if [ "$CLEAN_DB_MODE" = true ] && [ -f "./data/botsunichiroku.db" ]; then
            cp "./data/botsunichiroku.db" "$BACKUP_DIR/" 2>/dev/null || true
            log_info "🗄️ 没日録DBをバックアップ: $BACKUP_DIR/botsunichiroku.db"
        fi
        log_info "📦 前回の記録をバックアップ: $BACKUP_DIR"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: キューディレクトリ確保 + リセット（--clean時のみリセット）
# ═══════════════════════════════════════════════════════════════════════════════

# queue ディレクトリが存在しない場合は作成（初回起動時に必要）
[ -d ./queue/reports ] || mkdir -p ./queue/reports
[ -d ./queue/tasks ] || mkdir -p ./queue/tasks

if [ "$CLEAN_MODE" = true ]; then
    log_info "📜 前回の軍議記録を破棄中..."

    # 足軽タスクファイルリセット（足軽1）
    cat > ./queue/tasks/ashigaru1.yaml << EOF
# 足軽1専用タスクファイル
task:
  task_id: null
  parent_cmd: null
  description: null
  target_path: null
  status: idle
  timestamp: ""
EOF

    # 部屋子タスクファイルリセット（部屋子1 = ashigaru6）
    cat > ./queue/tasks/ashigaru6.yaml << EOF
# 部屋子1（ashigaru6）専用タスクファイル
task:
  task_id: null
  parent_cmd: null
  description: null
  target_path: null
  status: idle
  timestamp: ""
EOF

    # 足軽レポートファイルリセット（足軽1 + 部屋子1）
    for i in 1 6; do
        cat > ./queue/reports/ashigaru${i}_report.yaml << EOF
worker_id: ashigaru${i}
task_id: null
timestamp: ""
status: idle
result: null
EOF
    done

    # キューファイルリセット（2家老体制: roju=外部PJ, ooku=内部管理）
    cat > ./queue/shogun_to_karo.yaml << 'EOF'
queue: []
EOF

    cat > ./queue/shogun_to_roju.yaml << 'EOF'
queue: []
EOF

    cat > ./queue/shogun_to_ooku.yaml << 'EOF'
queue: []
EOF

    cat > ./queue/karo_to_ashigaru.yaml << 'EOF'
assignments:
  ashigaru1:
    task_id: null
    description: null
    target_path: null
    status: idle
  ashigaru6:
    task_id: null
    description: null
    target_path: null
    status: idle
EOF

    log_success "✅ 陣払い完了"
else
    log_info "📜 前回の陣容を維持して出陣..."
    log_success "✅ キュー・報告ファイルはそのまま継続"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2.5: 没日録DB初期化（--clean-db時のみ）
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$CLEAN_DB_MODE" = true ]; then
    log_info "🗄️ 没日録DBを初期化中..."
    if [ -f "./data/botsunichiroku.db" ]; then
        rm -f "./data/botsunichiroku.db"
        log_info "  └─ 既存DB削除完了"
    fi
    if python3 ./scripts/init_db.py 2>/dev/null; then
        log_success "  └─ 没日録DB再作成完了"
    else
        log_war "  └─ ⚠️ DB初期化に失敗。scripts/init_db.py を確認してください"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: ダッシュボード初期化（--clean時のみ）
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$CLEAN_MODE" = true ]; then
    log_info "📊 戦況報告板を初期化中..."
    TIMESTAMP=$(date "+%Y-%m-%d %H:%M")

    if [ "$LANG_SETTING" = "ja" ]; then
        # 日本語のみ
        cat > ./dashboard.md << EOF
# 📊 戦況報告
最終更新: ${TIMESTAMP}

## 🚨 要対応 - 殿のご判断をお待ちしております
なし

## 🔄 進行中 - 只今、戦闘中でござる
なし

## ✅ 本日の戦果
| 時刻 | 戦場 | 任務 | 結果 |
|------|------|------|------|

## 🎯 スキル化候補 - 承認待ち
なし

## 🛠️ 生成されたスキル
なし

## ⏸️ 待機中
なし

## ❓ 伺い事項
なし
EOF
    else
        # 日本語 + 翻訳併記
        cat > ./dashboard.md << EOF
# 📊 戦況報告 (Battle Status Report)
最終更新 (Last Updated): ${TIMESTAMP}

## 🚨 要対応 - 殿のご判断をお待ちしております (Action Required - Awaiting Lord's Decision)
なし (None)

## 🔄 進行中 - 只今、戦闘中でござる (In Progress - Currently in Battle)
なし (None)

## ✅ 本日の戦果 (Today's Achievements)
| 時刻 (Time) | 戦場 (Battlefield) | 任務 (Mission) | 結果 (Result) |
|------|------|------|------|

## 🎯 スキル化候補 - 承認待ち (Skill Candidates - Pending Approval)
なし (None)

## 🛠️ 生成されたスキル (Generated Skills)
なし (None)

## ⏸️ 待機中 (On Standby)
なし (None)

## ❓ 伺い事項 (Questions for Lord)
なし (None)
EOF
    fi

    log_success "  └─ ダッシュボード初期化完了 (言語: $LANG_SETTING, シェル: $SHELL_SETTING)"
else
    log_info "📊 前回のダッシュボードを維持"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: tmux の存在確認
# ═══════════════════════════════════════════════════════════════════════════════
if ! command -v tmux &> /dev/null; then
    echo ""
    echo "  ╔════════════════════════════════════════════════════════╗"
    echo "  ║  [ERROR] tmux not found!                              ║"
    echo "  ║  tmux が見つかりません                                 ║"
    echo "  ╠════════════════════════════════════════════════════════╣"
    echo "  ║  Run first_setup.sh first:                            ║"
    echo "  ║  まず first_setup.sh を実行してください:               ║"
    echo "  ║     ./first_setup.sh                                  ║"
    echo "  ╚════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: shogun セッション作成（1ペイン・window 0 を必ず確保）
# ═══════════════════════════════════════════════════════════════════════════════
log_war "👑 将軍の本陣を構築中..."

# shogun セッションがなければ作る（-s 時もここで必ず shogun が存在するようにする）
# window 0 のみ作成し -n main で名前付け（第二 window にするとアタッチ時に空ペインが開くため 1 window に限定）
if ! tmux has-session -t shogun 2>/dev/null; then
    tmux new-session -d -s shogun -n main
fi

# 将軍ペインはウィンドウ名 "main" で指定（base-index 1 環境でも動く）
SHOGUN_PROMPT=$(generate_prompt "将軍" "magenta" "$SHELL_SETTING")
tmux send-keys -t shogun:main "cd \"$(pwd)\" && export PS1='${SHOGUN_PROMPT}' && clear" Enter
tmux select-pane -t shogun:main -P 'bg=#002b36'  # 将軍の Solarized Dark
tmux set-option -p -t shogun:main @agent_id "shogun"

log_success "  └─ 将軍の本陣、構築完了"
echo ""

# pane-base-index を取得（1 の環境ではペインは 1,2,... になる）
PANE_BASE=$(tmux show-options -gv pane-base-index 2>/dev/null || echo 0)

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5.1: multiagent セッション作成（3ペイン：老中 + 足軽1 + 部屋子1）
# ═══════════════════════════════════════════════════════════════════════════════
log_war "⚔️ 老中・足軽・部屋子の陣を構築中（3名配備）..."

# ターミナルサイズチェック（4ペイン + 4ペインには最低 30行 × 120列 推奨）
TERM_LINES=$(tput lines 2>/dev/null || echo 24)
TERM_COLS=$(tput cols 2>/dev/null || echo 80)
MIN_LINES=30
MIN_COLS=120

if [ "$TERM_LINES" -lt "$MIN_LINES" ] || [ "$TERM_COLS" -lt "$MIN_COLS" ]; then
    echo ""
    echo "  ╔════════════════════════════════════════════════════════════════╗"
    echo "  ║  ⚠️  [警告] ターミナルサイズが小さすぎます                     ║"
    echo "  ╠════════════════════════════════════════════════════════════════╣"
    echo "  ║  現在: ${TERM_COLS}列 × ${TERM_LINES}行"
    echo "  ║  推奨: ${MIN_COLS}列 × ${MIN_LINES}行 以上"
    echo "  ║                                                                ║"
    echo "  ║  ペインを作成するにはターミナルを大きくしてください            ║"
    echo "  ╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo -n "  続行しますか？ [y/N]: "
    read -r CONTINUE_ANYWAY
    if [[ ! "$CONTINUE_ANYWAY" =~ ^[Yy]$ ]]; then
        echo "  中止しました。ターミナルを大きくして再実行してください。"
        exit 1
    fi
    echo ""
fi

# split-window のエラーハンドリング関数
split_pane_safely() {
    local direction="$1"
    local target="$2"
    if ! tmux split-window "$direction" -t "$target" 2>/dev/null; then
        echo ""
        echo "  ╔════════════════════════════════════════════════════════════════╗"
        echo "  ║  ❌ [ERROR] no space for new pane                              ║"
        echo "  ╠════════════════════════════════════════════════════════════════╣"
        echo "  ║  ペインを分割する空間が足りません                              ║"
        echo "  ║                                                                ║"
        echo "  ║  対処法:                                                       ║"
        echo "  ║  1. ターミナルウィンドウを最大化する                           ║"
        echo "  ║  2. フォントサイズを小さくする                                 ║"
        echo "  ║  3. 解像度の高いモニターで実行する                             ║"
        echo "  ║                                                                ║"
        echo "  ║  推奨サイズ: 120列 × 30行 以上                                 ║"
        echo "  ╚════════════════════════════════════════════════════════════════╝"
        echo ""
        tmux kill-session -t multiagent 2>/dev/null
        tmux kill-session -t ooku 2>/dev/null
        tmux kill-session -t shogun 2>/dev/null
        exit 1
    fi
}

# multiagent セッション作成
if ! tmux new-session -d -s multiagent -n "agents" 2>/dev/null; then
    echo "  [ERROR] multiagent セッション作成失敗"
    exit 1
fi

# 3ペイン作成（縦3分割）
# ペイン配置:
#   pane 0=karo-roju, pane 1=ashigaru1, pane 2=ashigaru6(heyago1)

split_pane_safely -v "multiagent:agents"

tmux select-pane -t "multiagent:agents.$((PANE_BASE+1))"
split_pane_safely -v "multiagent:agents"

# multiagent ペイン設定
MA_LABELS=("karo-roju" "ashigaru1" "heyago1")
MA_COLORS=("red" "blue" "cyan")
MA_AGENT_IDS=("karo-roju" "ashigaru1" "ashigaru6")

if [ "$KESSEN_MODE" = true ]; then
    MA_TITLES=("karo-roju(Opus)" "ashigaru1(Opus)" "heyago1(Opus)")
    MA_MODELS=("Opus Thinking" "Opus Thinking" "Opus Thinking")
else
    MA_TITLES=("karo-roju(Opus)" "ashigaru1(Sonnet)" "heyago1(Opus)")
    MA_MODELS=("Opus Thinking" "Sonnet Thinking" "Opus Thinking")
fi

for i in {0..2}; do
    p=$((PANE_BASE + i))
    tmux select-pane -t "multiagent:agents.${p}" -T "${MA_TITLES[$i]}"
    tmux set-option -p -t "multiagent:agents.${p}" @agent_id "${MA_AGENT_IDS[$i]}"
    tmux set-option -p -t "multiagent:agents.${p}" @model_name "${MA_MODELS[$i]}"
    PROMPT_STR=$(generate_prompt "${MA_LABELS[$i]}" "${MA_COLORS[$i]}" "$SHELL_SETTING")
    tmux send-keys -t "multiagent:agents.${p}" "cd \"$(pwd)\" && export PS1='${PROMPT_STR}' && clear" Enter
done

tmux set-option -t multiagent -w pane-border-status top
tmux set-option -t multiagent -w pane-border-format '#{pane_index} #{@agent_id} (#{@model_name})'

log_success "  └─ 老中・足軽・部屋子の陣、構築完了"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5.2: ooku セッション作成（2ペイン：お針子 + 高札）
# ═══════════════════════════════════════════════════════════════════════════════
log_war "🏯 お針子・高札の陣を構築中（1監査+1コンテナ配備）..."

if ! tmux new-session -d -s ooku -n "agents" 2>/dev/null; then
    echo "  [ERROR] ooku セッション作成失敗"
    exit 1
fi

# 2ペイン作成（縦2分割）
# ペイン配置:
#   pane 0=ohariko, pane 1=kousatsu

split_pane_safely -v "ooku:agents"

# ooku ペイン設定
OOKU_LABELS=("ohariko" "kousatsu")
OOKU_COLORS=("yellow" "green")
OOKU_AGENT_IDS=("ohariko" "kousatsu")

if [ "$KESSEN_MODE" = true ]; then
    OOKU_TITLES=("ohariko(Opus)" "kousatsu(高札API)")
    OOKU_MODELS=("Opus Thinking" "FTS5+MeCab")
else
    OOKU_TITLES=("ohariko(Sonnet)" "kousatsu(高札API)")
    OOKU_MODELS=("Sonnet Thinking" "FTS5+MeCab")
fi

for i in {0..1}; do
    p=$((PANE_BASE + i))
    tmux select-pane -t "ooku:agents.${p}" -T "${OOKU_TITLES[$i]}"
    tmux set-option -p -t "ooku:agents.${p}" @agent_id "${OOKU_AGENT_IDS[$i]}"
    tmux set-option -p -t "ooku:agents.${p}" @model_name "${OOKU_MODELS[$i]}"
    PROMPT_STR=$(generate_prompt "${OOKU_LABELS[$i]}" "${OOKU_COLORS[$i]}" "$SHELL_SETTING")
    tmux send-keys -t "ooku:agents.${p}" "cd \"$(pwd)\" && export PS1='${PROMPT_STR}' && clear" Enter
done

tmux set-option -t ooku -w pane-border-status top
tmux set-option -t ooku -w pane-border-format '#{pane_index} #{@agent_id} (#{@model_name})'

log_success "  └─ お針子・高札の陣、構築完了"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: Claude Code 起動（-s / --setup-only のときはスキップ）
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$SETUP_ONLY" = false ]; then
    # Claude Code CLI の存在チェック
    if ! command -v claude &> /dev/null; then
        log_info "⚠️  claude コマンドが見つかりません"
        echo "  first_setup.sh を再実行してください:"
        echo "    ./first_setup.sh"
        exit 1
    fi

    log_war "👑 全軍に Claude Code を召喚中..."

    # 将軍
    tmux send-keys -t shogun:main "MAX_THINKING_TOKENS=0 claude --model opus --dangerously-skip-permissions"
    tmux send-keys -t shogun:main Enter
    log_info "  └─ 将軍、召喚完了"

    sleep 1

    # ═══════════════════════════════════════════════════════════════════════════
    # multiagent セッション: 老中 + 足軽1-3
    # ═══════════════════════════════════════════════════════════════════════════
    # 老中（pane 0）: Opus Thinking（--idle時も起動）
    p=$((PANE_BASE + 0))
    tmux send-keys -t "multiagent:agents.${p}" "claude --model opus --dangerously-skip-permissions"
    tmux send-keys -t "multiagent:agents.${p}" Enter
    log_info "  └─ 老中（Opus Thinking）、召喚完了"

    if [ "$IDLE_MODE" = true ]; then
        # 省力起動: 足軽・部屋子・お針子はペイン作成のみ（Claude Code未起動）
        log_info "  └─ 省力起動モード: 足軽・部屋子・お針子は待機中（worker_ctl.sh で起動）"
    else
        # 足軽1 (pane 1) + 部屋子1 (pane 2)
        if [ "$KESSEN_MODE" = true ]; then
            p=$((PANE_BASE + 1))
            tmux send-keys -t "multiagent:agents.${p}" "claude --model opus --dangerously-skip-permissions"
            tmux send-keys -t "multiagent:agents.${p}" Enter
            p=$((PANE_BASE + 2))
            tmux send-keys -t "multiagent:agents.${p}" "claude --model opus --dangerously-skip-permissions"
            tmux send-keys -t "multiagent:agents.${p}" Enter
            log_info "  └─ 足軽1・部屋子1（Opus Thinking）、召喚完了"
        else
            # 平時: 足軽1=Sonnet, 部屋子1=Opus
            p=$((PANE_BASE + 1))
            tmux send-keys -t "multiagent:agents.${p}" "claude --model sonnet --dangerously-skip-permissions"
            tmux send-keys -t "multiagent:agents.${p}" Enter
            log_info "  └─ 足軽1（Sonnet Thinking）、召喚完了"
            p=$((PANE_BASE + 2))
            tmux send-keys -t "multiagent:agents.${p}" "claude --model opus --dangerously-skip-permissions"
            tmux send-keys -t "multiagent:agents.${p}" Enter
            log_info "  └─ 部屋子1（Opus Thinking）、召喚完了"
        fi

        # ═══════════════════════════════════════════════════════════════════════════
        # ooku セッション: お針子 (pane 0)
        # ═══════════════════════════════════════════════════════════════════════════
        # お針子 (pane 0)
        p=${PANE_BASE}
        if [ "$KESSEN_MODE" = true ]; then
            tmux send-keys -t "ooku:agents.${p}" "claude --model opus --dangerously-skip-permissions"
            tmux send-keys -t "ooku:agents.${p}" Enter
            log_info "  └─ お針子（Opus Thinking）、召喚完了"
        else
            tmux send-keys -t "ooku:agents.${p}" "claude --model sonnet --dangerously-skip-permissions"
            tmux send-keys -t "ooku:agents.${p}" Enter
            log_info "  └─ お針子（Sonnet Thinking）、召喚完了"
        fi
    fi

    if [ "$IDLE_MODE" = true ]; then
        log_success "✅ 省力起動完了（将軍+老中のみ。足軽等は worker_ctl.sh start で起動）"
    elif [ "$KESSEN_MODE" = true ]; then
        log_success "✅ 決戦の陣で出陣！全軍Opus！"
    else
        log_success "✅ 平時の陣で出陣"
    fi
    echo ""

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 6.5: 各エージェントに指示書を読み込ませる
    # ═══════════════════════════════════════════════════════════════════════════
    log_war "📜 各エージェントに指示書を読み込ませ中..."
    echo ""

    # ═══════════════════════════════════════════════════════════════════════════
    # 忍者戦士（syntax-samurai/ryu - CC0 1.0 Public Domain）
    # ═══════════════════════════════════════════════════════════════════════════
    echo -e "\033[1;35m  ┌────────────────────────────────────────────────────────────────────────────────────────────────────────────┐\033[0m"
    echo -e "\033[1;35m  │\033[0m                              \033[1;37m【 忍 者 戦 士 】\033[0m  Ryu Hayabusa (CC0 Public Domain)                        \033[1;35m│\033[0m"
    echo -e "\033[1;35m  └────────────────────────────────────────────────────────────────────────────────────────────────────────────┘\033[0m"

    cat << 'NINJA_EOF'
...................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                        ...................................
..................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                        ...................................
..................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                        ...................................
..................................░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                        ...................................
..................................░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                        ...................................
..................................░░░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░▒▒▒▒▒▒                         ...................................
..................................░░░░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  ▒▒▒▒▒▒░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░▒▒▒▒▒▒▒                         ...................................
..................................░░░░░░░░░░░░░░░░▒▒▒▒          ▒▒▒▒▒▒▒▒░░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒░░░░▒▒▒▒▒▒▒▒▒                             ...................................
..................................░░░░░░░░░░░░░░▒▒▒▒               ▒▒▒▒▒░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                                ...................................
..................................░░░░░░░░░░░░░▒▒▒                    ▒▒▒▒░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                                    ...................................
..................................░░░░░░░░░░░░▒                            ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                                        ...................................
..................................░░░░░░░░░░░      ░░░░░░░░░░░░░                                      ░░░░░░░░░░░░       ▒          ...................................
..................................░░░░░░░░░░ ▒    ░░░▓▓▓▓▓▓▓▓▓▓▓▓░░                                 ░░░░░░░░░░░░░░░ ░               ...................................
..................................░░░░░░░░░░     ░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░                          ░░░░░░░░░░░░░░░░░░░                ...................................
..................................░░░░░░░░░ ▒  ░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░             ░░▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░  ░   ▒         ...................................
..................................░░░░░░░░ ░  ░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░ ░  ▒         ...................................
..................................░░░░░░░░ ░  ░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░  ░    ▒        ...................................
..................................░░░░░░░░░▒  ░ ░               ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓░                 ░            ...................................
.................................░░░░░░░░░░   ░░░  ░                 ▓▓▓▓▓▓▓▓░▓▓▓▓░░░▓░░░░░░▓▓▓▓▓                    ░ ░   ▒         ..................................
.................................░░░░░░░░▒▒   ░░░░░ ░                  ▓▓▓▓▓▓░▓▓▓▓░░▓▓▓░░░░░░▓▓                    ░  ░ ░  ▒         ..................................
.................................░░░░░░░░▒    ░░░░░░░░░ ░                 ░▓░░▓▓▓▓▓░▓▓▓░░░░░                   ░ ░░ ░░ ░   ▒         ..................................
.................................░░░░░░░▒▒    ░░░░░░░   ░░                    ▓▓▓▓▓▓▓▓▓░░                   ░░    ░ ░░ ░    ▒        ..................................
.................................░░░░░░░▒▒    ░░░░░░░░░░                      ░▓▓▓▓▓▓▓░░░                     ░░░  ░  ░ ░   ▒        ..................................
.................................░░░░░░░ ▒    ░░░░░░                         ░░░▓▓▓░▓░░░░      ░                  ░ ░░ ░    ▒        ..................................
.................................░░░░░░░ ▒    ░░░░░░░     ▓▓        ▓  ░░ ░░░░░░░░░░░░░  ░   ░░  ▓        █▓       ░  ░ ░   ▒▒       ..................................
..................................░░░░░▒ ▒    ░░░░░░░░  ▓▓██  ▓  ██ ██▓  ▓ ░░░▓░  ░ ░ ░░░░  ▓   ██ ▓█  ▓  ██▓▓  ░░░░  ░ ░    ▒      ...................................
..................................░░░░░▒ ▒▒   ░░░░░░░░░  ▓██  ▓▓  ▓ ██▓  ▓░░░░▓▓░  ░░░░░░░░ ▓  ▓██ ▓   ▓  ██▓▓ ░░░░░░░ ░     ▒      ...................................
..................................░░░░░  ▒░   ░░░░░░░▓░░ ▓███  ▓▓▓▓ ███░  ░░░░▓▓░░░░░░░░░░    ░▓██  ▓▓▓  ███▓ ░░▓▓░░  ░    ▒ ▒      ...................................
...................................░░░░  ▒░    ░░░░▓▓▓▓▓▓░  ███    ██      ░░░░░▓▓▓▓▓░░░░░░░     ███   ████ ░░▓▓▓▓░░  ░    ▒ ▒      ...................................
...................................░░░░ ▒ ░▒    ░░▓▓▓▓▓▓▓▓▓▓ ██████  ▓▓▓░░ ░░░░▓▓▓▓▓▓░░░░░░░░░▓▓▓   █████  ▓▓▓▓▓▓▓░░░░    ▒▒ ▒      ...................................
...................................░░░░ ░ ░░     ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓█░░░░░░░▓▓▓▓▓▓▓░░░░ ░░   ░░▓░▓▓░░░░░░░▓▓▓▓▓▓░░      ▒▒ ▒      ...................................
...................................░░░░ ░ ░░      ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓██  ░░░░░░░▓▓▓▓▓▓▓░░░░  ░░░░░   ░░░░░░░░░▓▓▓▓▓░░ ░    ▒▒  ▒      ...................................
...................................░░░░▒░░▒░░      ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░▓▓▓▓▓▓▓▓░░░  ░░░░░░░░░░░░░░░░░░▓▓░░░░      ▒▒  ▒     ....................................
...................................░░░░▒░░ ░░       ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓▓░░░░  ░░░░░░░░░░░░░░░░░░░░░        ▒▒  ▒     ....................................
...................................░░░░░░░ ▒░▒       ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░▓▓▓░░   ░░░░░  ░░░░░░░░░░░░░░░░░░░░         ▒   ▒     ....................................
...................................░░░░░░░░░░░           ░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓              ░    ░░░░░░░░░░░░░░░            ▒   ▒     ....................................
....................................░░░░░░░░░░░▒  ▒▒        ▓▓▓▓▓▓▓▓▓▓▓▓▓  ░░░░░░░░░░▒▒                         ▒▒▒▒▒   ▒    ▒    .....................................
....................................░░░░░░░░░░ ░▒ ▒▒▒░░░        ▓▓▓▓▓▓   ░░░░░░░░░░░░░▒▒▒      ▒▒▒▒▒░░░░▒▒    ▒▒▒▒▒▒▒  ▒▒    ▒    .....................................
....................................░░░░░░░░░░ ░░░ ▒▒▒░░░░░░          ░░░░░ ░░░░░░░░░░▒░▒     ▒▒▒▒▒▒░░░░░░▒▒▒▒▒░▒▒▒▒   ▒▒         .....................................
.....................................░░░░░░░░░░ ░░░░░  ▒▒░░░░░░░░░░░░░    ░░░░░░░░░  ▒░▒▒    ▒▒▒▒▒░░░░▒▒▒▒▒▒░░▒▒▒   ▒▒▒         ......................................
.....................................░░░░░░░░░░░░░░░░░░  ▒░░░░░░░░░░░   ░░░░░░░░░░░░░░   ▒   ▒▒▒▒▒▒▒░▒▒▒▒▒▒░░░░▒▒▒   ▒▒          ......................................
.....................................░░░░░░░░░░░ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░      ▒▒▒▒▒▒▒    ▒  ░░░▒▒▒▒  ▒▒▒          ......................................
......................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ ▒░▒▒▒ ▒▒▒    ▒░░░░░░░░░░▒   ▒▒▒▒      ▒   .......................................
......................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒  ░░▒▒▒▒▒▒░░░░░░░░░░░░░▒  ░▒▒▒▒       ▒   .......................................
......................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒ ▒▒░▒▒▒▒▒▒▒░░░░░░░░░░  ░░▒▒▒▒▒       ▒   .......................................
......................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒ ░▒▒▒▒▒▒▒▒▒░░▒░░░░░░ ░░▒▒▒▒▒▒      ▒    .......................................
.......................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒░░▒░▒▒▒ ▒▒▒▒▒░░░░░░░░░▒▒▒▒▒        ▒    .......................................
.......................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒▒░▒▒▒▒▒     ░░░░░░░░▒▒▒▒▒▒        ▒    .......................................
.......................................░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒▒▒░░▒░▒▒▒▒▒▒  ▒░░░░░░░▒▒▒▒▒▒        ▒     .......................................
NINJA_EOF

    echo ""
    echo -e "                                    \033[1;35m「 天下布武！勝利を掴め！ 」\033[0m"
    echo ""
    echo -e "                               \033[0;36m[ASCII Art: syntax-samurai/ryu - CC0 1.0 Public Domain]\033[0m"
    echo ""

    # ═══════════════════════════════════════════════════════════════════════════
    # 没日録（botsunichiroku）- 秘密の記録書（オリジナル）
    # ═══════════════════════════════════════════════════════════════════════════
    echo -e "\033[1;33m  ┌──────────────────────────────────────────────────────────────────────────┐\033[0m"
    echo -e "\033[1;33m  │\033[0m                    \033[1;37m【 没 日 録 】\033[0m  \033[0;33m表には出ぬ永続の記録\033[0m                    \033[1;33m│\033[0m"
    echo -e "\033[1;33m  └──────────────────────────────────────────────────────────────────────────┘\033[0m"

    cat << 'BOTSU_EOF'

                    _______________________________________________
                   /\                                              \
                  /  \    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓    \
                 /    \   ┃  没 日 録                          ┃    \
                /      \  ┃  ──────────────────────────────    ┃     \
               /   /\   \ ┃  代々書き継がれし秘帳なり          ┃      \
              /   /  \   \┃  表の歴史には記されぬ              ┃       \
             /   /    \   ┃  されど真実はここにあり            ┃        \
            /   /  墨  \  ┃                                    ┃         \
           /   /   硯   \ ┃  commands ......... 指令の記録     ┃          \
          /   /    ___   \┃  subtasks ......... 任務の詳細     ┃           \
         /   /    / 筆\   ┃  reports ........... 戦果の報告    ┃            \
        /   /    | |||  | ┃  agents ............ 配下の名簿    ┃             \
       /   /     | |||  | ┃                                    ┃              \
      /   /      |_|||_/  ┃  「此の書、火にくべるべからず」    ┃               \
     /   /                ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛                \
    /   /_______________________________________________________________         \
   /                                                                     \        |
  /_______________________________________________________________________\       |
  |                                                                       |       |
  |   ~ botsunichiroku.db ~    SQLite に刻まれし不滅の記録               |      /
  |_______________________________________________________________________|     /
   \                                                                       \   /
    \_______________________________________________________________________\_/

BOTSU_EOF

    echo -e "                        \033[1;33m「 此の書、代々の総取締が書き継ぐものなり 」\033[0m"
    echo ""

    echo "  Claude Code の起動を待機中（最大30秒）..."

    # 将軍の起動を確認（最大30秒待機）
    for i in {1..30}; do
        if tmux capture-pane -t shogun:main -p | grep -q "bypass permissions"; then
            echo "  └─ 将軍の Claude Code 起動確認完了（${i}秒）"
            break
        fi
        sleep 1
    done

    # 将軍に指示書を読み込ませる
    log_info "  └─ 将軍に指示書を伝達中..."
    tmux send-keys -t shogun:main "instructions/shogun.md を読んで役割を理解せよ。"
    sleep 0.5
    tmux send-keys -t shogun:main Enter

    # ═══════════════════════════════════════════════════════════════════════════
    # multiagent セッション: 老中 + 足軽1-3
    # ═══════════════════════════════════════════════════════════════════════════
    # 老中に指示書を読み込ませる（pane 0）（--idle時も起動済み）
    sleep 2
    log_info "  └─ 老中に指示書を伝達中..."
    tmux send-keys -t "multiagent:agents.${PANE_BASE}" "instructions/karo.md を読んで役割を理解せよ。汝は老中（全プロジェクト統括）である。"
    sleep 0.5
    tmux send-keys -t "multiagent:agents.${PANE_BASE}" Enter

    if [ "$IDLE_MODE" = false ]; then
        # 足軽1に指示書を読み込ませる（pane 1）
        sleep 2
        log_info "  └─ 足軽に指示書を伝達中..."
        p=$((PANE_BASE + 1))
        tmux send-keys -t "multiagent:agents.${p}" "instructions/ashigaru.md を読んで役割を理解せよ。汝は足軽1号である。"
        sleep 0.3
        tmux send-keys -t "multiagent:agents.${p}" Enter

        # 部屋子1に指示書を読み込ませる（multiagent:agents pane 2）
        sleep 2
        log_info "  └─ 部屋子に指示書を伝達中..."
        p=$((PANE_BASE + 2))
        tmux send-keys -t "multiagent:agents.${p}" "instructions/ashigaru.md を読んで役割を理解せよ。汝は部屋子1（内部ID: ashigaru6）である。老中直轄の調査実働部隊じゃ。"
        sleep 0.3
        tmux send-keys -t "multiagent:agents.${p}" Enter

        # ═══════════════════════════════════════════════════════════════════════════
        # ooku セッション: お針子 (pane 0)
        # ═══════════════════════════════════════════════════════════════════════════
        # お針子に指示書を読み込ませる（ooku:agents pane 0）
        sleep 2
        log_info "  └─ お針子に指示書を伝達中..."
        p=${PANE_BASE}
        tmux send-keys -t "ooku:agents.${p}" "instructions/ohariko.md を読んで役割を理解せよ。汝はお針子（監査・先行割当担当）である。"
        sleep 0.3
        tmux send-keys -t "ooku:agents.${p}" Enter
    else
        log_info "  └─ 省力起動: 足軽・部屋子・お針子への指示書伝達はスキップ（worker_ctl.sh start 後に手動で伝達）"
    fi

    # kousatsu（高札）Docker起動（ooku:agents pane 1）
    sleep 1
    log_info "  └─ 高札（kousatsu）を放流中..."
    p=$((PANE_BASE + 1))
    tmux send-keys -t "ooku:agents.${p}" "cd tools/kousatsu && docker compose up --build 2>&1"
    sleep 0.3
    tmux send-keys -t "ooku:agents.${p}" Enter
    log_success "  └─ 高札（通信ハブ+検索API）、放流完了"

    log_success "✅ 全軍に指示書伝達完了 + 高札放流完了"
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: 環境確認・完了メッセージ
# ═══════════════════════════════════════════════════════════════════════════════
log_info "🔍 陣容を確認中..."
echo ""
echo "  ┌──────────────────────────────────────────────────────────┐"
echo "  │  📺 Tmux陣容 (Sessions)                                  │"
echo "  └──────────────────────────────────────────────────────────┘"
tmux list-sessions | sed 's/^/     /'
echo ""
echo "  ┌──────────────────────────────────────────────────────────┐"
echo "  │  📋 布陣図 (Formation)                                   │"
echo "  └──────────────────────────────────────────────────────────┘"
echo ""
echo "     【shogunセッション】将軍の本陣"
echo "     ┌─────────────────────────────┐"
echo "     │  Pane 0: 将軍 (SHOGUN)      │  ← 総大将・プロジェクト統括"
echo "     └─────────────────────────────┘"
echo ""
echo "     【multiagentセッション】老中・足軽・部屋子の陣（3ペイン）"
echo "     ┌────────────────────┐"
echo "     │ karo-roju (老中)   │"
echo "     ├────────────────────┤"
echo "     │ ashigaru1 (足軽1)  │"
echo "     ├────────────────────┤"
echo "     │ heyago1 (部屋子1)  │"
echo "     └────────────────────┘"
echo ""
echo "     【ookuセッション】お針子・高札の陣（2ペイン）"
echo "     ┌────────────────────┐"
echo "     │ ohariko (お針子)   │"
echo "     ├────────────────────┤"
echo "     │ kousatsu (高札)    │"
echo "     │ FTS5+MeCab 🐟Docker│"
echo "     └────────────────────┘"
echo ""

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  🏯 出陣準備完了！天下布武！                              ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

if [ "$SETUP_ONLY" = true ]; then
    echo "  ⚠️  セットアップのみモード: Claude Codeは未起動です"
    echo ""
    echo "  手動でClaude Codeを起動するには:"
    echo "  ┌──────────────────────────────────────────────────────────┐"
    echo "  │  # 将軍を召喚                                            │"
    echo "  │  tmux send-keys -t shogun:main \\                         │"
    echo "  │    'claude --dangerously-skip-permissions' Enter         │"
    echo "  │                                                          │"
    echo "  │  # 老中・足軽・部屋子を一斉召喚 (multiagent)                  │"
    echo "  │  for p in \$(seq $PANE_BASE $((PANE_BASE+2))); do         │"
    echo "  │      tmux send-keys -t multiagent:agents.\$p \\            │"
    echo "  │      'claude --dangerously-skip-permissions' Enter       │"
    echo "  │  done                                                    │"
    echo "  │                                                          │"
    echo "  │  # お針子を召喚 (ooku)                                     │"
    echo "  │  tmux send-keys -t ooku:agents.$PANE_BASE \\              │"
    echo "  │      'claude --dangerously-skip-permissions' Enter       │"
    echo "  └──────────────────────────────────────────────────────────┘"
    echo ""
fi

echo "  次のステップ:"
echo "  ┌──────────────────────────────────────────────────────────┐"
echo "  │  将軍の本陣にアタッチして命令を開始:                      │"
echo "  │     tmux attach-session -t shogun   (または: css)        │"
echo "  │                                                          │"
echo "  │  老中・足軽の陣を確認する:                                │"
echo "  │     tmux attach-session -t multiagent   (または: csm)    │"
echo "  │                                                          │"
echo "  │  部屋子・お針子の陣を確認する:                             │"
echo "  │     tmux attach-session -t ooku   (または: cso)          │"
echo "  │                                                          │"
echo "  │  ※ 各エージェントは指示書を読み込み済み。                 │"
echo "  │    すぐに命令を開始できます。                             │"
echo "  └──────────────────────────────────────────────────────────┘"
echo ""
echo "  ════════════════════════════════════════════════════════════"
echo "   天下布武！勝利を掴め！ (Tenka Fubu! Seize victory!)"
echo "  ════════════════════════════════════════════════════════════"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8: Windows Terminal でタブを開く（-t オプション時のみ）
# ═══════════════════════════════════════════════════════════════════════════════
if [ "$OPEN_TERMINAL" = true ]; then
    log_info "📺 Windows Terminal でタブを展開中..."

    # Windows Terminal が利用可能か確認
    if command -v wt.exe &> /dev/null; then
        wt.exe -w 0 new-tab wsl.exe -e bash -c "tmux attach-session -t shogun" \; new-tab wsl.exe -e bash -c "tmux attach-session -t multiagent" \; new-tab wsl.exe -e bash -c "tmux attach-session -t ooku"
        log_success "  └─ ターミナルタブ展開完了（shogun, multiagent, ooku）"
    else
        log_info "  └─ wt.exe が見つかりません。手動でアタッチしてください。"
    fi
    echo ""
fi
