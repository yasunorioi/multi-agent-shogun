"""botsu.search — 没日録DB FTS5全文検索サブコマンド (subtask_915/cmd_419 W2-a)
                + enrichサブコマンド (subtask_919/cmd_419 W3-c)

tools/kousatsu/main.py GET /search, GET /search/similar, POST /enrich のロジックをCLI化。
Docker不要で没日録DB内のsearch_index FTS5テーブルを直接検索する。

参照:
  - tools/kousatsu/main.py : GET /search, GET /search/similar, POST /enrich（ロジック移植元）
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


# ---------------------------------------------------------------------------
# enrich  (main.py POST /enrich 移植 — subtask_919/cmd_419 W3-c)
# ---------------------------------------------------------------------------

_PITFALL_PATTERNS = [
    ("P001", "%コミット漏れ%",    "high",     "commit忘れ",        "inbox descriptionに「git add+commit+push」を明記"),
    ("P001", "%git add%",          "high",     "commit忘れ",        "inbox descriptionに「git add+commit+push」を明記"),
    ("P002", "%ハルシネーション%", "critical", "ハルシネーション",  "成果物の実在確認（git ls-remote, ls -la）を必須化"),
    ("P002", "%捏造%",             "critical", "捏造",              "成果物の実在確認を必須化"),
    ("P003", "%マージ%",           "medium",   "マージ問題",        "ブランチ分岐状況を事前確認"),
    ("P004", "%差し戻%",           "medium",   "差し戻し",          "直近の差し戻し理由を確認"),
]


def _enrich_extract_pitfalls(conn, worker_id: str | None) -> list[dict]:
    """没日録DBから失敗パターンを抽出する（main.py _extract_pitfalls 移植）。"""
    pitfalls: list[dict] = []
    seen_ids: set[str] = set()
    for pid, like_pat, severity, desc_label, prevention in _PITFALL_PATTERNS:
        rows = conn.execute(
            """
            SELECT s.id, substr(s.description, 1, 100) AS description,
                   r.summary AS report_summary
            FROM subtasks s
            LEFT JOIN reports r ON r.task_id = s.id
            WHERE (r.summary LIKE ? OR s.description LIKE ?)
              AND s.status IN ('blocked', 'cancelled', 'done')
            ORDER BY s.completed_at DESC LIMIT 3
            """,
            (like_pat, like_pat),
        ).fetchall()
        for row in rows:
            if row["id"] in seen_ids:
                continue
            seen_ids.add(row["id"])
            pitfalls.append({
                "pattern_id": pid,
                "source_id":  row["id"],
                "severity":   severity,
                "description": f"{desc_label}: {row['description']}",
                "prevention": prevention,
            })

    # P005: worker別の失敗パターン
    if worker_id:
        rows = conn.execute(
            """
            SELECT s.id, substr(s.description, 1, 100) AS description
            FROM subtasks s
            WHERE s.worker_id = ? AND s.status IN ('blocked', 'cancelled')
            ORDER BY s.completed_at DESC LIMIT 3
            """,
            (worker_id,),
        ).fetchall()
        for row in rows:
            if row["id"] not in seen_ids:
                pitfalls.append({
                    "pattern_id": "P005",
                    "source_id":  row["id"],
                    "severity":   "medium",
                    "description": f"{worker_id}の過去失敗: {row['description']}",
                    "prevention": f"{worker_id}に割り当て時は過去の失敗パターンに注意",
                })

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    pitfalls.sort(key=lambda x: order.get(x["severity"], 4))
    return pitfalls


def _enrich_extract_positive(conn, keywords: list[str]) -> list[dict]:
    """audit PASS済みの成功パターンを抽出する（main.py _extract_positive_patterns 移植）。"""
    if not keywords:
        return []
    results: list[dict] = []
    seen: set[str] = set()
    for kw in keywords[:5]:
        rows = conn.execute(
            """
            SELECT s.id, s.project, s.worker_id,
                   substr(s.description, 1, 120) AS description,
                   r.summary AS report_summary
            FROM subtasks s
            JOIN reports r ON r.task_id = s.id AND r.status = 'done'
            WHERE s.audit_status = 'done'
              AND (s.description LIKE '%' || ? || '%'
                   OR r.summary LIKE '%' || ? || '%')
            ORDER BY s.completed_at DESC LIMIT 3
            """,
            (kw, kw),
        ).fetchall()
        for row in rows:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            results.append({
                "source_id":   row["id"],
                "project":     row["project"] or "",
                "description": f"{row['description']} → audit PASS",
                "strength":    "high" if len(rows) >= 3 else "medium",
                "hint":        "この方向を継続せよ",
            })
    return results


def enrich_data(cmd_id: str, worker_id: str | None = None) -> dict:
    """cmd_idに対してenrichデータを生成して返す（main.py POST /enrich 相当）。

    Stage1: 同PJ内FTS5検索（局所）
    Stage2: 全PJ横断FTS5検索（拡大）
    Stage2b: pitfalls抽出
    Stage2c: positive_patterns抽出
    Stage3: 外部検索 — TODO: 未実装（Docker不要CLI版ではスキップ）
    """
    conn = get_connection()
    try:
        # 対象コマンド取得
        cmd_row = conn.execute(
            "SELECT command, details, project FROM commands WHERE id = ?",
            (cmd_id,),
        ).fetchone()
        if cmd_row is None:
            return {"error": f"command '{cmd_id}' not found"}

        project = cmd_row["project"] or None
        raw_text = f"{cmd_row['command'] or ''} {cmd_row['details'] or ''}".strip()
        keywords = _extract_keywords(raw_text, max_kw=15)

        # search_index存在チェック
        has_fts = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'"
        ).fetchone() is not None

        # Stage1: 同PJ内FTS5検索
        local_results: list[dict] = []
        global_results: list[dict] = []
        if has_fts and keywords:
            match_query = " OR ".join(f'"{kw}"' for kw in keywords)
            if project:
                rows = conn.execute(
                    """
                    SELECT source_type, source_id, project, status,
                           snippet(search_index, 6, '...', '...', '', 32) AS snippet, rank
                    FROM search_index
                    WHERE search_index MATCH ? AND project = ?
                    ORDER BY rank LIMIT 10
                    """,
                    (match_query, project),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT source_type, source_id, project, status,
                           snippet(search_index, 6, '...', '...', '', 32) AS snippet, rank
                    FROM search_index
                    WHERE search_index MATCH ?
                    ORDER BY rank LIMIT 10
                    """,
                    (match_query,),
                ).fetchall()
            local_ids: set[str] = set()
            for row in rows:
                if row["source_id"] == cmd_id:
                    continue
                local_ids.add(row["source_id"])
                local_results.append({
                    "source_type": row["source_type"],
                    "source_id":   row["source_id"],
                    "project":     row["project"],
                    "status":      row["status"],
                    "snippet":     row["snippet"],
                    "stage":       "local",
                })

            # Stage2: クロスプロジェクトFTS5検索
            if project:
                rows2 = conn.execute(
                    """
                    SELECT source_type, source_id, project, status,
                           snippet(search_index, 6, '...', '...', '', 32) AS snippet, rank
                    FROM search_index
                    WHERE search_index MATCH ? AND project != ?
                    ORDER BY rank LIMIT 10
                    """,
                    (match_query, project),
                ).fetchall()
                for row in rows2:
                    if row["source_id"] == cmd_id or row["source_id"] in local_ids:
                        continue
                    global_results.append({
                        "source_type": row["source_type"],
                        "source_id":   row["source_id"],
                        "project":     row["project"],
                        "status":      row["status"],
                        "snippet":     row["snippet"],
                        "stage":       "global",
                        "hint":        f"{row['project']}プロジェクトの類似タスク",
                    })

        # Stage2b: pitfalls
        pitfalls = _enrich_extract_pitfalls(conn, worker_id)

        # Stage2c: positive_patterns
        positive = _enrich_extract_positive(conn, keywords)

        # Stage3: 外部検索 — TODO: 未実装（Docker不要CLI版ではスキップ）

    finally:
        conn.close()

    return {
        "cmd_id":           cmd_id,
        "project":          project,
        "keywords":         keywords,
        "internal":         local_results[:10],
        "cross_project":    global_results[:5],
        "pitfalls":         pitfalls[:5],
        "positive_patterns": positive[:5],
        "meta": {
            "internal_hits":      len(local_results),
            "cross_project_hits": len(global_results),
            "pitfall_hits":       len(pitfalls),
            "positive_hits":      len(positive),
            "keywords":           keywords[:10],
            "fts5_available":     has_fts,
        },
    }


def enrich_cmd(args) -> None:
    """search --enrich CMD_ID のエントリポイント。

    Args:
        args: argparse.Namespace
            - enrich : cmd_id (str)
    """
    cmd_id: str = args.enrich

    data = enrich_data(cmd_id)

    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        sys.exit(1)

    kw_str = ", ".join(data["keywords"][:10]) or "(なし)"
    print(f"Enrich: {cmd_id}  project={data['project'] or '-'}")
    print(f"Keywords: {kw_str}")
    print()

    # Internal
    internal = data["internal"]
    print(f"=== Internal hits ({len(internal)}) ===")
    if internal:
        TYPE_W = 10; ID_W = 16; PROJ_W = 14; STATUS_W = 12; SNIP_W = 50
        print(f"{'TYPE':<{TYPE_W}}  {'ID':<{ID_W}}  {'PROJECT':<{PROJ_W}}  {'STATUS':<{STATUS_W}}  SNIPPET")
        print(f"{'-'*TYPE_W}  {'-'*ID_W}  {'-'*PROJ_W}  {'-'*STATUS_W}  {'-'*SNIP_W}")
        for item in internal:
            snip = (item.get("snippet") or "").replace("\n", " ").strip()
            if len(snip) > SNIP_W:
                snip = snip[:SNIP_W - 1] + "…"
            print(
                f"{(item['source_type'] or '')[:TYPE_W]:<{TYPE_W}}  "
                f"{(item['source_id']   or '')[:ID_W]:<{ID_W}}  "
                f"{(item.get('project') or '')[:PROJ_W]:<{PROJ_W}}  "
                f"{(item.get('status')  or '')[:STATUS_W]:<{STATUS_W}}  {snip}"
            )
    else:
        print("  (なし)")
    print()

    # Cross-project
    cross = data["cross_project"]
    print(f"=== Cross-project hits ({len(cross)}) ===")
    if cross:
        for item in cross:
            snip = (item.get("snippet") or "").replace("\n", " ").strip()[:60]
            print(f"  [{item['project']}] {item['source_id']} ({item['source_type']})  {snip}")
    else:
        print("  (なし)")
    print()

    # Pitfalls
    pitfalls = data["pitfalls"]
    print(f"=== Pitfalls ({len(pitfalls)}) ===")
    if pitfalls:
        for p in pitfalls:
            print(f"  [{p['severity'].upper():8s}] {p['pattern_id']} {p['source_id']}")
            print(f"           {p['description']}")
            print(f"           → {p['prevention']}")
    else:
        print("  (なし)")
    print()

    # Positive patterns
    positive = data["positive_patterns"]
    print(f"=== Positive patterns ({len(positive)}) ===")
    if positive:
        for pp in positive:
            print(f"  [{pp['strength']:6s}] {pp['source_id']}  {pp['description'][:60]}")
    else:
        print("  (なし)")
