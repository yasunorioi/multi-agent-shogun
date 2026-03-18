"""report サブコマンド — 報告管理。"""

import sys

from . import get_connection, now_iso, print_table, print_json, row_to_dict, _try_notify, fts5_upsert


def report_add(args) -> None:
    conn = get_connection()

    task = conn.execute("SELECT id FROM subtasks WHERE id = ?", (args.task_id,)).fetchone()
    if not task:
        conn.close()
        print(f"Error: subtask '{args.task_id}' not found.", file=sys.stderr)
        sys.exit(1)

    ts = now_iso()
    conn.execute(
        """INSERT INTO reports (worker_id, task_id, timestamp, status, summary, findings, files_modified, skill_candidate_name, skill_candidate_desc)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            args.worker_id,
            args.task_id,
            ts,
            args.status,
            args.summary,
            args.findings,
            args.files_modified,
            args.skill_name,
            args.skill_desc,
        ),
    )
    conn.commit()
    report_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    raw_text = f"{args.summary or ''} {args.findings or ''}".strip()
    fts5_upsert(conn, "report", str(report_id), args.task_id, "", args.worker_id or "", args.status or "", raw_text)
    conn.commit()
    conn.close()
    print(f"Created: report #{report_id} (task={args.task_id}, worker={args.worker_id})")
    _try_notify(f"📋 report #{report_id} ({args.status}) — {args.summary[:50]}",
                title=f"subtask {args.task_id}", tags=args.status)


def report_list(args) -> None:
    conn = get_connection()
    query = "SELECT id, task_id, worker_id, status, summary, timestamp FROM reports WHERE 1=1"
    params: list = []

    if args.subtask:
        query += " AND task_id = ?"
        params.append(args.subtask)
    if args.worker:
        query += " AND worker_id = ?"
        params.append(args.worker)
    if args.status:
        query += " AND status = ?"
        params.append(args.status)

    query += " ORDER BY id DESC LIMIT 20"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No reports found.")
        return

    headers = ["ID", "SUBTASK", "WORKER", "STATUS", "SUMMARY", "CREATED"]
    table_rows = []
    for r in rows:
        summary = r["summary"] or ""
        summary_short = summary[:40] if len(summary) > 40 else summary
        table_rows.append([
            str(r["id"]),
            r["task_id"],
            r["worker_id"],
            r["status"],
            summary_short,
            r["timestamp"],
        ])
    print_table(headers, table_rows, [6, 14, 12, 10, 40, 20])
