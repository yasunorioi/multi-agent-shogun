"""tests/test_baku_filter.py — 獏ラプラシアンフィルタ(Phase 0)テスト"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/baku.pyをimport可能にする
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import baku


# === compute_content_hash ===

def test_compute_content_hash_returns_16chars():
    result = baku.compute_content_hash("test string")
    assert len(result) == 16


def test_compute_content_hash_same_input():
    h1 = baku.compute_content_hash("hello world")
    h2 = baku.compute_content_hash("hello world")
    assert h1 == h2


def test_compute_content_hash_different_input():
    h1 = baku.compute_content_hash("hello world")
    h2 = baku.compute_content_hash("goodbye world")
    assert h1 != h2


def test_compute_content_hash_empty_string():
    result = baku.compute_content_hash("")
    assert len(result) == 16


# === compute_jaccard ===

def test_jaccard_identical():
    score = baku.compute_jaccard("the quick brown fox", "the quick brown fox")
    assert score == 1.0


def test_jaccard_disjoint():
    score = baku.compute_jaccard("apple banana cherry", "dog elephant frog")
    assert score == 0.0


def test_jaccard_partial():
    score = baku.compute_jaccard("apple banana cherry", "apple dog frog")
    # 共通: apple(1) / 全体: apple,banana,cherry,dog,frog(5) = 0.2
    assert abs(score - 1 / 5) < 1e-9


def test_jaccard_empty_both():
    score = baku.compute_jaccard("", "")
    assert score == 1.0


def test_jaccard_one_empty():
    score = baku.compute_jaccard("hello", "")
    assert score == 0.0


# === delta_score閾値判定 ===

def test_delta_score_low_delta():
    """delta_score < DELTA_LOW_THRESHOLD → low_delta"""
    # Jaccardが高い（ほぼ同一テキスト）→ delta_scoreが低い
    text = "same content about infrastructure investment in asia"
    hashes = {}
    # 1回目: 初回登録（skip=False, delta=1.0）
    skip, delta = baku.check_content_hash("query1", text, hashes)
    assert not skip
    assert delta == 1.0

    # 2回目: 同一テキスト→hash一致→skip=True, delta=0.0
    skip2, delta2 = baku.check_content_hash("query1", text, hashes)
    assert skip2
    assert delta2 == 0.0
    assert delta2 < baku.DELTA_LOW_THRESHOLD


def test_delta_score_high_delta():
    """delta_score >= DELTA_LOW_THRESHOLD → 解釈を続行すべき"""
    hashes = {}
    text_a = "asia infrastructure railway construction update"
    text_b = "quantum computing breakthrough new algorithm patent"
    # 1回目登録
    baku.check_content_hash("query2", text_a, hashes)
    # 2回目: 全く異なるテキスト → delta高い
    skip, delta = baku.check_content_hash("query2", text_b, hashes)
    assert not skip
    assert delta >= baku.DELTA_LOW_THRESHOLD


# === load_content_hashes / save_content_hashes ===

def test_load_content_hashes_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(baku, "CONTENT_HASH_PATH", tmp_path / "nonexistent.json")
    result = baku.load_content_hashes()
    assert result == {}


def test_save_and_load_content_hashes(tmp_path, monkeypatch):
    path = tmp_path / "baku_content_hash.json"
    monkeypatch.setattr(baku, "CONTENT_HASH_PATH", path)
    data = {"abc123": {"last_hash": "deadbeef12345678", "last_result": "test", "last_checked": "2026-01-01T00:00:00", "check_count": 1, "delta_history": []}}
    baku.save_content_hashes(data)
    loaded = baku.load_content_hashes()
    assert loaded == data


def test_load_content_hashes_corrupted_json(tmp_path, monkeypatch):
    path = tmp_path / "baku_content_hash.json"
    path.write_text("not valid json", encoding="utf-8")
    monkeypatch.setattr(baku, "CONTENT_HASH_PATH", path)
    result = baku.load_content_hashes()
    assert result == {}


# === check_content_hash: delta_historyの蓄積 ===

def test_delta_history_accumulation():
    hashes = {}
    texts = [
        "initial content about topic",
        "slightly changed content topic new",
        "completely different information here now",
    ]
    for i, text in enumerate(texts):
        baku.check_content_hash("hist_query", text, hashes)

    key = baku._query_key("hist_query")
    history = hashes[key]["delta_history"]
    # 2回目以降からhistoryが蓄積される（1回目は初回登録でhistoryなし）
    assert len(history) >= 1


def test_delta_history_max_length():
    hashes = {}
    for i in range(baku.DELTA_HISTORY_MAX + 5):
        text = f"unique content number {i} different every time iteration"
        baku.check_content_hash("maxhist_query", text, hashes)

    key = baku._query_key("maxhist_query")
    history = hashes[key]["delta_history"]
    assert len(history) <= baku.DELTA_HISTORY_MAX


# === dream_once()がhash一致時にlow_deltaとして記録 ===

def test_dream_once_low_delta_on_hash_match(tmp_path, monkeypatch):
    """hash一致時にdream_entryのstatusがlow_deltaになること"""
    # CONTENT_HASH_PATHを一時ディレクトリに向ける
    hash_path = tmp_path / "baku_content_hash.json"
    monkeypatch.setattr(baku, "CONTENT_HASH_PATH", hash_path)
    monkeypatch.setattr(baku, "DREAMS_PATH", tmp_path / "dreams.jsonl")

    # search_ddg / search_kousatsu / interpret_dream をモック
    fixed_result = "fixed search result content unchanged"
    monkeypatch.setattr(baku, "search_ddg", lambda q: fixed_result)
    monkeypatch.setattr(baku, "search_kousatsu", lambda q: None)
    monkeypatch.setattr(baku, "interpret_dream", lambda entry, ctx="": {"relevance": "high"})
    monkeypatch.setattr(baku, "get_recent_cmd_summary", lambda: "")
    monkeypatch.setattr(baku, "get_recent_keywords", lambda days=7: [])
    monkeypatch.setattr(baku, "load_recent_dreams", lambda hours=6: [])
    monkeypatch.setattr(baku, "HAIKU_API_KEY", "dummy_key")

    queries = [{"domain": "test", "query": "test query stable", "relevance_score": 50, "matched_keywords": []}]
    monkeypatch.setattr(baku, "generate_dream_queries", lambda kw: queries)
    monkeypatch.setattr(baku, "search_rss_sources", lambda: [])  # RSS巡回なし

    import time as time_mod
    monkeypatch.setattr(time_mod, "sleep", lambda s: None)

    # 1回目: 初回 → interpreted（hash記録）
    baku.dream_once()
    dreams1 = [json.loads(l) for l in (tmp_path / "dreams.jsonl").read_text().strip().splitlines()]
    ddg_entries1 = [d for d in dreams1 if not d.get("source", "").startswith("rss_")]
    assert ddg_entries1[-1]["status"] == "interpreted"

    # 2回目: 同一結果 → hash一致 → low_delta
    baku.dream_once()
    dreams2 = [json.loads(l) for l in (tmp_path / "dreams.jsonl").read_text().strip().splitlines()]
    ddg_entries2 = [d for d in dreams2 if not d.get("source", "").startswith("rss_")]
    assert ddg_entries2[-1]["status"] == "low_delta"
    assert ddg_entries2[-1]["delta_score"] == 0.0
