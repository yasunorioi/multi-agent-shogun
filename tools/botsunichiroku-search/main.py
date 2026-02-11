"""没日録検索エンジン - FastAPI検索API

FTS5インデックスDBおよび没日録DB（読み取り専用）に対して
全文検索・矛盾検出・カバレッジチェックを提供する。
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import MeCab
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="没日録検索エンジン", version="1.0.0")

# --- 環境変数 ---
BOTSUNICHIROKU_DB = os.environ.get("BOTSUNICHIROKU_DB", "/data/botsunichiroku.db")
INDEX_DB = os.environ.get("INDEX_DB", "/data/search_index.db")

# --- MeCab シングルトン ---
_mecab_wakati: MeCab.Tagger | None = None
_mecab_default: MeCab.Tagger | None = None


def get_mecab_wakati() -> MeCab.Tagger:
    global _mecab_wakati
    if _mecab_wakati is None:
        _mecab_wakati = MeCab.Tagger("-Owakati")
    return _mecab_wakati


def get_mecab_default() -> MeCab.Tagger:
    global _mecab_default
    if _mecab_default is None:
        _mecab_default = MeCab.Tagger()
    return _mecab_default


def tokenize(text: str) -> str:
    """MeCab分かち書き。空白区切りのトークン列を返す。"""
    tagger = get_mecab_wakati()
    return tagger.parse(text).strip()


def extract_nouns(text: str) -> list[str]:
    """MeCabで名詞のみ抽出。カバレッジチェック用。"""
    tagger = get_mecab_default()
    node = tagger.parseToNode(text)
    nouns = []
    while node:
        features = node.feature.split(",")
        if features[0] == "名詞" and node.surface:
            surface = node.surface.strip()
            if len(surface) >= 2:
                nouns.append(surface)
        node = node.next
    return list(dict.fromkeys(nouns))


def get_index_db() -> sqlite3.Connection:
    """FTS5インデックスDBへの読み取り専用接続を返す。"""
    db_path = Path(INDEX_DB)
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="search_index.db not found")
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_botsunichiroku_db() -> sqlite3.Connection:
    """没日録DBへの読み取り専用接続を返す。"""
    db_path = Path(BOTSUNICHIROKU_DB)
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="botsunichiroku.db not found")
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# 1. GET /search - 全文検索
# ============================================================
@app.get("/search")
def search(
    q: str = Query(..., min_length=1, description="検索クエリ"),
    limit: int = Query(10, ge=1, le=50, description="返却件数"),
):
    tokenized = tokenize(q)
    if not tokenized.strip():
        raise HTTPException(status_code=400, detail="Empty query after tokenization")

    # FTS5 MATCH用: 各トークンをダブルクォートで囲みOR結合しない
    # スペース区切りはFTS5で暗黙AND扱い
    match_query = tokenized

    conn = get_index_db()
    try:
        cur = conn.execute(
            """
            SELECT
                source_type,
                source_id,
                parent_id,
                project,
                worker_id,
                status,
                snippet(search_index, 6, '...', '...', '', 32) AS snippet,
                rank
            FROM search_index
            WHERE search_index MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_query, limit),
        )
        rows = cur.fetchall()

        # 全件数取得
        count_cur = conn.execute(
            "SELECT COUNT(*) FROM search_index WHERE search_index MATCH ?",
            (match_query,),
        )
        total_hits = count_cur.fetchone()[0]

        results = []
        for i, row in enumerate(rows, 1):
            results.append(
                {
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                    "parent_id": row["parent_id"],
                    "project": row["project"],
                    "worker_id": row["worker_id"],
                    "status": row["status"],
                    "snippet": row["snippet"],
                    "rank": i,
                    "score": row["rank"],
                }
            )

        return {
            "query": q,
            "tokenized_query": tokenized,
            "total_hits": total_hits,
            "results": results,
        }
    finally:
        conn.close()


# ============================================================
# 2. GET /check/orphans - 矛盾・放置検出
# ============================================================
@app.get("/check/orphans")
def check_orphans():
    conn = get_botsunichiroku_db()
    try:
        checks = []

        # (a) subtask全doneなのにcmdがpendingのまま
        cur_a = conn.execute(
            """
            SELECT c.id AS cmd_id, c.status,
                   COUNT(s.id) AS subtask_count
            FROM commands c
            JOIN subtasks s ON s.parent_cmd = c.id
            WHERE c.status != 'done'
            GROUP BY c.id
            HAVING COUNT(s.id) > 0
               AND COUNT(s.id) = SUM(CASE WHEN s.status = 'done' THEN 1 ELSE 0 END)
            """
        )
        items_a = [
            {"cmd_id": r["cmd_id"], "status": r["status"], "subtask_count": r["subtask_count"]}
            for r in cur_a.fetchall()
        ]
        checks.append(
            {
                "check_type": "cmd_all_subtasks_done_but_pending",
                "description": "全subtaskがdoneだがcmdがpendingのまま",
                "count": len(items_a),
                "items": items_a,
            }
        )

        # (b) 7日以上pendingのまま放置されているcmd
        cur_b = conn.execute(
            """
            SELECT id AS cmd_id, status, created_at
            FROM commands
            WHERE status = 'pending'
              AND created_at <= datetime('now', '-7 days')
            """
        )
        items_b = [
            {"cmd_id": r["cmd_id"], "status": r["status"], "created_at": r["created_at"]}
            for r in cur_b.fetchall()
        ]
        checks.append(
            {
                "check_type": "cmd_pending_over_7_days",
                "description": "7日以上pendingのまま放置されているcmd",
                "count": len(items_b),
                "items": items_b,
            }
        )

        # (c) 7日以上assignedのまま放置されているsubtask
        cur_c = conn.execute(
            """
            SELECT id AS subtask_id, parent_cmd, worker_id, assigned_at
            FROM subtasks
            WHERE status = 'assigned'
              AND assigned_at <= datetime('now', '-7 days')
            """
        )
        items_c = [
            {
                "subtask_id": r["subtask_id"],
                "parent_cmd": r["parent_cmd"],
                "worker_id": r["worker_id"],
                "assigned_at": r["assigned_at"],
            }
            for r in cur_c.fetchall()
        ]
        checks.append(
            {
                "check_type": "subtask_assigned_over_7_days",
                "description": "7日以上assignedのまま放置されているsubtask",
                "count": len(items_c),
                "items": items_c,
            }
        )

        # (d) subtaskがdoneなのにreportが1件もない
        cur_d = conn.execute(
            """
            SELECT s.id AS subtask_id, s.parent_cmd, s.worker_id
            FROM subtasks s
            LEFT JOIN reports r ON r.task_id = s.id
            WHERE s.status = 'done'
              AND r.id IS NULL
            """
        )
        items_d = [
            {
                "subtask_id": r["subtask_id"],
                "parent_cmd": r["parent_cmd"],
                "worker_id": r["worker_id"],
            }
            for r in cur_d.fetchall()
        ]
        checks.append(
            {
                "check_type": "subtask_done_without_report",
                "description": "subtaskがdoneなのにreportが1件もない",
                "count": len(items_d),
                "items": items_d,
            }
        )

        total_issues = sum(c["count"] for c in checks)

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "checks": checks,
            "total_issues": total_issues,
        }
    finally:
        conn.close()


# ============================================================
# 3. GET /check/coverage - カバレッジチェック
# ============================================================
@app.get("/check/coverage")
def check_coverage(
    cmd_id: str = Query(..., description="対象コマンドID（例: cmd_145）"),
):
    conn = get_botsunichiroku_db()
    try:
        # 1. commandsテーブルからcmd_idの command + details を取得
        cmd_row = conn.execute(
            "SELECT command, details FROM commands WHERE id = ?",
            (cmd_id,),
        ).fetchone()
        if cmd_row is None:
            raise HTTPException(status_code=404, detail=f"Command {cmd_id} not found")

        instruction_text = " ".join(
            part for part in [cmd_row["command"], cmd_row["details"]] if part
        )

        # 2. MeCabで名詞を抽出（指示文のキーワード集合）
        instruction_keywords = extract_nouns(instruction_text)

        # 3. 該当cmdの全subtaskの全reportのsummaryを取得
        report_rows = conn.execute(
            """
            SELECT r.summary
            FROM reports r
            JOIN subtasks s ON r.task_id = s.id
            WHERE s.parent_cmd = ?
              AND r.summary IS NOT NULL
            """,
            (cmd_id,),
        ).fetchall()

        subtask_count = conn.execute(
            "SELECT COUNT(*) FROM subtasks WHERE parent_cmd = ?",
            (cmd_id,),
        ).fetchone()[0]

        report_count = len(report_rows)

        # 4. MeCabで名詞を抽出（報告文のキーワード集合）
        report_text = " ".join(r["summary"] for r in report_rows if r["summary"])
        report_keywords = extract_nouns(report_text) if report_text.strip() else []

        # 5. 指示文にあって報告文にないキーワード = 言及漏れ候補
        report_kw_set = set(report_keywords)
        missing_keywords = [kw for kw in instruction_keywords if kw not in report_kw_set]

        coverage_ratio = 0.0
        if instruction_keywords:
            covered = len(instruction_keywords) - len(missing_keywords)
            coverage_ratio = round(covered / len(instruction_keywords), 2)

        return {
            "cmd_id": cmd_id,
            "instruction_keywords": instruction_keywords,
            "report_keywords": report_keywords,
            "missing_keywords": missing_keywords,
            "coverage_ratio": coverage_ratio,
            "subtask_count": subtask_count,
            "report_count": report_count,
        }
    finally:
        conn.close()


# ============================================================
# 4. GET /search/similar - 類似タスク自動検索
# ============================================================
@app.get("/search/similar")
def search_similar(
    subtask_id: str = Query(..., description="基準subtask ID"),
    limit: int = Query(5, ge=1, le=20, description="返却件数"),
):
    # 1. 没日録DBからsubtaskのdescription取得
    bot_conn = get_botsunichiroku_db()
    try:
        row = bot_conn.execute(
            "SELECT description FROM subtasks WHERE id = ?",
            (subtask_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Subtask {subtask_id} not found")
        description = row["description"]
    finally:
        bot_conn.close()

    # 2. キーワード自動抽出
    keywords = extract_nouns(description)
    if not keywords:
        return {
            "subtask_id": subtask_id,
            "keywords": [],
            "results": [],
        }

    # 3. FTS5 OR検索
    match_query = " OR ".join(f'"{kw}"' for kw in keywords)

    idx_conn = get_index_db()
    try:
        cur = idx_conn.execute(
            """
            SELECT
                source_type,
                source_id,
                parent_id,
                project,
                worker_id,
                status,
                snippet(search_index, 6, '...', '...', '', 32) AS snippet,
                rank
            FROM search_index
            WHERE search_index MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_query, limit + 10),  # 自身除外分を余分に取得
        )
        rows = cur.fetchall()
    finally:
        idx_conn.close()

    # 4. 自分自身を除外し、audit_statusを付与
    bot_conn2 = get_botsunichiroku_db()
    try:
        results = []
        for row in rows:
            if row["source_id"] == subtask_id:
                continue
            if len(results) >= limit:
                break
            item = {
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "parent_id": row["parent_id"],
                "project": row["project"],
                "worker_id": row["worker_id"],
                "status": row["status"],
                "snippet": row["snippet"],
                "score": row["rank"],
            }
            # subtask型の結果にはaudit_statusを付与
            if row["source_type"] == "subtask":
                audit_row = bot_conn2.execute(
                    "SELECT audit_status FROM subtasks WHERE id = ?",
                    (row["source_id"],),
                ).fetchone()
                item["audit_status"] = audit_row["audit_status"] if audit_row else None
            results.append(item)
    finally:
        bot_conn2.close()

    return {
        "subtask_id": subtask_id,
        "keywords": keywords,
        "results": results,
    }


# ============================================================
# 5. GET /audit/history - 監査履歴
# ============================================================
@app.get("/audit/history")
def audit_history(
    worker_id: str = Query(None, description="足軽IDでフィルタ"),
    project: str = Query(None, description="プロジェクトでフィルタ"),
    limit: int = Query(20, ge=1, le=100, description="返却件数"),
):
    conn = get_botsunichiroku_db()
    try:
        # 動的フィルタ構築
        conditions = ["s.needs_audit = 1"]
        params: list = []
        if worker_id:
            conditions.append("s.worker_id = ?")
            params.append(worker_id)
        if project:
            conditions.append("s.project = ?")
            params.append(project)

        where_clause = " AND ".join(conditions)
        params.append(limit)

        cur = conn.execute(
            f"""
            SELECT
                s.id AS subtask_id,
                s.parent_cmd,
                s.worker_id,
                s.project,
                s.description,
                s.status,
                s.needs_audit,
                s.audit_status,
                s.assigned_at,
                s.completed_at,
                (SELECT r.summary FROM reports r WHERE r.task_id = s.id
                 ORDER BY r.timestamp DESC LIMIT 1) AS latest_report_summary
            FROM subtasks s
            WHERE {where_clause}
            ORDER BY s.completed_at DESC
            LIMIT ?
            """,
            params,
        )
        rows = cur.fetchall()

        items = []
        stats = {"total": 0, "done": 0, "rejected": 0, "pending": 0}
        for row in rows:
            items.append({
                "subtask_id": row["subtask_id"],
                "parent_cmd": row["parent_cmd"],
                "worker_id": row["worker_id"],
                "project": row["project"],
                "description": row["description"],
                "audit_status": row["audit_status"],
                "completed_at": row["completed_at"],
                "latest_report_summary": row["latest_report_summary"],
            })

        # 統計は全件（limitなし）で計算
        stat_params: list = []
        stat_conditions = ["needs_audit = 1"]
        if worker_id:
            stat_conditions.append("worker_id = ?")
            stat_params.append(worker_id)
        if project:
            stat_conditions.append("project = ?")
            stat_params.append(project)
        stat_where = " AND ".join(stat_conditions)

        stat_cur = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN audit_status = 'done' THEN 1 ELSE 0 END) AS done,
                SUM(CASE WHEN audit_status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN audit_status = 'pending' OR audit_status IS NULL THEN 1 ELSE 0 END) AS pending
            FROM subtasks
            WHERE {stat_where}
            """,
            stat_params,
        )
        stat_row = stat_cur.fetchone()
        stats["total"] = stat_row["total"] or 0
        stats["done"] = stat_row["done"] or 0
        stats["rejected"] = stat_row["rejected"] or 0
        stats["pending"] = stat_row["pending"] or 0
        stats["approval_rate"] = round(stats["done"] / stats["total"], 2) if stats["total"] > 0 else 0.0

        return {
            "items": items,
            "stats": stats,
        }
    finally:
        conn.close()


# ============================================================
# 6. GET /worker/stats - 足軽パフォーマンス統計
# ============================================================
@app.get("/worker/stats")
def worker_stats(
    worker_id: str = Query(None, description="足軽IDでフィルタ（省略時: 全足軽）"),
):
    conn = get_botsunichiroku_db()
    try:
        # worker_idフィルタ
        if worker_id:
            workers = [worker_id]
        else:
            cur = conn.execute(
                "SELECT DISTINCT worker_id FROM subtasks WHERE worker_id IS NOT NULL"
            )
            workers = [row["worker_id"] for row in cur.fetchall()]

        results = []
        for wid in workers:
            # タスク数集計
            task_cur = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_tasks,
                    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
                    SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                FROM subtasks
                WHERE worker_id = ?
                """,
                (wid,),
            )
            task_row = task_cur.fetchone()

            # audit統計
            audit_cur = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN audit_status = 'done' THEN 1 ELSE 0 END) AS audit_approved,
                    SUM(CASE WHEN audit_status = 'rejected' THEN 1 ELSE 0 END) AS audit_rejected
                FROM subtasks
                WHERE worker_id = ? AND needs_audit = 1
                """,
                (wid,),
            )
            audit_row = audit_cur.fetchone()
            audit_approved = audit_row["audit_approved"] or 0
            audit_rejected = audit_row["audit_rejected"] or 0
            audit_total = audit_approved + audit_rejected
            approval_rate = round(audit_approved / audit_total, 2) if audit_total > 0 else 0.0

            # プロジェクト別タスク数
            proj_cur = conn.execute(
                """
                SELECT project, COUNT(*) AS count
                FROM subtasks
                WHERE worker_id = ? AND project IS NOT NULL
                GROUP BY project
                """,
                (wid,),
            )
            projects = {row["project"]: row["count"] for row in proj_cur.fetchall()}

            # 平均完了時間（時間単位）
            avg_cur = conn.execute(
                """
                SELECT AVG(
                    (julianday(completed_at) - julianday(assigned_at)) * 24
                ) AS avg_hours
                FROM subtasks
                WHERE worker_id = ?
                  AND completed_at IS NOT NULL
                  AND assigned_at IS NOT NULL
                """,
                (wid,),
            )
            avg_row = avg_cur.fetchone()
            avg_completion_hours = round(avg_row["avg_hours"], 1) if avg_row["avg_hours"] else None

            # top_project
            top_project = max(projects, key=projects.get) if projects else None

            results.append({
                "worker_id": wid,
                "total_tasks": task_row["total_tasks"] or 0,
                "done": task_row["done"] or 0,
                "blocked": task_row["blocked"] or 0,
                "cancelled": task_row["cancelled"] or 0,
                "audit_approved": audit_approved,
                "audit_rejected": audit_rejected,
                "approval_rate": approval_rate,
                "projects": projects,
                "top_project": top_project,
                "avg_completion_hours": avg_completion_hours,
            })

        return {"workers": results}
    finally:
        conn.close()


# ============================================================
# 7. GET /health - ヘルスチェック
# ============================================================
@app.get("/health")
def health():
    index_db_path = Path(INDEX_DB)
    botsunichiroku_db_path = Path(BOTSUNICHIROKU_DB)

    index_exists = index_db_path.exists()
    botsunichiroku_exists = botsunichiroku_db_path.exists()

    # FTS5レコード数カウント
    index_record_count = 0
    if index_exists:
        try:
            uri = f"file:{index_db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            count = conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0]
            index_record_count = count
            conn.close()
        except Exception:
            pass

    # MeCab利用可否
    mecab_available = False
    try:
        get_mecab_wakati()
        mecab_available = True
    except Exception:
        pass

    return {
        "status": "ok",
        "index_db_exists": index_exists,
        "index_record_count": index_record_count,
        "botsunichiroku_db_exists": botsunichiroku_exists,
        "mecab_available": mecab_available,
    }
