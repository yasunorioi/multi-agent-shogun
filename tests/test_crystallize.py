"""crystallize.py のテスト (cmd_517 ハイブリッドv2)."""

import os
import sys
import sqlite3
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def crystals_env(tmp_path, monkeypatch):
    crystals_dir = tmp_path / "crystals"
    swarm_db = tmp_path / "swarm.db"
    monkeypatch.setenv("SHOGUN_CRYSTALS_DIR", str(crystals_dir))
    monkeypatch.setenv("SHOGUN_CRYSTALS_DISABLE", "0")
    monkeypatch.setenv("SWARM_DAT_URL", "http://127.0.0.1:1")  # 確実にHTTP失敗
    monkeypatch.setenv("SWARM_BOARD", "crystals")
    monkeypatch.setenv("SWARM_SERVER_PATH", "/nonexistent/path")  # 確実にPy直叩き失敗
    monkeypatch.setenv("SWARM_DB", str(swarm_db))
    # 空 swarm.db (thread_replies を作る)
    conn = sqlite3.connect(str(swarm_db))
    conn.execute(
        "CREATE TABLE thread_replies (id INTEGER PRIMARY KEY, thread_id TEXT, board TEXT,"
        " author TEXT, body TEXT, posted_at TEXT)"
    )
    conn.commit()
    conn.close()
    return {"crystals_dir": crystals_dir, "swarm_db": swarm_db}


@pytest.fixture
def botsu_with_seeded_db(seeded_db_path, monkeypatch):
    """shogun側の botsu モジュールに seeded DB を差し込む."""
    monkeypatch.setenv("SHOGUN_ROOT", str(seeded_db_path.parent.parent))
    # botsu パッケージを import 前に DB_PATH を差し替えるため、毎回リロード
    for k in [k for k in list(sys.modules) if k == "botsu" or k.startswith("botsu.")]:
        del sys.modules[k]
    import botsu
    monkeypatch.setattr(botsu, "DB_PATH", seeded_db_path)
    return botsu


def test_template_generation(botsu_with_seeded_db, crystals_env):
    """ダイジェスト生成: >>1-5 が5本生成される."""
    from botsu.crystallize import _build_templates, _fetch_cmd_info
    info = _fetch_cmd_info("cmd_001")
    assert info is not None
    bodies = _build_templates(info)
    assert len(bodies) == 5
    assert bodies[0].startswith(">>1 問い")
    assert bodies[1].startswith(">>2 結果")
    assert bodies[2].startswith(">>3 変更点")
    assert bodies[3].startswith(">>4 学び")
    assert bodies[4].startswith(">>5 関連")


def test_md_append_new(botsu_with_seeded_db, crystals_env):
    """MD目次append: 新規cmdで1ブロック追加."""
    from botsu.crystallize import crystallize_cmd
    result = crystallize_cmd("cmd_001")
    assert result["skipped"] is False
    assert result["md_appended"] is True
    md_path = crystals_env["crystals_dir"] / "shogun.md"
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "### cmd_001:" in content
    assert "→ DAT #cmd_001" in content


def test_md_append_idempotent(botsu_with_seeded_db, crystals_env):
    """冪等性: 同cmd再実行でMD目次が重複追加されない."""
    from botsu.crystallize import crystallize_cmd
    crystallize_cmd("cmd_001")
    crystallize_cmd("cmd_001")
    md_path = crystals_env["crystals_dir"] / "shogun.md"
    content = md_path.read_text(encoding="utf-8")
    assert content.count("### cmd_001:") == 1


def test_disable_kill_switch(botsu_with_seeded_db, crystals_env, monkeypatch):
    """SHOGUN_CRYSTALS_DISABLE=1 でスキップ動作."""
    monkeypatch.setenv("SHOGUN_CRYSTALS_DISABLE", "1")
    from botsu.crystallize import crystallize_cmd
    result = crystallize_cmd("cmd_001")
    assert result["skipped"] is True
    assert result["reason"] == "disabled"
    md_path = crystals_env["crystals_dir"] / "shogun.md"
    assert not md_path.exists()


def test_cmd_not_found(botsu_with_seeded_db, crystals_env):
    """存在しないcmd_id: skipped + reason=cmd_not_found."""
    from botsu.crystallize import crystallize_cmd
    result = crystallize_cmd("cmd_999_nonexistent")
    assert result["skipped"] is True
    assert result["reason"] == "cmd_not_found"


def test_dat_existing_skips_post(botsu_with_seeded_db, crystals_env):
    """DAT側に既存スレあり: postedはTrue扱い (再投稿しない)."""
    db = crystals_env["swarm_db"]
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO thread_replies (thread_id, board, author, body, posted_at)"
        " VALUES ('cmd_001', 'crystals', 'shogun', '>>1 既存', '2026-04-29T00:00:00')"
    )
    conn.commit()
    conn.close()
    from botsu.crystallize import crystallize_cmd
    result = crystallize_cmd("cmd_001")
    assert result["posted"] is True
