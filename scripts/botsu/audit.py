"""audit / stats サブコマンド — 監査・統計。"""

from datetime import datetime, timedelta, timezone

from . import get_connection, print_table, print_json, row_to_dict


def audit_list(args) -> None:
    conn = get_connection()
    subtask_filter = getattr(args, "subtask", None)
    params = []
    if args.all:
        base = "SELECT id, parent_cmd, worker_id, status, audit_status, needs_audit, description FROM subtasks WHERE needs_audit = 1"
    else:
        base = "SELECT id, parent_cmd, worker_id, status, audit_status, needs_audit, description FROM subtasks WHERE needs_audit = 1 AND (audit_status IS NULL OR audit_status = 'pending')"
    if subtask_filter:
        base += " AND id = ?"
        params.append(subtask_filter)
    query = base + " ORDER BY parent_cmd DESC, id"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        if args.all:
            print("No audit items found.")
        else:
            print("No pending audits.")
        return

    headers = ["ID", "CMD", "WORKER", "STATUS", "AUDIT", "DESCRIPTION"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["parent_cmd"],
            r["worker_id"] or "-",
            r["status"],
            r["audit_status"] or "pending",
            r["description"],
        ])
    print_table(headers, table_rows, [14, 10, 12, 14, 10, 40])


def audit_record(args) -> None:
    """audit history テーブルに retry-loop 監査記録を追加する。"""
    conn = get_connection()

    # audit_history テーブルが存在しない場合は作成（マイグレーション）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subtask_id TEXT NOT NULL,
            attempt INTEGER NOT NULL DEFAULT 1,
            score INTEGER,
            verdict TEXT,
            failure_category TEXT,
            findings_summary TEXT,
            worker_id TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        """INSERT INTO audit_history
           (subtask_id, attempt, score, verdict, failure_category, findings_summary, worker_id, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            args.subtask_id,
            args.attempt,
            args.score,
            args.verdict,
            args.failure_category,
            args.findings_summary,
            args.worker,
            ts,
        ),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    cat = args.failure_category or "-"
    vd = args.verdict or "-"
    print(f"Recorded: audit_history #{row_id} (subtask={args.subtask_id}, attempt={args.attempt}, score={args.score}, verdict={vd}, category={cat})")


def audit_history_stats(args) -> None:
    """failure_category 別の集計を表示する（再発率追跡）。"""
    conn = get_connection()

    # テーブル存在確認
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_history'"
    ).fetchone()
    if not exists:
        print("audit_history テーブルが存在しません。audit record を先に実行してください。")
        conn.close()
        return

    total = conn.execute("SELECT COUNT(*) FROM audit_history").fetchone()[0]
    if total == 0:
        print("監査履歴が0件です。")
        conn.close()
        return

    cat_rows = conn.execute(
        """SELECT COALESCE(failure_category, '(なし)') as cat, COUNT(*) as cnt
           FROM audit_history
           GROUP BY failure_category
           ORDER BY cnt DESC"""
    ).fetchall()

    verdict_rows = conn.execute(
        """SELECT COALESCE(verdict, '(未記録)') as vd, COUNT(*) as cnt
           FROM audit_history
           GROUP BY verdict
           ORDER BY cnt DESC"""
    ).fetchall()

    avg_score_val = conn.execute(
        "SELECT AVG(score) FROM audit_history WHERE score IS NOT NULL"
    ).fetchone()[0]

    recent_rows = conn.execute(
        """SELECT subtask_id, attempt, score, verdict, failure_category, timestamp
           FROM audit_history
           ORDER BY id DESC LIMIT 10"""
    ).fetchall()
    conn.close()

    if args.json:
        print_json({
            "total": total,
            "avg_score": round(avg_score_val, 1) if avg_score_val else None,
            "by_category": {r["cat"]: r["cnt"] for r in cat_rows},
            "by_verdict": {r["vd"]: r["cnt"] for r in verdict_rows},
        })
        return

    avg_str = str(round(avg_score_val, 1)) if avg_score_val else "N/A"
    print("═══════════════════════════════════════")
    print("  監査履歴統計 (audit_history)")
    print("═══════════════════════════════════════")
    print(f"  総記録数: {total}件  |  平均スコア: {avg_str}")
    print()
    print("  失敗カテゴリ別:")
    for r in cat_rows:
        pct = r["cnt"] * 100 // total
        print(f"    {r['cat']}: {r['cnt']}件 ({pct}%)")
    print()
    print("  verdict別:")
    for r in verdict_rows:
        pct = r["cnt"] * 100 // total
        print(f"    {r['vd']}: {r['cnt']}件 ({pct}%)")
    print()
    print("  直近10件:")
    headers = ["SUBTASK", "ATT", "SCORE", "VERDICT", "CATEGORY", "TIMESTAMP"]
    table_rows = [
        [r["subtask_id"], str(r["attempt"]), str(r["score"]) if r["score"] else "-",
         r["verdict"] or "-", r["failure_category"] or "-", (r["timestamp"] or "")[:16]]
        for r in recent_rows
    ]
    print_table(headers, table_rows, [14, 4, 6, 20, 16, 16])
    print("═══════════════════════════════════════")


def _ensure_audit_records(conn) -> None:
    """audit_records テーブルが存在しない場合は作成、severity カラムをマイグレーション。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subtask_id  TEXT    NOT NULL,
            cmd_id      TEXT,
            verdict     TEXT    NOT NULL CHECK(verdict IN ('PASS','FAIL','CONDITIONAL')),
            kenshu_thread TEXT,
            reviewers   TEXT,
            summary     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    # severity カラム追加（既存テーブルへの後方互換マイグレーション）
    cols = [r[1] for r in conn.execute("PRAGMA table_info(audit_records)").fetchall()]
    if "severity" not in cols:
        conn.execute("ALTER TABLE audit_records ADD COLUMN severity TEXT")


def _print_audit_record(r) -> None:
    print("─────────────────────────────────────────")
    print(f"  audit_record #{r['id']}")
    print(f"  subtask : {r['subtask_id']}")
    print(f"  cmd     : {r['cmd_id'] or '-'}")
    print(f"  verdict : {r['verdict']}")
    if r['severity']:
        print(f"  severity: {r['severity']}")
    print(f"  thread  : {r['kenshu_thread'] or '-'}")
    print(f"  reviewers: {r['reviewers'] or '-'}")
    print(f"  summary : {r['summary']}")
    print(f"  created : {r['created_at']}")
    print("─────────────────────────────────────────")


def audit_add(args) -> None:
    """audit_records テーブルに v4.0 合議結果を追加する。"""
    conn = get_connection()
    _ensure_audit_records(conn)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        """INSERT INTO audit_records
           (subtask_id, cmd_id, verdict, kenshu_thread, reviewers, summary, severity, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            args.subtask_id,
            args.cmd,
            args.verdict,
            args.kenshu_thread,
            args.reviewers,
            args.summary,
            getattr(args, "severity", None),
            ts,
        ),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    sev = getattr(args, "severity", None)
    sev_str = f", severity={sev}" if sev else ""
    print(f"Created: audit_record #{row_id} (subtask={args.subtask_id}, verdict={args.verdict}{sev_str})")


def audit_show(args) -> None:
    """audit_records の1件または subtask別に表示する。"""
    conn = get_connection()

    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_records'"
    ).fetchone()
    if not exists:
        print("audit_records テーブルが存在しません。audit add を先に実行してください。")
        conn.close()
        return

    if args.subtask:
        rows = conn.execute(
            "SELECT * FROM audit_records WHERE subtask_id = ? ORDER BY id DESC",
            (args.subtask,),
        ).fetchall()
        conn.close()
        if not rows:
            print(f"No audit_records for subtask={args.subtask}")
            return
        for r in rows:
            _print_audit_record(r)
    elif args.audit_id is not None:
        row = conn.execute(
            "SELECT * FROM audit_records WHERE id = ?",
            (args.audit_id,),
        ).fetchone()
        conn.close()
        if not row:
            print(f"audit_record #{args.audit_id} not found")
            return
        _print_audit_record(row)
    else:
        conn.close()
        print("audit_id (positional) または --subtask SUBTASK_ID を指定してください")


def stats_show(args) -> None:
    conn = get_connection()

    cmd_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM commands GROUP BY status"
    ).fetchall()
    cmd_counts = {r["status"]: r["cnt"] for r in cmd_rows}
    cmd_total = sum(cmd_counts.values())

    sub_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM subtasks GROUP BY status"
    ).fetchall()
    sub_counts = {r["status"]: r["cnt"] for r in sub_rows}
    sub_total = sum(sub_counts.values())

    agent_total = conn.execute(
        "SELECT COUNT(*) FROM agents WHERE role IN ('ashigaru', 'heyago')"
    ).fetchone()[0]
    agent_busy = conn.execute(
        "SELECT COUNT(*) FROM agents WHERE role IN ('ashigaru', 'heyago') AND status = 'busy'"
    ).fetchone()[0]

    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_done = conn.execute(
        "SELECT COUNT(*) FROM commands WHERE status IN ('done', 'archived') AND completed_at >= ?",
        (cutoff_24h,),
    ).fetchone()[0]

    proj_rows = conn.execute(
        "SELECT COALESCE(project, '(none)') as proj, COUNT(*) as cnt FROM commands GROUP BY project ORDER BY cnt DESC"
    ).fetchall()

    karo_rows = conn.execute(
        "SELECT COALESCE(assigned_karo, '(none)') as karo, COUNT(*) as cnt FROM commands GROUP BY assigned_karo ORDER BY cnt DESC"
    ).fetchall()

    conn.close()

    if args.json:
        data = {
            "commands": {"total": cmd_total, "by_status": cmd_counts},
            "subtasks": {"total": sub_total, "by_status": sub_counts},
            "agents": {"total": agent_total, "busy": agent_busy},
            "recent_24h_done": recent_done,
            "by_project": {r["proj"]: r["cnt"] for r in proj_rows},
            "by_karo": {r["karo"]: r["cnt"] for r in karo_rows},
        }
        print_json(data)
        return

    cmd_status_str = " | ".join(
        f"{s}: {cmd_counts.get(s, 0)}"
        for s in ("pending", "in_progress", "done", "cancelled", "archived")
    )
    sub_status_str = " | ".join(
        f"{s}: {sub_counts.get(s, 0)}"
        for s in ("pending", "assigned", "in_progress", "done", "blocked", "archived")
    )
    proj_str = " | ".join(f"{r['proj']}={r['cnt']}" for r in proj_rows)
    karo_str = " | ".join(f"{r['karo']}={r['cnt']}" for r in karo_rows)

    pct = (agent_busy * 100 // agent_total) if agent_total > 0 else 0

    print("═══════════════════════════════════════")
    print("  没日録 統計情報")
    print("═══════════════════════════════════════")
    print(f"  コマンド: {cmd_total}件")
    print(f"    {cmd_status_str}")
    print(f"  サブタスク: {sub_total}件")
    print(f"    {sub_status_str}")
    print(f"  足軽稼働率: {agent_busy}/{agent_total} ({pct}%)")
    print(f"  直近24h完了: {recent_done}件")
    print(f"  プロジェクト別: {proj_str}")
    print(f"  家老別: {karo_str}")
    print("═══════════════════════════════════════")
