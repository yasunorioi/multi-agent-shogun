#!/usr/bin/env python3
"""没日録DB FTS5インデックス移行スクリプト (subtask_913/cmd_419 W1-a)

没日録DB (botsunichiroku.db) 内に search_index FTS5テーブルを作成し、
全テーブルのデータをMeCab分かち書きで投入する。

冪等設計: 再実行しても安全（DELETE FROM search_index → INSERT）。

参照:
  - tools/kousatsu/build_index.py  : MeCab tokenize ロジックの移植元
  - docs/shogun/2ch_integration_design.md §5 : FTS5テーブル定義・移行設計

使用方法:
  python3 scripts/migrate_fts5.py [--db <path>]

MeCab未インストール時:
  MeCab tokenize をスキップし、raw テキストをそのまま投入する。
  FTS5 tokenize='unicode61' により最低限の検索は動作する。
  全機能を使うには: apt install mecab libmecab-dev mecab-ipadic-utf8
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

# MeCab はオプション依存。未インストールでも動作する。
try:
    import MeCab
    _MECAB_AVAILABLE = True
except ImportError:
    _MECAB_AVAILABLE = False

# ─────────────────────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────────────────────

DEFAULT_DB = os.environ.get(
    "BOTSUNICHIROKU_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "botsunichiroku.db"),
)

# MeCab品詞フィルタ: 名詞・動詞・形容詞のみ抽出 (build_index.py と同一)
ALLOWED_POS = {"名詞", "動詞", "形容詞"}

# ★ FTS5テーブル定義（2ch_integration_design.md §5.1 準拠）
FTS5_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    source_type,
    source_id,
    parent_id,
    project,
    worker_id,
    status,
    content,
    tokenize='unicode61'
);
"""

# ─────────────────────────────────────────────────────────────
# MeCab tokenizer
# ─────────────────────────────────────────────────────────────

def _create_tagger():
    """MeCab Taggerを生成する。MeCab未インストール時はNone。"""
    if not _MECAB_AVAILABLE:
        return None
    try:
        return MeCab.Tagger()
    except Exception as exc:
        print(f"WARNING: MeCab Tagger初期化失敗 ({exc})、rawテキストで代替", file=sys.stderr)
        return None


def tokenize(tagger, text: str) -> str:
    """テキストをMeCabで分かち書きし、名詞・動詞・形容詞のみ抽出する。

    MeCab未インストール or Tagger=None の場合は raw テキストをそのまま返す。
    (unicode61 tokenizer が最低限の分割を担当する)

    Returns:
        スペース区切りの分かち書き文字列、またはraw text
    """
    if not text:
        return ""
    if tagger is None:
        return text
    tokens = []
    try:
        node = tagger.parseToNode(text)
        while node:
            features = node.feature.split(",")
            if features[0] in ALLOWED_POS:
                surface = node.surface.strip()
                if surface:
                    tokens.append(surface)
            node = node.next
    except Exception as exc:
        # MeCab parse失敗時は raw テキストにフォールバック
        print(f"WARNING: MeCab parse失敗 ({exc})、rawテキストで代替", file=sys.stderr)
        return text
    return " ".join(tokens)


def safe_str(value) -> str:
    """NoneやNULL値を空文字列に変換する。"""
    if value is None:
        return ""
    return str(value)


# ─────────────────────────────────────────────────────────────
# インデックス構築
# ─────────────────────────────────────────────────────────────

def migrate(db_path: str) -> None:
    """没日録DB内にFTS5テーブルを作成し全データを投入する。"""

    db_path = os.path.realpath(db_path)
    if not os.path.exists(db_path):
        print(f"ERROR: 没日録DB が見つかりません: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"DB: {db_path}")

    if not _MECAB_AVAILABLE:
        print("WARNING: MeCab未インストール。rawテキスト+unicode61 tokenizer で動作します。")
        print("         全機能: apt install mecab libmecab-dev mecab-ipadic-utf8")

    tagger = _create_tagger()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # WALモード有効化（並行アクセス対策）
    conn.execute("PRAGMA journal_mode=WAL")

    # FTS5テーブル作成（存在しない場合のみ）
    conn.execute(FTS5_CREATE)
    conn.commit()

    # 冪等保証: 既存データを全削除してから再投入
    conn.execute("DELETE FROM search_index")
    conn.commit()
    print("search_index クリア完了")

    counts = {
        "commands": 0,
        "subtasks": 0,
        "reports": 0,
        "dashboard_entries": 0,
        "diary_entries": 0,
        "thread_replies": 0,
    }

    # ── commands ────────────────────────────────────────────
    for row in conn.execute(
        "SELECT id, command, project, status, details FROM commands"
    ):
        raw_text = " ".join(filter(None, [
            safe_str(row["command"]),
            safe_str(row["details"]),
        ]))
        content = tokenize(tagger, raw_text)
        conn.execute(
            "INSERT INTO search_index"
            " (source_type, source_id, parent_id, project, worker_id, status, content)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "command",
                safe_str(row["id"]),
                "",
                safe_str(row["project"]),
                "",
                safe_str(row["status"]),
                content,
            ),
        )
        counts["commands"] += 1

    # ── subtasks ─────────────────────────────────────────────
    for row in conn.execute(
        "SELECT id, parent_cmd, worker_id, project, description, status, notes"
        " FROM subtasks"
    ):
        raw_text = " ".join(filter(None, [
            safe_str(row["description"]),
            safe_str(row["notes"]),
        ]))
        content = tokenize(tagger, raw_text)
        conn.execute(
            "INSERT INTO search_index"
            " (source_type, source_id, parent_id, project, worker_id, status, content)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "subtask",
                safe_str(row["id"]),
                safe_str(row["parent_cmd"]),
                safe_str(row["project"]),
                safe_str(row["worker_id"]),
                safe_str(row["status"]),
                content,
            ),
        )
        counts["subtasks"] += 1

    # ── reports ──────────────────────────────────────────────
    for row in conn.execute(
        "SELECT id, worker_id, task_id, status, summary, findings, notes"
        " FROM reports"
    ):
        raw_text = " ".join(filter(None, [
            safe_str(row["summary"]),
            safe_str(row["findings"]),
            safe_str(row["notes"]),
        ]))
        content = tokenize(tagger, raw_text)
        conn.execute(
            "INSERT INTO search_index"
            " (source_type, source_id, parent_id, project, worker_id, status, content)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "report",
                str(row["id"]),
                safe_str(row["task_id"]),
                "",
                safe_str(row["worker_id"]),
                safe_str(row["status"]),
                content,
            ),
        )
        counts["reports"] += 1

    # ── dashboard_entries ────────────────────────────────────
    try:
        dashboard_rows = conn.execute(
            "SELECT id, cmd_id, section, content, status, tags FROM dashboard_entries"
        ).fetchall()
    except sqlite3.OperationalError:
        dashboard_rows = []
        print("WARNING: dashboard_entries テーブル不在、スキップ")

    for row in dashboard_rows:
        raw_text = " ".join(filter(None, [
            safe_str(row["section"]),
            safe_str(row["content"]),
        ]))
        content = tokenize(tagger, raw_text)
        conn.execute(
            "INSERT INTO search_index"
            " (source_type, source_id, parent_id, project, worker_id, status, content)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "dashboard",
                str(row["id"]),
                safe_str(row["cmd_id"]),
                "",
                safe_str(row["tags"]),   # worker_id フィールドに tags を格納 (build_index.py 踏襲)
                safe_str(row["status"]),
                content,
            ),
        )
        counts["dashboard_entries"] += 1

    # ── diary_entries ────────────────────────────────────────
    try:
        diary_rows = conn.execute(
            "SELECT id, agent_id, date, cmd_id, subtask_id, summary, body, tags"
            " FROM diary_entries"
        ).fetchall()
    except sqlite3.OperationalError:
        diary_rows = []
        print("WARNING: diary_entries テーブル不在、スキップ")

    for row in diary_rows:
        raw_text = " ".join(filter(None, [
            safe_str(row["summary"]),
            safe_str(row["body"]),
        ]))
        content = tokenize(tagger, raw_text)
        conn.execute(
            "INSERT INTO search_index"
            " (source_type, source_id, parent_id, project, worker_id, status, content)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "diary",
                str(row["id"]),
                safe_str(row["cmd_id"]) or safe_str(row["subtask_id"]),
                "",
                safe_str(row["agent_id"]),
                "",
                content,
            ),
        )
        counts["diary_entries"] += 1

    # ── thread_replies ───────────────────────────────────────
    try:
        reply_rows = conn.execute(
            "SELECT id, thread_id, board, author, body"
            " FROM thread_replies"
        ).fetchall()
    except sqlite3.OperationalError:
        reply_rows = []
        print("WARNING: thread_replies テーブル不在、スキップ")

    for row in reply_rows:
        raw_text = safe_str(row["body"])
        content = tokenize(tagger, raw_text)
        conn.execute(
            "INSERT INTO search_index"
            " (source_type, source_id, parent_id, project, worker_id, status, content)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "reply",
                str(row["id"]),
                safe_str(row["thread_id"]),
                safe_str(row["board"]),
                safe_str(row["author"]),
                "",
                content,
            ),
        )
        counts["thread_replies"] += 1

    conn.commit()
    conn.close()

    # 件数サマリー表示
    print(
        f"Indexed: {counts['commands']} commands, {counts['subtasks']} subtasks, "
        f"{counts['reports']} reports, {counts['dashboard_entries']} dashboard entries, "
        f"{counts['diary_entries']} diary entries, {counts['thread_replies']} thread replies"
    )


# ─────────────────────────────────────────────────────────────
# CLI エントリーポイント
# ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="没日録DB内にFTS5 search_indexテーブルを作成・全データ投入する"
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"没日録DBパス (デフォルト: {DEFAULT_DB})",
    )
    args = parser.parse_args()
    migrate(args.db)


if __name__ == "__main__":
    main()
