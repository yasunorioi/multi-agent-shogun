"""vec.py — sqlite-vec ベクトル検索モジュール。

FTS5の横にベクトルインデックスを追加し、RRFでハイブリッド検索を実現する。
sqlite-vec / sentence-transformers が未インストールの場合は graceful degradation。

使用方法（クラスインターフェース）:
    vs = VecSearch(db_path)
    conn = sqlite3.connect(db_path)
    vs.setup(conn)
    vs.upsert(conn, "subtask_001", "タスク内容", source_type="subtask")
    results = vs.search(conn, "検索クエリ")
    results = vs.hybrid_search(conn, "検索クエリ")
"""

from __future__ import annotations

import math
import sqlite3
import struct
from datetime import datetime

# ---------------------------------------------------------------------------
# 遅延ロード（モデルは検索/upsert時にのみロード）
# ---------------------------------------------------------------------------

_embed_model = None
_VEC_DIM = 768  # Ruri v3-310m actual dimension
MODEL_NAME = "cl-nagoya/ruri-v3-310m"


def _load_vec(conn: sqlite3.Connection) -> bool:
    """sqlite-vec拡張をロード。成功=True。"""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        return True
    except Exception:
        return False


def _get_embedding(text: str, mode: str = "passage") -> bytes | None:
    """テキストをRuri v3でベクトル化。モデルは遅延ロード。

    mode="passage" → "文章: " プレフィックス（upsert時）
    mode="query"   → "クエリ: " プレフィックス（検索時）
    """
    global _embed_model
    try:
        if _embed_model is None:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer(MODEL_NAME, device="cpu")
        prefix = "クエリ: " if mode == "query" else "文章: "
        vec = _embed_model.encode(prefix + text, normalize_embeddings=True)
        return struct.pack(f"{len(vec)}f", *vec)
    except Exception:
        return None


def freshness_score(created_at: str, half_life_days: float = 90.0) -> float:
    """文書の時間鮮度スコア。新しいほど1.0、古いほど0.0に近い。"""
    if not created_at:
        return 0.5
    try:
        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        age_days = (datetime.now(dt.tzinfo) - dt).days
        return math.exp(-age_days * math.log(2) / half_life_days)
    except Exception:
        return 0.5


# ---------------------------------------------------------------------------
# テーブル作成
# ---------------------------------------------------------------------------

def ensure_tables(conn: sqlite3.Connection) -> bool:
    """vec_index + vec_meta テーブルを作成。sqlite-vec未対応なら False。"""
    if not _load_vec(conn):
        return False
    conn.execute(f"""CREATE VIRTUAL TABLE IF NOT EXISTS vec_index
                     USING vec0(source_id TEXT PRIMARY KEY, embedding float[{_VEC_DIM}])""")
    conn.execute("""CREATE TABLE IF NOT EXISTS vec_meta (
                    source_id   TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    parent_id   TEXT,
                    project     TEXT,
                    created_at  TEXT,
                    model_name  TEXT DEFAULT 'cl-nagoya/ruri-v3-310m',
                    vectorized_at TEXT
                    )""")
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def vec_upsert(
    conn: sqlite3.Connection,
    source_id: str,
    source_type: str,
    raw_text: str,
    parent_id: str = "",
    project: str = "",
    created_at: str = "",
) -> bool:
    """ベクトルをupsert。成功=True。vec_indexが存在しなければ何もしない。"""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vec_meta'"
    ).fetchone()
    if not exists:
        return False

    embedding = _get_embedding(raw_text, mode="passage")
    if embedding is None:
        return False

    # vec_index upsert (DELETE + INSERT)
    conn.execute("DELETE FROM vec_index WHERE source_id = ?", (source_id,))
    conn.execute(
        "INSERT INTO vec_index (source_id, embedding) VALUES (?, ?)",
        (source_id, embedding),
    )

    # vec_meta upsert
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO vec_meta"
        " (source_id, source_type, parent_id, project, created_at, model_name, vectorized_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (source_id, source_type, parent_id, project, created_at, MODEL_NAME, now),
    )
    return True


# ---------------------------------------------------------------------------
# 検索
# ---------------------------------------------------------------------------

def vec_search(
    conn: sqlite3.Connection,
    query: str,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """ベクトル検索。[(source_id, distance), ...] を返す。"""
    query_vec = _get_embedding(query, mode="query")
    if query_vec is None:
        return []
    rows = conn.execute(
        "SELECT source_id, distance FROM vec_index"
        " WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (query_vec, top_n),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    top_n: int = 20,
    k: int = 60,
    fts_table: str = "search_index",
    source_type: str | None = None,
    project: str | None = None,
    freshness_weight: float = 0.0,
) -> list[dict]:
    """FTS5 + ベクトル検索のRRFハイブリッド検索。

    freshness_weight > 0 の場合、時間鮮度スコアをRRFに乗算して新しい文書を優先する。
    formula: final = rrf * (alpha + (1-alpha) * freshness)  alpha=0.3
    """
    pool = top_n * 3

    # 1. FTS5検索
    fts_sql = f"SELECT source_id, rank FROM {fts_table} WHERE content MATCH ? LIMIT ?"
    fts_results = conn.execute(fts_sql, (query, pool)).fetchall()

    # 2. ベクトル検索
    vec_results = vec_search(conn, query, top_n=pool)

    # 3. RRF統合
    scores: dict[str, float] = {}
    for rank, row in enumerate(fts_results):
        sid = row[0]
        scores[sid] = scores.get(sid, 0) + 1 / (k + rank + 1)
    for rank, (sid, _dist) in enumerate(vec_results):
        scores[sid] = scores.get(sid, 0) + 1 / (k + rank + 1)

    # 4. source_type / project フィルタ
    if source_type or project:
        placeholders = ",".join("?" * len(scores))
        meta_rows = conn.execute(
            f"SELECT source_id, source_type, project FROM vec_meta"
            f" WHERE source_id IN ({placeholders})",
            list(scores.keys()),
        ).fetchall()
        meta = {r[0]: (r[1], r[2]) for r in meta_rows}
        if source_type:
            scores = {s: v for s, v in scores.items()
                      if meta.get(s, ("", ""))[0] == source_type}
        if project:
            scores = {s: v for s, v in scores.items()
                      if meta.get(s, ("", ""))[1] == project}

    # 5. 鮮度スコア適用（freshness_weight > 0 の場合）
    if freshness_weight > 0.0 and scores:
        _alpha = 0.3
        _ids = list(scores.keys())
        _ph = ",".join("?" * len(_ids))
        _fresh_rows = conn.execute(
            f"SELECT source_id, created_at FROM vec_meta WHERE source_id IN ({_ph})",
            _ids,
        ).fetchall()
        _fresh_map = {r[0]: r[1] for r in _fresh_rows}
        scores = {
            sid: score * (_alpha + (1 - _alpha) * freshness_score(_fresh_map.get(sid, "")))
            for sid, score in scores.items()
        }

    # 6. Top-Nソート & コンテンツ取得
    ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_n]
    results = []
    for sid, score in ranked:
        row = conn.execute(
            "SELECT source_type, source_id, parent_id, project, worker_id, status, content"
            " FROM search_index WHERE source_id = ?",
            (sid,),
        ).fetchone()
        if row:
            results.append({
                "source_type": row[0],
                "source_id": row[1],
                "parent_id": row[2],
                "project": row[3],
                "worker_id": row[4],
                "status": row[5],
                "content": row[6],
                "hybrid_score": score,
            })
    return results


# ---------------------------------------------------------------------------
# VecSearch クラス（OOPインターフェース — agent-swarm等から利用）
# ---------------------------------------------------------------------------

class VecSearch:
    """sqlite-vec ベクトル検索クラス。

    没日録・agent-swarm 両DBで再利用可能な共通インターフェース。
    モデルは遅延ロード（__init__ではロードしない）。
    """

    def __init__(self, db_path: str, model_name: str = MODEL_NAME) -> None:
        self.db_path = db_path
        self.model_name = model_name
        self._model = None  # 遅延ロード

    def _embed(self, text: str, mode: str = "passage") -> bytes | None:
        """テキストをベクトル化。モデルは初回呼び出し時にロード。

        mode="passage" → "文章: " プレフィックス（upsert時）
        mode="query"   → "クエリ: " プレフィックス（検索時）
        """
        try:
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            prefix = "クエリ: " if mode == "query" else "文章: "
            vec = self._model.encode(prefix + text, normalize_embeddings=True)
            return struct.pack(f"{len(vec)}f", *vec)
        except Exception:
            return None

    def setup(self, conn: sqlite3.Connection) -> bool:
        """vec_index + vec_meta テーブルを作成。sqlite-vec未対応なら False。"""
        return ensure_tables(conn)

    def upsert(
        self,
        conn: sqlite3.Connection,
        source_id: str,
        text: str,
        source_type: str = "",
        parent_id: str = "",
        project: str = "",
        created_at: str = "",
        **_meta,
    ) -> bool:
        """ベクトルをupsert。成功=True。"""
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vec_meta'"
        ).fetchone():
            return False

        embedding = self._embed(text, mode="passage")
        if embedding is None:
            return False

        conn.execute("DELETE FROM vec_index WHERE source_id = ?", (source_id,))
        conn.execute(
            "INSERT INTO vec_index (source_id, embedding) VALUES (?, ?)",
            (source_id, embedding),
        )
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO vec_meta"
            " (source_id, source_type, parent_id, project, created_at, model_name, vectorized_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (source_id, source_type, parent_id, project, created_at, self.model_name, now),
        )
        return True

    def search(
        self,
        conn: sqlite3.Connection,
        query: str,
        top_n: int = 20,
    ) -> list[tuple[str, float]]:
        """ベクトル類似検索。[(source_id, distance), ...] を返す。"""
        query_vec = self._embed(query, mode="query")
        if query_vec is None:
            return []
        rows = conn.execute(
            "SELECT source_id, distance FROM vec_index"
            " WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (query_vec, top_n),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def hybrid_search(
        self,
        conn: sqlite3.Connection,
        query: str,
        top_n: int = 20,
        fts_table: str = "search_index",
        k: int = 60,
        source_type: str | None = None,
        project: str | None = None,
        freshness_weight: float = 0.0,
    ) -> list[dict]:
        """FTS5 + ベクトル検索のRRF統合。モジュール関数に委譲。"""
        return hybrid_search(
            conn, query,
            top_n=top_n, k=k, fts_table=fts_table,
            source_type=source_type, project=project,
            freshness_weight=freshness_weight,
        )
