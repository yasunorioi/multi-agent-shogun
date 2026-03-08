#!/usr/bin/env bash
# shogun-gc.sh - roju_reports.yaml / roju_ohariko.yaml 自動GCスクリプト
#
# 使い方:
#   scripts/shogun-gc.sh            # dry-run結果を表示 → 確認プロンプト
#   scripts/shogun-gc.sh --dry-run  # 削除候補表示のみ（実削除しない）
#   scripts/shogun-gc.sh --force    # 確認なしで即実行
#
# 動作: read:true かつ最新10件を超えるエントリを削除
#   soft_limit: 10件超過で警告表示
#   hard_limit: 30件超過で自動実行強く推奨

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REPORTS_YAML="$REPO_ROOT/queue/inbox/roju_reports.yaml"
OHARIKO_YAML="$REPO_ROOT/queue/inbox/roju_ohariko.yaml"

SOFT_LIMIT=10
HARD_LIMIT=30
KEEP=10

DRY_RUN=false
FORCE=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --force)   FORCE=true ;;
    *) echo "Unknown option: $arg"; echo "Usage: $0 [--dry-run] [--force]"; exit 1 ;;
  esac
done

python3 - "$REPORTS_YAML" "$OHARIKO_YAML" \
          "$DRY_RUN" "$FORCE" \
          "$SOFT_LIMIT" "$HARD_LIMIT" "$KEEP" <<'PYEOF'
import sys
import yaml

reports_path, ohariko_path, dry_run_str, force_str, soft_str, hard_str, keep_str = sys.argv[1:]

DRY_RUN   = dry_run_str == "true"
FORCE     = force_str   == "true"
SOFT_LIMIT = int(soft_str)
HARD_LIMIT = int(hard_str)
KEEP       = int(keep_str)


def analyze(path, list_key, sort_key=None):
    """YAMLファイルを解析し、GC候補を返す。"""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    entries = data.get(list_key) or []

    read_entries   = [e for e in entries if e.get("read") is True]
    unread_entries = [e for e in entries if e.get("read") is not True]

    # ソート: sort_key があれば降順（最新が先頭）、なければ挿入順（末尾が最新）
    if sort_key:
        read_sorted = sorted(read_entries,
                             key=lambda e: e.get(sort_key) or "",
                             reverse=True)
    else:
        read_sorted = list(read_entries)  # 挿入順のまま（末尾=最新）

    if len(read_sorted) <= KEEP:
        keep_entries   = read_sorted
        delete_entries = []
    else:
        if sort_key:
            # 降順: 先頭KEEP件が最新
            keep_entries   = read_sorted[:KEEP]
            delete_entries = read_sorted[KEEP:]
        else:
            # 挿入順: 末尾KEEP件が最新
            keep_entries   = read_sorted[-KEEP:]
            delete_entries = read_sorted[:-KEEP]

    status_msgs = []
    read_count = len(read_entries)
    if read_count > HARD_LIMIT:
        status_msgs.append(
            f"  ⚠️  HARD LIMIT超過: {read_count}件 > {HARD_LIMIT}件 — 自動実行を強く推奨")
    elif read_count > SOFT_LIMIT:
        status_msgs.append(
            f"  ⚠️  soft_limit超過: {read_count}件 > {SOFT_LIMIT}件 — GC推奨")

    return {
        "path":           path,
        "list_key":       list_key,
        "data":           data,
        "entries":        entries,
        "read_count":     read_count,
        "total":          len(entries),
        "keep_entries":   keep_entries,
        "delete_entries": delete_entries,
        "status_msgs":    status_msgs,
    }


files = [
    (reports_path, "reports",     "reported_at"),
    (ohariko_path, "audit_queue", None),
]

results = []
for path, list_key, sort_key in files:
    try:
        results.append(analyze(path, list_key, sort_key))
    except FileNotFoundError:
        print(f"WARN: {path} が見つかりません。スキップ。")
    except yaml.YAMLError as e:
        print(f"WARN: {path} のYAMLパースに失敗。スキップ。")
        print(f"  詳細: {e}")
    except Exception as e:
        print(f"ERROR: {path}: {e}")
        sys.exit(1)

# ─── 結果表示 ────────────────────────────────────────────────────────────────
any_delete = False
for r in results:
    fname = r["path"].split("/")[-1]
    print(f"\n{'='*52}")
    print(f"  {fname}")
    print(f"  総エントリ: {r['total']}件 / read:true: {r['read_count']}件")
    for msg in r["status_msgs"]:
        print(msg)

    if not r["delete_entries"]:
        print(f"  ✅ GC対象なし（read:true が {KEEP}件以下）")
    else:
        any_delete = True
        print(f"  🗑️  削除候補: {len(r['delete_entries'])}件 / 保持: {len(r['keep_entries'])}件")
        for e in r["delete_entries"]:
            label = e.get("subtask_id") or e.get("cmd_id") or "?"
            ts    = e.get("reported_at") or ""
            print(f"    - {label}  {ts}")

if not any_delete:
    print("\nGC対象なし。終了。")
    sys.exit(0)

if DRY_RUN:
    print("\n[DRY-RUN] 実削除はしません。")
    sys.exit(0)

# ─── 確認プロンプト ───────────────────────────────────────────────────────────
if not FORCE:
    print("\n上記エントリを削除します。続行しますか？ [y/N]: ", end="", flush=True)
    ans = input().strip().lower()
    if ans != "y":
        print("中止。")
        sys.exit(0)

# ─── 実削除 ──────────────────────────────────────────────────────────────────
for r in results:
    if not r["delete_entries"]:
        continue

    delete_ids = {id(e) for e in r["delete_entries"]}
    list_key   = r["list_key"]
    data       = r["data"]

    new_entries = [
        e for e in (data.get(list_key) or [])
        if id(e) not in delete_ids
    ]
    data[list_key] = new_entries

    with open(r["path"], "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True,
                  default_flow_style=False, sort_keys=False)

    fname = r["path"].split("/")[-1]
    print(f"✅ {fname}: {len(r['delete_entries'])}件削除完了"
          f"（残: {len(new_entries)}件）")

print("\nGC完了。")
PYEOF
