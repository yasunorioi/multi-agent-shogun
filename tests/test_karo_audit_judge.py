"""karo_audit_judge.py のテスト (cmd_573 S7)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from karo_audit_judge import judge_needs_audit


def test_keyword_crystallize():
    """crystallize キーワードを含む説明は flagged=True。"""
    flagged, reasons = judge_needs_audit(
        "scripts/botsu/crystallize.py に新機能を追加する",
        target_path=None,
    )
    assert flagged is True
    assert any("crystallize" in r for r in reasons)


def test_path_scripts_botsu():
    """target_path が scripts/botsu/ を含む場合は flagged=True。"""
    flagged, reasons = judge_needs_audit(
        "ユニットテスト追加",
        target_path="/home/yasu/multi-agent-shogun/scripts/botsu/crystallize.py",
    )
    assert flagged is True
    assert any("scripts/botsu/" in r for r in reasons)


def test_unrelated_returns_false():
    """結晶化・没日録・禁止事項に無関係なタスクは flagged=False。"""
    flagged, reasons = judge_needs_audit(
        "README.md のtypo修正",
        target_path="/home/yasu/some-project/README.md",
    )
    assert flagged is False
    assert reasons == []


def test_keyword_botsunichiroku():
    """botsunichiroku キーワードで flagged=True。"""
    flagged, reasons = judge_needs_audit(
        "botsunichiroku.py に新サブコマンドを追加",
        target_path=None,
    )
    assert flagged is True


def test_keyword_F004():
    """F004 等の禁止事項キーワードで flagged=True。"""
    flagged, reasons = judge_needs_audit(
        "forbidden_actions の F004 違反チェックを追加",
        target_path=None,
    )
    assert flagged is True


def test_path_instructions():
    """target_path が instructions/ を含む場合は flagged=True。"""
    flagged, reasons = judge_needs_audit(
        "役割定義の更新",
        target_path="/home/yasu/multi-agent-shogun/instructions/ashigaru.md",
    )
    assert flagged is True
    assert any("instructions/" in r for r in reasons)


def test_reasons_content():
    """reasons リストが具体的な理由文字列を返す。"""
    _, reasons = judge_needs_audit(
        "結晶化機構のテストを追加",
        target_path="scripts/botsu/test_crystallize.py",
    )
    assert len(reasons) >= 1
    assert all(isinstance(r, str) for r in reasons)
