#!/usr/bin/env python3
"""
獏: raw夢の一括再解釈スクリプト
並列ワーカー対応 — 結果を個別ファイルに書き出し、--merge で統合

Usage:
  # 4並列で解釈
  python3 scripts/baku_reinterpret.py --worker 0 --total 4 &
  python3 scripts/baku_reinterpret.py --worker 1 --total 4 &
  python3 scripts/baku_reinterpret.py --worker 2 --total 4 &
  python3 scripts/baku_reinterpret.py --worker 3 --total 4 &
  wait
  # 結果をdreams.jsonlに統合
  python3 scripts/baku_reinterpret.py --merge
"""
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.baku import interpret_dream, DREAMS_PATH

RESULT_DIR = DREAMS_PATH.parent / "reinterpret_results"


def load_raw_dreams():
    dreams = []
    with open(DREAMS_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            d = json.loads(line)
            if d.get("status") == "raw":
                d["_line_index"] = i
                dreams.append(d)
    return dreams


def run_worker(worker_id, total, dry_run=False):
    all_raw = load_raw_dreams()
    my_dreams = [d for i, d in enumerate(all_raw) if i % total == worker_id]
    print(f"[足軽{worker_id}] 担当 {len(my_dreams)}/{len(all_raw)} 件の夢解釈を承る！")

    if dry_run:
        for d in my_dreams[:5]:
            print(f"  [{d.get('domain')}] {d.get('query', '')[:60]}")
        print(f"  ... (残り {max(0, len(my_dreams)-5)} 件)")
        return

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result_file = RESULT_DIR / f"worker_{worker_id}.jsonl"

    success = 0
    fail = 0
    with open(result_file, "w", encoding="utf-8") as out:
        for i, dream in enumerate(my_dreams):
            try:
                result = interpret_dream(dream, "農業IoT・温室LLM・マルチエージェント・金融OSINT・水資源")
                if result:
                    dream["interpretation"] = result
                    dream["status"] = "interpreted"
                    dream["interpreted_at"] = datetime.now().isoformat()
                    action = result.get("action", "?")
                    rel = result.get("relevance", "?")
                    print(f"  [{i+1}/{len(my_dreams)}] {dream.get('domain')}: {dream.get('query','')[:45]} → {action}({rel})")
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                print(f"  [{i+1}/{len(my_dreams)}] ERROR: {e}")
                fail += 1

            # _line_index を保持して書き出し
            out.write(json.dumps(dream, ensure_ascii=False) + "\n")
            out.flush()

            # Rate limit: 0.3s間隔 (Haiku tier1 = 60rpm程度)
            time.sleep(0.3)

    print(f"[足軽{worker_id}] 完了！ 成功={success} 失敗={fail} → {result_file}")


def merge_results():
    """ワーカー結果をdreams.jsonlに統合"""
    if not RESULT_DIR.exists():
        print("結果ディレクトリが無い。先にワーカーを実行せよ。")
        return

    # 結果を読み込み: line_index → updated dream
    updates = {}
    for result_file in sorted(RESULT_DIR.glob("worker_*.jsonl")):
        with open(result_file, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                idx = d.pop("_line_index", None)
                if idx is not None and d.get("status") == "interpreted":
                    updates[idx] = d
        print(f"  {result_file.name}: {sum(1 for v in updates.values())} 件の解釈済み")

    if not updates:
        print("解釈済みの夢がない。")
        return

    # dreams.jsonl を更新
    lines = DREAMS_PATH.read_text(encoding="utf-8").splitlines()
    applied = 0
    for idx, dream in updates.items():
        if 0 <= idx < len(lines):
            lines[idx] = json.dumps(dream, ensure_ascii=False)
            applied += 1

    DREAMS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"統合完了: {applied}/{len(updates)} 件を dreams.jsonl に反映")

    # 結果ファイルを削除
    for f in RESULT_DIR.glob("worker_*.jsonl"):
        f.unlink()
    RESULT_DIR.rmdir()
    print("一時ファイル削除完了")


def main():
    parser = argparse.ArgumentParser(description="獏: raw夢の一括再解釈")
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--total", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--merge", action="store_true", help="ワーカー結果をdreams.jsonlに統合")
    args = parser.parse_args()

    if args.merge:
        merge_results()
    else:
        run_worker(args.worker, args.total, args.dry_run)


if __name__ == "__main__":
    main()
