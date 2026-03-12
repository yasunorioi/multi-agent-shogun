#!/usr/bin/env python3
"""dream.py — 高札v2 夢見機能プロトタイプ

殿が見そうな夢をネットの海から探し、没日録に蓄積する。
1時間ごとにcronで実行。

動作:
1. 没日録DBから直近7日のcmd/subtaskキーワードを抽出
2. 殿の興味マップ（固定キーワード）とクロス
3. Web検索で関連情報を取得（claude CLI経由）
4. 結果をdreams.jsonlに蓄積（後で高札に食わせる用）
5. 標準出力にサマリを表示

使い方:
  python3 scripts/dream.py                    # 通常実行
  python3 scripts/dream.py --dry-run          # 検索せず、キーワード生成のみ
  python3 scripts/dream.py --topic "量子塩梅"  # 手動トピック指定
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# === 設定 ===

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"
DREAMS_PATH = PROJECT_ROOT / "data" / "dreams.jsonl"

# 殿の興味マップ — Memory MCPとauto memoryから抽出
TONO_INTERESTS = {
    "agriculture_iot": [
        "greenhouse climate control AI",
        "smart agriculture LLM",
        "side window ventilation automation",
        "crop growth model edge computing",
    ],
    "llm_edge": [
        "mixture of experts edge inference",
        "local LLM distillation production",
        "small language model tool calling",
        "MoE quantization raspberry pi",
    ],
    "brain_science": [
        "predictive coding brain LLM",
        "scalar signal dopamine learning",
        "associative memory neural network",
        "hallucination as learning mechanism",
    ],
    "system_design": [
        "multi-agent system self-evolving",
        "event-driven architecture autonomous",
        "FTS5 associative memory pattern",
        "SQLite knowledge graph lightweight",
    ],
    "philosophy": [
        "quantum decision theory uncertainty",
        "information physics causality loop",
        "塩梅 最適化 不確実性",
        "MacGyver engineering philosophy minimal",
    ],
    "economics": [
        "LLM inference cost optimization",
        "edge computing total cost ownership",
        "LLM API cost reduction knowledge distillation",
    ],
}

# 1回の夢見で検索するトピック数（全部回すとコスト過大）
MAX_SEARCHES_PER_RUN = 3

# === DB操作 ===


def get_recent_keywords(days: int = 7) -> list[str]:
    """没日録DBから直近N日のcmd/subtaskキーワードを抽出"""
    if not DB_PATH.exists():
        print(f"WARN: DB not found: {DB_PATH}", file=sys.stderr)
        return []

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    keywords = []

    # commands
    for row in conn.execute(
        "SELECT command, details FROM commands WHERE created_at > ? OR timestamp > ?",
        (cutoff, cutoff),
    ):
        text = f"{row['command'] or ''} {row['details'] or ''}"
        keywords.extend(extract_nouns_simple(text))

    # subtasks
    for row in conn.execute(
        "SELECT description FROM subtasks WHERE assigned_at > ?", (cutoff,)
    ):
        text = row["description"] or ""
        keywords.extend(extract_nouns_simple(text))

    conn.close()

    # 重複除去、頻度順
    from collections import Counter

    freq = Counter(keywords)
    # 2回以上出現 or 長い単語（専門用語の可能性）
    significant = [
        w for w, c in freq.most_common(50) if c >= 2 or len(w) >= 6
    ]
    return significant[:20]


def extract_nouns_simple(text: str) -> list[str]:
    """簡易名詞抽出（MeCabなし版。プロトタイプ用）"""
    # 英単語（3文字以上）
    en_words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
    # 日本語（カタカナ2文字以上、漢字2文字以上）
    ja_katakana = re.findall(r"[ァ-ヶー]{2,}", text)
    ja_kanji = re.findall(r"[一-龥]{2,}", text)

    # ストップワード
    stopwords = {
        "the", "and", "for", "that", "this", "with", "from", "have", "not",
        "are", "was", "will", "can", "has", "been", "but", "all", "cmd",
        "subtask", "status", "done", "assigned", "description", "yaml",
        "queue", "inbox", "report", "する", "ある", "いる", "なる", "できる",
        "これ", "それ", "もの", "こと", "ため", "よう", "ところ",
    }
    words = en_words + ja_katakana + ja_kanji
    return [w.lower() for w in words if w.lower() not in stopwords]


# === 夢見のコア ===


def generate_dream_queries(recent_kw: list[str]) -> list[dict]:
    """殿の興味マップ × 直近キーワードから検索クエリを生成"""
    queries = []

    # 直近キーワードと興味マップの交差点を探す
    for domain, templates in TONO_INTERESTS.items():
        for template in templates:
            # 直近キーワードとの関連度を簡易スコアリング
            score = 0
            for kw in recent_kw:
                if kw.lower() in template.lower():
                    score += 3  # 完全一致
                elif any(
                    kw.lower() in t.lower() for t in template.split()
                ):
                    score += 1  # 部分一致

            queries.append({
                "domain": domain,
                "query": template,
                "relevance_score": score,
                "matched_keywords": [
                    kw for kw in recent_kw if kw.lower() in template.lower()
                ],
            })

    # スコア順ソート + ランダム性を入れる（同じ夢ばかり見ないように）
    import random

    # 上位半分はスコア順、下位半分からランダムに1つ（セレンディピティ）
    queries.sort(key=lambda q: q["relevance_score"], reverse=True)
    top = queries[: MAX_SEARCHES_PER_RUN - 1]
    rest = queries[MAX_SEARCHES_PER_RUN - 1 :]
    if rest:
        serendipity = [random.choice(rest)]
        top.extend(serendipity)

    return top[:MAX_SEARCHES_PER_RUN]


def search_web(query: str) -> str | None:
    """DuckDuckGo Lite経由でWeb検索（プロトタイプ、API課金ゼロ）

    本番では高札コンテナ内のHTTPクライアントに置き換え。
    """
    import urllib.request
    import urllib.parse
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "jp-jp"})
        url = f"https://lite.duckduckgo.com/lite/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "dream.py/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # HTMLから検索結果のタイトルとスニペットを抽出（簡易パーサ）
        results = []
        # DuckDuckGo Liteの結果はテーブル形式
        snippets = re.findall(
            r'result-snippet[^>]*>(.*?)</td>', html, re.DOTALL
        )
        links = re.findall(
            r"class='result-link'>(.*?)</a>", html, re.DOTALL
        )

        for i, snippet in enumerate(snippets[:3]):
            title = links[i] if i < len(links) else ""
            title = re.sub(r"<[^>]+>", "", title).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if snippet:
                results.append(f"[{title}] {snippet}" if title else snippet)

        if results:
            return " | ".join(results)
    except Exception as e:
        print(f"WARN: web search failed for '{query}': {e}", file=sys.stderr)
    return None


def search_web_curl(query: str) -> str | None:
    """高札API経由の検索（高札v2実装後に使用）"""
    try:
        result = subprocess.run(
            [
                "curl", "-s", "--get",
                "http://localhost:8080/search",
                "--data-urlencode", f"q={query}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except subprocess.TimeoutExpired:
        pass
    return None


# === 蓄積 ===


def save_dream(dream: dict) -> None:
    """夢をJSONLに追記"""
    DREAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DREAMS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(dream, ensure_ascii=False) + "\n")


def load_recent_dreams(hours: int = 24) -> list[dict]:
    """直近N時間の夢を読み込み（重複防止用）"""
    if not DREAMS_PATH.exists():
        return []
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    dreams = []
    with open(DREAMS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line.strip())
                if d.get("dreamt_at", "") > cutoff:
                    dreams.append(d)
            except json.JSONDecodeError:
                continue
    return dreams


# === メイン ===


def dream(dry_run: bool = False, manual_topic: str | None = None) -> None:
    """夢見の本体"""
    now = datetime.now()
    print(f"=== dream.py 起動 {now.strftime('%Y-%m-%d %H:%M')} ===")

    # 1. 直近キーワード抽出
    recent_kw = get_recent_keywords(days=7)
    print(f"直近7日のキーワード ({len(recent_kw)}): {', '.join(recent_kw[:10])}...")

    # 2. 検索クエリ生成
    if manual_topic:
        queries = [{"domain": "manual", "query": manual_topic, "relevance_score": 99, "matched_keywords": []}]
    else:
        queries = generate_dream_queries(recent_kw)

    # 重複チェック
    recent_dreams = load_recent_dreams(hours=6)
    recent_queries = {d.get("query", "") for d in recent_dreams}
    queries = [q for q in queries if q["query"] not in recent_queries]

    if not queries:
        print("直近6時間と同じ夢は見ない。スキップ。")
        return

    print(f"\n今夜の夢 ({len(queries)}件):")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. [{q['domain']}] {q['query']} (relevance: {q['relevance_score']})")

    if dry_run:
        print("\n--dry-run: 検索はスキップ")
        return

    # 3. 検索実行
    dreams_found = []
    for q in queries:
        print(f"\n夢見中: {q['query']}...")
        # まず内部検索（高札API）
        internal = search_web_curl(q["query"])

        # 外部検索（claude CLI）
        external = search_web(q["query"])

        dream_entry = {
            "dreamt_at": now.isoformat(),
            "domain": q["domain"],
            "query": q["query"],
            "relevance_score": q["relevance_score"],
            "matched_keywords": q["matched_keywords"],
            "internal_result": internal[:500] if internal else None,
            "external_result": external[:500] if external else None,
            "status": "raw",  # raw → reviewed → applied
        }

        save_dream(dream_entry)
        dreams_found.append(dream_entry)

        # 結果表示
        if external:
            print(f"  → {external[:200]}...")
        elif internal:
            print(f"  → (内部) {internal[:200]}...")
        else:
            print("  → 夢なし")

    # 4. サマリ
    found = sum(1 for d in dreams_found if d["external_result"] or d["internal_result"])
    print(f"\n=== 夢見完了: {found}/{len(dreams_found)}件の夢を見た ===")
    print(f"蓄積先: {DREAMS_PATH}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="高札v2 夢見機能プロトタイプ")
    parser.add_argument("--dry-run", action="store_true", help="検索せずキーワード生成のみ")
    parser.add_argument("--topic", type=str, help="手動トピック指定")
    args = parser.parse_args()

    dream(dry_run=args.dry_run, manual_topic=args.topic)
