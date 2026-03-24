#!/usr/bin/env python3
"""
bloom_router.py — Bloom Auto-Router v1
没日録の類似タスク成功率でeffortを自動決定する。

Phase 1実装 (cmd_439 subtask_975)
設計書: docs/shogun/quality_guardrails_design_v2.md §2.4

使用方法:
  # モジュールとして
  from scripts.bloom_router import route
  effort = route("YAML編集", bloom_level=2)  # → "low"

  # CLIとして
  python3 scripts/bloom_router.py "YAML編集" 2          → low
  python3 scripts/bloom_router.py "新規アーキテクチャ設計" 6  → max
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# botsunichiroku.pyへのパス（このスクリプトと同じディレクトリ）
_SCRIPTS_DIR = Path(__file__).resolve().parent
_BOTSUNICHIROKU = str(_SCRIPTS_DIR / "botsunichiroku.py")


def route(description: str, bloom_level: int) -> str:
    """没日録の類似タスク検索結果とbloom_levelからeffortを決定する。

    Args:
        description: タスクの説明文（最初の50文字を検索に使用）
        bloom_level: Bloomタキソノミーレベル (1-6)

    Returns:
        effort level: "low" | "medium" | "high" | "max"
    """
    # 没日録で類似タスクを検索し "Total hits: N" からヒット数を取得
    similar_count = 0
    try:
        result = subprocess.run(
            ["python3", _BOTSUNICHIROKU, "search", description[:50]],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Total hits:"):
                # "Total hits: 2  (showing 2)" → 2
                similar_count = int(line.split(":")[1].split()[0])
                break
    except Exception:
        # 検索失敗時はbloom_levelのみで判定（fail-open）
        similar_count = 0

    # bloom_levelベースのeffort（フォールバック用）
    # L1-3(記憶・理解・応用) → low / L4-5(分析・評価) → high / L6(創造) → max
    if bloom_level <= 3:
        bloom_effort = "low"
    elif bloom_level <= 5:
        bloom_effort = "high"
    else:
        bloom_effort = "max"

    if similar_count >= 3:
        # 既知パターン: CogRouterの「後半94.8%がL1に収束」
        return "low"
    elif similar_count >= 1:
        # 1-2件: bloom_levelがシンプル(≤3)なら安全にlow、そうでなければmedium
        return "low" if bloom_level <= 3 else "medium"
    else:
        # 未知領域: bloom_levelに従う
        return bloom_effort


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python3 scripts/bloom_router.py <description> <bloom_level>",
            file=sys.stderr,
        )
        sys.exit(1)

    desc = sys.argv[1]
    try:
        level = int(sys.argv[2])
    except ValueError:
        print(f"Error: bloom_level must be an integer, got: {sys.argv[2]}", file=sys.stderr)
        sys.exit(1)

    print(route(desc, level))
