#!/usr/bin/env python3
"""
migrate_dashboard_to_db.py - dashboard.md → 没日録DB 移行スクリプト

dashboard.md (500行超) をセクション別にパースし、完了済み/裁定済みエントリを
没日録DBのdashboard_entriesテーブルにINSERTする。

Usage:
    python3 scripts/migrate_dashboard_to_db.py --dry-run    # プレビュー（デフォルト）
    python3 scripts/migrate_dashboard_to_db.py --execute    # 実際にDBにINSERT
    python3 scripts/migrate_dashboard_to_db.py --db PATH    # DBパス指定
    python3 scripts/migrate_dashboard_to_db.py --dashboard PATH  # dashboard.mdパス指定
"""

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "botsunichiroku.db"
DEFAULT_DASHBOARD = PROJECT_ROOT / "dashboard.md"


@dataclass
class DashboardEntry:
    section: str
    content: str
    status: str
    cmd_id: Optional[str] = None
    tags: Optional[str] = None


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def extract_cmd_id(text: str) -> Optional[str]:
    """テキストから最初の cmd_XXX を抽出する"""
    m = re.search(r'cmd_(\d+)', text)
    return f"cmd_{m.group(1)}" if m else None


def strip_strikethrough(text: str) -> str:
    """~~text~~ → text に変換"""
    return re.sub(r'~~(.+?)~~', r'\1', text)


def is_table_separator(row_cols: list[str]) -> bool:
    """テーブルセパレーター行（|---|---| など）か判定"""
    return bool(row_cols) and all(re.match(r'^[-:]+$', c.replace(' ', '')) for c in row_cols)


def split_table_row(line: str) -> list[str]:
    """| col1 | col2 | col3 | → ['col1', 'col2', 'col3'] に分割"""
    cols = [c.strip() for c in line.split('|')]
    # 先頭末尾の空文字列を除去
    return [c for c in cols if c != '']


# ---------------------------------------------------------------------------
# セクション A+D: 🚨 要対応
# ---------------------------------------------------------------------------

def determine_yotaiou_status(heading: str) -> Optional[str]:
    """
    要対応セクションの見出し行から status を判断する。
    アクティブな（未解決の）項目はNoneを返す（スキップ対象）。
    """
    # 取消線付き見出し: ### ~~...~~
    if heading.startswith('~~'):
        # 中止・破棄・キャンセルを最初にチェック（殿裁定の有無より優先）
        if re.search(r'(❌|中止|破棄|キャンセル)', heading):
            return 'cancelled'
        # 凍結
        if re.search(r'(🧊|🗑️|凍結)', heading):
            return 'frozen'
        # 解消・終了・完了・その他 → resolved
        return 'resolved'

    # ✅ マーク付き見出し
    if heading.startswith('✅'):
        return 'resolved'

    # ❌ マーク付き見出し
    if heading.startswith('❌'):
        return 'cancelled'

    # 🧊/🗑️ マーク付き見出し
    if heading.startswith(('🧊', '🗑️')):
        return 'frozen'

    # 🔴/🟡/cmd_XXX など → アクティブ → スキップ
    return None


def parse_yotaiou_section(lines: list[str]) -> list[DashboardEntry]:
    """🚨 要対応 セクションをパースして解決済みエントリを返す"""
    entries = []

    for line in lines:
        if not line.startswith('### '):
            continue

        heading = line[4:].strip()  # '### ' を除去
        status = determine_yotaiou_status(heading)

        if status is None:
            continue  # アクティブな項目はスキップ

        # cmd_id 抽出: 取消線内または見出し全体から
        clean_heading = strip_strikethrough(heading)
        cmd_id = extract_cmd_id(clean_heading)

        entries.append(DashboardEntry(
            section='殿裁定',
            content=line.rstrip(),
            status=status,
            cmd_id=cmd_id,
        ))

    return entries


# ---------------------------------------------------------------------------
# セクション B: ✅ 本日の戦果
# ---------------------------------------------------------------------------

def parse_senka_section(lines: list[str]) -> list[DashboardEntry]:
    """✅ 本日の戦果 セクションのテーブル行をパース"""
    entries = []
    header_seen = False

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith('|'):
            continue

        cols = split_table_row(stripped)
        if not cols:
            continue

        # セパレーター行スキップ
        if is_table_separator(cols):
            header_seen = True  # セパレーターの後がデータ行
            continue

        # ヘッダー行スキップ
        if cols[0] in ('時刻',):
            header_seen = True
            continue

        if not header_seen:
            continue

        # データ行: | 時刻 | 戦場 | 任務 | 結果 |
        if len(cols) < 3:
            continue

        time_col = cols[0] if len(cols) > 0 else ''
        basho_col = cols[1] if len(cols) > 1 else ''
        mission_col = cols[2] if len(cols) > 2 else ''
        result_col = cols[3] if len(cols) > 3 else ''

        if not mission_col:
            continue

        content = f"| {time_col} | {basho_col} | {mission_col} | {result_col} |"
        cmd_id = extract_cmd_id(mission_col)
        tags = basho_col if basho_col else None

        entries.append(DashboardEntry(
            section='戦果',
            content=content,
            status='done',
            cmd_id=cmd_id,
            tags=tags,
        ))

    return entries


# ---------------------------------------------------------------------------
# セクション C: 🎯 スキル化候補
# ---------------------------------------------------------------------------

# 裁定マーク → status のマッピング（Noneはスキップ）
SKILL_STATUS_MAP = [
    ('✅', 'adopted'),
    ('❌', 'rejected'),
    ('⏸️', 'frozen'),
    ('🆕', None),   # 未裁定 → スキップ
]


def parse_skill_section(lines: list[str]) -> list[DashboardEntry]:
    """🎯 スキル化候補 セクションのテーブル行をパース"""
    entries = []
    header_seen = False

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith('|'):
            continue

        cols = split_table_row(stripped)
        if not cols:
            continue

        # セパレーター行スキップ
        if is_table_separator(cols):
            header_seen = True
            continue

        # ヘッダー行スキップ
        if cols[0] in ('候補名',):
            header_seen = True
            continue

        if not header_seen:
            continue

        # データ行: | 候補名 | 提案元 | 説明 | 裁定 |
        if len(cols) < 4:
            continue

        name_col = cols[0]
        proposer_col = cols[1] if len(cols) > 1 else ''
        desc_col = cols[2] if len(cols) > 2 else ''
        verdict_col = cols[3] if len(cols) > 3 else ''

        if not name_col:
            continue

        # 裁定マーク判定
        status = None
        matched = False
        for marker, st in SKILL_STATUS_MAP:
            if marker in verdict_col:
                status = st
                matched = True
                break

        if not matched or status is None:
            # 🆕 未裁定、またはマーク不明 → スキップ
            continue

        # 候補名の取消線を除去してタグに使用
        clean_name = strip_strikethrough(name_col).strip()
        content = f"| {name_col} | {proposer_col} | {desc_col} | {verdict_col} |"

        entries.append(DashboardEntry(
            section='スキル候補',
            content=content,
            status=status,
            cmd_id=None,  # スキル候補はcmd_idなし、候補名をtagsに
            tags=clean_name,
        ))

    return entries


# ---------------------------------------------------------------------------
# メインパース処理
# ---------------------------------------------------------------------------

def parse_dashboard(dashboard_path: Path) -> list[DashboardEntry]:
    """dashboard.md をパースしてエントリリストを返す"""
    text = dashboard_path.read_text(encoding='utf-8')
    lines = text.splitlines()

    # セクション境界インデックスを特定（最初の出現を使用）
    section_indices: dict[str, int] = {}
    for i, line in enumerate(lines):
        if not line.startswith('## '):
            continue
        if '要対応' in line and 'yotaiou' not in section_indices:
            section_indices['yotaiou'] = i
        elif '進行中' in line and 'shinkochu' not in section_indices:
            section_indices['shinkochu'] = i
        elif 'スキル化候補' in line and '過去' not in line and 'skill' not in section_indices:
            # 「過去のスキル化候補」セクションは除外し、アクティブなセクションのみ対象
            section_indices['skill'] = i
        elif '本日の戦果' in line and 'senka' not in section_indices:
            section_indices['senka'] = i
        elif '過去のスキル化候補' in line and 'past_skill' not in section_indices:
            section_indices['past_skill'] = i

    entries: list[DashboardEntry] = []

    # (A+D) 要対応 → 進行中
    y_start = section_indices.get('yotaiou', -1)
    y_end = section_indices.get('shinkochu', len(lines))
    if y_start >= 0:
        entries.extend(parse_yotaiou_section(lines[y_start:y_end]))

    # (C) スキル化候補 → 本日の戦果
    sk_start = section_indices.get('skill', -1)
    sk_end = section_indices.get('senka', len(lines))
    if sk_start >= 0:
        entries.extend(parse_skill_section(lines[sk_start:sk_end]))

    # (B) 本日の戦果 → 過去のスキル化候補（またはファイル末尾）
    se_start = section_indices.get('senka', -1)
    se_end = section_indices.get('past_skill', len(lines))
    if se_start >= 0:
        entries.extend(parse_senka_section(lines[se_start:se_end]))

    return entries


# ---------------------------------------------------------------------------
# DB操作
# ---------------------------------------------------------------------------

def open_db(db_path: Path) -> sqlite3.Connection:
    """DBに接続して返す"""
    if not db_path.exists():
        print(f"Error: DB が見つかりません: {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def check_table_exists(conn: sqlite3.Connection) -> bool:
    """dashboard_entries テーブルが存在するか確認"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_entries'"
    ).fetchone()
    return row is not None


def check_duplicate(conn: sqlite3.Connection, entry: DashboardEntry) -> bool:
    """
    重複チェック: 同一 cmd_id + section + content先頭50文字。
    2回実行しても安全にするための冪等性保証。
    """
    content_prefix = entry.content[:50]
    row = conn.execute(
        "SELECT id FROM dashboard_entries "
        "WHERE cmd_id IS ? AND section = ? AND substr(content, 1, 50) = ?",
        (entry.cmd_id, entry.section, content_prefix),
    ).fetchone()
    return row is not None


def insert_entry(conn: sqlite3.Connection, entry: DashboardEntry) -> int:
    """エントリをDBにINSERT、rowid を返す"""
    ts = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO dashboard_entries (cmd_id, section, content, status, tags, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (entry.cmd_id, entry.section, entry.content, entry.status, entry.tags, ts),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='dashboard.md → 没日録DB 移行スクリプト'
    )
    parser.add_argument(
        '--dry-run', action='store_true', default=False,
        help='INSERTせずにパース結果をプレビュー表示（デフォルト動作）'
    )
    parser.add_argument(
        '--execute', action='store_true',
        help='実際にDBにINSERT（--dry-run より優先）'
    )
    parser.add_argument(
        '--db', default=str(DEFAULT_DB),
        help=f'DBパス（デフォルト: {DEFAULT_DB}）'
    )
    parser.add_argument(
        '--dashboard', default=str(DEFAULT_DASHBOARD),
        help=f'dashboard.mdパス（デフォルト: {DEFAULT_DASHBOARD}）'
    )
    args = parser.parse_args()

    # --execute が指定されなければ dry-run
    dry_run = not args.execute

    dashboard_path = Path(args.dashboard)
    db_path = Path(args.db)

    if not dashboard_path.exists():
        print(f"Error: dashboard.md が見つかりません: {dashboard_path}", file=sys.stderr)
        sys.exit(1)

    # --- パース ---
    print(f"Parsing: {dashboard_path}")
    entries = parse_dashboard(dashboard_path)

    # セクション別集計
    by_section: dict[str, list[DashboardEntry]] = {}
    for e in entries:
        by_section.setdefault(e.section, []).append(e)

    print()
    print("=== パース結果 ===")
    total = 0
    for section in ('殿裁定', 'スキル候補', '戦果'):
        items = by_section.get(section, [])
        if not items:
            print(f"  [{section}] 0件")
            continue
        by_status: dict[str, int] = {}
        for item in items:
            by_status[item.status] = by_status.get(item.status, 0) + 1
        status_str = ', '.join(f"{s}:{n}" for s, n in sorted(by_status.items()))
        print(f"  [{section}] {len(items)}件 ({status_str})")
        total += len(items)
    print(f"  合計: {total}件")

    if dry_run:
        print()
        print("=== dry-run プレビュー（最初の5件 / セクション） ===")
        for section in ('殿裁定', 'スキル候補', '戦果'):
            items = by_section.get(section, [])
            if not items:
                continue
            print(f"\n--- {section} ({len(items)}件) ---")
            for e in items[:5]:
                print(f"  cmd_id={e.cmd_id!r:12s} status={e.status!r:12s} tags={e.tags!r}")
                preview = e.content[:100]
                print(f"    {preview}{'...' if len(e.content) > 100 else ''}")
            if len(items) > 5:
                print(f"  ... 他{len(items) - 5}件")
        print()
        print("実際にINSERTするには --execute を指定してください。")
        return

    # --- execute モード ---
    conn = open_db(db_path)

    if not check_table_exists(conn):
        print(
            "Error: dashboard_entries テーブルが存在しません。\n"
            "足軽1号のDBマイグレーション完了後に再実行してください。",
            file=sys.stderr,
        )
        conn.close()
        sys.exit(1)

    inserted = 0
    skipped = 0

    for entry in entries:
        if check_duplicate(conn, entry):
            skipped += 1
            continue
        insert_entry(conn, entry)
        inserted += 1

    conn.commit()
    conn.close()

    print()
    print("=== 実行完了 ===")
    print(f"  INSERT: {inserted}件")
    print(f"  スキップ（重複）: {skipped}件")
    print(f"  合計処理: {total}件")


if __name__ == '__main__':
    main()
