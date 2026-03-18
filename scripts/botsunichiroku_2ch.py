#!/usr/bin/env python3
"""botsunichiroku_2ch.py — 没日録データの2ch DAT表示レイヤー (subtask_922/cmd_419 W5-a)

没日録DB (data/botsunichiroku.db) のデータを2ch DAT形式でレンダリングする。
スキーマ変更ゼロ、既存CLI完全互換。

参照:
  - docs/shogun/2ch_integration_design.md §2（スレッド分類）+ §4.2（tripコード）+ 付録A（サンプル出力）

使用方法:
  python3 scripts/botsunichiroku_2ch.py cmd_419         # 管理板: CMDスレッド表示
  python3 scripts/botsunichiroku_2ch.py --board kanri   # 管理板: スレッド一覧
  python3 scripts/botsunichiroku_2ch.py --board kanri --limit 10
  python3 scripts/botsunichiroku_2ch.py --board dreams  # 夢見板
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

# ---------------------------------------------------------------------------
# 定数 (付録A準拠)
# ---------------------------------------------------------------------------

RULE = "━" * 38
THIN_RULE = "───────────────"

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

# tripコード (§4.2準拠)
TRIPS: dict[str, str] = {
    "shogun":    "◆SHGN",
    "karo-roju": "◆ROJU",
    "roju":      "◆ROJU",
    "ashigaru1": "◆ASH1",
    "ashigaru2": "◆ASH2",
    "ashigaru3": "◆ASH3",
    "ashigaru4": "◆ASH4",
    "ashigaru5": "◆ASH5",
    "ashigaru6": "◆HYG6",
    "gunshi":    "◆GNSH",
    "ohariko":   "◆OHRK",
    "baku":      "◆BAKU",
}

# 表示名
NAMES: dict[str, str] = {
    "shogun":    "将軍",
    "karo-roju": "老中",
    "roju":      "老中",
    "ashigaru1": "足軽1",
    "ashigaru2": "足軽2",
    "ashigaru3": "足軽3",
    "ashigaru4": "足軽4",
    "ashigaru5": "足軽5",
    "ashigaru6": "部屋子1",
    "gunshi":    "軍師",
    "ohariko":   "お針子",
    "baku":      "獏",
}


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"没日録DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def fmt_ts(ts_str: str | None) -> str:
    """ISO timestamp → 2ch形式 YYYY/MM/DD(曜) HH:MM:SS"""
    if not ts_str:
        return "----/--/--(-) --:--:--"
    try:
        # タイムゾーン・マイクロ秒除去
        ts_clean = ts_str.split("+")[0].split("Z")[0]
        if "." in ts_clean:
            ts_clean = ts_clean.split(".")[0]
        dt = datetime.strptime(ts_clean, "%Y-%m-%dT%H:%M:%S")
        wd = WEEKDAYS[dt.weekday()]
        return dt.strftime(f"%Y/%m/%d({wd}) %H:%M:%S")
    except Exception:
        return ts_str[:19] if len(ts_str) >= 10 else "----/--/--(-) --:--:--"


def agent_name(agent_id: str | None) -> str:
    if not agent_id:
        return "名無し"
    return NAMES.get(agent_id, agent_id)


def trip(agent_id: str | None) -> str:
    if not agent_id:
        return ""
    return TRIPS.get(agent_id, f"◆{agent_id[:4].upper()}")


def nametrip(agent_id: str | None) -> str:
    n = agent_name(agent_id)
    t = trip(agent_id)
    return f"{n} {t}" if t else n


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

        # subtask_id → post番号マッピング (blocked_by の >>N参照用)
        subtask_to_post: dict[str, int] = {}
        for i, st in enumerate(subtasks, 2):
            subtask_to_post[st["id"]] = i

        # reports (subtaskに紐づくもの)
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

    # ── ヘッダー ─────────────────────────────────
    cmd_summary = (cmd["command"] or "")[:40]
    print(RULE)
    print(f"【管理板】{cmd_id} — {cmd_summary}")
    print(RULE)
    print()

    # ── >>1: CMD本体 (付録A §1準拠) ──────────────
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

    # ── >>2~: subtasks (時系列順) ─────────────────
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

    # ── reports / audits ──────────────────────────
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
            " FROM commands ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        # 各CMDのレス数（subtask数 + report数）
        counts: dict[str, int] = {}
        for cmd in cmds:
            n_sub = conn.execute(
                "SELECT COUNT(*) FROM subtasks WHERE parent_cmd = ?", (cmd["id"],)
            ).fetchone()[0]
            counts[cmd["id"]] = n_sub + 1  # +1 for >>1 (CMD本体)
    finally:
        conn.close()

    print(RULE)
    print("【管理板】スレッド一覧")
    print(RULE)
    print()

    if not cmds:
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
    print()
    print(f"  {len(cmds)}スレッド表示中")


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

    # dreamt_at の日付でグループ化
    by_date: dict[str, list[dict]] = defaultdict(list)
    for d in dreams:
        ts = d.get("dreamt_at", "")
        date = ts[:10] if ts else "unknown"
        by_date[date].append(d)

    # 最新日付から最大7日分表示
    dates = sorted(by_date.keys(), reverse=True)[:7]

    for date in dates:
        day_dreams = by_date[date]
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
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

            # external_result から [タイトル] を1件抽出して表示
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
        choices=["kanri", "dreams"],
        help="板を指定 (kanri=管理板一覧, dreams=夢見板)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="管理板一覧の最大表示件数 (デフォルト: 20)",
    )
    args = parser.parse_args()

    if args.board == "kanri":
        show_kanri_board(args.limit)
    elif args.board == "dreams":
        show_dreams_board()
    elif args.cmd_id:
        show_cmd_thread(args.cmd_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
