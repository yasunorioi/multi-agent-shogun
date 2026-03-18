#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# healthcheck.sh — 4コンポーネント生存確認（Silent Degradation検知）
# 異常時は警告表示のみ（ブロックしない）。常に exit 0。
# ═══════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
TOTAL=0

check() {
    TOTAL=$((TOTAL + 1))
    if eval "$1" >/dev/null 2>&1; then
        echo "[OK]   $2"
        PASS=$((PASS + 1))
    else
        echo "[WARN] $3"
    fi
}

echo "═══ HealthCheck ═══"

# 1. Memory MCP設定確認
MCP_CFG="$SCRIPT_DIR/.mcp.json"
TOTAL=$((TOTAL + 1))
if [ -f "$MCP_CFG" ] && grep -q '"memory"' "$MCP_CFG" 2>/dev/null; then
    MEM_FILE=$(python3 -c "import json; print(json.load(open('$MCP_CFG'))['mcpServers']['memory']['env']['MEMORY_FILE_PATH'])" 2>/dev/null)
    if [ -n "$MEM_FILE" ] && [ -f "$MEM_FILE" ]; then
        echo "[OK]   Memory MCP: 設定あり, memory file存在"
    else
        echo "[OK]   Memory MCP: 設定あり (memory fileは未生成の可能性)"
    fi
    PASS=$((PASS + 1))
else
    echo "[WARN] Memory MCP: .mcp.json にmemory設定なし"
fi

# 2. 高札Docker（廃止済み確認）
TOTAL=$((TOTAL + 1))
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health --max-time 2 2>/dev/null)
HTTP_CODE="${HTTP_CODE:-000}"
if [ "$HTTP_CODE" = "000" ]; then
    echo "[OK]   高札Docker: 停止中（正常）"
    PASS=$((PASS + 1))
else
    echo "[WARN] 高札Docker: 応答あり(HTTP $HTTP_CODE) — 不要なDocker稼働中？"
fi

# 3. inbox YAML構文チェック
for YFILE in roju_reports.yaml roju_ohariko.yaml; do
    YPATH="$SCRIPT_DIR/queue/inbox/$YFILE"
    TOTAL=$((TOTAL + 1))
    if [ ! -f "$YPATH" ]; then
        echo "[WARN] inbox YAML: $YFILE 不在"
    elif python3 -c "import yaml; yaml.safe_load(open('$YPATH'))" 2>/dev/null; then
        echo "[OK]   inbox YAML: $YFILE 構文OK"
        PASS=$((PASS + 1))
    else
        echo "[WARN] inbox YAML: $YFILE 構文エラー"
    fi
done

# 4. 没日録DB整合性
DB_PATH="$SCRIPT_DIR/data/botsunichiroku.db"
TOTAL=$((TOTAL + 1))
if [ ! -f "$DB_PATH" ]; then
    echo "[WARN] 没日録DB: ファイル不在"
else
    INTEGRITY=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check" 2>/dev/null)
    CMD_COUNT=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM commands" 2>/dev/null || echo "?")
    if [ "$INTEGRITY" = "ok" ]; then
        echo "[OK]   没日録DB: integrity_check=ok, commands=${CMD_COUNT}件"
        PASS=$((PASS + 1))
    else
        echo "[WARN] 没日録DB: integrity_check=$INTEGRITY"
    fi
fi

echo "═══ ${PASS}/${TOTAL} passed ═══"
exit 0
