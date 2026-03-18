#!/usr/bin/env python3
"""
botsunichiroku.py - CLI tool for the multi-agent-shogun SQLite database (没日録).

Provides subcommands to manage commands, subtasks, reports, agents, and counters
stored in data/botsunichiroku.db.

Usage:
    python3 scripts/botsunichiroku.py cmd list [--status STATUS] [--project PROJECT] [--json]
    python3 scripts/botsunichiroku.py cmd add "description" [--project PROJECT] [--priority PRIORITY] [--karo roju|midaidokoro]
    python3 scripts/botsunichiroku.py cmd update CMD_ID --status STATUS
    python3 scripts/botsunichiroku.py cmd show CMD_ID [--json]

    python3 scripts/botsunichiroku.py subtask list [--cmd CMD_ID] [--worker WORKER] [--status STATUS] [--needs-audit 0|1] [--audit-status STATUS] [--json]
    python3 scripts/botsunichiroku.py subtask add CMD_ID "description" [--worker WORKER] [--wave N] [--project PROJECT] [--target-path PATH] [--needs-audit] [--blocked-by ID1,ID2]
    python3 scripts/botsunichiroku.py subtask update SUBTASK_ID [--status STATUS] [--worker WORKER] [--audit-status {pending,in_progress,done}] [--blocked-by ID1,ID2]
    python3 scripts/botsunichiroku.py subtask show SUBTASK_ID [--json]

    python3 scripts/botsunichiroku.py report add TASK_ID WORKER_ID --status STATUS --summary "text" [--findings JSON] [--files-modified JSON] [--skill-name NAME] [--skill-desc DESC]
    python3 scripts/botsunichiroku.py report list [--subtask SUBTASK_ID] [--worker WORKER_ID] [--status STATUS] [--json]

    python3 scripts/botsunichiroku.py agent list [--role ROLE] [--json]
    python3 scripts/botsunichiroku.py agent update AGENT_ID --status STATUS [--task TASK_ID]

    python3 scripts/botsunichiroku.py counter next NAME
    python3 scripts/botsunichiroku.py counter show [--json]

    python3 scripts/botsunichiroku.py audit list [--all] [--json]

    python3 scripts/botsunichiroku.py stats [--json]
    python3 scripts/botsunichiroku.py archive [--days N] [--dry-run]

    python3 scripts/botsunichiroku.py dashboard add SECTION CONTENT [--cmd CMD_ID] [--tags TAG1,TAG2] [--status STATUS]
    python3 scripts/botsunichiroku.py dashboard list [--section SECTION] [--limit N] [--cmd CMD_ID]
    python3 scripts/botsunichiroku.py dashboard search KEYWORD

    python3 scripts/botsunichiroku.py diary add AGENT_ID --summary "要約" --body "本文" [--cmd CMD_ID] [--subtask SUBTASK_ID] [--tags tag1,tag2]
    python3 scripts/botsunichiroku.py diary list [--agent AGENT_ID] [--date YYYY-MM-DD] [--cmd CMD_ID] [--limit N] [--json]
    python3 scripts/botsunichiroku.py diary show DIARY_ID [--json]
    python3 scripts/botsunichiroku.py diary today [--agent AGENT_ID]

    python3 scripts/botsunichiroku.py kenchi add ID NAME --category CATEGORY --description DESC --path PATH [--depends-on DEPS] [--called-by CALLERS] [--notes NOTES]
    python3 scripts/botsunichiroku.py kenchi list [--category CATEGORY] [--json]
    python3 scripts/botsunichiroku.py kenchi show ID [--json]
    python3 scripts/botsunichiroku.py kenchi update ID [--name NAME] [--description DESC] [--depends-on DEPS] [--called-by CALLERS] [--notes NOTES]
    python3 scripts/botsunichiroku.py kenchi search KEYWORD [--json]
    python3 scripts/botsunichiroku.py kenchi delete ID

    python3 scripts/botsunichiroku.py search QUERY [--limit N] [--project PROJECT]
"""

import argparse
import sys

from botsu.cmd import cmd_list, cmd_add, cmd_update, cmd_show
from botsu.subtask import subtask_list, subtask_add, subtask_update, subtask_show
from botsu.report import report_add, report_list
from botsu.agent import agent_list, agent_update
from botsu.counter import counter_next, counter_show
from botsu.audit import audit_list, stats_show
from botsu.archive import archive_run
from botsu.diary import diary_add, diary_list, diary_show, diary_today
from botsu.kenchi import kenchi_add, kenchi_list, kenchi_show, kenchi_update, kenchi_search, kenchi_delete
from botsu.dashboard import dashboard_add, dashboard_list, dashboard_search
from botsu.search import search


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="botsunichiroku",
        description="CLI tool for the multi-agent-shogun database (没日録 botsunichiroku.db)",
    )
    top_sub = parser.add_subparsers(dest="entity", required=True, help="Entity to manage")

    # === cmd ===
    cmd_parser = top_sub.add_parser("cmd", help="Manage commands")
    cmd_sub = cmd_parser.add_subparsers(dest="action", required=True)

    p = cmd_sub.add_parser("list", help="List commands")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--project", help="Filter by project")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_list)

    p = cmd_sub.add_parser("add", help="Add a new command")
    p.add_argument("description", help="Short description of the command")
    p.add_argument("--project", help="Project name (e.g., arsprout, shogun)")
    p.add_argument("--priority", default="medium", choices=["critical", "high", "medium", "low"], help="Priority level")
    p.add_argument("--karo", choices=["roju", "midaidokoro"], help="Assign to specific karo")
    p.add_argument("--file", dest="details_file", help="Read details from file")
    p.add_argument("--stdin", dest="details_stdin", action="store_true", help="Read details from stdin")
    p.set_defaults(func=cmd_add)

    p = cmd_sub.add_parser("update", help="Update command status")
    p.add_argument("cmd_id", help="Command ID (e.g., cmd_083)")
    p.add_argument("--status", required=True, choices=["pending", "acknowledged", "in_progress", "done", "cancelled", "archived"], help="New status")
    p.set_defaults(func=cmd_update)

    p = cmd_sub.add_parser("show", help="Show command details")
    p.add_argument("cmd_id", help="Command ID (e.g., cmd_083)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_show)

    # === subtask ===
    subtask_parser = top_sub.add_parser("subtask", help="Manage subtasks")
    subtask_sub = subtask_parser.add_subparsers(dest="action", required=True)

    p = subtask_sub.add_parser("list", help="List subtasks")
    p.add_argument("--cmd", help="Filter by parent command ID")
    p.add_argument("--worker", help="Filter by worker ID")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--needs-audit", type=int, choices=[0, 1], help="Filter by needs_audit (0 or 1)")
    p.add_argument("--audit-status", choices=["pending", "in_progress", "done", "rejected"], help="Filter by audit status")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=subtask_list)

    p = subtask_sub.add_parser("add", help="Add a new subtask")
    p.add_argument("cmd_id", help="Parent command ID (e.g., cmd_083)")
    p.add_argument("description", help="Subtask description")
    p.add_argument("--worker", help="Assign to worker (e.g., ashigaru1)")
    p.add_argument("--wave", type=int, default=1, help="Wave number (default: 1)")
    p.add_argument("--project", help="Project name")
    p.add_argument("--target-path", help="Target working directory")
    p.add_argument("--needs-audit", action="store_true", help="Mark as requiring ohariko audit")
    p.add_argument("--blocked-by", help="Comma-separated subtask IDs this task depends on (e.g., subtask_200,subtask_201). Forces status=blocked.")
    p.set_defaults(func=subtask_add)

    p = subtask_sub.add_parser("update", help="Update subtask status")
    p.add_argument("subtask_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("--status", choices=["pending", "assigned", "in_progress", "done", "blocked", "cancelled", "archived"], help="New status")
    p.add_argument("--worker", help="Assign/reassign to worker")
    p.add_argument("--audit-status", choices=["pending", "in_progress", "done"], help="Set audit status")
    p.add_argument("--blocked-by", help="Set/update blocked_by dependencies (comma-separated subtask IDs, or empty string to clear)")
    p.set_defaults(func=subtask_update)

    p = subtask_sub.add_parser("show", help="Show subtask details")
    p.add_argument("subtask_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=subtask_show)

    # === report ===
    report_parser = top_sub.add_parser("report", help="Manage reports")
    report_sub = report_parser.add_subparsers(dest="action", required=True)

    p = report_sub.add_parser("add", help="Add a report")
    p.add_argument("task_id", help="Subtask ID (e.g., subtask_191)")
    p.add_argument("worker_id", help="Worker ID (e.g., ashigaru1)")
    p.add_argument("--status", required=True, choices=["done", "blocked", "error"], help="Report status")
    p.add_argument("--summary", required=True, help="Summary text")
    p.add_argument("--findings", help="Findings as JSON array string")
    p.add_argument("--files-modified", help="Modified files as JSON array string")
    p.add_argument("--skill-name", help="Skill candidate name")
    p.add_argument("--skill-desc", help="Skill candidate description")
    p.set_defaults(func=report_add)

    p = report_sub.add_parser("list", help="List reports")
    p.add_argument("--subtask", help="Filter by subtask ID")
    p.add_argument("--worker", help="Filter by worker ID")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=report_list)

    # === agent ===
    agent_parser = top_sub.add_parser("agent", help="Manage agents")
    agent_sub = agent_parser.add_subparsers(dest="action", required=True)

    p = agent_sub.add_parser("list", help="List agents")
    p.add_argument("--role", choices=["shogun", "karo", "ashigaru"], help="Filter by role")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=agent_list)

    p = agent_sub.add_parser("update", help="Update agent status")
    p.add_argument("agent_id", help="Agent ID (e.g., ashigaru1)")
    p.add_argument("--status", required=True, choices=["idle", "busy", "error", "offline"], help="New status")
    p.add_argument("--task", help="Current task ID (use 'none' to clear)")
    p.set_defaults(func=agent_update)

    # === counter ===
    counter_parser = top_sub.add_parser("counter", help="Manage counters")
    counter_sub = counter_parser.add_subparsers(dest="action", required=True)

    p = counter_sub.add_parser("next", help="Atomically increment and return next value")
    p.add_argument("name", help="Counter name (e.g., cmd_id, subtask_id)")
    p.set_defaults(func=counter_next)

    p = counter_sub.add_parser("show", help="Show all counters")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=counter_show)

    # === audit ===
    audit_parser = top_sub.add_parser("audit", help="Manage audits")
    audit_sub = audit_parser.add_subparsers(dest="action", required=True)

    p = audit_sub.add_parser("list", help="List audit items (default: pending only)")
    p.add_argument("--all", action="store_true", help="Show all audit items (not just pending)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=audit_list)

    # === stats ===
    p = top_sub.add_parser("stats", help="Show database statistics")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=stats_show)

    # === archive ===
    p = top_sub.add_parser("archive", help="Archive old completed commands")
    p.add_argument("--days", type=int, default=7, help="Archive commands completed more than N days ago (default: 7)")
    p.add_argument("--dry-run", action="store_true", help="Show what would be archived without making changes")
    p.set_defaults(func=archive_run)

    # === dashboard ===
    dashboard_parser = top_sub.add_parser("dashboard", help="Manage dashboard entries")
    dashboard_sub = dashboard_parser.add_subparsers(dest="action", required=True)

    p = dashboard_sub.add_parser("add", help="Add a dashboard entry")
    p.add_argument("section", help="Section name (e.g., 戦果, スキル候補, findings, 殿裁定, ブロック事項)")
    p.add_argument("content", help="Entry content text")
    p.add_argument("--cmd", help="Related command ID (e.g., cmd_249)", default=None)
    p.add_argument("--tags", help="Comma-separated tags (e.g., OTA,Arduino)", default=None)
    p.add_argument("--status", help="Entry status (e.g., done, adopted, rejected, resolved, frozen)", default=None)
    p.set_defaults(func=dashboard_add)

    p = dashboard_sub.add_parser("list", help="List dashboard entries")
    p.add_argument("--section", help="Filter by section name", default=None)
    p.add_argument("--limit", type=int, default=20, help="Max entries to show (default: 20)")
    p.add_argument("--cmd", help="Filter by command ID", default=None)
    p.set_defaults(func=dashboard_list)

    p = dashboard_sub.add_parser("search", help="Search dashboard entries by keyword")
    p.add_argument("keyword", help="Keyword to search in content")
    p.set_defaults(func=dashboard_search)

    # === diary ===
    diary_parser = top_sub.add_parser("diary", help="Manage diary entries (思考記録)")
    diary_sub = diary_parser.add_subparsers(dest="action", required=True)

    p = diary_sub.add_parser("add", help="Add a diary entry")
    p.add_argument("agent_id", help="Agent ID (e.g., ashigaru1, roju)")
    p.add_argument("--summary", required=True, help="1-line summary")
    p.add_argument("--body", required=True, help="Body text (思考過程・判断理由)")
    p.add_argument("--cmd", help="Related command ID (e.g., cmd_414)", default=None)
    p.add_argument("--subtask", help="Related subtask ID", default=None)
    p.add_argument("--tags", help="Comma-separated tags", default=None)
    p.set_defaults(func=diary_add)

    p = diary_sub.add_parser("list", help="List diary entries")
    p.add_argument("--agent", help="Filter by agent ID")
    p.add_argument("--date", help="Filter by date (YYYY-MM-DD)")
    p.add_argument("--cmd", help="Filter by command ID")
    p.add_argument("--limit", type=int, default=20, help="Max entries (default: 20)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=diary_list)

    p = diary_sub.add_parser("show", help="Show diary entry details")
    p.add_argument("diary_id", type=int, help="Diary entry ID")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=diary_show)

    p = diary_sub.add_parser("today", help="Show today's diary entries (コンパクション復帰用)")
    p.add_argument("--agent", help="Filter by agent ID")
    p.set_defaults(func=diary_today)

    # === kenchi (検地帳) ===
    kenchi_parser = top_sub.add_parser("kenchi", help="検地帳 — リソース台帳管理")
    kenchi_sub = kenchi_parser.add_subparsers(dest="action", required=True)

    p = kenchi_sub.add_parser("add", help="Register a resource")
    p.add_argument("id", help="Resource ID (e.g. scripts/notify.py)")
    p.add_argument("name", help="Human-readable name")
    p.add_argument("--category", required=True, choices=["script", "config", "api", "lib", "db", "doc", "infra"], help="Resource category")
    p.add_argument("--description", required=True, help="What it does")
    p.add_argument("--path", required=True, help="File path")
    p.add_argument("--depends-on", help="Dependencies (JSON array or comma-separated)")
    p.add_argument("--called-by", help="Callers (JSON array or comma-separated)")
    p.add_argument("--notes", help="Additional notes")
    p.set_defaults(func=kenchi_add)

    p = kenchi_sub.add_parser("list", help="List resources")
    p.add_argument("--category", help="Filter by category")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=kenchi_list)

    p = kenchi_sub.add_parser("show", help="Show resource details")
    p.add_argument("id", help="Resource ID")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=kenchi_show)

    p = kenchi_sub.add_parser("update", help="Update a resource")
    p.add_argument("id", help="Resource ID")
    p.add_argument("--name", help="New name")
    p.add_argument("--category", help="New category")
    p.add_argument("--description", help="New description")
    p.add_argument("--path", help="New path")
    p.add_argument("--depends-on", help="New dependencies")
    p.add_argument("--called-by", help="New callers")
    p.add_argument("--notes", help="New notes")
    p.set_defaults(func=kenchi_update)

    p = kenchi_sub.add_parser("search", help="Search resources by keyword")
    p.add_argument("keyword", help="Search keyword")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=kenchi_search)

    p = kenchi_sub.add_parser("delete", help="Delete a resource")
    p.add_argument("id", help="Resource ID")
    p.set_defaults(func=kenchi_delete)

    # === search ===
    p = top_sub.add_parser(
        "search",
        help="FTS5全文検索 (search_index テーブル)",
    )
    p.add_argument("query", help="検索クエリ")
    p.add_argument("--limit", type=int, default=20, metavar="N", help="最大返却件数 (デフォルト: 20)")
    p.add_argument("--project", metavar="PROJECT", help="projectで絞り込み")
    p.set_defaults(func=search)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
