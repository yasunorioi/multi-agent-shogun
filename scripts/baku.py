#!/usr/bin/env python3
"""baku.py — 獏（ばく）: 夢見デーモン

殿が見そうな夢をネットの海から探し続けるバックグラウンドデーモン。
1時間ごとに自律検索し、data/dreams.jsonl に蓄積。
毎朝7時に直近24時間の夢サマリをdata/dreams_daily.mdに出力。

使い方:
  python3 scripts/baku.py                     # デーモン起動（1時間ごと）
  python3 scripts/baku.py --once              # 1回だけ実行して終了
  python3 scripts/baku.py --summary           # 直近24時間の夢サマリ生成
  python3 scripts/baku.py --topic "量子塩梅"   # 手動トピック指定（1回）
  python3 scripts/baku.py --interval 1800     # 30分ごと（秒指定）
"""

import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# === 設定 ===

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"
DREAMS_PATH = PROJECT_ROOT / "data" / "dreams.jsonl"
DAILY_SUMMARY_PATH = PROJECT_ROOT / "data" / "dreams_daily.md"
PID_FILE = PROJECT_ROOT / "data" / "baku.pid"

DEFAULT_INTERVAL = 3600  # 1時間
MAX_SEARCHES_PER_RUN = 5
SUMMARY_HOUR = 7  # 朝7時にサマリ生成

# 殿の興味マップ — Memory MCPとauto memoryから抽出
TONO_INTERESTS = {
    "agriculture_iot": [
        "greenhouse climate control AI",
        "smart agriculture LLM",
        "side window ventilation automation",
        "crop growth model edge computing",
        "PoE sensor node industrial agriculture",
    ],
    "llm_edge": [
        "mixture of experts edge inference",
        "local LLM distillation production",
        "small language model tool calling",
        "MoE quantization raspberry pi",
        "RP2040 W5500 PoE IoT firmware",
    ],
    "brain_science": [
        "predictive coding brain LLM",
        "scalar signal dopamine learning",
        "associative memory neural network",
        "hallucination as learning mechanism",
        "forgetting curve memory consolidation",
    ],
    "system_design": [
        "multi-agent system self-evolving",
        "event-driven architecture autonomous",
        "FTS5 associative memory pattern",
        "SQLite knowledge graph lightweight",
        "spreading activation memory retrieval",
    ],
    "philosophy": [
        "quantum decision theory uncertainty",
        "information physics causality loop",
        "塩梅 最適化 不確実性",
        "MacGyver engineering philosophy minimal",
    ],
    "economics": [
        "LLM inference cost optimization edge",
        "edge computing total cost ownership",
        "agricultural IoT cost benefit analysis",
    ],
    "hardware": [
        "DIN rail IoT module PoE sensor",
        "IP67 enclosure raspberry pi industrial",
        "UniPi Iris PoE automation",
    ],
}

# === シグナルハンドリング ===

_running = True


def _signal_handler(signum, frame):
    global _running
    print(f"\n獏: シグナル {signum} を受信。夢から覚める...")
    _running = False


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)

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

    for row in conn.execute(
        "SELECT command, details FROM commands WHERE created_at > ? OR timestamp > ?",
        (cutoff, cutoff),
    ):
        text = f"{row['command'] or ''} {row['details'] or ''}"
        keywords.extend(extract_nouns_simple(text))

    for row in conn.execute(
        "SELECT description FROM subtasks WHERE assigned_at > ?", (cutoff,)
    ):
        text = row["description"] or ""
        keywords.extend(extract_nouns_simple(text))

    conn.close()

    freq = Counter(keywords)
    significant = [
        w for w, c in freq.most_common(50) if c >= 2 or len(w) >= 6
    ]
    return significant[:20]


def extract_nouns_simple(text: str) -> list[str]:
    """簡易名詞抽出（MeCabなし版）"""
    en_words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
    ja_katakana = re.findall(r"[ァ-ヶー]{2,}", text)
    ja_kanji = re.findall(r"[一-龥]{2,}", text)

    stopwords = {
        "the", "and", "for", "that", "this", "with", "from", "have", "not",
        "are", "was", "will", "can", "has", "been", "but", "all", "cmd",
        "subtask", "status", "done", "assigned", "description", "yaml",
        "queue", "inbox", "report", "する", "ある", "いる", "なる", "できる",
        "これ", "それ", "もの", "こと", "ため", "よう", "ところ",
    }
    words = en_words + ja_katakana + ja_kanji
    return [w.lower() for w in words if w.lower() not in stopwords]


# === 検索 ===


def search_ddg(query: str) -> str | None:
    """DuckDuckGo Lite経由でWeb検索（API課金ゼロ）"""
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "jp-jp"})
        url = f"https://lite.duckduckgo.com/lite/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (baku/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = []
        snippets = re.findall(r'result-snippet[^>]*>(.*?)</td>', html, re.DOTALL)
        links = re.findall(r"class='result-link'>(.*?)</a>", html, re.DOTALL)

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
        print(f"  WARN: DDG検索失敗 '{query}': {e}", file=sys.stderr)
    return None


def search_kousatsu(query: str) -> str | None:
    """高札API経由の内部検索"""
    try:
        result = subprocess.run(
            ["curl", "-s", "--get", "http://localhost:8080/search",
             "--data-urlencode", f"q={query}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


# === クエリ生成 ===


def generate_dream_queries(recent_kw: list[str]) -> list[dict]:
    """殿の興味マップ × 直近キーワードから検索クエリを生成"""
    import random

    queries = []
    for domain, templates in TONO_INTERESTS.items():
        for template in templates:
            score = 0
            for kw in recent_kw:
                if kw.lower() in template.lower():
                    score += 3
                elif any(kw.lower() in t.lower() for t in template.split()):
                    score += 1

            queries.append({
                "domain": domain,
                "query": template,
                "relevance_score": score,
                "matched_keywords": [
                    kw for kw in recent_kw if kw.lower() in template.lower()
                ],
            })

    queries.sort(key=lambda q: q["relevance_score"], reverse=True)
    top = queries[:MAX_SEARCHES_PER_RUN - 1]
    rest = queries[MAX_SEARCHES_PER_RUN - 1:]
    if rest:
        top.append(random.choice(rest))

    return top[:MAX_SEARCHES_PER_RUN]


# === 蓄積 ===


def save_dream(dream: dict) -> None:
    """夢をJSONLに追記"""
    DREAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DREAMS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(dream, ensure_ascii=False) + "\n")


def load_recent_dreams(hours: int = 24) -> list[dict]:
    """直近N時間の夢を読み込み"""
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


# === 夢見の本体 ===


def dream_once(manual_topic: str | None = None) -> int:
    """1回の夢見を実行。見つかった夢の数を返す"""
    now = datetime.now()
    print(f"=== 獏: 夢見開始 {now.strftime('%Y-%m-%d %H:%M')} ===")

    recent_kw = get_recent_keywords(days=7)
    print(f"直近7日のキーワード ({len(recent_kw)}): {', '.join(recent_kw[:10])}...")

    if manual_topic:
        queries = [{"domain": "manual", "query": manual_topic,
                     "relevance_score": 99, "matched_keywords": []}]
    else:
        queries = generate_dream_queries(recent_kw)

    # 重複チェック（6時間以内の同一クエリはスキップ）
    recent_dreams = load_recent_dreams(hours=6)
    recent_queries = {d.get("query", "") for d in recent_dreams}
    queries = [q for q in queries if q["query"] not in recent_queries]

    if not queries:
        print("直近6時間と同じ夢は見ない。スキップ。")
        return 0

    print(f"今回の夢 ({len(queries)}件):")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. [{q['domain']}] {q['query']} (relevance: {q['relevance_score']})")

    dreams_found = []
    for q in queries:
        print(f"  夢見中: {q['query']}...")
        internal = search_kousatsu(q["query"])
        external = search_ddg(q["query"])

        # 検索間のsleep（DuckDuckGo ban防止）
        time.sleep(3)

        dream_entry = {
            "dreamt_at": now.isoformat(),
            "domain": q["domain"],
            "query": q["query"],
            "relevance_score": q["relevance_score"],
            "matched_keywords": q["matched_keywords"],
            "internal_result": internal[:500] if internal else None,
            "external_result": external[:500] if external else None,
            "status": "raw",
        }

        save_dream(dream_entry)
        dreams_found.append(dream_entry)

        if external:
            print(f"    → {external[:150]}...")
        elif internal:
            print(f"    → (内部) {internal[:150]}...")
        else:
            print("    → 夢なし")

    found = sum(1 for d in dreams_found if d["external_result"] or d["internal_result"])
    print(f"=== 獏: 夢見完了 {found}/{len(dreams_found)}件 ===\n")
    return found


# === 日次サマリ ===


def generate_daily_summary() -> str:
    """直近24時間の夢をMarkdownサマリにまとめる"""
    dreams = load_recent_dreams(hours=24)
    if not dreams:
        return "# 獏の夢日記\n\n夢なし。\n"

    now = datetime.now()
    lines = [
        f"# 獏の夢日記 — {now.strftime('%Y-%m-%d')}",
        f"",
        f"直近24時間で {len(dreams)} 件の夢を見た。",
        f"",
        f"## 夢一覧",
        f"",
        f"| # | 時刻 | ドメイン | クエリ | 結果 |",
        f"|---|------|---------|--------|------|",
    ]

    for i, d in enumerate(dreams, 1):
        t = d.get("dreamt_at", "")[:16]
        domain = d.get("domain", "?")
        query = d.get("query", "?")
        ext = d.get("external_result", "")
        if ext:
            # 最初の100文字
            result = ext[:100].replace("|", "/").replace("\n", " ")
        else:
            result = "(内部のみ)"
        lines.append(f"| {i} | {t} | {domain} | {query} | {result} |")

    # ドメイン別集計
    domain_counts = Counter(d.get("domain", "?") for d in dreams)
    lines.extend([
        f"",
        f"## ドメイン別",
        f"",
    ])
    for domain, count in domain_counts.most_common():
        lines.append(f"- **{domain}**: {count}件")

    # 当たり/ゴミ判定用の生データは省略（Opusがまとめる時に読む）
    lines.extend([
        f"",
        f"---",
        f"*生データ: {DREAMS_PATH}*",
        f"*Opusによる選別・洞察はこの下に追記される*",
        f"",
    ])

    return "\n".join(lines)


def write_daily_summary():
    """日次サマリを書き出す"""
    summary = generate_daily_summary()
    with open(DAILY_SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"獏: 日次サマリを書き出し → {DAILY_SUMMARY_PATH}")


# === デーモン ===


def write_pid():
    """PIDファイルを書き出す"""
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    """PIDファイルを削除"""
    if PID_FILE.exists():
        PID_FILE.unlink()


def daemon_loop(interval: int = DEFAULT_INTERVAL):
    """デーモンのメインループ"""
    write_pid()
    print(f"獏: デーモン起動 (PID={os.getpid()}, interval={interval}s)")
    print(f"獏: 夢の蓄積先 → {DREAMS_PATH}")
    print(f"獏: 日次サマリ → {DAILY_SUMMARY_PATH}")
    print(f"獏: 停止するには kill {os.getpid()} または Ctrl+C\n")

    last_summary_date = None

    try:
        while _running:
            # 夢見実行
            try:
                dream_once()
            except Exception as e:
                print(f"獏: 夢見中にエラー: {e}", file=sys.stderr)

            # 朝のサマリチェック
            now = datetime.now()
            today = now.date()
            if now.hour >= SUMMARY_HOUR and last_summary_date != today:
                try:
                    write_daily_summary()
                    last_summary_date = today
                except Exception as e:
                    print(f"獏: サマリ生成エラー: {e}", file=sys.stderr)

            # 次の夢見まで待つ（シグナルで中断可能）
            for _ in range(interval):
                if not _running:
                    break
                time.sleep(1)
    finally:
        remove_pid()
        print("獏: 夢から覚めた。おやすみ。")


# === メイン ===


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="獏（baku）: 夢見デーモン")
    parser.add_argument("--once", action="store_true", help="1回だけ実行して終了")
    parser.add_argument("--summary", action="store_true", help="日次サマリ生成")
    parser.add_argument("--topic", type=str, help="手動トピック指定（1回）")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                        help=f"実行間隔（秒、デフォルト={DEFAULT_INTERVAL}）")
    args = parser.parse_args()

    if args.summary:
        write_daily_summary()
    elif args.once or args.topic:
        dream_once(manual_topic=args.topic)
    else:
        daemon_loop(interval=args.interval)
