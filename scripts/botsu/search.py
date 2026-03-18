"""botsu.search — 没日録DB FTS5全文検索サブコマンド (subtask_915/cmd_419 W2-a)

tools/kousatsu/main.py GET /search, GET /search/similar のロジックをCLI化。
Docker不要で没日録DB内のsearch_index FTS5テーブルを直接検索する。

参照:
  - tools/kousatsu/main.py : GET /search, GET /search/similar エンドポイント（ロジック移植元）
  - docs/shogun/2ch_integration_design.md 付録B : CLI置換対応表
"""

from __future__ import annotations

import re as _re
import sys

from botsu import get_connection

# MeCab はオプション。未インストール時はraw textで検索
try:
    import MeCab
    _MECAB_AVAILABLE = True
except ImportError:
    _MECAB_AVAILABLE = False

# MeCab品詞フィルタ (build_index.py / migrate_fts5.py と同一)
_ALLOWED_POS = {"名詞", "動詞", "形容詞"}

_SNIPPET_WIDTH = 80   # 表示最大幅
_SNIPPET_TOKENS = 32  # FTS5 snippet() トークン数


# ---------------------------------------------------------------------------
# Tokenizer (main.py tokenize() 移植)
# ---------------------------------------------------------------------------

def _create_tagger():
    if not _MECAB_AVAILABLE:
        return None
    try:
        return MeCab.Tagger()
    except Exception:
        return None


_tagger = None  # モジュールレベルでシングルトン化


def _tokenize(text: str) -> str:
    """MeCabで分かち書き。MeCab未インストール時はそのまま返す。"""
    global _tagger
    if not text:
        return ""
    if not _MECAB_AVAILABLE:
        return text
    if _tagger is None:
        _tagger = _create_tagger()
    if _tagger is None:
        return text
    try:
        tokens = []
        node = _tagger.parseToNode(text)
        while node:
            features = node.feature.split(",")
            if features[0] in _ALLOWED_POS:
                surface = node.surface.strip()
                if surface:
                    tokens.append(surface)
            node = node.next
        result = " ".join(tokens)
        return result if result.strip() else text
    except Exception:
        return text


def _build_match_query(query: str) -> str:
    """FTS5 MATCH用クエリ文字列を構築する。

    main.py と同一ロジック:
    各トークンをダブルクォートで囲み、FTS5演算子(ハイフン/コロン等)の誤解釈を防ぐ。
    """
    tokenized = _tokenize(query)
    tokens = tokenized.split()
    if not tokens:
        return f'"{query}"'
    return " ".join(f'"{t}"' for t in tokens if t.strip())


# ---------------------------------------------------------------------------
# Search function
# ---------------------------------------------------------------------------

def search(args) -> None:
    """FTS5全文検索を実行してテーブル表示する。

    --similar SUBTASK_ID が指定された場合は search_similar() にディスパッチ。

    Args:
        args: argparse.Namespace
            - query   : 検索クエリ文字列 (--similar 指定時は不要)
            - similar : 基準subtask ID (省略可)
            - limit   : 最大返却件数 (デフォルト20)
            - project : projectフィールドで絞り込み (省略可)
    """
    if getattr(args, "similar", None):
        search_similar(args)
        return

    query: str = args.query
    limit: int = args.limit
    project: str | None = args.project

    if not query.strip():
        print("Error: 検索クエリが空です。", file=sys.stderr)
        sys.exit(1)

    match_query = _build_match_query(query)

    conn = get_connection()
    try:
        # search_index 存在チェック
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'"
        ).fetchone()
        if not exists:
            print(
                "Error: search_index テーブルが見つかりません。\n"
                "  python3 scripts/migrate_fts5.py を先に実行してください。",
                file=sys.stderr,
            )
            sys.exit(1)

        # project絞り込みがある場合はWHERE句を追加
        if project:
            sql = """
                SELECT
                    source_type,
                    source_id,
                    parent_id,
                    project,
                    worker_id,
                    status,
                    snippet(search_index, 6, '', '', '...', ?) AS snip,
                    rank
                FROM search_index
                WHERE search_index MATCH ?
                  AND project = ?
                ORDER BY rank
                LIMIT ?
            """
            params = (_SNIPPET_TOKENS, match_query, project, limit)
            count_sql = (
                "SELECT COUNT(*) FROM search_index"
                " WHERE search_index MATCH ? AND project = ?"
            )
            count_params = (match_query, project)
        else:
            sql = """
                SELECT
                    source_type,
                    source_id,
                    parent_id,
                    project,
                    worker_id,
                    status,
                    snippet(search_index, 6, '', '', '...', ?) AS snip,
                    rank
                FROM search_index
                WHERE search_index MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            params = (_SNIPPET_TOKENS, match_query, limit)
            count_sql = (
                "SELECT COUNT(*) FROM search_index WHERE search_index MATCH ?"
            )
            count_params = (match_query,)

        rows = conn.execute(sql, params).fetchall()
        total = conn.execute(count_sql, count_params).fetchone()[0]

    except Exception as exc:
        print(f"Error: 検索失敗: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    # ── 表示 ─────────────────────────────────────────────────────
    tokenized = _tokenize(query)
    print(f"Query: {query}")
    if tokenized != query:
        print(f"Tokenized: {tokenized}")
    if project:
        print(f"Project: {project}")
    print(f"Total hits: {total}  (showing {min(len(rows), limit)})")
    print()

    if not rows:
        print("(結果なし)")
        return

    # ヘッダー
    TYPE_W  = 10
    ID_W    = 16
    PROJ_W  = 14
    STATUS_W = 12
    SNIP_W  = _SNIPPET_WIDTH

    header = (
        f"{'TYPE':<{TYPE_W}}  {'ID':<{ID_W}}  {'PROJECT':<{PROJ_W}}  "
        f"{'STATUS':<{STATUS_W}}  SNIPPET"
    )
    sep = (
        f"{'-'*TYPE_W}  {'-'*ID_W}  {'-'*PROJ_W}  "
        f"{'-'*STATUS_W}  {'-'*SNIP_W}"
    )
    print(header)
    print(sep)

    for row in rows:
        snip = (row["snip"] or "").replace("\n", " ").strip()
        if len(snip) > SNIP_W:
            snip = snip[:SNIP_W - 1] + "…"

        src_type  = (row["source_type"] or "")[:TYPE_W]
        src_id    = (row["source_id"]   or "")[:ID_W]
        proj      = (row["project"]     or "")[:PROJ_W]
        status    = (row["status"]      or "")[:STATUS_W]

        print(
            f"{src_type:<{TYPE_W}}  {src_id:<{ID_W}}  {proj:<{PROJ_W}}  "
            f"{status:<{STATUS_W}}  {snip}"
        )


# ---------------------------------------------------------------------------
# Keyword extraction helper (search_similar / check_coverage 共通)
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    "の", "は", "が", "を", "に", "へ", "で", "と", "も",
    "から", "より", "など", "この", "その", "あの", "これ", "それ",
    "する", "ある", "いる", "なる", "れる", "られる",
})


def _extract_keywords(text: str, max_kw: int = 20) -> list[str]:
    """キーワード抽出。MeCab名詞抽出を試みる。未インストール時は単語分割で代替。

    main.py の extract_nouns() 相当。
    """
    if not text:
        return []

    # MeCab名詞抽出（辞書がある場合のみ動作）
    global _tagger
    if _MECAB_AVAILABLE:
        if _tagger is None:
            _tagger = _create_tagger()
        if _tagger is not None:
            try:
                node = _tagger.parseToNode(text)
                nouns: list[str] = []
                seen_n: set[str] = set()
                while node:
                    features = node.feature.split(",")
                    surface = node.surface.strip()
                    if features[0] == "名詞" and surface and len(surface) >= 2 and surface not in seen_n:
                        seen_n.add(surface)
                        nouns.append(surface)
                    node = node.next
                if nouns:
                    return nouns[:max_kw]
            except Exception:
                pass

    # Fallback: 記号/空白で分割 → 短語・ストップワードを除去
    tokens = _re.split(r'[\s\u3000\n\r\t、。，．・:：/\\|「」【】（）\[\]{}()\-_+=]+', text)
    seen_t: set[str] = set()
    result: list[str] = []
    for t in tokens:
        t = t.strip()
        if len(t) >= 2 and t not in seen_t and t not in _STOP_WORDS:
            seen_t.add(t)
            result.append(t)
    return result[:max_kw]


# ---------------------------------------------------------------------------
# search --similar SUBTASK_ID  (main.py GET /search/similar 移植)
# ---------------------------------------------------------------------------

def search_similar(args) -> None:
    """指定subtaskのdescriptionを元にFTS5で類似タスクを検索する。

    Args:
        args: argparse.Namespace
            - similar : 基準subtask ID
            - limit   : 最大返却件数 (デフォルト5)
    """
    subtask_id: str = args.similar
    limit: int = getattr(args, "limit", 5)

    conn = get_connection()
    try:
        # 1. subtask description取得
        row = conn.execute(
            "SELECT description FROM subtasks WHERE id = ?",
            (subtask_id,),
        ).fetchone()
        if row is None:
            print(f"Error: subtask '{subtask_id}' が見つかりません。", file=sys.stderr)
            sys.exit(1)
        description = row["description"] or ""

        # 2. search_index 存在チェック
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'"
        ).fetchone()
        if not exists:
            print(
                "Error: search_index テーブルが見つかりません。\n"
                "  python3 scripts/migrate_fts5.py を先に実行してください。",
                file=sys.stderr,
            )
            sys.exit(1)

        # 3. キーワード抽出 + FTS5 OR検索
        keywords = _extract_keywords(description, max_kw=20)
        if not keywords:
            print(f"Similar to: {subtask_id}")
            print("(キーワード抽出結果なし — descriptionが空の可能性)")
            return

        match_query = " OR ".join(f'"{kw}"' for kw in keywords)
        rows = conn.execute(
            """
            SELECT
                source_type, source_id, parent_id, project,
                worker_id, status,
                snippet(search_index, 6, '', '', '...', 32) AS snippet,
                rank
            FROM search_index
            WHERE search_index MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_query, limit + 10),  # 自身除外分を余分に取得
        ).fetchall()

        # 4. 自身除外 + audit_status付与 + 件数制限
        results: list[dict] = []
        for r in rows:
            if r["source_id"] == subtask_id:
                continue
            if len(results) >= limit:
                break
            item: dict = {
                "source_type": r["source_type"],
                "source_id":   r["source_id"],
                "parent_id":   r["parent_id"],
                "project":     r["project"],
                "worker_id":   r["worker_id"],
                "status":      r["status"],
                "snippet":     r["snippet"],
            }
            if r["source_type"] == "subtask":
                audit_row = conn.execute(
                    "SELECT audit_status FROM subtasks WHERE id = ?",
                    (r["source_id"],),
                ).fetchone()
                item["audit_status"] = audit_row["audit_status"] if audit_row else None
            results.append(item)

    except Exception as exc:
        print(f"Error: 検索失敗: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    # ── 表示 ─────────────────────────────────────────────────────
    kw_display = ", ".join(keywords[:8]) + ("..." if len(keywords) > 8 else "")
    print(f"Similar to: {subtask_id}")
    print(f"Keywords({len(keywords)}): {kw_display}")
    print(f"Results: {len(results)}")
    print()

    if not results:
        print("(結果なし)")
        return

    TYPE_W = 10; ID_W = 16; PROJ_W = 14; STATUS_W = 12; SNIP_W = 55
    print(
        f"{'TYPE':<{TYPE_W}}  {'ID':<{ID_W}}  {'PROJECT':<{PROJ_W}}  "
        f"{'STATUS':<{STATUS_W}}  SNIPPET"
    )
    print(
        f"{'-'*TYPE_W}  {'-'*ID_W}  {'-'*PROJ_W}  "
        f"{'-'*STATUS_W}  {'-'*SNIP_W}"
    )
    for item in results:
        snip = (item.get("snippet") or "").replace("\n", " ").strip()
        if len(snip) > SNIP_W:
            snip = snip[:SNIP_W - 1] + "…"
        audit_tag = f" [{item['audit_status']}]" if item.get("audit_status") else ""
        print(
            f"{(item['source_type'] or ''):<{TYPE_W}}  "
            f"{(item['source_id']   or ''):<{ID_W}}  "
            f"{(item.get('project') or ''):<{PROJ_W}}  "
            f"{(item.get('status')  or ''):<{STATUS_W}}  "
            f"{snip}{audit_tag}"
        )
