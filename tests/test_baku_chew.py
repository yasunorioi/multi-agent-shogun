"""tests/test_baku_chew.py — 獏噛み砕きループ(Phase 1)テスト"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import baku


# === should_chew() ===

def _make_entry(delta_score=0.8, action="investigate", domain="agriculture_iot"):
    entry = {
        "domain": domain,
        "query": "test query",
        "delta_score": delta_score,
        "status": "interpreted",
    }
    if action is not None:
        entry["interpretation"] = {"action": action, "relevance": "high"}
    return entry


def test_should_chew_all_conditions_true():
    assert baku.should_chew(_make_entry()) is True


def test_should_chew_low_delta():
    """delta_score < DELTA_HIGH_THRESHOLD → False"""
    entry = _make_entry(delta_score=baku.DELTA_HIGH_THRESHOLD - 0.01)
    assert baku.should_chew(entry) is False


def test_should_chew_delta_exactly_threshold():
    """delta_score == DELTA_HIGH_THRESHOLD → True（< の反転なので境界値は通過）"""
    entry = _make_entry(delta_score=baku.DELTA_HIGH_THRESHOLD)
    assert baku.should_chew(entry) is True


def test_should_chew_action_not_investigate():
    """action != investigate → False"""
    assert baku.should_chew(_make_entry(action="archive")) is False
    assert baku.should_chew(_make_entry(action="ignore")) is False


def test_should_chew_no_interpretation():
    """interpretationなし → False"""
    entry = {"domain": "agriculture_iot", "delta_score": 0.9, "status": "raw"}
    assert baku.should_chew(entry) is False


def test_should_chew_wrong_domain():
    """domain not in priority_domains → False"""
    assert baku.should_chew(_make_entry(domain="philosophy")) is False
    assert baku.should_chew(_make_entry(domain="hardware")) is False


def test_should_chew_all_priority_domains():
    """priority_domainsの全ドメインでTrue"""
    for domain in baku.CHEW_PRIORITY_DOMAINS:
        assert baku.should_chew(_make_entry(domain=domain)) is True


# === chew_loop() ===

def _mock_setup(monkeypatch, ddg_results=None, int_results=None, haiku_verdicts=None):
    """chew_loop()のモックセットアップ"""
    call_count = {"ddg": 0, "int": 0, "haiku": 0}

    ddg_results = ddg_results or ["result A", "result B", "result C"]
    int_results = int_results or [None, None, None]
    haiku_verdicts = haiku_verdicts or [None, None, None]

    def mock_ddg(q):
        i = call_count["ddg"]
        call_count["ddg"] += 1
        return ddg_results[i] if i < len(ddg_results) else "default result"

    def mock_int(q):
        i = call_count["int"]
        call_count["int"] += 1
        return int_results[i] if i < len(int_results) else None

    def mock_haiku(entry, sources):
        i = call_count["haiku"]
        call_count["haiku"] += 1
        return haiku_verdicts[i] if i < len(haiku_verdicts) else None

    monkeypatch.setattr(baku, "search_ddg", mock_ddg)
    monkeypatch.setattr(baku, "search_kousatsu", mock_int)
    monkeypatch.setattr(baku, "_haiku_chew_judge", mock_haiku)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return call_count


def test_chew_loop_max_iter_stop(monkeypatch):
    """max_iter=3到達 → convergence_reason=max_iter"""
    # Haikuが常にneed_moreを返す
    verdicts = [
        {"verdict": "need_more", "next_query": "follow up q", "insight": "partial"},
        {"verdict": "need_more", "next_query": "more q", "insight": "more partial"},
        {"verdict": "need_more", "next_query": "even more", "insight": "still partial"},
    ]
    _mock_setup(monkeypatch, haiku_verdicts=verdicts)

    entry = _make_entry()
    result = baku.chew_loop(entry, max_iter=3)
    assert result["convergence_reason"] == "max_iter"
    assert result["iterations"] == 3


def test_chew_loop_haiku_sufficient(monkeypatch):
    """Haikuがsufficient → convergence_reason=haiku_sufficient"""
    verdicts = [
        {"verdict": "sufficient", "next_query": None, "insight": "十分な知見が得られた"},
    ]
    _mock_setup(monkeypatch, haiku_verdicts=verdicts)

    entry = _make_entry()
    result = baku.chew_loop(entry, max_iter=3)
    assert result["convergence_reason"] == "haiku_sufficient"
    assert result["iterations"] == 1
    assert result["chewed_insight"] == "十分な知見が得られた"


def test_chew_loop_jaccard_converge(monkeypatch):
    """前iterationと同一結果 → Jaccard収束 → convergence_reason=jaccard_converged"""
    same_result = "identical content word word word word word"
    _mock_setup(
        monkeypatch,
        ddg_results=[same_result, same_result, same_result],
        haiku_verdicts=[None, None, None],
    )

    entry = _make_entry()
    result = baku.chew_loop(entry, max_iter=3)
    assert result["convergence_reason"] == "jaccard_converged"
    # 2回目で収束するので iterations == 2
    assert result["iterations"] == 2


def test_chew_result_structure(monkeypatch):
    """chew_resultの必須キーが全て存在すること"""
    _mock_setup(monkeypatch, haiku_verdicts=[
        {"verdict": "sufficient", "next_query": None, "insight": "ok"}
    ])
    entry = _make_entry()
    result = baku.chew_loop(entry, max_iter=3)

    required_keys = {"iterations", "convergence_reason", "additional_sources",
                     "internal_connections", "chewed_insight", "chewed_at"}
    assert required_keys.issubset(result.keys())
    assert isinstance(result["additional_sources"], list)
    assert isinstance(result["internal_connections"], list)
    assert isinstance(result["iterations"], int)


def test_chew_loop_nullclaw_mode(monkeypatch):
    """API未設定（NullClaw）でもmax_iterまで動作すること"""
    _mock_setup(monkeypatch, haiku_verdicts=[None, None, None])

    entry = _make_entry()
    result = baku.chew_loop(entry, max_iter=3)
    # Haikuなしではsufficient判定されない → max_iterまで回るかjaccard収束
    assert result["convergence_reason"] in {"max_iter", "jaccard_converged"}


def test_chew_loop_internal_connections_recorded(monkeypatch):
    """search_kousatsu()が返した結果がinternal_connectionsに記録されること"""
    _mock_setup(
        monkeypatch,
        int_results=["cmd_451: Dexterパターン発見", None, None],
        haiku_verdicts=[{"verdict": "sufficient", "next_query": None, "insight": "ok"}],
    )
    entry = _make_entry()
    result = baku.chew_loop(entry, max_iter=3)
    assert len(result["internal_connections"]) >= 1
    assert "cmd_451" in result["internal_connections"][0]


# === Phase 0テスト（引き続きPASS確認） ===

def test_phase0_tests_still_importable():
    """Phase 0のフィルタ関数が引き続きimport可能であること"""
    assert callable(baku.load_content_hashes)
    assert callable(baku.save_content_hashes)
    assert callable(baku.compute_content_hash)
    assert callable(baku.compute_jaccard)
    assert callable(baku.check_content_hash)
