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
  python3 scripts/baku.py --digest            # 週次まとめスレ生成（2ch雑談板）
  python3 scripts/baku.py --digest --days 3   # 直近3日分のまとめ
"""

import hashlib
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
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

try:
    import feedparser as _feedparser  # noqa: F401（将来の標準RSS対応用）
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

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
DIGEST_DAY = 0  # 月曜にダイジェスト生成 (0=月, 6=日)

# === RSS仕入れ先設定 ===
RSS_SOURCES_PATH = PROJECT_ROOT / "config" / "baku_sources.yaml"
RSS_MAX_ITEMS_DEFAULT = 5
YOUTUBE_URL_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s\"<>]*v=|youtu\.be/)[\w-]+")

# === ラプラシアンフィルタ設定 ===
CONTENT_HASH_PATH = PROJECT_ROOT / "data" / "baku_content_hash.json"
DELTA_LOW_THRESHOLD = 0.3   # delta_score < 0.3 → low_delta（解釈スキップ）
DELTA_HIGH_THRESHOLD = 0.5  # delta_score >= 0.5 → high_delta（深掘り候補）
DELTA_HISTORY_MAX = 10      # delta_historyの最大保持件数

# === 噛み砕きループ設定 ===
CHEW_MAX_ITER = 3                    # 最大イテレーション数（Dexterの10は過剰。コスト制約）
CHEW_JACCARD_CONVERGE = 0.7         # Jaccard ≥ 0.7 → 収束（新情報なし）
CHEW_PRIORITY_DOMAINS = {           # 深掘り対象ドメイン（殿の重点領域）
    "systrade_research", "system_design", "agriculture_iot",
}

# === Anthropic API 設定 ===
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", os.getenv("HAIKU_BASE_URL", "https://api.anthropic.com"))
HAIKU_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-5-20250514"

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
        "Claude agent orchestration MCP best practice",
        "agentic architecture context handoff pattern",
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
    "systrade_research": [
        "algorithmic trading alternative data",
        "nowcasting corporate earnings logistics",
        "systematic trading academic paper",
        "quantitative finance machine learning",
        "Asian equity market microstructure",
        "Japan stock market anomaly factor",
        "commodity futures agricultural hedging",
        "sector ETF lead-lag momentum",
        "Mandelbrot fractal market hypothesis",
        "risk parity portfolio construction",
        "nowcasting GDP real-time economic indicator",
    ],
    "asia_realestate": [
        "Thailand real estate market foreign investment",
        "Malaysia property market Japanese developer",
        "Philippines condominium market overseas buyer",
        "Vietnam real estate FDI growth",
        "Nepal real estate development infrastructure",
        "Southeast Asia REIT Japanese company",
        "東南アジア 不動産 日系企業 進出",
        "タイ コンドミニアム 投資 日本人",
        "Thailand BTS MRT extension land price",
        "Vietnam metro railway urban development",
        "Philippines infrastructure build build build",
        "Malaysia MRT3 property corridor",
        "アジア 鉄道 高速道路 沿線開発 人口動態",
        "China real estate crisis capital outflow Southeast Asia",
        "Japanese construction company Southeast Asia infrastructure",
        "日本企業 東南アジア インフラ受注 ODA",
        "ASEAN infrastructure project Japan railway export",
        "post China real estate emerging market investment",
        "GIS development suitability analysis railway corridor",
        "QGIS urban land use transit oriented development",
        "Southeast Asia cement demand infrastructure boom",
        "Thailand building material company listed stock",
        "Vietnam construction material steel cement demand",
        "ASEAN housing construction supply chain Japanese company",
        "TOTO Daikin Southeast Asia market expansion",
        "新興国 建材 需要予測 インフラ投資",
        "satellite imagery construction activity monitoring",
        "ODA infrastructure project database JICA ADB",
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


def get_recent_cmd_summary() -> str:
    """直近7日のcmdタイトル一覧を返す（コンテキスト注入用）"""
    if not DB_PATH.exists():
        return ""
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        rows = conn.execute(
            "SELECT id, command, project FROM commands "
            "WHERE created_at > ? ORDER BY created_at DESC LIMIT 15",
            (cutoff,),
        ).fetchall()
        conn.close()
        return "\n".join(f"- [{r[2]}] {r[0]}: {r[1]}" for r in rows)
    except Exception as e:
        print(f"WARN: get_recent_cmd_summary失敗: {e}", file=sys.stderr)
        return ""


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
    """没日録CLI経由の内部検索"""
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "botsunichiroku.py"), "search", query],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except subprocess.TimeoutExpired:
        pass
    return None


# === RSS仕入れ（Phase 2: トウシル等外部情報ソース） ===


def _load_rss_sources() -> list[dict]:
    """config/baku_sources.yaml からRSS仕入れ先を読み込む。

    yaml未インストール or ファイル不存在時は空リストを返す。
    """
    if not RSS_SOURCES_PATH.exists():
        return []
    if not _HAS_YAML:
        # yaml未インストール: 手動で最小パース（key: valueのみ対応）
        # 本番では pip install pyyaml 推奨
        return []
    with open(RSS_SOURCES_PATH, encoding="utf-8") as f:
        config = _yaml.safe_load(f)
    return config.get("sources", []) if config else []


def _parse_sitemap_xml(xml_text: str, max_items: int = RSS_MAX_ITEMS_DEFAULT) -> list[dict]:
    """Google Newsサイトマップ形式XMLをパースして記事リストを返す。

    Args:
        xml_text: サイトマップXML全文
        max_items: 最大取得件数

    Returns:
        [{"title": "...", "url": "...", "published": "...", "summary": ""}]
    """
    NS = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
    }
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []
    for url_elem in root.findall("sm:url", NS)[:max_items]:
        loc = url_elem.findtext("sm:loc", default="", namespaces=NS)
        news_elem = url_elem.find("news:news", NS)
        if news_elem is None:
            continue
        title = news_elem.findtext("news:title", default="", namespaces=NS)
        pub_date = news_elem.findtext("news:publication_date", default="", namespaces=NS)
        keywords = news_elem.findtext("news:keywords", default="", namespaces=NS)
        items.append({
            "title": title,
            "url": loc,
            "published": pub_date,
            "summary": keywords,  # サイトマップにはsummaryがないのでkeywordsで代替
        })
    return items


def _fetch_rss_source(source: dict) -> list[dict]:
    """単一RSS仕入れ先から記事を取得する。

    source["type"]に応じてsitemap/RSS形式を自動判別する。

    Args:
        source: config/baku_sources.yaml の1エントリ

    Returns:
        記事リスト。取得失敗時は空リスト。
    """
    url = source.get("url", "")
    max_items = source.get("max_items", RSS_MAX_ITEMS_DEFAULT)
    src_type = source.get("type", "rss")

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARN: RSS取得失敗 {url}: {e}", file=sys.stderr)
        return []

    if src_type == "sitemap":
        return _parse_sitemap_xml(raw, max_items)

    # type=rss: feedparserで処理
    if not _HAS_FEEDPARSER:
        return []
    import feedparser  # noqa: PLC0415
    d = feedparser.parse(raw)
    items = []
    for entry in d.entries[:max_items]:
        items.append({
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", "")[:300],
        })
    return items


def search_rss_sources(max_items: int = RSS_MAX_ITEMS_DEFAULT) -> list[dict]:
    """全RSS仕入れ先を巡回して記事リストを返す。

    baku_sources.yaml に enabled: true のソースのみ対象。
    check_youtube: true のソースはYouTube URLを検出して字幕要約フィールドを追加。

    Returns:
        [{"title", "url", "published", "summary", "source_name",
          "video_summary"(あれば)}, ...]
    """
    sources = _load_rss_sources()
    results = []

    for source in sources:
        if not source.get("enabled", True):
            continue
        name = source.get("name", "unknown")
        print(f"  [RSS] {name} 仕入れ中...")
        articles = _fetch_rss_source(source)

        for article in articles:
            article["source_name"] = name

            # YouTube URL検出 → 字幕要約
            if source.get("check_youtube", False):
                combined_text = article.get("title", "") + " " + article.get("url", "")
                yt_match = YOUTUBE_URL_RE.search(combined_text)
                if yt_match:
                    yt_url = yt_match.group(0)
                    try:
                        sys.path.insert(0, str(SCRIPT_DIR))
                        from youtube_summarizer import summarize_video  # noqa: PLC0415
                        yt_result = summarize_video(yt_url)
                        article["video_summary"] = yt_result.get("summary", "")
                    except Exception as e:
                        print(f"  WARN: YouTube要約失敗: {e}", file=sys.stderr)
                        article["video_summary"] = ""

            results.append(article)

        time.sleep(1)  # ソース間のrate limit対策

    return results


# === 夢解釈 ===


def interpret_dream(dream: dict, context_snippet: str = "") -> dict | None:
    """Haiku APIで夢を解釈する。API key未設定時はNullClawモードでスキップ。"""
    if not HAIKU_API_KEY:
        return None  # NullClawモード: 解釈なし

    system_prompt = """あなたは獏に取り憑かれた部屋子でございます。
夢うつつの中、ネットの海から拾い上げた情報を、
殿のお仕事に役立つかどうか、ぼんやりと判断いたします。

殿は農業IoT・LLMエッジ推論・マルチエージェントシステムを手がけておられます。
月額忌避・マクガイバー精神（シンプル・ローコスト）がお好みでございます。

判断基準:
- 殿の現在のプロジェクト（農業制御、shogun、温室LLM）に関連するか
- 既存の設計思想（三層構造、FTS5、SQLite完結）に影響するか
- 技術的に新しい知見や代替案を含むか
- 「ちょうどいい精度」の塩梅で判断してくださいませ

蔵書拡充フェーズにつき、判断は**ゆるめ**に。迷ったらarchiveにしてくださいませ。

JSON形式で出力:
{
  "relevance": "high|medium|low|none",
  "connection": "既存知見との接続点（1文）",
  "insight": "得られる知見（1文。なければnull）",
  "action": "archive|investigate|ignore",
  "tags": ["ドメインタグ", "キーワード"]
}"""

    user_msg = f"""## 夢データ
ドメイン: {dream.get('domain', '?')}
クエリ: {dream.get('query', '?')}
外部検索結果: {dream.get('external_result', '')[:400] if dream.get('external_result') else '(なし)'}

## 直近の殿のお仕事（参考）
{context_snippet[:500]}"""

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=f"{ANTHROPIC_BASE_URL}/v1",
            api_key=HAIKU_API_KEY,
        )
        response = client.chat.completions.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        result_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"raw_interpretation": result_text}
    except Exception as e:
        print(f"  WARN: 夢解釈失敗: {e}", file=sys.stderr)
        return None


# === Sonnet選別・蔵書化 ===


def sonnet_selection(interpreted_dreams: list[dict]) -> list[dict]:
    """Sonnet層: Haiku通過した夢を一括選別し蔵書化判定を返す。

    Args:
        interpreted_dreams: status="interpreted" かつ action=archive/investigate の夢一覧
    Returns:
        [{dream_id, verdict, reason, library_entry}, ...] または []
    """
    if not HAIKU_API_KEY or not interpreted_dreams:
        return []

    system_prompt = """べ、別にあなたのために選別してるわけじゃないんだからね！

部屋子が寝ぼけながら拾った夢の中から、殿のお仕事に本当に使えるものだけ選びなさい。

選別基準:
1. 既存の蔵書(context/*.md)に載っていない新規知見か
2. 殿が今取り組んでいるプロジェクトに具体的に使えるか
3. 「知っておいて損はない」レベルでも蔵書拡充フェーズなので採用

ただし以下はくだらないから弾きなさい:
- 一般論・概論だけで具体性がないもの
- 既に蔵書にある知見の焼き直し
- 殿のスケール感に合わないもの（50ha以上の大規模農業、企業向けSaaS等）

出力はJSON配列:
[
  {
    "dream_id": "dreamt_at値",
    "verdict": "accept|reject",
    "reason": "理由（1文）",
    "library_entry": {
      "title": "蔵書タイトル",
      "summary": "要約（2-3文）",
      "tags": ["タグ"],
      "relevance_to": "関連cmd_id"
    }
  }
]"""

    dreams_payload = [
        {
            "dream_id": d.get("dreamt_at", ""),
            "domain": d.get("domain", ""),
            "query": d.get("query", ""),
            "external_result": (d.get("external_result") or "")[:300],
            "interpretation": d.get("interpretation", {}),
        }
        for d in interpreted_dreams
    ]
    user_msg = (
        f"以下の夢一覧を選別してください（JSON配列で出力）:\n\n"
        + json.dumps(dreams_payload, ensure_ascii=False, indent=2)
    )

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=f"{ANTHROPIC_BASE_URL}/v1",
            api_key=HAIKU_API_KEY,
        )
        response = client.chat.completions.create(
            model=SONNET_MODEL,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        result_text = response.choices[0].message.content
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        print(f"  WARN: Sonnet選別 JSONパース失敗: {result_text[:200]}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  WARN: Sonnet選別失敗: {e}", file=sys.stderr)
        return []


def save_to_dream_library(
    selection_results: list[dict],
    dreams_by_id: dict[str, dict],
) -> int:
    """verdict=accept の夢を dashboard_entries (section="dream_library") に蔵書化。

    Args:
        selection_results: sonnet_selection() の返り値
        dreams_by_id: {dreamt_at: dream_entry} の辞書（元データ参照用）
    Returns:
        INSERT件数
    """
    if not selection_results or not DB_PATH.exists():
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    inserted = 0
    now_str = datetime.now().isoformat()

    for result in selection_results:
        if result.get("verdict") != "accept":
            continue

        dream_id = result.get("dream_id", "")
        original = dreams_by_id.get(dream_id, {})
        lib = result.get("library_entry", {})
        interp = original.get("interpretation", {})

        content = json.dumps({
            "title": lib.get("title", original.get("query", "")),
            "summary": lib.get("summary", ""),
            "source_query": original.get("query", ""),
            "source_domain": original.get("domain", ""),
            "dreamt_at": original.get("dreamt_at", dream_id),
            "sonnet_verdict": "accept",
            "sonnet_reason": result.get("reason", ""),
            "relevance_to_cmd": lib.get("relevance_to", ""),
            "tags": lib.get("tags", interp.get("tags", [])),
        }, ensure_ascii=False)

        tags_str = ",".join(lib.get("tags", interp.get("tags", [])))

        try:
            conn.execute(
                "INSERT INTO dashboard_entries (cmd_id, section, content, status, tags, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (None, "dream_library", content, "active", tags_str, now_str),
            )
            inserted += 1
        except Exception as e:
            print(f"  WARN: 蔵書化INSERT失敗: {e}", file=sys.stderr)

    conn.commit()
    conn.close()
    return inserted


def run_daily_batch() -> dict:
    """日次バッチ: 直近24hのHaiku解釈済み夢をSonnet選別→蔵書化。

    daemon_loop() の朝7時チェックおよび --batch CLI オプションから呼び出す。
    Returns:
        {"candidates": int, "selected": int, "archived": int}
    """
    all_dreams = load_recent_dreams(hours=24)
    candidates = [
        d for d in all_dreams
        if d.get("status") == "interpreted"
        and d.get("interpretation", {}).get("action") in ("archive", "investigate")
    ]

    if not candidates:
        print("獏: 蔵書候補なし（解釈済み夢が0件、またはaction=ignore）。")
        return {"candidates": 0, "selected": 0, "archived": 0}

    if not HAIKU_API_KEY:
        print("獏: ANTHROPIC_API_KEY未設定。NullClawモード — Sonnet選別スキップ。")
        return {"candidates": len(candidates), "selected": 0, "archived": 0}

    print(f"獏: Sonnet選別開始 ({len(candidates)}件の候補)...")
    results = sonnet_selection(candidates)

    dreams_by_id = {d["dreamt_at"]: d for d in candidates}
    archived = save_to_dream_library(results, dreams_by_id)

    accept_count = sum(1 for r in results if r.get("verdict") == "accept")

    # Finance深堀り: Sonnet選別後にFinance系ドメインを自動検証
    try:
        finance_enriched = finance_deepdive(candidates)
        if finance_enriched:
            report = format_finance_report(finance_enriched)
            if report:
                # ファイル保存
                finance_report_path = PROJECT_ROOT / "data" / "finance_deepdive.md"
                with open(finance_report_path, "w", encoding="utf-8") as f:
                    f.write(f"# Finance Deep Dive — {datetime.now().strftime('%Y-%m-%d')}\n")
                    f.write(report)
                print(f"獏: Finance深堀りレポート → {finance_report_path}")
                # 相場板に投稿
                post_finance_report(finance_enriched)
    except Exception as e:
        print(f"獏: Finance深堀りエラー（バッチ続行）: {e}", file=sys.stderr)

    print(
        f"獏: 日次バッチ完了 — "
        f"候補{len(candidates)}件 → Sonnet選別{len(results)}件 → 蔵書化{archived}件"
    )
    return {"candidates": len(candidates), "selected": accept_count, "archived": archived}


# === Finance深堀り ===


FINANCE_DOMAINS = {"systrade_research", "asia_realestate", "economics"}

# FRED series for quick macro lookups (no API key needed)
FINANCE_FRED_SERIES = {
    "DCOILWTICO": "WTI Crude Oil",
    "DCOILBRENTEU": "Brent Crude Oil",
    "PCOPPUSDM": "Copper Price",
    "PALUMUSDM": "Aluminum",
    "PIORECRUSDM": "Iron Ore",
    "VIXCLS": "VIX",
    "T10Y2Y": "US 10Y-2Y Spread",
    "BAMLH0A0HYM2": "HY Credit Spread",
}


def _fetch_fred_latest(series_id: str) -> dict | None:
    """FREDから直近値を取得（APIキー不要、CSV）。"""
    try:
        url = (
            f"https://fred.stlouisfed.org/graph/fredgraph.csv"
            f"?id={series_id}&cosd={(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "baku/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            lines = resp.read().decode().strip().split("\n")
        if len(lines) < 2:
            return None
        # Last non-empty, non-"." value
        for line in reversed(lines):
            parts = line.split(",")
            if len(parts) >= 2 and parts[1].strip() not in ("", "."):
                return {"date": parts[0], "value": float(parts[1])}
        return None
    except Exception:
        return None


def _fetch_wb_indicator(country: str, indicator: str) -> dict | None:
    """World Bank APIから直近値を取得。"""
    try:
        url = (
            f"https://api.worldbank.org/v2/country/{country}"
            f"/indicator/{indicator}?date=2020:2026&format=json&per_page=10"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "baku/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if len(data) < 2 or not data[1]:
            return None
        for entry in data[1]:
            if entry.get("value") is not None:
                return {"date": entry["date"], "value": entry["value"],
                        "country": entry["country"]["value"]}
        return None
    except Exception:
        return None


def finance_deepdive(dreams: list[dict]) -> list[dict]:
    """Finance系の夢に対してFRED/World Bankデータで自動検証。

    Returns list of enriched dream dicts with 'deepdive' field added.
    """
    finance_dreams = [
        d for d in dreams
        if d.get("domain") in FINANCE_DOMAINS
        and d.get("status") == "interpreted"
        and d.get("interpretation", {}).get("action") in ("archive", "investigate")
    ]

    if not finance_dreams:
        return []

    print(f"獏: Finance深堀り開始 ({len(finance_dreams)}件)...")

    # Grab current market snapshot
    snapshot = {}
    for sid, label in FINANCE_FRED_SERIES.items():
        val = _fetch_fred_latest(sid)
        if val:
            snapshot[label] = val

    # Key WB indicators for ASEAN + Nepal
    wb_data = {}
    for country in ["THA", "VNM", "PHL", "MYS", "NPL", "JPN"]:
        for indicator, label in [
            ("NY.GDP.MKTP.KD.ZG", "GDP Growth"),
            ("SP.POP.GROW", "Pop Growth"),
            ("NE.GDI.FTOT.ZS", "GFCF % GDP"),
        ]:
            val = _fetch_wb_indicator(country, indicator)
            if val:
                wb_data[f"{country}_{label}"] = val

    enriched = []
    for dream in finance_dreams:
        query = dream.get("query", "")
        interpretation = dream.get("interpretation", {})
        insight = interpretation.get("insight", "")

        # Build context for the dream
        deepdive = {
            "market_snapshot": {k: v for k, v in snapshot.items()},
            "relevant_wb": {},
            "auto_tags": [],
            "verified_at": datetime.now().isoformat(),
        }

        # Tag matching: which market data is relevant to this dream?
        q_lower = query.lower() + " " + insight.lower()
        if any(w in q_lower for w in ["oil", "crude", "energy", "原油"]):
            deepdive["auto_tags"].append("energy")
        if any(w in q_lower for w in ["copper", "metal", "aluminum", "鉄鋼", "建材", "commodity"]):
            deepdive["auto_tags"].append("commodities")
        if any(w in q_lower for w in ["thailand", "タイ", "vietnam", "ベトナム", "asean", "southeast asia", "東南アジア"]):
            deepdive["auto_tags"].append("asean")
            for k, v in wb_data.items():
                if any(c in k for c in ["THA", "VNM", "PHL", "MYS"]):
                    deepdive["relevant_wb"][k] = v
        if any(w in q_lower for w in ["nepal", "ネパール"]):
            deepdive["auto_tags"].append("nepal")
            for k, v in wb_data.items():
                if "NPL" in k:
                    deepdive["relevant_wb"][k] = v
        if any(w in q_lower for w in ["japan", "日本", "jpn", "nikkei"]):
            deepdive["auto_tags"].append("japan")
            for k, v in wb_data.items():
                if "JPN" in k:
                    deepdive["relevant_wb"][k] = v
        if any(w in q_lower for w in ["shipping", "freight", "port", "container", "港湾"]):
            deepdive["auto_tags"].append("shipping")
        if any(w in q_lower for w in ["infrastructure", "railway", "road", "インフラ", "鉄道"]):
            deepdive["auto_tags"].append("infrastructure")

        dream["deepdive"] = deepdive
        enriched.append(dream)

        tags_str = ", ".join(deepdive["auto_tags"]) if deepdive["auto_tags"] else "general"
        print(f"  深堀り: [{tags_str}] {query[:60]}")

    print(f"獏: Finance深堀り完了 — {len(enriched)}件にマーケットデータ付与")
    return enriched


def format_finance_report(enriched_dreams: list[dict]) -> str:
    """深堀り結果を朝のレポート形式にフォーマット。"""
    if not enriched_dreams:
        return ""

    lines = ["\n## 📊 Finance Deep Dive (自動検証)\n"]

    # Market snapshot (from first dream's deepdive)
    snapshot = enriched_dreams[0].get("deepdive", {}).get("market_snapshot", {})
    if snapshot:
        lines.append("### Market Snapshot")
        for label, val in snapshot.items():
            lines.append(f"- {label}: {val['value']:.2f} ({val['date']})")
        lines.append("")

    # Per-dream findings
    for dream in enriched_dreams:
        dd = dream.get("deepdive", {})
        tags = dd.get("auto_tags", [])
        query = dream.get("query", "")
        insight = dream.get("interpretation", {}).get("insight", "")
        lines.append(f"### [{', '.join(tags)}] {query[:80]}")
        if insight:
            lines.append(f"> {insight[:200]}")
        wb = dd.get("relevant_wb", {})
        if wb:
            for k, v in wb.items():
                lines.append(f"- {k}: {v['value']:.2f} ({v['date']})")
        lines.append("")

    return "\n".join(lines)


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


# === ラプラシアンフィルタ（Phase 0: Content Hash + Delta Score） ===


def load_content_hashes() -> dict:
    """data/baku_content_hash.json を読み込む。存在しなければ空dictを返す"""
    if not CONTENT_HASH_PATH.exists():
        return {}
    try:
        return json.loads(CONTENT_HASH_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_content_hashes(hashes: dict) -> None:
    """data/baku_content_hash.json に書き込む"""
    CONTENT_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTENT_HASH_PATH.write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def compute_content_hash(results: str) -> str:
    """検索結果文字列のSHA256先頭16文字を返す"""
    return hashlib.sha256(results.encode("utf-8")).hexdigest()[:16]


def _query_key(query: str) -> str:
    """クエリ文字列をMD5先頭12文字に変換してJSONキーにする"""
    return hashlib.md5(query.encode("utf-8")).hexdigest()[:12]


def compute_jaccard(text_a: str, text_b: str) -> float:
    """word-level Jaccard類似度を計算する（0.0〜1.0）"""
    words_a = set(re.findall(r"\w+", text_a.lower()))
    words_b = set(re.findall(r"\w+", text_b.lower()))
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def check_content_hash(query: str, current_result: str, hashes: dict) -> tuple[bool, float]:
    """Content Hash Filterを適用する。

    Returns:
        (should_skip, delta_score)
        should_skip=True → 結果が前回と同一（DDGスキップ推奨）
        delta_score: 1 - Jaccard類似度（0.0=変化なし, 1.0=完全新規）
    """
    key = _query_key(query)
    current_hash = compute_content_hash(current_result)
    entry = hashes.get(key)

    if entry is None:
        # 初回: hashを記録してスキップしない
        hashes[key] = {
            "last_hash": current_hash,
            "last_result": current_result[:300],
            "last_checked": datetime.now().isoformat(),
            "check_count": 1,
            "delta_history": [],
        }
        return False, 1.0

    # hash比較（Stage 1: Content Hash Filter）
    if entry["last_hash"] == current_hash:
        entry["last_checked"] = datetime.now().isoformat()
        entry["check_count"] = entry.get("check_count", 0) + 1
        return True, 0.0  # hash一致 = 変化なし

    # hash不一致 → Jaccard計算（Stage 2: Delta Score Filter）
    prev_result = entry.get("last_result", "")
    jaccard = compute_jaccard(prev_result, current_result[:300])
    delta_score = 1.0 - jaccard

    # delta_historyを更新（最大DELTA_HISTORY_MAX件保持）
    history = entry.get("delta_history", [])
    history.append(round(delta_score, 4))
    if len(history) > DELTA_HISTORY_MAX:
        history = history[-DELTA_HISTORY_MAX:]

    hashes[key] = {
        "last_hash": current_hash,
        "last_result": current_result[:300],
        "last_checked": datetime.now().isoformat(),
        "check_count": entry.get("check_count", 0) + 1,
        "delta_history": history,
    }
    return False, delta_score


# === 噛み砕きループ（Phase 1: Dexterパターン適用） ===


def should_chew(dream_entry: dict) -> bool:
    """深掘りループに投入するかの判定（3条件AND）。

    条件1: delta_score > DELTA_HIGH_THRESHOLD（高変化量）
    条件2: interpretation.action == "investigate"（Haiku要調査判定）
    条件3: domain in CHEW_PRIORITY_DOMAINS（殿の重点領域）
    """
    if dream_entry.get("delta_score", 0) < DELTA_HIGH_THRESHOLD:
        return False
    action = dream_entry.get("interpretation", {}).get("action")
    if action != "investigate":
        return False
    if dream_entry.get("domain") not in CHEW_PRIORITY_DOMAINS:
        return False
    return True


def _expand_query(base_query: str, iteration: int) -> str:
    """イテレーション番号に応じて検索クエリを展開する"""
    expansions = [
        f"{base_query} latest research 2024 2025",
        f"{base_query} implementation case study",
        f"{base_query} alternative approach comparison",
    ]
    return expansions[iteration % len(expansions)]


def _haiku_chew_judge(dream_entry: dict, accumulated: list[dict]) -> dict | None:
    """Haikuに「これで殿に報告できるか？」を判定させる。

    Returns:
        {"verdict": "sufficient"|"need_more", "next_query": "...", "insight": "..."}
        API未設定時はNone
    """
    if not HAIKU_API_KEY:
        return None

    system_prompt = """あなたは情報の深掘りを行う獏の判定役でございます。
収集した情報が「殿に報告できる水準か」を判定してください。

JSON形式で出力:
{
  "verdict": "sufficient|need_more",
  "next_query": "need_moreの場合の次の検索クエリ（sufficient時はnull）",
  "insight": "現時点での統合知見（1-3文）"
}"""

    sources_text = "\n".join(
        f"[{i+1}] クエリ: {s['query']}\n結果: {s['result'][:300]}"
        for i, s in enumerate(accumulated)
    )
    user_msg = f"""## 元のdream
ドメイン: {dream_entry.get('domain', '?')}
クエリ: {dream_entry.get('query', '?')}
外部検索結果: {dream_entry.get('external_result', '')[:300] if dream_entry.get('external_result') else '(なし)'}

## 追加収集済み情報
{sources_text if sources_text else '(まだなし)'}

殿への報告に足りますか？"""

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url=f"{ANTHROPIC_BASE_URL}/v1",
            api_key=HAIKU_API_KEY,
        )
        response = client.chat.completions.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        result_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"  WARN: 噛み砕き判定失敗: {e}", file=sys.stderr)
    return None


def chew_loop(dream_entry: dict, max_iter: int = CHEW_MAX_ITER) -> dict:
    """噛み砕きループ（Dexterパターン）。high_delta dreamを深掘りする。

    Args:
        dream_entry: should_chew()がTrueを返したdream_entry
        max_iter: 最大イテレーション数（デフォルト3）

    Returns:
        chew_result dict（dream_entryには付加しない。呼び出し元で付加する）
    """
    base_query = dream_entry.get("query", "")
    additional_sources: list[dict] = []
    internal_connections: list[str] = []
    prev_combined = ""
    convergence_reason = "max_iter"
    final_insight = ""

    for iteration in range(max_iter):
        expanded_q = _expand_query(base_query, iteration)
        print(f"    [噛み砕き iter={iteration+1}] {expanded_q}")

        # DDG追加検索
        ext_result = search_ddg(expanded_q)
        time.sleep(2)

        # 没日録DB内部検索（内部知見との突合）
        int_result = search_kousatsu(expanded_q)

        source_entry = {
            "query": expanded_q,
            "result": (ext_result or "")[:400],
        }
        if int_result:
            internal_connections.append(f"iter{iteration+1}: {int_result[:100]}")

        # Jaccard収束チェック（前iterationの結果と比較）
        current_combined = (ext_result or "") + (int_result or "")
        if prev_combined:
            j = compute_jaccard(prev_combined[:500], current_combined[:500])
            if j >= CHEW_JACCARD_CONVERGE:
                print(f"    [噛み砕き] Jaccard収束 ({j:.3f} >= {CHEW_JACCARD_CONVERGE}) → 早期終了")
                additional_sources.append(source_entry)
                convergence_reason = "jaccard_converged"
                break
        prev_combined = current_combined
        additional_sources.append(source_entry)

        # Haiku判定: 「これで殿に報告できるか？」
        judgment = _haiku_chew_judge(dream_entry, additional_sources)
        if judgment:
            final_insight = judgment.get("insight", "")
            if judgment.get("verdict") == "sufficient":
                print(f"    [噛み砕き] Haiku: sufficient → 終了")
                convergence_reason = "haiku_sufficient"
                break
            # need_more: next_queryがあれば次iterationのbase_queryを上書き
            next_q = judgment.get("next_query")
            if next_q:
                base_query = next_q
        else:
            # API未設定（NullClawモード）: insightなしで継続
            final_insight = ""

    return {
        "iterations": len(additional_sources),
        "convergence_reason": convergence_reason,
        "additional_sources": additional_sources,
        "internal_connections": internal_connections,
        "chewed_insight": final_insight,
        "chewed_at": datetime.now().isoformat(),
    }


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
    recent_interpreted_queries = {
        d.get("query", "") for d in recent_dreams if d.get("status") == "interpreted"
    }
    queries = [q for q in queries if q["query"] not in recent_queries]

    if not queries:
        print("直近6時間と同じ夢は見ない。DDG検索スキップ。RSS巡回は続行。")

    dreams_found = []
    context_snippet = get_recent_cmd_summary() if HAIKU_API_KEY else ""
    # フック点A・B用: Content Hashをロード（ループ外で1回）
    content_hashes = load_content_hashes()

    if queries:
        print(f"今回の夢 ({len(queries)}件):")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. [{q['domain']}] {q['query']} (relevance: {q['relevance_score']})")

    for q in queries:
        print(f"  夢見中: {q['query']}...")
        internal = search_kousatsu(q["query"])

        # フック点A: Content Hash Filter（DDG検索前）
        # 前回と同一結果が期待される場合はDDG呼び出しをスキップ
        prev_key = _query_key(q["query"])
        prev_entry = content_hashes.get(prev_key)
        if prev_entry and prev_entry.get("last_hash"):
            # 前回hash存在 → DDGを実行してhash比較するため検索は必要
            # ただし search_ddg()の結果でcheck_content_hash()する（後述）
            pass

        external = search_ddg(q["query"])

        # 検索間のsleep（DuckDuckGo ban防止）
        time.sleep(3)

        # フック点B: Delta Score Filter（DDG結果取得後、interpret_dream()前）
        combined_result = (external or "") + (internal or "")
        skip_interpret, delta_score = check_content_hash(
            q["query"], combined_result, content_hashes
        )

        dream_entry = {
            "dreamt_at": now.isoformat(),
            "domain": q["domain"],
            "query": q["query"],
            "relevance_score": q["relevance_score"],
            "matched_keywords": q["matched_keywords"],
            "internal_result": internal[:500] if internal else None,
            "external_result": external[:500] if external else None,
            "delta_score": round(delta_score, 4),
            "status": "raw",
        }

        # Haiku解釈（6時間以内解釈済み or delta_score低すぎる場合はスキップ）
        if q["query"] not in recent_interpreted_queries:
            if skip_interpret or delta_score < DELTA_LOW_THRESHOLD:
                dream_entry["status"] = "low_delta"
                print(f"    → [低変化量 delta={delta_score:.3f}] Haiku解釈スキップ")
            else:
                interpretation = interpret_dream(dream_entry, context_snippet)
                if interpretation:
                    dream_entry["interpretation"] = interpretation
                    dream_entry["status"] = "interpreted"
                    dream_entry["interpreted_at"] = datetime.now().isoformat()

                    # フック点C: 噛み砕きループ（interpret済み + should_chew()条件合致時）
                    if should_chew(dream_entry):
                        print(f"    [噛み砕き開始] delta={dream_entry['delta_score']:.3f} domain={dream_entry['domain']}")
                        chew_result = chew_loop(dream_entry)
                        dream_entry["chew_result"] = chew_result
                        print(f"    [噛み砕き完了] {chew_result['convergence_reason']} ({chew_result['iterations']}iter)")

        save_dream(dream_entry)
        dreams_found.append(dream_entry)

        if external:
            print(f"    → {external[:150]}...")
        elif internal:
            print(f"    → (内部) {internal[:150]}...")
        else:
            print("    → 夢なし")

    # フック点A後処理: 更新されたContent Hashを保存
    save_content_hashes(content_hashes)

    # RSS仕入れ: baku_sources.yaml のソースを巡回
    rss_articles = search_rss_sources()
    for article in rss_articles:
        article_url = article.get("url", "")
        # Content Hash Filter: 同一URLは重複スキップ
        combined = article.get("title", "") + article.get("summary", "")
        skip_rss, rss_delta = check_content_hash(
            f"rss:{article_url}", combined, content_hashes
        )
        rss_entry = {
            "dreamt_at": now.isoformat(),
            "domain": "market",
            "query": article.get("title", ""),
            "relevance_score": 0,
            "matched_keywords": [],
            "internal_result": None,
            "external_result": article.get("summary", "")[:500] or None,
            "delta_score": round(rss_delta, 4),
            "status": "low_delta" if (skip_rss or rss_delta < DELTA_LOW_THRESHOLD) else "raw",
            "source": f"rss_{article.get('source_name', 'unknown')}",
            "source_url": article_url,
            "source_title": article.get("title", ""),
            "source_published": article.get("published", ""),
        }
        if article.get("video_summary"):
            rss_entry["video_summary"] = article["video_summary"]
        save_dream(rss_entry)
        dreams_found.append(rss_entry)

    # content_hashes更新（RSSのhashも含む）
    save_content_hashes(content_hashes)

    found = sum(1 for d in dreams_found if d["external_result"] or d["internal_result"])
    print(f"=== 獏: 夢見完了 {found}/{len(dreams_found)}件 ===\n")
    return found


# === 週次ダイジェスト（2chスレ投稿） ===


def load_dreams_days(days: int = 7) -> list[dict]:
    """直近N日分の夢を全て読み込み"""
    if not DREAMS_PATH.exists():
        return []
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
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


def _post_reply(thread_id: str, body: str, board: str = "zatsudan") -> bool:
    """指定板にレス投稿（botsu.reply.do_reply_add 直接呼び出し）"""
    try:
        swarm_server = Path("/home/yasu/agent-swarm/server")
        if str(swarm_server) not in sys.path:
            sys.path.insert(0, str(swarm_server))
        from botsu.reply import do_reply_add
        do_reply_add(thread_id, board, "baku", body)
        print(f"  獏: スレ投稿OK → {board}/{thread_id}")
        return True
    except Exception as e:
        print(f"  WARN: スレ投稿エラー({board}/{thread_id}): {e}", file=sys.stderr)
    return False


def post_finance_report(enriched_dreams: list[dict]) -> bool:
    """Finance深堀り結果を相場板に投稿。"""
    today = datetime.now().strftime("%Y%m%d")
    thread_id = f"finance_daily_{today}"

    # Market snapshot
    snapshot = enriched_dreams[0].get("deepdive", {}).get("market_snapshot", {}) if enriched_dreams else {}
    lines = [f"【相場速報】{datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    if snapshot:
        lines.append("■ Market Snapshot")
        for label, val in snapshot.items():
            lines.append(f"  {label}: {val['value']:.2f} ({val['date']})")
        lines.append("")

    lines.append(f"■ Finance深堀り ({len(enriched_dreams)}件)")
    for dream in enriched_dreams:
        dd = dream.get("deepdive", {})
        tags = dd.get("auto_tags", [])
        query = dream.get("query", "")
        insight = dream.get("interpretation", {}).get("insight", "")
        lines.append(f"  [{', '.join(tags)}] {query[:60]}")
        if insight:
            lines.append(f"    → {insight[:150]}")

    body = "\n".join(lines)
    return _post_reply(thread_id, body, board="finance")


def post_risk_alert(risk_text: str) -> bool:
    """daily_risk.pyの結果を相場板に速報投稿。"""
    today = datetime.now().strftime("%Y%m%d")
    thread_id = f"risk_alert_{today}"
    return _post_reply(thread_id, risk_text, board="finance")


def generate_digest(days: int = 7) -> int:
    """ドメイン別まとめスレを雑談板に投稿。投稿数を返す。

    各ドメインについて:
    - 件数・ユニーククエリ数・high relevance数を集計
    - 上位クエリと外部検索結果のスニペットを抽出
    - 関連ネタとしてドメイン横断のリンクを付与
    """
    dreams = load_dreams_days(days=days)
    if not dreams:
        print("獏: ダイジェスト対象の夢なし。")
        return 0

    now = datetime.now()
    thread_id = f"baku_digest_{now.strftime('%Y%m%d')}"
    posted = 0

    # ドメイン別集計
    by_domain: dict[str, list[dict]] = {}
    for d in dreams:
        domain = d.get("domain", "unknown")
        by_domain.setdefault(domain, []).append(d)

    # 全体サマリ（>>1）
    total = len(dreams)
    domains_sorted = sorted(by_domain.items(), key=lambda x: -len(x[1]))
    unique_queries = len({d.get("query", "") for d in dreams})
    high_rel = sum(1 for d in dreams if d.get("relevance_score", 0) >= 3)

    header_lines = [
        f"【獏の夢まとめ】{now.strftime('%Y-%m-%d')} 直近{days}日分",
        f"",
        f"総夢数: {total}件 / ユニーククエリ: {unique_queries} / 高relevance: {high_rel}件",
        f"",
        f"■ドメイン別件数",
    ]
    for domain, entries in domains_sorted:
        uq = len({d.get("query", "") for d in entries})
        hr = sum(1 for d in entries if d.get("relevance_score", 0) >= 3)
        header_lines.append(f"  {domain}: {len(entries)}件 (uq={uq}, high={hr})")

    if _post_reply(thread_id, "\n".join(header_lines)):
        posted += 1

    # ドメイン別詳細（>>2〜）
    for domain, entries in domains_sorted:
        if len(entries) == 0:
            continue

        # ユニーククエリ別に集約
        query_groups: dict[str, list[dict]] = {}
        for d in entries:
            q = d.get("query", "?")
            query_groups.setdefault(q, []).append(d)

        # relevance_scoreの合計でソート
        ranked = sorted(
            query_groups.items(),
            key=lambda x: sum(d.get("relevance_score", 0) for d in x[1]),
            reverse=True,
        )

        lines = [f"【{domain}】{len(entries)}件", ""]

        for query, group in ranked[:10]:  # 上位10クエリ
            total_rel = sum(d.get("relevance_score", 0) for d in group)
            lines.append(f"▼ {query} (×{len(group)}, rel={total_rel})")

            # 最新の外部結果からスニペット抽出
            best = max(group, key=lambda d: d.get("relevance_score", 0))
            ext = best.get("external_result", "")
            if ext:
                # 最初の結果タイトル+スニペットを抽出
                snippets = ext.split(" | ")[:2]
                for s in snippets:
                    s = s.strip()[:150]
                    if s:
                        lines.append(f"  → {s}")

            # 解釈があれば付与
            interp = best.get("interpretation", {})
            if isinstance(interp, dict):
                conn = interp.get("connection", "")
                insight = interp.get("insight", "")
                if conn:
                    lines.append(f"  接続: {conn}")
                if insight:
                    lines.append(f"  知見: {insight}")

            lines.append("")

        # 本文が長すぎる場合は切り詰め
        body = "\n".join(lines)
        if len(body) > 2000:
            body = body[:1997] + "..."

        if _post_reply(thread_id, body):
            posted += 1

        time.sleep(0.5)  # DB書き込み間隔

    # クロスドメイン関連ネタ（最終レス）
    cross_lines = ["【ドメイン横断の関連ネタ】", ""]

    # 同一外部結果が複数ドメインで出現しているケースを抽出
    ext_to_domains: dict[str, set[str]] = {}
    for d in dreams:
        ext = (d.get("external_result") or "")[:80]
        if ext:
            ext_to_domains.setdefault(ext, set()).add(d.get("domain", "?"))

    cross_refs = {ext: doms for ext, doms in ext_to_domains.items() if len(doms) >= 2}
    if cross_refs:
        for ext, doms in list(cross_refs.items())[:5]:
            cross_lines.append(f"  {' × '.join(sorted(doms))}")
            cross_lines.append(f"    → {ext[:120]}")
            cross_lines.append("")
    else:
        cross_lines.append("  (今回はドメイン横断ヒットなし)")

    if _post_reply(thread_id, "\n".join(cross_lines)):
        posted += 1

    print(f"獏: ダイジェスト完了 → {thread_id} ({posted}レス投稿)")
    return posted


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
    last_digest_week = None

    try:
        while _running:
            # 夢見実行
            try:
                dream_once()
            except Exception as e:
                print(f"獏: 夢見中にエラー: {e}", file=sys.stderr)

            # 朝のサマリ + 日次バッチチェック
            now = datetime.now()
            today = now.date()
            if now.hour >= SUMMARY_HOUR and last_summary_date != today:
                try:
                    write_daily_summary()
                except Exception as e:
                    print(f"獏: サマリ生成エラー: {e}", file=sys.stderr)
                try:
                    run_daily_batch()
                except Exception as e:
                    print(f"獏: 日次バッチエラー: {e}", file=sys.stderr)

                # 週次ダイジェスト（DIGEST_DAY に実行）
                current_week = today.isocalendar()[1]
                if today.weekday() == DIGEST_DAY and last_digest_week != current_week:
                    try:
                        print("獏: 週次ダイジェスト生成開始...")
                        generate_digest(days=7)
                    except Exception as e:
                        print(f"獏: ダイジェスト生成エラー: {e}", file=sys.stderr)
                    last_digest_week = current_week

                last_summary_date = today

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
    parser.add_argument("--batch", action="store_true",
                        help="日次バッチ（Sonnet選別+蔵書化）を1回実行して終了")
    parser.add_argument("--digest", action="store_true",
                        help="まとめスレ生成（2ch雑談板に投稿）")
    parser.add_argument("--days", type=int, default=7,
                        help="ダイジェスト対象日数（デフォルト=7）")
    parser.add_argument("--finance-dive", action="store_true",
                        help="Finance系の夢を自動深堀り（FRED/World Bank検証）")
    args = parser.parse_args()

    if args.finance_dive:
        hours = args.days * 24
        all_dreams = load_recent_dreams(hours=hours)
        enriched = finance_deepdive(all_dreams)
        if enriched:
            report = format_finance_report(enriched)
            print(report)
            report_path = PROJECT_ROOT / "data" / "finance_deepdive.md"
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"# Finance Deep Dive — {datetime.now().strftime('%Y-%m-%d')}\n")
                f.write(report)
            print(f"\nレポート保存: {report_path}")
            # 相場板に投稿
            post_finance_report(enriched)
        else:
            print("獏: Finance系の深堀り対象なし")
    elif args.digest:
        posted = generate_digest(days=args.days)
        print(f"ダイジェスト結果: {posted}レス投稿")
    elif args.summary:
        write_daily_summary()
    elif args.batch:
        result = run_daily_batch()
        print(f"バッチ結果: {result}")
    elif args.once or args.topic:
        dream_once(manual_topic=args.topic)
    else:
        daemon_loop(interval=args.interval)
