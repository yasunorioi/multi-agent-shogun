#!/usr/bin/env python3
"""botsunichiroku_2ch.py — 没日録データの2ch DAT表示レイヤー (subtask_922+923/cmd_419 W5-a+b)

没日録DB (data/botsunichiroku.db) のデータを2ch DAT形式でレンダリングする。
スキーマ変更ゼロ、既存CLI完全互換。

参照:
  - docs/shogun/2ch_integration_design.md §2（スレッド分類）+ §4.2（tripコード）+ 付録A（サンプル出力）

使用方法:
  python3 scripts/botsunichiroku_2ch.py cmd_419         # 管理板: CMDスレッド表示
  python3 scripts/botsunichiroku_2ch.py --board kanri   # 管理板: スレッド一覧 (dat落ち含む)
  python3 scripts/botsunichiroku_2ch.py --board kanri --limit 10
  python3 scripts/botsunichiroku_2ch.py --board dreams  # 夢見板
  python3 scripts/botsunichiroku_2ch.py --board docs    # 書庫板
  python3 scripts/botsunichiroku_2ch.py --board docs --limit 20
  python3 scripts/botsunichiroku_2ch.py --board diary   # 日記板
  python3 scripts/botsunichiroku_2ch.py --board audit   # 監査板
  python3 scripts/botsunichiroku_2ch.py --board zatsudan           # 雑談板: スレ一覧
  python3 scripts/botsunichiroku_2ch.py --thread <thread_id>       # スレ内全レス表示
  python3 scripts/botsunichiroku_2ch.py --reply <thread_id> --author ashigaru2 --body "内容"
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# パス設定
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"
DREAMS_PATH = PROJECT_ROOT / "data" / "dreams.jsonl"

import sys  # noqa: E402
sys.path.insert(0, str(SCRIPT_DIR))

from botsu.nich import NAMES, fmt_ts, nametrip  # noqa: E402
from botsu.reply import do_reply_add  # noqa: E402

# ---------------------------------------------------------------------------
# 定数 (CLI表示固有)
# ---------------------------------------------------------------------------

RULE = "━" * 38
THIN_RULE = "───────────────"


# ---------------------------------------------------------------------------
# DB接続（CLI用 — sys.exitしない版）
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"没日録DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ---------------------------------------------------------------------------
# 管理板: CMDスレッド表示
# ---------------------------------------------------------------------------

def show_cmd_thread(cmd_id: str) -> None:
    conn = get_conn()
    try:
        cmd = conn.execute("SELECT * FROM commands WHERE id = ?", (cmd_id,)).fetchone()
        if cmd is None:
            print(f"Error: command '{cmd_id}' が見つかりません。")
            return

        subtasks = conn.execute(
            "SELECT * FROM subtasks WHERE parent_cmd = ? ORDER BY wave, id",
            (cmd_id,),
        ).fetchall()

        subtask_to_post: dict[str, int] = {}
        for i, st in enumerate(subtasks, 2):
            subtask_to_post[st["id"]] = i

        subtask_ids = tuple(st["id"] for st in subtasks)
        if subtask_ids:
            placeholders = ",".join("?" * len(subtask_ids))
            reports = conn.execute(
                f"SELECT * FROM reports WHERE task_id IN ({placeholders})"
                f" ORDER BY timestamp, id",
                subtask_ids,
            ).fetchall()
        else:
            reports = []

    finally:
        conn.close()

    cmd_summary = (cmd["command"] or "")[:40]
    print(RULE)
    print(f"【管理板】{cmd_id} — {cmd_summary}")
    print(RULE)
    print()

    author = cmd["assigned_karo"] or "roju"
    ts = fmt_ts(cmd["created_at"] or cmd["timestamp"])
    print(f"1 名前：{nametrip(author)} {ts}")
    project = cmd["project"] or "-"
    command = cmd["command"] or ""
    print(f"  [{project}] {command}")
    priority = cmd["priority"] or "-"
    status = cmd["status"] or "-"
    print(f"  priority: {priority} | status: {status}")
    if cmd["details"]:
        first_line = cmd["details"].strip().split("\n")[0][:60]
        print(f"  {first_line}")
    print(f"  {THIN_RULE}")
    print()

    post_num = 2
    for st in subtasks:
        worker = st["worker_id"] or "未割当"
        ts = fmt_ts(st["assigned_at"])
        print(f"{post_num} 名前：{nametrip(worker)} {ts}")
        st_id = st["id"]
        desc = (st["description"] or "")[:80]
        print(f"  [{st_id}] {desc}")
        wave = st["wave"] if st["wave"] is not None else "-"
        st_status = st["status"] or "-"
        print(f"  status: {st_status} | wave: {wave}")
        if st["blocked_by"]:
            refs = []
            for dep in st["blocked_by"].split(","):
                dep = dep.strip()
                ref_num = subtask_to_post.get(dep)
                refs.append(f">>{ref_num}" if ref_num else dep)
            print(f"  blocked_by: {', '.join(refs)}")
        if st["notes"]:
            note_first = st["notes"].strip().split("\n")[0][:60]
            print(f"  memo: {note_first}")
        print(f"  {THIN_RULE}")
        print()
        post_num += 1

    for rep in reports:
        worker = rep["worker_id"] or "名無し"
        ts = fmt_ts(rep["timestamp"])
        print(f"{post_num} 名前：{nametrip(worker)} {ts}")
        is_audit = (worker == "ohariko")
        label = "audit" if is_audit else "report"
        task_id = rep["task_id"] or "-"
        summary = (rep["summary"] or "")[:80]
        print(f"  [{label}] {task_id} {summary}")
        if rep["findings"]:
            finding_first = rep["findings"].strip().split("\n")[0][:70]
            print(f"  {finding_first}")
        if is_audit:
            print("  べ、別にあなたのために監査したんじゃないんだからね！")
        print(f"  {THIN_RULE}")
        print()
        post_num += 1

    print(f"  合計 {post_num - 1} レス")


# ---------------------------------------------------------------------------
# 管理板: スレッド一覧
# ---------------------------------------------------------------------------

def show_kanri_board(limit: int = 20) -> None:
    conn = get_conn()
    try:
        cmds = conn.execute(
            "SELECT id, command, project, status, priority, created_at, timestamp"
            " FROM commands WHERE status != 'archived' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        archived_cmds = conn.execute(
            "SELECT id, command, project, status, priority, created_at, timestamp"
            " FROM commands WHERE status = 'archived' ORDER BY id DESC LIMIT 10",
        ).fetchall()
        counts: dict[str, int] = {}
        for cmd in list(cmds) + list(archived_cmds):
            n_sub = conn.execute(
                "SELECT COUNT(*) FROM subtasks WHERE parent_cmd = ?", (cmd["id"],)
            ).fetchone()[0]
            counts[cmd["id"]] = n_sub + 1
    finally:
        conn.close()

    print(RULE)
    print("【管理板】スレッド一覧")
    print(RULE)
    print()

    if not cmds and not archived_cmds:
        print("  (スレッドなし)")
        return

    for i, cmd in enumerate(cmds, 1):
        cmd_id = cmd["id"]
        command = (cmd["command"] or "")[:38]
        project = cmd["project"] or "-"
        status = cmd["status"] or "-"
        ts = fmt_ts(cmd["created_at"] or cmd["timestamp"])[:16]
        res_count = counts.get(cmd_id, 1)
        print(f"{i:3d}. [{cmd_id}] {command}")
        print(f"       [{project}] status:{status}  {ts}  ({res_count}レス)")

    if archived_cmds:
        print()
        print("  ── dat落ち ──")
        for cmd in archived_cmds:
            cmd_id = cmd["id"]
            command = (cmd["command"] or "")[:38]
            project = cmd["project"] or "-"
            ts = fmt_ts(cmd["created_at"] or cmd["timestamp"])[:16]
            res_count = counts.get(cmd_id, 1)
            print(f"  [dat落ち] [{cmd_id}] {command}")
            print(f"            [{project}] archived  {ts}  ({res_count}レス)")

    print()
    active_count = len(cmds)
    dat_count = len(archived_cmds)
    summary = f"{active_count}スレッド表示中"
    if dat_count:
        summary += f" + dat落ち{dat_count}件"
    print(f"  {summary}")


# ---------------------------------------------------------------------------
# 夢見板: dreams.jsonl → 日次スレッドレンダリング
# ---------------------------------------------------------------------------

def show_dreams_board() -> None:
    print(RULE)
    print("【夢見板】獏の夢スレ")
    print(RULE)
    print()

    if not DREAMS_PATH.exists():
        print("  夢見板: まだ夢がありません")
        print("  （獏スクリプトが data/dreams.jsonl を生成するまでお待ちください）")
        return

    dreams: list[dict] = []
    try:
        with open(DREAMS_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    dreams.append(json.loads(line))
    except Exception as exc:
        print(f"  Error: dreams.jsonl 読み込み失敗: {exc}")
        return

    if not dreams:
        print("  夢見板: まだ夢がありません")
        return

    by_date: dict[str, list[dict]] = defaultdict(list)
    for d in dreams:
        ts = d.get("dreamt_at", "")
        date = ts[:10] if ts else "unknown"
        by_date[date].append(d)

    dates = sorted(by_date.keys(), reverse=True)[:7]

    for date in dates:
        day_dreams = by_date[date]
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            from botsu.nich import WEEKDAYS
            wd = WEEKDAYS[dt.weekday()]
            date_str = dt.strftime(f"%Y/%m/%d({wd})")
        except Exception:
            date_str = date

        print(f"── {date_str} ── ({len(day_dreams)}件)")
        print()

        for i, d in enumerate(day_dreams[:20], 1):
            ts_str = d.get("dreamt_at", "")
            ts = fmt_ts(ts_str)
            domain = d.get("domain", "-")
            query = d.get("query", "")
            score = d.get("relevance_score", 0)
            status = d.get("status", "-")

            print(f"{i} 名前：獏 ◆BAKU {ts}")
            print(f"  【{domain}】{query}")
            print(f"  relevance: {score} | status: {status}")

            ext = d.get("external_result", "")
            if ext:
                titles = re.findall(r'\[([^\]]{5,80})\]', ext)
                if titles:
                    print(f"  → {titles[0][:70]}")

            print(f"  {THIN_RULE}")
            print()

        if len(day_dreams) > 20:
            print(f"  ... 他 {len(day_dreams) - 20} 件")
        print()


# ---------------------------------------------------------------------------
# 日記板: diary_entries → エージェント別日記スレッド
# ---------------------------------------------------------------------------

def show_diary_board() -> None:
    conn = get_conn()
    try:
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='diary_entries'"
        ).fetchone()
        if not tbl:
            print(RULE)
            print("【日記板】エージェント日記")
            print(RULE)
            print()
            print("  日記板: diary_entries テーブルが存在しません")
            return

        total = conn.execute("SELECT COUNT(*) FROM diary_entries").fetchone()[0]
        if total == 0:
            print(RULE)
            print("【日記板】エージェント日記")
            print(RULE)
            print()
            print("  日記板: まだ記録がありません")
            return

        agents = conn.execute(
            "SELECT DISTINCT agent_id FROM diary_entries ORDER BY agent_id"
        ).fetchall()

        agent_entries: dict[str, list] = {}
        for ag in agents:
            aid = ag["agent_id"]
            rows = conn.execute(
                "SELECT * FROM diary_entries WHERE agent_id = ? ORDER BY id DESC LIMIT 20",
                (aid,),
            ).fetchall()
            agent_entries[aid] = list(rows)

    finally:
        conn.close()

    print(RULE)
    print("【日記板】エージェント日記")
    print(RULE)
    print()

    for aid, entries in agent_entries.items():
        print(f"── {nametrip(aid)} の日記スレ ({len(entries)}件) ──")
        print()
        for i, e in enumerate(entries, 1):
            ts = fmt_ts(e["created_at"])
            cmd_ref = f" [{e['cmd_id']}]" if e["cmd_id"] else ""
            subtask_ref = f" [{e['subtask_id']}]" if e["subtask_id"] else ""
            tags_str = f" #{'  #'.join(e['tags'].split(','))}" if e["tags"] else ""
            print(f"{i} 名前：{nametrip(aid)} {ts}")
            print(f"  【{e['date']}】{cmd_ref}{subtask_ref} {e['summary']}")
            for line in (e["body"] or "").strip().split("\n")[:2]:
                print(f"  {line[:80]}")
            if tags_str:
                print(f"  {tags_str}")
            print(f"  {THIN_RULE}")
            print()
        print()

    print(f"  合計 {total} 件の日記エントリ")


# ---------------------------------------------------------------------------
# 雑談板: thread_replies → 論議スレ
# ---------------------------------------------------------------------------

def ensure_thread_replies_table(conn: sqlite3.Connection) -> None:
    """thread_repliesテーブルが存在しない場合は作成する（既存テーブル変更なし）"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS thread_replies (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT    NOT NULL,
            board     TEXT    NOT NULL DEFAULT 'zatsudan',
            author    TEXT    NOT NULL,
            body      TEXT    NOT NULL,
            posted_at TEXT    NOT NULL
        )
    """)
    conn.commit()


def show_zatsudan_board(limit: int = 20) -> None:
    """雑談板: スレ一覧表示"""
    conn = get_conn()
    try:
        ensure_thread_replies_table(conn)
        threads = conn.execute(
            "SELECT thread_id, COUNT(*) AS reply_count,"
            " MIN(posted_at) AS created_at, MAX(posted_at) AS last_at"
            " FROM thread_replies WHERE board = 'zatsudan'"
            " GROUP BY thread_id ORDER BY last_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(DISTINCT thread_id) FROM thread_replies WHERE board = 'zatsudan'"
        ).fetchone()[0]
    finally:
        conn.close()

    print(RULE)
    print("【雑談板】論議スレ一覧")
    print(RULE)
    print()

    if not threads:
        print("  雑談板: スレッドがありません")
        print("  (--reply <thread_id> --author <name> --body <text> でスレを立てられます)")
        return

    for i, th in enumerate(threads, 1):
        thread_id = th["thread_id"]
        reply_count = th["reply_count"]
        last_at = fmt_ts(th["last_at"])[:16]
        created_at = fmt_ts(th["created_at"])[:16]
        print(f"{i:3d}. 【{thread_id}】")
        print(f"       作成: {created_at}  最終: {last_at}  ({reply_count}レス)")

    print()
    print(f"  {len(threads)}スレッド表示中 (全{total}スレッド)")


def show_thread(thread_id: str) -> None:
    """指定スレのレスを全件DAT形式で表示"""
    conn = get_conn()
    try:
        ensure_thread_replies_table(conn)
        replies = conn.execute(
            "SELECT * FROM thread_replies WHERE thread_id = ? ORDER BY id",
            (thread_id,),
        ).fetchall()
    finally:
        conn.close()

    print(RULE)
    print(f"【雑談板】スレ: {thread_id}")
    print(RULE)
    print()

    if not replies:
        print(f"  スレ '{thread_id}' のレスがありません")
        return

    for i, rep in enumerate(replies, 1):
        author = rep["author"]
        ts = fmt_ts(rep["posted_at"])
        body = rep["body"]
        print(f"{i} 名前：{nametrip(author)} {ts}")
        for line in body.strip().split("\n"):
            print(f"  {line[:100]}")
        print(f"  {THIN_RULE}")
        print()

    print(f"  合計 {len(replies)} レス")


def post_reply(thread_id: str, author: str, body: str) -> None:
    """スレにレスを投稿する（botsu.reply.do_reply_add 経由）"""
    if not thread_id or not author or not body:
        raise ValueError("thread_id, author, body はすべて必須です")
    reply_id = do_reply_add(thread_id, "zatsudan", author, body)
    print(f"[zatsudan] {thread_id} にレスを投稿しました (author: {author}, reply #{reply_id})")


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="没日録データを2ch DAT形式でレンダリングする表示レイヤー",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python3 scripts/botsunichiroku_2ch.py cmd_419
  python3 scripts/botsunichiroku_2ch.py --board kanri
  python3 scripts/botsunichiroku_2ch.py --board kanri --limit 10
  python3 scripts/botsunichiroku_2ch.py --board dreams
  python3 scripts/botsunichiroku_2ch.py --board senryaku
  python3 scripts/botsunichiroku_2ch.py --board houkoku
  python3 scripts/botsunichiroku_2ch.py --board ofure
  python3 scripts/botsunichiroku_2ch.py --board zatsudan
  python3 scripts/botsunichiroku_2ch.py --thread <thread_id>
  python3 scripts/botsunichiroku_2ch.py --reply <thread_id> --author ashigaru2 --body "内容"
        """,
    )
    parser.add_argument(
        "cmd_id",
        nargs="?",
        default=None,
        help="表示するCMD ID (例: cmd_419)",
    )
    parser.add_argument(
        "--board",
        choices=["kanri", "dreams", "diary", "zatsudan"],
        help="板を指定 (kanri=管理板, dreams=夢見板, diary=日記板, zatsudan=雑談板)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="板一覧の最大表示件数 (デフォルト: 20)",
    )
    parser.add_argument(
        "--thread",
        metavar="THREAD_ID",
        help="雑談板: 指定スレの全レスをDAT形式で表示",
    )
    parser.add_argument(
        "--reply",
        metavar="THREAD_ID",
        help="雑談板: 指定スレにレスを投稿 (--author, --body と組み合わせて使用)",
    )
    parser.add_argument(
        "--author",
        metavar="AGENT_ID",
        help="--reply 時の投稿者エージェントID (例: ashigaru2)",
    )
    parser.add_argument(
        "--body",
        metavar="TEXT",
        help="--reply 時の投稿本文",
    )
    args = parser.parse_args()

    if args.board == "kanri":
        show_kanri_board(args.limit)
    elif args.board == "dreams":
        show_dreams_board()
    elif args.board == "diary":
        show_diary_board()
    elif args.board == "zatsudan":
        show_zatsudan_board(args.limit)
    elif args.thread:
        show_thread(args.thread)
    elif args.reply:
        if not args.author or not args.body:
            parser.error("--reply には --author と --body が必要です")
        post_reply(args.reply, args.author, args.body)
    elif args.cmd_id:
        show_cmd_thread(args.cmd_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
