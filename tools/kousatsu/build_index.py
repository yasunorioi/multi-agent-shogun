"""没日録FTS5インデックスビルダー

没日録DB（botsunichiroku.db）からテキストデータを読み取り、
MeCabで形態素解析後、FTS5仮想テーブルに投入する。
コンテナ起動時に毎回再構築（冪等）。
"""

import os
import sqlite3
import sys

import MeCab


SOURCE_DB = os.environ.get("BOTSUNICHIROKU_DB", "/data/botsunichiroku.db")
INDEX_DB = os.environ.get("INDEX_DB", "/data/search_index.db")

# MeCab品詞フィルタ: 名詞・動詞・形容詞のみ抽出
ALLOWED_POS = {"名詞", "動詞", "形容詞"}

# ★ FTS5スキーマ契約（部屋子2号の main.py と共有）
FTS5_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    source_type,
    source_id,
    parent_id,
    project,
    worker_id,
    status,
    content
);
"""


def create_tagger() -> MeCab.Tagger:
    """MeCab Taggerを生成する。"""
    return MeCab.Tagger()


def tokenize(tagger: MeCab.Tagger, text: str) -> str:
    """テキストをMeCabで分かち書きし、名詞・動詞・形容詞のみ抽出する。

    Returns:
        スペース区切りの分かち書き文字列
    """
    if not text:
        return ""
    tokens = []
    node = tagger.parseToNode(text)
    while node:
        features = node.feature.split(",")
        if features[0] in ALLOWED_POS:
            surface = node.surface.strip()
            if surface:
                tokens.append(surface)
        node = node.next
    return " ".join(tokens)


def safe_str(value) -> str:
    """NoneやNULL値を空文字列に変換する。"""
    if value is None:
        return ""
    return str(value)


def build_index() -> None:
    """没日録DBからFTS5インデックスを構築する。"""

    # 没日録DB存在チェック
    if not os.path.exists(SOURCE_DB):
        print(f"ERROR: 没日録DB が見つかりません: {SOURCE_DB}", file=sys.stderr)
        sys.exit(1)

    tagger = create_tagger()

    # 没日録DB（読み取り専用）
    src = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    # 検索インデックスDB（毎回再構築）
    if os.path.exists(INDEX_DB):
        os.remove(INDEX_DB)
    idx = sqlite3.connect(INDEX_DB)
    idx.execute(FTS5_CREATE)

    counts = {"command": 0, "subtask": 0, "report": 0, "dashboard": 0}

    # --- commands ---
    for row in src.execute("SELECT id, command, project, status, details FROM commands"):
        raw_text = " ".join(filter(None, [safe_str(row["command"]), safe_str(row["details"])]))
        content = tokenize(tagger, raw_text)
        idx.execute(
            "INSERT INTO search_index (source_type, source_id, parent_id, project, worker_id, status, content) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("command", row["id"], "", safe_str(row["project"]), "", safe_str(row["status"]), content),
        )
        counts["command"] += 1

    # --- subtasks ---
    for row in src.execute(
        "SELECT id, parent_cmd, worker_id, project, description, status, notes FROM subtasks"
    ):
        raw_text = " ".join(
            filter(None, [safe_str(row["description"]), safe_str(row["notes"])])
        )
        content = tokenize(tagger, raw_text)
        idx.execute(
            "INSERT INTO search_index (source_type, source_id, parent_id, project, worker_id, status, content) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "subtask",
                row["id"],
                safe_str(row["parent_cmd"]),
                safe_str(row["project"]),
                safe_str(row["worker_id"]),
                safe_str(row["status"]),
                content,
            ),
        )
        counts["subtask"] += 1

    # --- reports ---
    for row in src.execute(
        "SELECT id, worker_id, task_id, status, summary, findings, notes FROM reports"
    ):
        raw_text = " ".join(
            filter(None, [safe_str(row["summary"]), safe_str(row["findings"]), safe_str(row["notes"])])
        )
        content = tokenize(tagger, raw_text)
        idx.execute(
            "INSERT INTO search_index (source_type, source_id, parent_id, project, worker_id, status, content) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
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
        counts["report"] += 1

    # --- dashboard_entries ---
    # テーブル存在チェック付き（古いDBでもクラッシュしない）
    try:
        dashboard_rows = src.execute(
            "SELECT id, cmd_id, section, content, status, tags FROM dashboard_entries"
        ).fetchall()
    except sqlite3.OperationalError:
        dashboard_rows = []

    for row in dashboard_rows:
        content = tokenize(tagger, safe_str(row["content"]))
        idx.execute(
            "INSERT INTO search_index (source_type, source_id, parent_id, project, worker_id, status, content) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "dashboard",
                str(row["id"]),
                safe_str(row["cmd_id"]),   # parent_id = cmd_id
                "",                         # project = ""
                safe_str(row["tags"]),      # worker_id フィールドにtagsを格納
                safe_str(row["status"]),
                content,
            ),
        )
        counts["dashboard"] += 1

    idx.commit()
    idx.close()
    src.close()

    print(
        f"Indexed: {counts['command']} commands, {counts['subtask']} subtasks, "
        f"{counts['report']} reports, {counts['dashboard']} dashboard entries"
    )


if __name__ == "__main__":
    build_index()
