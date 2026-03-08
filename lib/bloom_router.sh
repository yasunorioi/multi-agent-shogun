#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# bloom_router.sh — Bloom Routing基盤スクリプト
# ═══════════════════════════════════════════════════════════════
# Bloomの認知レベル(L1-L6)に基づきモデル推奨を返す関数ライブラリ。
# Claude専用に簡素化（マルチCLI対応なし）。
#
# Usage:
#   source lib/bloom_router.sh            # 関数をロード
#   bash lib/bloom_router.sh test         # 簡易テスト実行
#
# 依存: python3 + PyYAML（config/settings.yaml読み取り用）
# ═══════════════════════════════════════════════════════════════

_BLOOM_ROUTER_DIR="${_BLOOM_ROUTER_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
_BLOOM_SETTINGS="${_BLOOM_SETTINGS:-${_BLOOM_ROUTER_DIR}/config/settings.yaml}"

# ─── 内部ヘルパー: settings.yamlから値を取得 ───
_bloom_yaml_get() {
    local expr="$1"
    python3 -c "
import yaml, sys
try:
    d = yaml.safe_load(open('${_BLOOM_SETTINGS}'))
    val = eval('d' + sys.argv[1])
    print(val)
except Exception as e:
    print('ERROR:' + str(e), file=sys.stderr)
    print('')
" "$expr" 2>/dev/null
}

# ═══════════════════════════════════════════════════════════════
# 1. get_capability_tier(model_name) → max_bloom (1-6)
# ═══════════════════════════════════════════════════════════════
get_capability_tier() {
    local model="$1"
    if [ -z "$model" ]; then
        echo "ERROR: model_name required" >&2
        return 1
    fi
    local tier
    tier=$(_bloom_yaml_get "['capability_tiers']['${model}']['max_bloom']")
    if [ -z "$tier" ] || [[ "$tier" == ERROR* ]]; then
        echo "ERROR: unknown model '${model}'" >&2
        return 1
    fi
    echo "$tier"
}

# ═══════════════════════════════════════════════════════════════
# 2. get_recommended_model(bloom_level) → model_name
# ═══════════════════════════════════════════════════════════════
get_recommended_model() {
    local level="$1"
    if [ -z "$level" ]; then
        echo "ERROR: bloom_level required (1-6)" >&2
        return 1
    fi

    # Bloom level → preference key
    local pref_key
    if [ "$level" -le 3 ] 2>/dev/null; then
        pref_key="L1-L3"
    elif [ "$level" -le 5 ] 2>/dev/null; then
        pref_key="L4-L5"
    elif [ "$level" -eq 6 ] 2>/dev/null; then
        pref_key="L6"
    else
        echo "ERROR: invalid bloom_level '${level}' (must be 1-6)" >&2
        return 1
    fi

    local model
    model=$(_bloom_yaml_get "['bloom_model_preference']['${pref_key}'][0]")
    if [ -z "$model" ] || [[ "$model" == ERROR* ]]; then
        echo "ERROR: no preference for ${pref_key}" >&2
        return 1
    fi
    echo "$model"
}

# ═══════════════════════════════════════════════════════════════
# 3. get_bloom_routing() → auto|manual|off
# ═══════════════════════════════════════════════════════════════
get_bloom_routing() {
    local mode
    mode=$(_bloom_yaml_get "['bloom_routing']")
    if [ -z "$mode" ] || [[ "$mode" == ERROR* ]]; then
        echo "off"  # デフォルト
        return 0
    fi
    echo "$mode"
}

# ═══════════════════════════════════════════════════════════════
# 4. needs_model_switch(current_model, bloom_level) → yes|no
# ═══════════════════════════════════════════════════════════════
needs_model_switch() {
    local current_model="$1"
    local bloom_level="$2"
    if [ -z "$current_model" ] || [ -z "$bloom_level" ]; then
        echo "ERROR: current_model and bloom_level required" >&2
        return 1
    fi

    local max_bloom
    max_bloom=$(get_capability_tier "$current_model")
    if [ $? -ne 0 ]; then
        echo "ERROR: cannot get capability tier for '${current_model}'" >&2
        return 1
    fi

    if [ "$max_bloom" -ge "$bloom_level" ] 2>/dev/null; then
        echo "no"
    else
        echo "yes"
    fi
}

# ═══════════════════════════════════════════════════════════════
# 5. validate_gunshi_analysis(yaml_path) → valid|error
# ═══════════════════════════════════════════════════════════════
validate_gunshi_analysis() {
    local yaml_path="$1"
    if [ -z "$yaml_path" ]; then
        echo "ERROR: yaml_path required" >&2
        return 1
    fi
    if [ ! -f "$yaml_path" ]; then
        echo "ERROR: file not found '${yaml_path}'" >&2
        return 1
    fi

    local result
    result=$(python3 -c "
import yaml, sys
try:
    d = yaml.safe_load(open(sys.argv[1]))
    errors = []
    if not d.get('task_id'):
        errors.append('missing task_id')
    a = d.get('analysis', {})
    if not a.get('bloom_level'):
        errors.append('missing analysis.bloom_level')
    if not a.get('recommended_model'):
        errors.append('missing analysis.recommended_model')
    if errors:
        print('error:' + '; '.join(errors))
    else:
        print('valid')
except Exception as e:
    print('error:' + str(e))
" "$yaml_path" 2>/dev/null)

    if [[ "$result" == valid ]]; then
        echo "valid"
        return 0
    else
        echo "$result" >&2
        echo "error"
        return 1
    fi
}

# ═══════════════════════════════════════════════════════════════
# 簡易テスト（bash lib/bloom_router.sh test で実行）
# ═══════════════════════════════════════════════════════════════
bloom_router_test() {
    local pass=0
    local fail=0

    _test() {
        local desc="$1" expected="$2" actual="$3"
        if [ "$expected" = "$actual" ]; then
            echo "  PASS: $desc (=$expected)"
            pass=$((pass + 1))
        else
            echo "  FAIL: $desc (expected=$expected, actual=$actual)"
            fail=$((fail + 1))
        fi
    }

    echo "=== bloom_router.sh テスト ==="

    # get_capability_tier
    echo "[get_capability_tier]"
    _test "opus→6" "6" "$(get_capability_tier claude-opus-4-6)"
    _test "sonnet→4" "4" "$(get_capability_tier claude-sonnet-4-6)"
    _test "haiku→2" "2" "$(get_capability_tier claude-haiku-4-5)"

    # get_recommended_model
    echo "[get_recommended_model]"
    _test "L1→sonnet" "claude-sonnet-4-6" "$(get_recommended_model 1)"
    _test "L3→sonnet" "claude-sonnet-4-6" "$(get_recommended_model 3)"
    _test "L4→sonnet" "claude-sonnet-4-6" "$(get_recommended_model 4)"
    _test "L5→sonnet" "claude-sonnet-4-6" "$(get_recommended_model 5)"
    _test "L6→opus" "claude-opus-4-6" "$(get_recommended_model 6)"

    # get_bloom_routing
    echo "[get_bloom_routing]"
    _test "routing=off" "off" "$(get_bloom_routing)"

    # needs_model_switch
    echo "[needs_model_switch]"
    _test "opus+L6→no" "no" "$(needs_model_switch claude-opus-4-6 6)"
    _test "sonnet+L4→no" "no" "$(needs_model_switch claude-sonnet-4-6 4)"
    _test "sonnet+L6→yes" "yes" "$(needs_model_switch claude-sonnet-4-6 6)"
    _test "haiku+L3→yes" "yes" "$(needs_model_switch claude-haiku-4-5 3)"
    _test "haiku+L1→no" "no" "$(needs_model_switch claude-haiku-4-5 1)"

    # validate_gunshi_analysis
    echo "[validate_gunshi_analysis]"
    local tmp_valid tmp_invalid
    tmp_valid=$(mktemp /tmp/bloom_test_XXXXXX.yaml)
    tmp_invalid=$(mktemp /tmp/bloom_test_XXXXXX.yaml)
    cat > "$tmp_valid" <<'YAML'
task_id: gunshi_strategy_001
analysis:
  bloom_level: 5
  recommended_model: claude-opus-4-6
  summary: "test analysis"
YAML
    cat > "$tmp_invalid" <<'YAML'
analysis:
  bloom_level: 5
YAML
    _test "valid yaml→valid" "valid" "$(validate_gunshi_analysis "$tmp_valid")"
    _test "invalid yaml→error" "error" "$(validate_gunshi_analysis "$tmp_invalid" 2>/dev/null)"
    rm -f "$tmp_valid" "$tmp_invalid"

    echo ""
    echo "=== 結果: PASS=$pass FAIL=$fail ==="
    if [ "$fail" -gt 0 ]; then
        return 1
    fi
    return 0
}

# ─── エントリポイント ───
if [ "${1:-}" = "test" ]; then
    bloom_router_test
fi
