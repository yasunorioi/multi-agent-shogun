#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# worker_ctl.sh - Dynamic worker start/stop/status management
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   scripts/worker_ctl.sh start ashigaru1 [--model sonnet|opus]
#   scripts/worker_ctl.sh stop ashigaru1 [--force]
#   scripts/worker_ctl.sh status
#   scripts/worker_ctl.sh idle
#   scripts/worker_ctl.sh count-needed
#   scripts/worker_ctl.sh stop-idle
#
# Manages Claude Code instances in tmux panes dynamically.
# Starts/stops workers on demand to save API costs.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_ROOT/data/botsunichiroku.db"

# ═══════════════════════════════════════════════════════════════════════════════
# Worker configuration
# ═══════════════════════════════════════════════════════════════════════════════

# Map agent_id -> tmux pane target
declare -A PANE_MAP=(
    [ashigaru1]="multiagent:agents.1"
    [ashigaru2]="multiagent:agents.2"
    [ashigaru3]="multiagent:agents.3"
    [ashigaru6]="ooku:agents.0"
    [ashigaru7]="ooku:agents.1"
    [ohariko]="ooku:agents.2"
)

# Map agent_id -> default model
declare -A DEFAULT_MODEL=(
    [ashigaru1]="sonnet"
    [ashigaru2]="sonnet"
    [ashigaru3]="sonnet"
    [ashigaru6]="opus"
    [ashigaru7]="opus"
    [ohariko]="sonnet"
)

# Map agent_id -> display label for pane title
declare -A DISPLAY_LABEL=(
    [ashigaru1]="ashigaru1"
    [ashigaru2]="ashigaru2"
    [ashigaru3]="ashigaru3"
    [ashigaru6]="heyago1"
    [ashigaru7]="heyago2"
    [ohariko]="ohariko"
)

# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

log_info() {
    echo -e "\033[1;33m【報】\033[0m $1"
}

log_success() {
    echo -e "\033[1;32m【成】\033[0m $1"
}

log_error() {
    echo -e "\033[1;31m【誤】\033[0m $1" >&2
}

# Check if a pane exists
pane_exists() {
    local pane="$1"
    tmux has-session -t "${pane%%:*}" 2>/dev/null && \
    tmux list-panes -t "${pane%.*}" -F '#{pane_index}' 2>/dev/null | grep -q "^${pane##*.}$"
}

# Get pane state: running-busy, running-idle, stopped
get_pane_state() {
    local pane="$1"

    if ! pane_exists "$pane"; then
        echo "no-pane"
        return
    fi

    local content
    content=$(tmux capture-pane -t "$pane" -p 2>/dev/null | tail -20)

    # Check if Claude Code is running and busy
    if echo "$content" | grep -qE "(thinking|Effecting|Boondoggling|Puzzling|Calculating|Fermenting|Crunching|Esc to interrupt)"; then
        echo "running-busy"
        return
    fi

    # Check if Claude Code is running and idle (at prompt)
    if echo "$content" | grep -qE "(bypass permissions|❯ )"; then
        echo "running-idle"
        return
    fi

    # Check if shell prompt is showing (Claude Code not running)
    if echo "$content" | grep -qE "(\\\$|%) $"; then
        echo "stopped"
        return
    fi

    # Default: assume stopped
    echo "stopped"
}

# Get model display name
model_display() {
    local model="$1"
    case "$model" in
        opus)   echo "Opus Thinking" ;;
        sonnet) echo "Sonnet Thinking" ;;
        *)      echo "$model" ;;
    esac
}

# ═══════════════════════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════════════════════

cmd_start() {
    local agent_id="$1"
    local model="${2:-${DEFAULT_MODEL[$agent_id]}}"

    if [ -z "${PANE_MAP[$agent_id]}" ]; then
        log_error "Unknown agent: $agent_id"
        echo "Valid agents: ${!PANE_MAP[*]}"
        exit 1
    fi

    local pane="${PANE_MAP[$agent_id]}"
    local state
    state=$(get_pane_state "$pane")

    case "$state" in
        running-busy)
            log_info "$agent_id is already running (busy)"
            return 0
            ;;
        running-idle)
            log_info "$agent_id is already running (idle)"
            return 0
            ;;
        no-pane)
            log_error "Pane $pane does not exist. Run shutsujin_departure.sh first."
            exit 1
            ;;
    esac

    # Start Claude Code
    log_info "Starting $agent_id with model=$model on $pane..."

    tmux send-keys -t "$pane" "claude --model $model --dangerously-skip-permissions"
    tmux send-keys -t "$pane" Enter

    # Update tmux pane metadata
    local display_name
    display_name=$(model_display "$model")
    local label="${DISPLAY_LABEL[$agent_id]}"
    tmux select-pane -t "$pane" -T "${label}(${display_name})"
    tmux set-option -p -t "$pane" @model_name "$display_name"

    # Wait for startup (max 30 seconds)
    log_info "Waiting for startup (max 30s)..."
    for i in $(seq 1 30); do
        local new_state
        new_state=$(get_pane_state "$pane")
        if [ "$new_state" = "running-idle" ] || [ "$new_state" = "running-busy" ]; then
            log_success "$agent_id started successfully (${i}s)"
            return 0
        fi
        sleep 1
    done

    log_error "$agent_id startup timed out after 30s. Check pane manually."
    exit 1
}

cmd_stop() {
    local agent_id="$1"
    local force="${2:-false}"

    if [ -z "${PANE_MAP[$agent_id]}" ]; then
        log_error "Unknown agent: $agent_id"
        exit 1
    fi

    local pane="${PANE_MAP[$agent_id]}"
    local state
    state=$(get_pane_state "$pane")

    case "$state" in
        stopped)
            log_info "$agent_id is already stopped"
            return 0
            ;;
        running-busy)
            if [ "$force" != "true" ]; then
                log_error "$agent_id is busy! Use --force to stop anyway."
                exit 1
            fi
            log_info "Force-stopping busy $agent_id..."
            ;;
        running-idle)
            log_info "Stopping idle $agent_id..."
            ;;
    esac

    # Send /exit to Claude Code
    tmux send-keys -t "$pane" '/exit'
    tmux send-keys -t "$pane" Enter

    # Wait for exit (max 10 seconds)
    for i in $(seq 1 10); do
        local new_state
        new_state=$(get_pane_state "$pane")
        if [ "$new_state" = "stopped" ]; then
            log_success "$agent_id stopped (${i}s)"
            return 0
        fi
        sleep 1
    done

    log_error "$agent_id did not stop within 10s. May need manual intervention."
    exit 1
}

cmd_status() {
    echo ""
    echo "  ┌────────────────────────────────────────────────────────┐"
    echo "  │  Worker Status                                          │"
    echo "  └────────────────────────────────────────────────────────┘"
    echo ""

    printf "  %-12s  %-24s  %-15s  %-16s\n" "AGENT" "PANE" "STATE" "MODEL"
    printf "  %-12s  %-24s  %-15s  %-16s\n" "────────────" "────────────────────────" "───────────────" "────────────────"

    for agent_id in ashigaru1 ashigaru2 ashigaru3 ashigaru6 ashigaru7 ohariko; do
        local pane="${PANE_MAP[$agent_id]}"
        local state
        state=$(get_pane_state "$pane")

        local model_name="-"
        if [ "$state" = "running-idle" ] || [ "$state" = "running-busy" ]; then
            model_name=$(tmux show-options -p -t "$pane" -v @model_name 2>/dev/null || echo "unknown")
        fi

        # Color-code state
        local colored_state
        case "$state" in
            running-busy)  colored_state="\033[1;31m$state\033[0m" ;;
            running-idle)  colored_state="\033[1;32m$state\033[0m" ;;
            stopped)       colored_state="\033[1;33m$state\033[0m" ;;
            no-pane)       colored_state="\033[1;35m$state\033[0m" ;;
            *)             colored_state="$state" ;;
        esac

        printf "  %-12s  %-24s  ${colored_state}%*s  %-16s\n" "$agent_id" "$pane" "$((15 - ${#state}))" "" "$model_name"
    done
    echo ""
}

cmd_idle() {
    local idle_workers=()

    for agent_id in ashigaru1 ashigaru2 ashigaru3 ashigaru6 ashigaru7 ohariko; do
        local pane="${PANE_MAP[$agent_id]}"
        local state
        state=$(get_pane_state "$pane")
        if [ "$state" = "running-idle" ]; then
            idle_workers+=("$agent_id")
        fi
    done

    if [ ${#idle_workers[@]} -eq 0 ]; then
        echo "No idle workers found."
    else
        echo "Idle workers (${#idle_workers[@]}):"
        for w in "${idle_workers[@]}"; do
            echo "  - $w (${PANE_MAP[$w]})"
        done
    fi
}

cmd_count_needed() {
    if [ ! -f "$DB_PATH" ]; then
        log_error "Database not found: $DB_PATH"
        exit 1
    fi

    # Count subtasks with status 'assigned' or 'pending' (ready to work)
    local count
    count=$(python3 -c "import sqlite3; conn=sqlite3.connect('$DB_PATH'); print(conn.execute(\"SELECT COUNT(*) FROM subtasks WHERE status IN ('assigned','pending')\").fetchone()[0])")
    echo "Subtasks needing workers: $count"

    # Count currently running workers
    local running=0
    for agent_id in ashigaru1 ashigaru2 ashigaru3 ashigaru6 ashigaru7; do
        local state
        state=$(get_pane_state "${PANE_MAP[$agent_id]}")
        if [ "$state" = "running-idle" ] || [ "$state" = "running-busy" ]; then
            running=$((running + 1))
        fi
    done
    echo "Running workers: $running"

    local needed=$((count - running))
    if [ "$needed" -lt 0 ]; then
        needed=0
    fi
    echo "Additional workers needed: $needed"
}

cmd_stop_idle() {
    local stopped=0

    for agent_id in ashigaru1 ashigaru2 ashigaru3 ashigaru6 ashigaru7 ohariko; do
        local pane="${PANE_MAP[$agent_id]}"
        local state
        state=$(get_pane_state "$pane")
        if [ "$state" = "running-idle" ]; then
            log_info "Stopping idle $agent_id..."
            tmux send-keys -t "$pane" '/exit'
            tmux send-keys -t "$pane" Enter
            stopped=$((stopped + 1))
        fi
    done

    if [ "$stopped" -eq 0 ]; then
        log_info "No idle workers to stop."
    else
        # Wait a moment for exits
        sleep 3
        log_success "Stopped $stopped idle worker(s)."
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

show_usage() {
    echo ""
    echo "Usage: scripts/worker_ctl.sh <command> [args]"
    echo ""
    echo "Commands:"
    echo "  start <agent_id> [--model sonnet|opus]  Start Claude Code in worker pane"
    echo "  stop <agent_id> [--force]               Stop Claude Code (warns if busy)"
    echo "  status                                  Show all worker states"
    echo "  idle                                    List idle workers"
    echo "  count-needed                            Count workers needed for pending tasks"
    echo "  stop-idle                               Stop all idle workers"
    echo ""
    echo "Agent IDs: ashigaru1-3, ashigaru6-7 (heyago), ohariko"
    echo ""
    echo "Examples:"
    echo "  scripts/worker_ctl.sh start ashigaru1"
    echo "  scripts/worker_ctl.sh start ashigaru6 --model sonnet"
    echo "  scripts/worker_ctl.sh stop ashigaru2"
    echo "  scripts/worker_ctl.sh stop ashigaru1 --force"
    echo "  scripts/worker_ctl.sh status"
    echo "  scripts/worker_ctl.sh stop-idle"
    echo ""
}

if [ $# -lt 1 ]; then
    show_usage
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    start)
        if [ $# -lt 1 ]; then
            log_error "Usage: worker_ctl.sh start <agent_id> [--model sonnet|opus]"
            exit 1
        fi
        AGENT_ID="$1"
        shift
        MODEL=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --model)
                    MODEL="$2"
                    shift 2
                    ;;
                *)
                    log_error "Unknown option: $1"
                    exit 1
                    ;;
            esac
        done
        cmd_start "$AGENT_ID" "$MODEL"
        ;;
    stop)
        if [ $# -lt 1 ]; then
            log_error "Usage: worker_ctl.sh stop <agent_id> [--force]"
            exit 1
        fi
        AGENT_ID="$1"
        shift
        FORCE="false"
        while [ $# -gt 0 ]; do
            case "$1" in
                --force) FORCE="true"; shift ;;
                *) log_error "Unknown option: $1"; exit 1 ;;
            esac
        done
        cmd_stop "$AGENT_ID" "$FORCE"
        ;;
    status)
        cmd_status
        ;;
    idle)
        cmd_idle
        ;;
    count-needed)
        cmd_count_needed
        ;;
    stop-idle)
        cmd_stop_idle
        ;;
    -h|--help|help)
        show_usage
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac
