"""archive サブコマンド — 完了タスクのアーカイブ。"""

from datetime import datetime, timedelta, timezone

from . import get_connection


def archive_run(args) -> None:
    conn = get_connection()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

    target_cmds = conn.execute(
        "SELECT id FROM commands WHERE status = 'done' AND completed_at IS NOT NULL AND completed_at < ?",
        (cutoff,),
    ).fetchall()
    cmd_ids = [r["id"] for r in target_cmds]

    if not cmd_ids:
        conn.close()
        print(f"アーカイブ対象: 0件（{args.days}日以上前に完了したcmdなし）")
        return

    placeholders = ",".join("?" for _ in cmd_ids)
    sub_count = conn.execute(
        f"SELECT COUNT(*) FROM subtasks WHERE parent_cmd IN ({placeholders}) AND status = 'done'",
        cmd_ids,
    ).fetchone()[0]

    if args.dry_run:
        print(f"[dry-run] アーカイブ対象: commands {len(cmd_ids)}件, subtasks {sub_count}件（{args.days}日以上前に完了）")
        print(f"[dry-run] 対象cmd: {', '.join(cmd_ids[:10])}{'...' if len(cmd_ids) > 10 else ''}")
        conn.close()
        return

    conn.execute(
        f"UPDATE commands SET status = 'archived' WHERE id IN ({placeholders})",
        cmd_ids,
    )

    conn.execute(
        f"UPDATE subtasks SET status = 'archived' WHERE parent_cmd IN ({placeholders}) AND status = 'done'",
        cmd_ids,
    )

    conn.commit()
    conn.close()
    print(f"アーカイブ対象: {len(cmd_ids)}件（{args.days}日以上前に完了）")
    print(f"更新完了: commands {len(cmd_ids)}件, subtasks {sub_count}件 → archived")
