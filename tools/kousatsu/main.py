"""高札（kousatsu）- 通信ハブ+検索API

FTS5インデックスDBおよび没日録DB（読み取り専用）に対して
全文検索・矛盾検出・カバレッジチェックを提供する。
"""

import json as _json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import MeCab
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="高札 - 通信ハブ+検索API", version="2.0.0")

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


def get_botsunichiroku_db_rw() -> sqlite3.Connection:
    """没日録DBへの読み書き接続を返す（POST/PATCH系エンドポイント用）。"""
    db_path = Path(BOTSUNICHIROKU_DB)
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="botsunichiroku.db not found")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# --- Pydanticモデル ---

class ReportCreate(BaseModel):
    subtask_id: str
    worker_id: str
    status: str       # done|blocked|error
    summary: str
    body: str = ""
    skill_candidate_name: str = ""
    skill_candidate_desc: str = ""


class AuditCreate(BaseModel):
    subtask_id: str
    result: str       # approved|rejected_trivial|rejected_judgment
    summary: str
    findings: str = ""


class DashboardEntryCreate(BaseModel):
    section: str         # "戦果", "スキル候補", "findings", "殿裁定" 等
    content: str         # エントリ本文
    cmd_id: str = ""     # nullable, 関連cmd_id
    status: str = ""     # "done", "adopted", "rejected" 等
    tags: str = ""       # カンマ区切りタグ


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

    # FTS5 MATCH用: 各トークンをダブルクォートで囲んで特殊文字をエスケープ
    # ハイフン(-), コロン(:), ドット(.)等がFTS5演算子として誤解釈される問題を防ぐ
    tokens = tokenized.split()
    match_query = " ".join(f'"{t}"' for t in tokens if t.strip())

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


# ============================================================
# 8. POST /reports - 足軽/部屋子が報告を登録
# ============================================================
@app.post("/reports", status_code=201)
def create_report(report: ReportCreate):
    valid_statuses = {"done", "blocked", "error"}
    if report.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of {valid_statuses}")

    conn = get_botsunichiroku_db_rw()
    try:
        # subtask存在チェック
        row = conn.execute(
            "SELECT id FROM subtasks WHERE id = ?", (report.subtask_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"subtask '{report.subtask_id}' not found")

        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        cur = conn.execute(
            """INSERT INTO reports
               (worker_id, task_id, timestamp, status, summary, notes,
                skill_candidate_name, skill_candidate_desc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report.worker_id,
                report.subtask_id,
                ts,
                report.status,
                report.summary,
                report.body or None,
                report.skill_candidate_name or None,
                report.skill_candidate_desc or None,
            ),
        )
        conn.commit()
        report_id = cur.lastrowid
    finally:
        conn.close()

    return {"report_id": report_id, "status": "created"}


# ============================================================
# 9. POST /audit - お針子が監査結果を登録
# ============================================================
@app.post("/audit", status_code=200)
def create_audit(audit: AuditCreate):
    valid_results = {"approved", "rejected_trivial", "rejected_judgment"}
    if audit.result not in valid_results:
        raise HTTPException(status_code=422, detail=f"result must be one of {valid_results}")

    audit_status = "done" if audit.result == "approved" else "rejected"

    conn = get_botsunichiroku_db_rw()
    try:
        # subtask存在チェック
        row = conn.execute(
            "SELECT id, notes FROM subtasks WHERE id = ?", (audit.subtask_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"subtask '{audit.subtask_id}' not found")

        # notes に [audit] プレフィックス付きで追記
        existing_notes = row["notes"] or ""
        audit_note = f"[audit] {audit.findings}" if audit.findings else f"[audit] {audit.summary}"
        new_notes = (existing_notes + "\n" + audit_note).strip() if existing_notes else audit_note

        conn.execute(
            "UPDATE subtasks SET audit_status = ?, notes = ? WHERE id = ?",
            (audit_status, new_notes, audit.subtask_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {"subtask_id": audit.subtask_id, "audit_status": audit_status, "status": "updated"}


# ============================================================
# 10. GET /reports/{report_id} - 報告全文取得
# ============================================================
@app.get("/reports/{report_id}")
def get_report(report_id: int):
    conn = get_botsunichiroku_db()
    try:
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"report {report_id} not found")
        return {
            "id": row["id"],
            "worker_id": row["worker_id"],
            "task_id": row["task_id"],
            "timestamp": row["timestamp"],
            "status": row["status"],
            "summary": row["summary"],
            "notes": row["notes"],
            "skill_candidate_name": row["skill_candidate_name"],
            "skill_candidate_desc": row["skill_candidate_desc"],
        }
    finally:
        conn.close()


# ============================================================
# 12. POST /dashboard - dashboardエントリ登録
# ============================================================
@app.post("/dashboard", status_code=201)
def create_dashboard_entry(entry: DashboardEntryCreate):
    conn = get_botsunichiroku_db_rw()
    try:
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        cmd_id_value = entry.cmd_id if entry.cmd_id else None
        cur = conn.execute(
            """INSERT INTO dashboard_entries
               (cmd_id, section, content, status, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                cmd_id_value,
                entry.section,
                entry.content,
                entry.status or None,
                entry.tags or None,
                ts,
            ),
        )
        conn.commit()
        entry_id = cur.lastrowid
    finally:
        conn.close()

    return {"id": entry_id, "status": "created"}


# ============================================================
# 13. GET /dashboard - dashboardエントリ取得
# ============================================================
@app.get("/dashboard")
def get_dashboard(
    section: str = Query(None, description="セクションでフィルタ"),
    cmd_id: str = Query(None, description="cmd_idでフィルタ"),
    q: str = Query(None, description="contentのLIKE検索"),
    limit: int = Query(20, ge=1, le=100, description="返却件数"),
):
    conn = get_botsunichiroku_db()
    try:
        conditions = []
        params: list = []
        if section:
            conditions.append("section = ?")
            params.append(section)
        if cmd_id:
            conditions.append("cmd_id = ?")
            params.append(cmd_id)
        if q:
            conditions.append("content LIKE ?")
            params.append(f"%{q}%")

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_cur = conn.execute(
            f"SELECT COUNT(*) FROM dashboard_entries {where_clause}",
            params.copy(),
        )
        total = count_cur.fetchone()[0]

        params.append(limit)
        cur = conn.execute(
            f"""SELECT id, cmd_id, section, content, status, tags, created_at
                FROM dashboard_entries
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?""",
            params,
        )
        rows = cur.fetchall()

        entries = [
            {
                "id": row["id"],
                "cmd_id": row["cmd_id"],
                "section": row["section"],
                "content": row["content"],
                "status": row["status"],
                "tags": row["tags"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

        return {"total": total, "entries": entries}
    finally:
        conn.close()


# ============================================================
# 14. GET /docs/{category}/{filename} - Markdownドキュメント配信
# ============================================================
_DOCS_ROOT = Path("/app/static")
_ALLOWED_CATEGORIES = {"instructions", "context"}


@app.get("/docs/{category}/{filename}")
def get_doc(category: str, filename: str):
    if category not in _ALLOWED_CATEGORIES:
        raise HTTPException(status_code=404, detail=f"Unknown category: {category}")
    # パストラバーサル防止: filenameにスラッシュ・dotdotを含まないこと
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    doc_path = _DOCS_ROOT / category / filename
    if not doc_path.exists() or not doc_path.is_file():
        raise HTTPException(status_code=404, detail=f"{category}/{filename} not found")
    content = doc_path.read_text(encoding="utf-8")
    from fastapi.responses import Response
    return Response(content=content, media_type="text/markdown; charset=utf-8")


# ============================================================
# 11. GET /audit/{subtask_id} - 監査結果取得
# ============================================================
@app.get("/audit/{subtask_id}")
def get_audit(subtask_id: str):
    conn = get_botsunichiroku_db()
    try:
        row = conn.execute(
            "SELECT id, audit_status, needs_audit, notes FROM subtasks WHERE id = ?",
            (subtask_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"subtask '{subtask_id}' not found")
        return {
            "subtask_id": subtask_id,
            "audit_status": row["audit_status"],
            "needs_audit": bool(row["needs_audit"]),
            "notes": row["notes"],
        }
    finally:
        conn.close()


# ============================================================
# 15. POST /enrich v2.0 - 連想記憶+pitfalls+prediction+positive
# ============================================================

def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class EnrichRequest(BaseModel):
    cmd_id: str
    text: str
    project: str | None = None
    include_external: bool = False
    worker_id: str | None = None


class PitfallItem(BaseModel):
    pattern_id: str
    source_id: str
    severity: str
    description: str
    prevention: str


class PositivePattern(BaseModel):
    source_id: str
    project: str
    description: str
    strength: str
    hint: str


class Prediction(BaseModel):
    question: str
    predicted_choice: str
    confidence: str
    basis: list[dict]
    note: str


@app.post("/enrich")
def enrich(req: EnrichRequest):
    t0 = time.monotonic()

    keywords = extract_nouns(req.text)

    # --- Stage 1: 同PJ内FTS5検索（局所） ---
    local_results = []
    t_local = 0
    if keywords:
        match_query = " OR ".join(f'"{kw}"' for kw in keywords[:15])
        idx_conn = get_index_db()
        try:
            t1 = time.monotonic()
            if req.project:
                rows = idx_conn.execute("""
                    SELECT source_type, source_id, parent_id, project,
                           worker_id, status,
                           snippet(search_index, 6, '...', '...', '', 64) AS snippet,
                           rank
                    FROM search_index
                    WHERE search_index MATCH ? AND project = ?
                    ORDER BY rank LIMIT 10
                """, (match_query, req.project)).fetchall()
            else:
                rows = idx_conn.execute("""
                    SELECT source_type, source_id, parent_id, project,
                           worker_id, status,
                           snippet(search_index, 6, '...', '...', '', 64) AS snippet,
                           rank
                    FROM search_index
                    WHERE search_index MATCH ?
                    ORDER BY rank LIMIT 10
                """, (match_query,)).fetchall()
            t_local = int((time.monotonic() - t1) * 1000)
            for row in rows:
                if row["source_id"] == req.cmd_id:
                    continue
                local_results.append({
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                    "project": row["project"],
                    "snippet": row["snippet"],
                    "score": row["rank"],
                    "stage": "local",
                })
        finally:
            idx_conn.close()

    # --- Stage 2: 全PJ横断FTS5検索（拡大） ---
    global_results = []
    t_global = 0
    if keywords and req.project:
        local_ids = {r["source_id"] for r in local_results}
        idx_conn = get_index_db()
        try:
            t2 = time.monotonic()
            rows = idx_conn.execute("""
                SELECT source_type, source_id, parent_id, project,
                       worker_id, status,
                       snippet(search_index, 6, '...', '...', '', 64) AS snippet,
                       rank
                FROM search_index
                WHERE search_index MATCH ? AND project != ?
                ORDER BY rank LIMIT 10
            """, (match_query, req.project)).fetchall()
            t_global = int((time.monotonic() - t2) * 1000)
            for row in rows:
                sid = row["source_id"]
                if sid == req.cmd_id or sid in local_ids:
                    continue
                global_results.append({
                    "source_type": row["source_type"],
                    "source_id": sid,
                    "project": row["project"],
                    "snippet": row["snippet"],
                    "score": row["rank"],
                    "stage": "global",
                    "hint": f"{row['project']}プロジェクトの類似タスク",
                    "confidence": round(0.5 + min(abs(row["rank"]) / 20, 0.4), 2),
                })
        finally:
            idx_conn.close()

    # --- Stage 2b: pitfalls抽出 ---
    t_pit = time.monotonic()
    pitfalls = _extract_pitfalls(keywords, req.worker_id)
    t_pitfall = int((time.monotonic() - t_pit) * 1000)

    # --- Stage 2c: positive_patterns抽出 ---
    positive_patterns = _extract_positive_patterns(keywords)

    # --- Stage 2d: 直近24h SQL LIKE補完 ---
    recent = _search_recent_cmds(keywords, req.cmd_id)
    local_results.extend(recent)

    # --- Stage 3: 外部検索（sanitized） ---
    external = []
    if req.include_external and len(local_results) <= 2:
        external = _search_external_sanitized(keywords)

    # --- TAGE的判断予測 ---
    prediction = _predict_decision(keywords, req.project, req.cmd_id)

    # --- キャッシュ保存 ---
    _cache_enrichment(req.cmd_id, local_results, pitfalls,
                      positive_patterns, prediction, global_results, external)

    total_ms = int((time.monotonic() - t0) * 1000)
    return {
        "cmd_id": req.cmd_id,
        "enriched_at": _now_iso(),
        "internal": local_results[:10],
        "pitfalls": [p if isinstance(p, dict) else p.dict() for p in pitfalls[:5]],
        "positive_patterns": [p if isinstance(p, dict) else p.dict() for p in positive_patterns[:5]],
        "prediction": prediction.dict() if prediction else None,
        "cross_project": global_results[:5],
        "external": external[:5],
        "meta": {
            "internal_hits": len(local_results),
            "pitfall_hits": len(pitfalls),
            "positive_hits": len(positive_patterns),
            "cross_project_hits": len(global_results),
            "prediction_table": (prediction.basis[0]["table"]
                                 if prediction and prediction.basis else None),
            "fts5_local_ms": t_local,
            "fts5_global_ms": t_global,
            "pitfall_query_ms": t_pitfall,
            "total_ms": total_ms,
            "keywords": keywords[:10],
        },
    }


# ============================================================
# 16. GET /enrich/{cmd_id} - キャッシュ済みenrich結果取得
# ============================================================

@app.get("/enrich/{cmd_id}")
def get_enrichment(cmd_id: str):
    """キャッシュ済みenrich結果を取得。"""
    bot_conn = get_botsunichiroku_db()
    try:
        row = bot_conn.execute("""
            SELECT content, created_at FROM dashboard_entries
            WHERE cmd_id = ? AND section = 'enrich_cache'
            ORDER BY created_at DESC LIMIT 1
        """, (cmd_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404,
                                detail=f"No enrichment found for {cmd_id}")
        cached = _json.loads(row["content"])
        return {
            "cmd_id": cmd_id,
            "enriched_at": row["created_at"],
            **cached,
            "meta": {"source": "cache"},
        }
    finally:
        bot_conn.close()


# ============================================================
# Internal: pitfalls抽出
# ============================================================

def _extract_pitfalls(keywords: list[str], worker_id: str | None) -> list[dict]:
    """没日録DBから失敗パターンを抽出する。"""
    bot_conn = get_botsunichiroku_db()
    pitfalls = []
    try:
        patterns = [
            ("P001", "%コミット漏れ%", "high",
             "commit忘れ", "inbox descriptionに「git add+commit+push」を明記"),
            ("P002", "%ハルシネーション%", "critical",
             "ハルシネーション", "成果物の実在確認（git ls-remote, ls -la）を必須化"),
            ("P002", "%捏造%", "critical",
             "捏造", "成果物の実在確認を必須化"),
            ("P003", "%マージ%", "medium",
             "マージ問題", "ブランチ分岐状況を事前確認"),
            ("P004", "%差し戻%", "medium",
             "差し戻し", "直近の差し戻し理由を確認"),
        ]
        seen_ids: set[str] = set()
        for pid, like_pattern, severity, desc_label, prevention in patterns:
            rows = bot_conn.execute("""
                SELECT s.id, s.parent_cmd, s.worker_id,
                       substr(s.description, 1, 100) AS description,
                       r.summary AS report_summary
                FROM subtasks s
                LEFT JOIN reports r ON r.task_id = s.id
                WHERE (r.summary LIKE ? OR s.description LIKE ?)
                  AND s.status IN ('blocked', 'cancelled', 'done')
                ORDER BY s.completed_at DESC LIMIT 3
            """, (like_pattern, like_pattern)).fetchall()
            for row in rows:
                if row["id"] in seen_ids:
                    continue
                seen_ids.add(row["id"])
                pitfalls.append({
                    "pattern_id": pid,
                    "source_id": row["id"],
                    "severity": severity,
                    "description": f"{desc_label}: {row['description']}",
                    "prevention": prevention,
                })

        # P005: worker別の失敗パターン
        if worker_id:
            rows = bot_conn.execute("""
                SELECT s.id, substr(s.description, 1, 100) AS description
                FROM subtasks s
                WHERE s.worker_id = ? AND s.status IN ('blocked', 'cancelled')
                ORDER BY s.completed_at DESC LIMIT 3
            """, (worker_id,)).fetchall()
            for row in rows:
                if row["id"] not in seen_ids:
                    pitfalls.append({
                        "pattern_id": "P005",
                        "source_id": row["id"],
                        "severity": "medium",
                        "description": f"{worker_id}の過去失敗: {row['description']}",
                        "prevention": f"{worker_id}に割り当て時は過去の失敗パターンに注意",
                    })
    finally:
        bot_conn.close()

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    pitfalls.sort(key=lambda x: order.get(x["severity"], 4))
    return pitfalls


# ============================================================
# Internal: positive_patterns抽出（正の強化信号）
# ============================================================

def _extract_positive_patterns(keywords: list[str]) -> list[dict]:
    """audit PASS済みの成功パターンを抽出する。"""
    if not keywords:
        return []
    bot_conn = get_botsunichiroku_db()
    results = []
    seen: set[str] = set()
    try:
        for kw in keywords[:5]:
            rows = bot_conn.execute("""
                SELECT s.id, s.project, s.worker_id,
                       substr(s.description, 1, 120) AS description,
                       r.summary AS report_summary
                FROM subtasks s
                JOIN reports r ON r.task_id = s.id AND r.status = 'done'
                WHERE s.audit_status = 'done'
                  AND (s.description LIKE '%' || ? || '%'
                       OR r.summary LIKE '%' || ? || '%')
                ORDER BY s.completed_at DESC LIMIT 3
            """, (kw, kw)).fetchall()
            for row in rows:
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                results.append({
                    "source_id": row["id"],
                    "project": row["project"] or "",
                    "description": f"{row['description']} → audit PASS",
                    "strength": "high" if len(rows) >= 3 else "medium",
                    "hint": "この方向を継続せよ",
                })
    finally:
        bot_conn.close()
    return results


# ============================================================
# Internal: TAGE的判断予測
# ============================================================

def _predict_decision(keywords: list[str], project: str | None,
                      cmd_id: str) -> Prediction | None:
    """殿の過去裁定履歴から判断を予測する。TAGE分岐予測器方式。"""
    if not keywords:
        return None
    bot_conn = get_botsunichiroku_db()
    try:
        # T1: 直近cmd（最短履歴テーブル）
        t1_rows = bot_conn.execute("""
            SELECT c.id, c.command, c.details, c.project
            FROM commands c
            WHERE c.status = 'done' AND c.id != ?
            ORDER BY c.created_at DESC LIMIT 5
        """, (cmd_id,)).fetchall()

        # T2: 同PJ内（中程度履歴テーブル）
        t2_rows = []
        if project:
            t2_rows = bot_conn.execute("""
                SELECT c.id, c.command, c.details
                FROM commands c
                WHERE c.project = ? AND c.status = 'done' AND c.id != ?
                ORDER BY c.created_at DESC LIMIT 10
            """, (project, cmd_id)).fetchall()

        # T3: 全PJ（最長履歴テーブル）
        t3_rows = bot_conn.execute("""
            SELECT c.id, c.command, c.details
            FROM commands c
            WHERE c.status = 'done' AND c.id != ?
            ORDER BY c.created_at DESC LIMIT 30
        """, (cmd_id,)).fetchall()

        # 既知の判断パターン（殿の好み）
        known_patterns = [
            {"question": "DBエンジン選定",
             "keywords": ["DB", "データベース", "SQLite", "Postgres"],
             "predicted_choice": "SQLite",
             "reason": "殿のマクガイバー精神。月額課金回避"},
            {"question": "言語選定",
             "keywords": ["Python", "Go", "Rust", "言語"],
             "predicted_choice": "Python",
             "reason": "既存基盤がPython。Simple>Complex"},
            {"question": "デプロイ方式",
             "keywords": ["Docker", "デプロイ", "コンテナ"],
             "predicted_choice": "Docker Compose",
             "reason": "既存高札がDocker Compose"},
            {"question": "設計方針",
             "keywords": ["設計", "アーキテクチャ"],
             "predicted_choice": "マクガイバー精神（ありもの活用）",
             "reason": "新規依存最小化"},
        ]

        for pattern in known_patterns:
            if any(kw in keywords for kw in pattern["keywords"]):
                basis = []
                for table_name, table_rows in [("T1", t1_rows),
                                                ("T2", t2_rows),
                                                ("T3", t3_rows)]:
                    for row in table_rows:
                        text = f"{row['command']} {row['details'] or ''}"
                        if any(pk in text for pk in pattern["keywords"]):
                            basis.append({
                                "table": table_name,
                                "source": f"{row['id']}: {row['command'][:60]}",
                                "match": True,
                            })
                if basis:
                    conf = ("high" if len(basis) >= 3
                            else ("medium" if len(basis) >= 2 else "low"))
                    return Prediction(
                        question=pattern["question"],
                        predicted_choice=pattern["predicted_choice"],
                        confidence=conf,
                        basis=basis[:5],
                        note=(f"確信度{conf}。" + (
                            "足軽は投機実行可。ミスプレディクション時はaudit FAILで巻き戻し"
                            if conf == "high"
                            else "家老が殿に確認推奨"
                        )),
                    )
    finally:
        bot_conn.close()
    return None


# ============================================================
# Internal: 直近cmd補完
# ============================================================

def _search_recent_cmds(keywords: list[str],
                        exclude_cmd_id: str) -> list[dict]:
    """直近24時間のcmdをSQL LIKEで検索。"""
    if not keywords:
        return []
    bot_conn = get_botsunichiroku_db()
    results = []
    try:
        for kw in keywords[:5]:
            rows = bot_conn.execute("""
                SELECT id, project, status,
                       substr(command || ' ' || COALESCE(details, ''), 1, 200) AS snippet
                FROM commands
                WHERE created_at > datetime('now', '-24 hours')
                  AND id != ?
                  AND (command LIKE '%' || ? || '%'
                       OR details LIKE '%' || ? || '%')
                LIMIT 3
            """, (exclude_cmd_id, kw, kw)).fetchall()
            for row in rows:
                results.append({
                    "source_type": "command_recent",
                    "source_id": row["id"],
                    "project": row["project"],
                    "snippet": row["snippet"],
                    "score": 0,
                    "stage": "local",
                })
    finally:
        bot_conn.close()
    seen: set[str] = set()
    return [r for r in results
            if r["source_id"] not in seen and not seen.add(r["source_id"])]


# ============================================================
# Internal: 外部検索（sanitized）
# ============================================================

def _search_external_sanitized(keywords: list[str]) -> list[dict]:
    """外部Web検索を実行し、sanitizerでフィルタして返す。"""
    from sanitizer import sanitize_external_result

    results = []
    query = " ".join(keywords[:5])
    try:
        url = (f"https://api.duckduckgo.com/"
               f"?q={urllib.parse.quote(query)}&format=json&no_html=1")
        req = urllib.request.Request(url, headers={"User-Agent": "kousatsu/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            if data.get("Abstract"):
                sanitized = sanitize_external_result({
                    "source": "duckduckgo",
                    "title": data.get("Heading", ""),
                    "snippet": data["Abstract"],
                    "url": data.get("AbstractURL", ""),
                })
                if sanitized:
                    results.append(sanitized)
            for topic in (data.get("RelatedTopics") or [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    sanitized = sanitize_external_result({
                        "source": "duckduckgo",
                        "title": topic.get("Text", "")[:80],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                    })
                    if sanitized:
                        results.append(sanitized)
    except Exception:
        pass  # 外部検索失敗はgraceful degradation
    return results


# ============================================================
# Internal: キャッシュ保存
# ============================================================

def _cache_enrichment(cmd_id, internal, pitfalls, positive_patterns,
                      prediction, cross_project, external):
    """結果をdashboard_entriesにキャッシュ保存。"""
    bot_conn = get_botsunichiroku_db_rw()
    try:
        cache_data = _json.dumps({
            "internal": internal[:10],
            "pitfalls": [p if isinstance(p, dict) else p.dict()
                         for p in pitfalls[:5]],
            "positive_patterns": [p if isinstance(p, dict) else p.dict()
                                  for p in positive_patterns[:5]],
            "prediction": (prediction.dict() if prediction else None),
            "cross_project": cross_project[:5],
            "external": external[:5],
        }, ensure_ascii=False)
        bot_conn.execute("""
            INSERT INTO dashboard_entries
                (cmd_id, section, content, status, created_at)
            VALUES (?, 'enrich_cache', ?, 'cached', datetime('now'))
        """, (cmd_id, cache_data))
        bot_conn.commit()
    finally:
        bot_conn.close()
