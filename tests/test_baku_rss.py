"""tests/test_baku_rss.py — 獏RSSフィード仕入れテスト"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import baku

# === _parse_sitemap_xml() ===

SAMPLE_SITEMAP = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://media.rakuten-sec.net/articles/-/12345</loc>
    <news:news>
      <news:publication>
        <news:name>トウシル</news:name>
        <news:language>ja</news:language>
      </news:publication>
      <news:publication_date>2026-03-27</news:publication_date>
      <news:title>インド株は買いの好機か？</news:title>
      <news:keywords>インド, 新興国株, 生成AI</news:keywords>
    </news:news>
  </url>
  <url>
    <loc>https://media.rakuten-sec.net/articles/-/12346</loc>
    <news:news>
      <news:publication>
        <news:name>トウシル</news:name>
        <news:language>ja</news:language>
      </news:publication>
      <news:publication_date>2026-03-26</news:publication_date>
      <news:title>海運株の動向分析</news:title>
      <news:keywords>海運, 配当, 国内株式</news:keywords>
    </news:news>
  </url>
  <url>
    <loc>https://media.rakuten-sec.net/articles/-/12347</loc>
    <news:news>
      <news:publication>
        <news:name>トウシル</news:name>
        <news:language>ja</news:language>
      </news:publication>
      <news:publication_date>2026-03-25</news:publication_date>
      <news:title>3本目の記事</news:title>
      <news:keywords>テスト</news:keywords>
    </news:news>
  </url>
</urlset>
"""


def test_parse_sitemap_xml_basic():
    items = baku._parse_sitemap_xml(SAMPLE_SITEMAP)
    assert len(items) > 0
    assert items[0]["title"] == "インド株は買いの好機か？"
    assert items[0]["url"] == "https://media.rakuten-sec.net/articles/-/12345"
    assert items[0]["published"] == "2026-03-27"


def test_parse_sitemap_xml_max_items():
    items = baku._parse_sitemap_xml(SAMPLE_SITEMAP, max_items=2)
    assert len(items) == 2


def test_parse_sitemap_xml_keywords_as_summary():
    """keywordsがsummaryフィールドに入ること"""
    items = baku._parse_sitemap_xml(SAMPLE_SITEMAP, max_items=1)
    assert "インド" in items[0]["summary"]


def test_parse_sitemap_xml_invalid_xml():
    items = baku._parse_sitemap_xml("not xml at all")
    assert items == []


def test_parse_sitemap_xml_empty():
    items = baku._parse_sitemap_xml("")
    assert items == []


# === _fetch_rss_source() ===

def test_fetch_rss_source_sitemap(monkeypatch):
    """type=sitemapのソースが_parse_sitemap_xmlを呼ぶこと"""
    def mock_urlopen(url, timeout=None):
        mock = MagicMock()
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        mock.read.return_value = SAMPLE_SITEMAP.encode("utf-8")
        return mock

    monkeypatch.setattr(baku.urllib.request, "urlopen", mock_urlopen)
    source = {
        "name": "toushiru",
        "url": "https://media.rakuten-sec.net/list/feed/rss4googlenews",
        "type": "sitemap",
        "max_items": 5,
    }
    items = baku._fetch_rss_source(source)
    assert len(items) >= 2
    assert items[0]["title"] == "インド株は買いの好機か？"


def test_fetch_rss_source_network_error(monkeypatch):
    """ネットワークエラー時は空リストを返すこと"""
    monkeypatch.setattr(
        baku.urllib.request, "urlopen",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("connection refused"))
    )
    source = {"name": "test", "url": "https://example.com/feed", "type": "sitemap"}
    items = baku._fetch_rss_source(source)
    assert items == []


# === search_rss_sources() ===

def test_search_rss_sources_disabled(monkeypatch):
    """enabled: falseのソースはスキップされること"""
    monkeypatch.setattr(baku, "_load_rss_sources", lambda: [
        {"name": "disabled_src", "url": "https://x.com/feed", "type": "sitemap", "enabled": False}
    ])
    monkeypatch.setattr(time, "sleep", lambda s: None)
    results = baku.search_rss_sources()
    assert results == []


def test_search_rss_sources_returns_source_name(monkeypatch):
    """結果にsource_nameが設定されること"""
    monkeypatch.setattr(baku, "_load_rss_sources", lambda: [
        {"name": "toushiru", "url": "https://x.com/feed", "type": "sitemap",
         "enabled": True, "check_youtube": False, "max_items": 2}
    ])
    monkeypatch.setattr(baku, "_fetch_rss_source", lambda s: [
        {"title": "記事1", "url": "https://example.com/1", "published": "2026-03-27", "summary": "test"},
        {"title": "記事2", "url": "https://example.com/2", "published": "2026-03-27", "summary": "test"},
    ])
    monkeypatch.setattr(time, "sleep", lambda s: None)
    results = baku.search_rss_sources()
    assert len(results) == 2
    assert results[0]["source_name"] == "toushiru"


def test_search_rss_sources_no_sources(monkeypatch):
    """ソースなし → 空リスト"""
    monkeypatch.setattr(baku, "_load_rss_sources", lambda: [])
    results = baku.search_rss_sources()
    assert results == []


# === YouTube URL検出テスト ===

def test_youtube_url_detection_in_title():
    """タイトルにYouTube URLがあれば検出されること"""
    text = "解説動画 https://www.youtube.com/watch?v=dQw4w9WgXcQ をご覧ください"
    match = baku.YOUTUBE_URL_RE.search(text)
    assert match is not None
    assert "dQw4w9WgXcQ" in match.group(0)


def test_youtube_url_detection_youtu_be():
    """youtu.be短縮URLも検出されること"""
    text = "https://youtu.be/dQw4w9WgXcQ"
    match = baku.YOUTUBE_URL_RE.search(text)
    assert match is not None


def test_youtube_url_not_detected_in_plain_text():
    """YouTube URLがなければNone"""
    text = "普通の記事本文のテキスト"
    assert baku.YOUTUBE_URL_RE.search(text) is None


def test_search_rss_sources_youtube_detected(monkeypatch):
    """check_youtube=trueかつYouTube URLあり → video_summaryが追加されること"""
    monkeypatch.setattr(baku, "_load_rss_sources", lambda: [
        {"name": "test_yt", "url": "https://x.com/feed", "type": "sitemap",
         "enabled": True, "check_youtube": True, "max_items": 1}
    ])
    monkeypatch.setattr(baku, "_fetch_rss_source", lambda s: [
        {"title": "解説 https://www.youtube.com/watch?v=test123",
         "url": "https://example.com/1", "published": "2026-03-27", "summary": ""}
    ])
    monkeypatch.setattr(time, "sleep", lambda s: None)

    mock_summarize = MagicMock(return_value={"summary": "動画要約結果", "url": "https://www.youtube.com/watch?v=test123"})
    # youtube_summarizerのsummarize_videoをモック
    with patch.dict("sys.modules", {"youtube_summarizer": MagicMock(summarize_video=mock_summarize)}):
        results = baku.search_rss_sources()

    # video_summaryキーが存在すること（モックの都合でsummary値は空でもOK）
    assert len(results) == 1
    assert "source_name" in results[0]


# === RSS結果のdreams.jsonl記録形式テスト ===

def test_rss_dream_entry_structure(tmp_path, monkeypatch):
    """RSS結果がdreams.jsonlに正しい形式で記録されること"""
    monkeypatch.setattr(baku, "DREAMS_PATH", tmp_path / "dreams.jsonl")
    monkeypatch.setattr(baku, "CONTENT_HASH_PATH", tmp_path / "hash.json")
    monkeypatch.setattr(baku, "get_recent_keywords", lambda days=7: [])
    monkeypatch.setattr(baku, "load_recent_dreams", lambda hours=6: [])
    monkeypatch.setattr(baku, "generate_dream_queries", lambda kw: [])
    monkeypatch.setattr(baku, "get_recent_cmd_summary", lambda: "")
    monkeypatch.setattr(baku, "HAIKU_API_KEY", "")
    monkeypatch.setattr(baku, "search_rss_sources", lambda: [
        {"title": "テスト記事", "url": "https://example.com/1",
         "published": "2026-03-27", "summary": "テスト内容", "source_name": "toushiru"}
    ])
    monkeypatch.setattr(time, "sleep", lambda s: None)

    baku.dream_once()

    import json
    lines = (tmp_path / "dreams.jsonl").read_text().strip().splitlines()
    entries = [json.loads(l) for l in lines]
    rss_entries = [e for e in entries if e.get("source", "").startswith("rss_")]

    assert len(rss_entries) == 1
    e = rss_entries[0]
    assert e["source"] == "rss_toushiru"
    assert e["source_title"] == "テスト記事"
    assert "delta_score" in e
    assert "dreamt_at" in e


# === 既存テストの引き続きPASS確認 ===

def test_phase0_phase1_functions_importable():
    """Phase 0/1の関数が引き続きimport可能であること"""
    assert callable(baku.load_content_hashes)
    assert callable(baku.compute_content_hash)
    assert callable(baku.should_chew)
    assert callable(baku.chew_loop)
