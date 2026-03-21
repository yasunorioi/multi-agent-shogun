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
        # 通常スレッド (archived 以外)
        cmds = conn.execute(
            "SELECT id, command, project, status, priority, created_at, timestamp"
            " FROM commands WHERE status != 'archived' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        # dat落ちスレッド (archived)
        archived_cmds = conn.execute(
            "SELECT id, command, project, status, priority, created_at, timestamp"
            " FROM commands WHERE status = 'archived' ORDER BY id DESC LIMIT 10",
        ).fetchall()
        # 各CMDのレス数（subtask数 + report数）
        counts: dict[str, int] = {}
        for cmd in list(cmds) + list(archived_cmds):
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
# 書庫板: doc_keywords → ドキュメント索引スレッド
# ---------------------------------------------------------------------------

def show_docs_board(limit: int = 20) -> None:
    conn = get_conn()
    try:
        # 存在チェック
        tbl = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='doc_keywords'"
        ).fetchone()
        if not tbl:
            print(RULE)
            print("【書庫板】ドキュメント索引")
            print(RULE)
            print()
            print("  書庫板: doc_keywords テーブルが存在しません")
            return

        # doc_id 一覧 (keyword数降順)
        doc_rows = conn.execute(
            "SELECT doc_id, doc_type, COUNT(*) AS kw_cnt"
            " FROM doc_keywords GROUP BY doc_id ORDER BY doc_id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        # 各 doc_id のキーワード取得
        kw_map: dict[str, list[str]] = {}
        for dr in doc_rows:
            kws = conn.execute(
                "SELECT keyword FROM doc_keywords WHERE doc_id = ? ORDER BY keyword",
                (dr["doc_id"],),
            ).fetchall()
            kw_map[dr["doc_id"]] = [r["keyword"] for r in kws]

        total_docs = conn.execute(
            "SELECT COUNT(DISTINCT doc_id) FROM doc_keywords"
        ).fetchone()[0]

    finally:
        conn.close()

    print(RULE)
    print("【書庫板】ドキュメント索引")
    print(RULE)
    print()

    if not doc_rows:
        print("  書庫板: まだドキュメントがありません")
        return

    for i, dr in enumerate(doc_rows, 1):
        doc_id = dr["doc_id"]
        doc_type = dr["doc_type"] or "-"
        kw_cnt = dr["kw_cnt"]
        kws = kw_map.get(doc_id, [])

        print(f"{i:3d}. 【{doc_id}】 (type:{doc_type}  キーワード:{kw_cnt}件)")
        # キーワードを1行に並べて表示（最大10件）
        kw_line = " / ".join(kws[:10])
        if len(kws) > 10:
            kw_line += f" ... (+{len(kws) - 10})"
        print(f"       {kw_line}")
        print(f"       {THIN_RULE}")
        print()

    print(f"  {len(doc_rows)}件表示中 (全{total_docs}件)")


# ---------------------------------------------------------------------------
# 日記板: diary_entries → エージェント別日記スレッド
# ---------------------------------------------------------------------------

def show_diary_board() -> None:
    conn = get_conn()
    try:
        # テーブル存在チェック
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

        # エージェント別に取得
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
            # body を最大2行
            for line in (e["body"] or "").strip().split("\n")[:2]:
                print(f"  {line[:80]}")
            if tags_str:
                print(f"  {tags_str}")
            print(f"  {THIN_RULE}")
            print()
        print()

    print(f"  合計 {total} 件の日記エントリ")


# ---------------------------------------------------------------------------
# 監査板: needs_audit=1 subtask → 監査結果スレッド
# ---------------------------------------------------------------------------

_AUDIT_ICON = {
    "approved":           "✅",
    "done":               "✅",
    "rejected":           "❌",
    "rejected_trivial":   "❌",
    "rejected_judgment":  "❌",
    "in_progress":        "🔍",
    "pending":            "⏳",
}


def _audit_icon(status: str | None) -> str:
    if not status:
        return "⏳"
    return _AUDIT_ICON.get(status, "⏳")


def show_audit_board(limit: int = 20) -> None:
    conn = get_conn()
    try:
        subtasks = conn.execute(
            "SELECT s.*, c.command AS cmd_title"
            " FROM subtasks s"
            " LEFT JOIN commands c ON c.id = s.parent_cmd"
            " WHERE s.needs_audit = 1"
            " ORDER BY s.id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        # 各subtaskの監査レポート（ohariko）
        audit_reports: dict[str, list] = {}
        for st in subtasks:
            reps = conn.execute(
                "SELECT * FROM reports WHERE task_id = ? AND worker_id = 'ohariko'"
                " ORDER BY id DESC",
                (st["id"],),
            ).fetchall()
            audit_reports[st["id"]] = list(reps)

        total_needs = conn.execute(
            "SELECT COUNT(*) FROM subtasks WHERE needs_audit = 1"
        ).fetchone()[0]

    finally:
        conn.close()

    print(RULE)
    print("【監査板】お針子の目")
    print(RULE)
    print()

    if not subtasks:
        print("  監査板: 監査対象タスクがありません")
        return

    for i, st in enumerate(subtasks, 1):
        st_id = st["id"]
        audit_st = st["audit_status"]
        icon = _audit_icon(audit_st)
        worker = st["worker_id"] or "未割当"
        ts = fmt_ts(st["assigned_at"])
        desc = (st["description"] or "")[:70]
        cmd_ref = f"[{st['parent_cmd']}]" if st["parent_cmd"] else ""
        audit_label = f" audit:{audit_st}" if audit_st else " audit:pending"

        print(f"{i} 名前：{nametrip(worker)} {ts}")
        print(f"  {icon} [{st_id}] {cmd_ref} {desc}")
        print(f"  status:{st['status'] or '-'}{audit_label}")

        # 監査レポートがあれば1件表示
        reps = audit_reports.get(st_id, [])
        if reps:
            rep = reps[0]
            rep_ts = fmt_ts(rep["timestamp"])
            summary = (rep["summary"] or "")[:70]
            print(f"  お針子 {rep_ts}: {summary}")
            print("  べ、別にあなたのために監査したんじゃないんだからね！")
        else:
            print("  （監査レポートなし）")

        print(f"  {THIN_RULE}")
        print()

    print(f"  {len(subtasks)}件表示中 (全{total_needs}件要監査)")


# ---------------------------------------------------------------------------
# 戦略板: bloom_level L4/L5/L6 subtask → 軍師の戦略分析スレッド
# ---------------------------------------------------------------------------

def show_senryaku_board(limit: int = 20) -> None:
    conn = get_conn()
    try:
        # bloom_level カラム存在チェック
        cols = [r[1] for r in conn.execute("PRAGMA table_info(subtasks)").fetchall()]
        if "bloom_level" in cols:
            subtasks = conn.execute(
                "SELECT s.*, c.command AS cmd_title"
                " FROM subtasks s"
                " LEFT JOIN commands c ON c.id = s.parent_cmd"
                " WHERE s.bloom_level IN ('L4','L5','L6')"
                " ORDER BY s.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            # フォールバック: gunshi担当タスク（軍師はL4-L6担当）
            subtasks = conn.execute(
                "SELECT s.*, c.command AS cmd_title"
                " FROM subtasks s"
                " LEFT JOIN commands c ON c.id = s.parent_cmd"
                " WHERE s.worker_id = 'gunshi'"
                " ORDER BY s.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        total = len(subtasks)
    finally:
        conn.close()

    print(RULE)
    print("【戦略板】軍師の戦略分析スレ")
    print(RULE)
    print()

    if not subtasks:
        print("  戦略板: 戦略分析タスクがありません")
        return

    for i, st in enumerate(subtasks, 1):
        worker = st["worker_id"] or "未割当"
        ts = fmt_ts(st["assigned_at"])
        st_id = st["id"]
        desc = (st["description"] or "")[:80]
        cmd_ref = f"[{st['parent_cmd']}]" if st["parent_cmd"] else ""
        st_status = st["status"] or "-"
        wave = st["wave"] if st["wave"] is not None else "-"
        bloom = st["bloom_level"] if "bloom_level" in st.keys() else "L?"

        print(f"{i} 名前：{nametrip(worker)} {ts}")
        print(f"  [{st_id}] {cmd_ref} {desc}")
        print(f"  Bloom:{bloom} | status:{st_status} | wave:{wave}")
        if st["notes"]:
            note = st["notes"].strip().split("\n")[0][:70]
            print(f"  memo: {note}")
        print(f"  {THIN_RULE}")
        print()

    print(f"  {total}件表示中")


# ---------------------------------------------------------------------------
# 報告板: status='completed' subtask → 足軽完了報告一覧スレッド
# ---------------------------------------------------------------------------

def show_houkoku_board(limit: int = 20) -> None:
    conn = get_conn()
    try:
        subtasks = conn.execute(
            "SELECT s.*, c.command AS cmd_title"
            " FROM subtasks s"
            " LEFT JOIN commands c ON c.id = s.parent_cmd"
            " WHERE s.status IN ('completed', 'done')"
            " ORDER BY s.completed_at DESC, s.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM subtasks WHERE status IN ('completed', 'done')"
        ).fetchone()[0]
    finally:
        conn.close()

    print(RULE)
    print("【報告板】足軽完了報告スレ")
    print(RULE)
    print()

    if not subtasks:
        print("  報告板: 完了報告がありません")
        return

    for i, st in enumerate(subtasks, 1):
        worker = st["worker_id"] or "名無し"
        ts = fmt_ts(st["completed_at"] or st["assigned_at"])
        st_id = st["id"]
        desc = (st["description"] or "")[:70]
        cmd_ref = f"[{st['parent_cmd']}]" if st["parent_cmd"] else ""

        print(f"{i} 名前：{nametrip(worker)} {ts}")
        print(f"  [{st_id}] {cmd_ref} {desc}")
        print(f"  完了: {fmt_ts(st['completed_at'])[:16]}")
        print(f"  {THIN_RULE}")
        print()

    print(f"  {len(subtasks)}件表示中 (全{total}件完了)")


# ---------------------------------------------------------------------------
# 御触板: commands → 殿・老中からの全体通達スレッド
# ---------------------------------------------------------------------------

def show_ofure_board(limit: int = 20) -> None:
    conn = get_conn()
    try:
        cmds = conn.execute(
            "SELECT * FROM commands ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    finally:
        conn.close()

    print(RULE)
    print("【御触板】老中からの全体通達スレ")
    print(RULE)
    print()

    if not cmds:
        print("  御触板: 通達がありません")
        return

    for i, cmd in enumerate(cmds, 1):
        author = cmd["assigned_karo"] or "roju"
        ts = fmt_ts(cmd["created_at"] or cmd["timestamp"])
        cmd_id = cmd["id"]
        command = (cmd["command"] or "")[:60]
        project = cmd["project"] or "-"
        status = cmd["status"] or "-"
        priority = cmd["priority"] or "-"

        print(f"{i} 名前：{nametrip(author)} {ts}")
        print(f"  【{cmd_id}】{command}")
        print(f"  project:{project} | status:{status} | priority:{priority}")
        if cmd["details"]:
            first_line = cmd["details"].strip().split("\n")[0][:70]
            print(f"  {first_line}")
        print(f"  {THIN_RULE}")
        print()

    print(f"  {len(cmds)}件表示中 (全{total}件)")


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
    """スレにレスを投稿する"""
    if not thread_id or not author or not body:
        raise ValueError("thread_id, author, body はすべて必須です")
    conn = get_conn()
    try:
        ensure_thread_replies_table(conn)
        posted_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        conn.execute(
            "INSERT INTO thread_replies (thread_id, board, author, body, posted_at)"
            " VALUES (?, 'zatsudan', ?, ?, ?)",
            (thread_id, author, body, posted_at),
        )
        conn.commit()
        print(f"[zatsudan] {thread_id} にレスを投稿しました (author: {author})")
    finally:
        conn.close()


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
        choices=["kanri", "dreams", "docs", "diary", "audit", "senryaku", "houkoku", "ofure", "zatsudan"],
        help="板を指定 (kanri=管理板一覧, dreams=夢見板, docs=書庫板, diary=日記板, audit=監査板, senryaku=戦略板, houkoku=報告板, ofure=御触板, zatsudan=雑談板)",
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
    elif args.board == "docs":
        show_docs_board(args.limit)
    elif args.board == "diary":
        show_diary_board()
    elif args.board == "audit":
        show_audit_board(args.limit)
    elif args.board == "senryaku":
        show_senryaku_board(args.limit)
    elif args.board == "houkoku":
        show_houkoku_board(args.limit)
    elif args.board == "ofure":
        show_ofure_board(args.limit)
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
