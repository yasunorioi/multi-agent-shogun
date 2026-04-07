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


def audit_records_list(args) -> None:
    """audit_records テーブルの一覧表示（verdict/severityフィルタ対応）。"""
    conn = get_connection()

    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_records'"
    ).fetchone()
    if not exists:
        print("audit_records テーブルが存在しません。audit add を先に実行してください。")
        conn.close()
        return

    conditions = []
    params = []
    if args.verdict:
        conditions.append("verdict = ?")
        params.append(args.verdict)
    if args.severity:
        conditions.append("severity = ?")
        params.append(args.severity)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"SELECT * FROM audit_records {where} ORDER BY id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("No audit_records found.")
        return

    headers = ["ID", "SUBTASK", "CMD", "VERDICT", "SEVERITY", "REVIEWERS", "CREATED"]
    table_rows = [
        [
            str(r["id"]),
            r["subtask_id"],
            r["cmd_id"] or "-",
            r["verdict"],
            r["severity"] or "-",
            (r["reviewers"] or "-")[:20],
            (r["created_at"] or "")[:16],
        ]
        for r in rows
    ]
    print_table(headers, table_rows, [5, 16, 10, 12, 9, 22, 16])


def audit_dashboard(args) -> None:
    """検収PASS率ダッシュボード — audit_records から集計表示。"""
    conn = get_connection()

    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_records'"
    ).fetchone()
    if not exists:
        print("audit_records テーブルが存在しません。")
        conn.close()
        return

    # --- 全体集計 ---
    total = conn.execute("SELECT COUNT(*) FROM audit_records").fetchone()[0]
    if total == 0:
        print("検収記録が0件です。")
        conn.close()
        return

    verdict_rows = conn.execute(
        "SELECT verdict, COUNT(*) as cnt FROM audit_records GROUP BY verdict ORDER BY cnt DESC"
    ).fetchall()
    verdict_map = {r["verdict"]: r["cnt"] for r in verdict_rows}
    pass_cnt = verdict_map.get("PASS", 0)
    fail_cnt = verdict_map.get("FAIL", 0)
    cond_cnt = verdict_map.get("CONDITIONAL", 0)
    pass_rate = pass_cnt * 100.0 / total if total > 0 else 0.0

    # --- severity 分布 ---
    sev_rows = conn.execute(
        "SELECT COALESCE(severity, '(未設定)') as sev, COUNT(*) as cnt FROM audit_records GROUP BY severity ORDER BY sev"
    ).fetchall()

    # --- 直近N件PASS率 ---
    recent_n = getattr(args, "recent", 10)
    recent_rows = conn.execute(
        "SELECT id, subtask_id, cmd_id, verdict, severity, reviewers, created_at FROM audit_records ORDER BY id DESC LIMIT ?",
        (recent_n,),
    ).fetchall()
    recent_pass = sum(1 for r in recent_rows if r["verdict"] == "PASS")
    recent_rate = recent_pass * 100.0 / len(recent_rows) if recent_rows else 0.0

    # --- 足軽別PASS率 (JOIN subtasks for worker_id) ---
    worker_rows = conn.execute(
        """SELECT COALESCE(s.worker_id, '(不明)') as worker,
                  COUNT(*) as total,
                  SUM(CASE WHEN ar.verdict = 'PASS' THEN 1 ELSE 0 END) as pass_cnt
           FROM audit_records ar
           LEFT JOIN subtasks s ON ar.subtask_id = s.id
           GROUP BY s.worker_id
           ORDER BY total DESC"""
    ).fetchall()

    conn.close()

    if args.json:
        data = {
            "total": total,
            "pass": pass_cnt,
            "fail": fail_cnt,
            "conditional": cond_cnt,
            "pass_rate": round(pass_rate, 1),
            "recent_n": recent_n,
            "recent_pass_rate": round(recent_rate, 1),
            "severity": {r["sev"]: r["cnt"] for r in sev_rows},
            "by_worker": [
                {"worker": r["worker"], "total": r["total"], "pass": r["pass_cnt"],
                 "rate": round(r["pass_cnt"] * 100.0 / r["total"], 1) if r["total"] > 0 else 0}
                for r in worker_rows
            ],
            "recent": [
                {"id": r["id"], "subtask": r["subtask_id"], "cmd": r["cmd_id"],
                 "verdict": r["verdict"], "severity": r["severity"]}
                for r in recent_rows
            ],
        }
        print_json(data)
        return

    # --- CLI表示 ---
    print("═══════════════════════════════════════════════")
    print("  検収PASS率ダッシュボード (audit_records)")
    print("═══════════════════════════════════════════════")
    print()
    print(f"  総検収件数: {total}件")
    print(f"    PASS: {pass_cnt}  |  FAIL: {fail_cnt}  |  CONDITIONAL: {cond_cnt}")
    print(f"    全体PASS率: {pass_rate:.1f}%")
    print()
    print(f"  直近{recent_n}件PASS率: {recent_rate:.1f}% ({recent_pass}/{len(recent_rows)})")
    print()

    print("  severity分布:")
    for r in sev_rows:
        bar = "█" * r["cnt"]
        print(f"    {r['sev']:6s}: {r['cnt']:2d}件 {bar}")
    print()

    print("  足軽別PASS率:")
    for r in worker_rows:
        w_rate = r["pass_cnt"] * 100.0 / r["total"] if r["total"] > 0 else 0.0
        bar = "█" * r["pass_cnt"] + "░" * (r["total"] - r["pass_cnt"])
        print(f"    {r['worker']:12s}: {w_rate:5.1f}% ({r['pass_cnt']}/{r['total']}) {bar}")
    print()

    print(f"  直近{recent_n}件推移:")
    for r in reversed(recent_rows):
        mark = "✓" if r["verdict"] == "PASS" else ("✗" if r["verdict"] == "FAIL" else "△")
        sev = r["severity"] or "-"
        print(f"    #{r['id']:2d} {r['subtask_id']:16s} {r['cmd_id'] or '-':10s} {mark} {r['verdict']:12s} {sev}")
    print("═══════════════════════════════════════════════")

    # --- dashboard.md 自動更新 ---
    if getattr(args, "update_dashboard", False):
        _update_dashboard_md(total, pass_cnt, fail_cnt, cond_cnt, pass_rate,
                             recent_n, recent_rate, recent_pass, len(recent_rows),
                             sev_rows, worker_rows, recent_rows)


def _update_dashboard_md(total, pass_cnt, fail_cnt, cond_cnt, pass_rate,
                         recent_n, recent_rate, recent_pass, recent_total,
                         sev_rows, worker_rows, recent_rows) -> None:
    """dashboard.md に検収PASS率セクションを書き込む。"""
    from pathlib import Path
    from . import PROJECT_ROOT

    dashboard_path = PROJECT_ROOT / "dashboard.md"
    if not dashboard_path.exists():
        print(f"Warning: {dashboard_path} not found, skipping update.")
        return

    content = dashboard_path.read_text(encoding="utf-8")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    section_lines = [
        "## 検収PASS率 (自動生成)",
        "",
        f"最終更新: {ts}",
        "",
        f"| 指標 | 値 |",
        f"|------|-----|",
        f"| 総検収件数 | {total}件 |",
        f"| PASS | {pass_cnt} |",
        f"| FAIL | {fail_cnt} |",
        f"| CONDITIONAL | {cond_cnt} |",
        f"| 全体PASS率 | {pass_rate:.1f}% |",
        f"| 直近{recent_n}件PASS率 | {recent_rate:.1f}% ({recent_pass}/{recent_total}) |",
        "",
        "### severity分布",
        "",
        "| Severity | 件数 |",
        "|----------|------|",
    ]
    for r in sev_rows:
        section_lines.append(f"| {r['sev']} | {r['cnt']} |")

    section_lines.extend([
        "",
        "### 足軽別PASS率",
        "",
        "| Worker | PASS率 | PASS/Total |",
        "|--------|--------|------------|",
    ])
    for r in worker_rows:
        w_rate = r["pass_cnt"] * 100.0 / r["total"] if r["total"] > 0 else 0.0
        section_lines.append(f"| {r['worker']} | {w_rate:.1f}% | {r['pass_cnt']}/{r['total']} |")

    section_lines.extend([
        "",
        f"### 直近{recent_n}件推移",
        "",
        "| # | Subtask | CMD | Verdict | Severity |",
        "|---|---------|-----|---------|----------|",
    ])
    for r in reversed(recent_rows):
        sev = r["severity"] or "-"
        section_lines.append(f"| {r['id']} | {r['subtask_id']} | {r['cmd_id'] or '-'} | {r['verdict']} | {sev} |")

    section_lines.append("")
    new_section = "\n".join(section_lines)

    # Replace existing section or append
    marker_start = "## 検収PASS率 (自動生成)"
    marker_end_candidates = ["## ", "---"]

    if marker_start in content:
        start_idx = content.index(marker_start)
        rest = content[start_idx + len(marker_start):]
        end_idx = None
        for line_start in rest.split("\n"):
            if line_start.startswith("## ") and line_start != marker_start:
                end_idx = start_idx + len(marker_start) + rest.index(line_start)
                break
        if end_idx is not None:
            content = content[:start_idx] + new_section + "\n" + content[end_idx:]
        else:
            content = content[:start_idx] + new_section
    else:
        content = content.rstrip() + "\n\n" + new_section

    dashboard_path.write_text(content, encoding="utf-8")
    print(f"dashboard.md 更新完了: 検収PASS率セクション")


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
