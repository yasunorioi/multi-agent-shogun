"""botsu.check — 矛盾・放置検出 / カバレッジチェック (subtask_916/cmd_419 W2-b)

tools/kousatsu/main.py GET /check/orphans, GET /check/coverage のロジックをCLI化。
Docker不要で没日録DB（botsunichiroku.db）に直接クエリする。

参照:
  - tools/kousatsu/main.py : GET /check/orphans, GET /check/coverage（ロジック移植元）
  - docs/shogun/2ch_integration_design.md 付録B : CLI置換対応表
"""

from __future__ import annotations

import sys
from datetime import datetime

from botsu import get_connection
from botsu.search import _extract_keywords


# ---------------------------------------------------------------------------
# check orphans  (main.py GET /check/orphans 移植)
# ---------------------------------------------------------------------------

def check_orphans(args) -> None:
    """矛盾・放置タスクを検出する（4種類のチェック）。

    Args:
        args: argparse.Namespace (未使用。将来の拡張用)
    """
    conn = get_connection()
    checks: list[dict] = []
    try:
        # (a) 全subtaskがdoneだがcmdがdoneでない
        rows_a = conn.execute(
            """
            SELECT c.id AS cmd_id, c.status, COUNT(s.id) AS subtask_count
            FROM commands c
            JOIN subtasks s ON s.parent_cmd = c.id
            WHERE c.status != 'done'
            GROUP BY c.id
            HAVING COUNT(s.id) > 0
               AND COUNT(s.id) = SUM(CASE WHEN s.status = 'done' THEN 1 ELSE 0 END)
            """
        ).fetchall()
        checks.append({
            "check_type": "cmd_all_subtasks_done_but_pending",
            "description": "全subtaskがdoneだがcmdがdoneでない",
            "count": len(rows_a),
            "items": [
                {"cmd_id": r["cmd_id"], "status": r["status"], "subtask_count": r["subtask_count"]}
                for r in rows_a
            ],
        })

        # (b) 7日以上pendingのcmd
        rows_b = conn.execute(
            """
            SELECT id AS cmd_id, status, created_at
            FROM commands
            WHERE status = 'pending'
              AND created_at <= datetime('now', '-7 days')
            """
        ).fetchall()
        checks.append({
            "check_type": "cmd_pending_over_7_days",
            "description": "7日以上pendingのcmd",
            "count": len(rows_b),
            "items": [
                {"cmd_id": r["cmd_id"], "status": r["status"], "created_at": r["created_at"]}
                for r in rows_b
            ],
        })

        # (c) 7日以上assignedのsubtask
        rows_c = conn.execute(
            """
            SELECT id AS subtask_id, parent_cmd, worker_id, assigned_at
            FROM subtasks
            WHERE status = 'assigned'
              AND assigned_at <= datetime('now', '-7 days')
            """
        ).fetchall()
        checks.append({
            "check_type": "subtask_assigned_over_7_days",
            "description": "7日以上assignedのsubtask",
            "count": len(rows_c),
            "items": [
                {
                    "subtask_id": r["subtask_id"],
                    "parent_cmd": r["parent_cmd"],
                    "worker_id": r["worker_id"],
                    "assigned_at": r["assigned_at"],
                }
                for r in rows_c
            ],
        })

        # (d) doneなのにreportが0件のsubtask
        rows_d = conn.execute(
            """
            SELECT s.id AS subtask_id, s.parent_cmd, s.worker_id
            FROM subtasks s
            LEFT JOIN reports r ON r.task_id = s.id
            WHERE s.status = 'done'
              AND r.id IS NULL
            """
        ).fetchall()
        checks.append({
            "check_type": "subtask_done_without_report",
            "description": "doneなのにreportが0件のsubtask",
            "count": len(rows_d),
            "items": [
                {
                    "subtask_id": r["subtask_id"],
                    "parent_cmd": r["parent_cmd"],
                    "worker_id": r["worker_id"],
                }
                for r in rows_d
            ],
        })

    finally:
        conn.close()

    total = sum(c["count"] for c in checks)
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # ── 表示 ─────────────────────────────────────────────────────
    print(f"=== check orphans  ({ts}) ===")
    print(f"Total issues: {total}")
    print()

    for c in checks:
        icon = "✓" if c["count"] == 0 else "⚠"
        print(f"{icon} [{c['check_type']}]")
        print(f"  {c['description']}: {c['count']}件")
        for item in c["items"][:5]:
            parts = "    " + "  ".join(f"{k}={v}" for k, v in item.items())
            print(parts)
        if len(c["items"]) > 5:
            print(f"    ... and {len(c['items']) - 5} more")
        print()

    if total == 0:
        print("ORPHANS_CLEAN: 矛盾・放置なし ✓")
    else:
        print(f"ORPHANS_FOUND:{total}  — 老中への報告を推奨")


# ---------------------------------------------------------------------------
# check coverage  (main.py GET /check/coverage 移植)
# ---------------------------------------------------------------------------

def check_coverage(args) -> None:
    """cmd指示文と報告文のキーワードカバレッジを検出する。

    Args:
        args: argparse.Namespace
            - cmd_id : 対象コマンドID (例: cmd_419)
    """
    cmd_id: str = args.cmd_id

    conn = get_connection()
    try:
        # 1. cmd取得
        cmd_row = conn.execute(
            "SELECT command, details FROM commands WHERE id = ?",
            (cmd_id,),
        ).fetchone()
        if cmd_row is None:
            print(f"Error: Command '{cmd_id}' が見つかりません。", file=sys.stderr)
            sys.exit(1)

        instruction_text = " ".join(
            part for part in [cmd_row["command"], cmd_row["details"]] if part
        )

        # 2. 指示文キーワード抽出
        instruction_keywords = _extract_keywords(instruction_text, max_kw=30)

        # 3. 該当cmdの全subtask報告summaryを取得
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

        # 4. 報告文キーワード抽出
        report_text = " ".join(r["summary"] for r in report_rows if r["summary"])
        report_keywords = _extract_keywords(report_text, max_kw=100) if report_text.strip() else []

        # 5. 差分計算
        report_kw_set = set(report_keywords)
        missing_keywords = [kw for kw in instruction_keywords if kw not in report_kw_set]
        covered = len(instruction_keywords) - len(missing_keywords)
        coverage_ratio = (
            round(covered / len(instruction_keywords), 2) if instruction_keywords else 1.0
        )

    finally:
        conn.close()

    # ── 表示 ─────────────────────────────────────────────────────
    print(f"=== check coverage: {cmd_id} ===")
    print(f"Subtasks: {subtask_count}  Reports: {report_count}")

    ikw_display = ", ".join(instruction_keywords[:10])
    if len(instruction_keywords) > 10:
        ikw_display += f" ... (+{len(instruction_keywords) - 10})"
    print(f"Instruction keywords({len(instruction_keywords)}): {ikw_display}")

    print(f"Coverage ratio: {coverage_ratio:.2f}  ({covered}/{len(instruction_keywords)})")

    if missing_keywords:
        print(f"\nMissing keywords({len(missing_keywords)}): {', '.join(missing_keywords)}")

    print()
    if coverage_ratio >= 0.7:
        print("✓ coverage_ratio >= 0.7: OK")
    else:
        print("⚠ coverage_ratio < 0.7: 言及漏れの可能性あり — findingsに[高札分析]で記載推奨")
