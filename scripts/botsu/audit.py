"""audit / stats サブコマンド — 監査・統計。"""

from datetime import datetime, timedelta, timezone

from . import get_connection, print_table, print_json, row_to_dict


def audit_list(args) -> None:
    conn = get_connection()
    if args.all:
        query = """SELECT id, parent_cmd, worker_id, status, audit_status, needs_audit, description
                   FROM subtasks WHERE needs_audit = 1
                   ORDER BY parent_cmd DESC, id"""
    else:
        query = """SELECT id, parent_cmd, worker_id, status, audit_status, needs_audit, description
                   FROM subtasks WHERE needs_audit = 1 AND (audit_status IS NULL OR audit_status = 'pending')
                   ORDER BY parent_cmd DESC, id"""
    rows = conn.execute(query).fetchall()
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
