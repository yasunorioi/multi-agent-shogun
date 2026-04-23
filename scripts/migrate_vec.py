#!/usr/bin/env python3
"""migrate_vec.py — 既存FTS5データのバッチベクトル化（1回実行）。

Usage:
  python3 scripts/migrate_vec.py              # 全件ベクトル化
  python3 scripts/migrate_vec.py --dry-run    # 件数確認のみ
"""

from __future__ import annotations

import sqlite3
import struct
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from botsu import DB_PATH
from botsu.vec import MODEL_NAME, _VEC_DIM, _load_vec, ensure_tables

BATCH_SIZE = 32


def _build_created_at_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    """各テーブルの作成日時を {source_id: created_at} 形式で返す。"""
    lookup: dict[str, str] = {}
    tables = [
        ("commands",      "SELECT id, created_at FROM commands",       str),
        ("subtasks",      "SELECT id, assigned_at FROM subtasks",       str),
        ("reports",       "SELECT id, timestamp FROM reports",          str),
        ("diary_entries", "SELECT id, created_at FROM diary_entries",   str),
    ]
    for _name, sql, _cast in tables:
        try:
            for row in conn.execute(sql).fetchall():
                key = str(row[0])
                if row[1]:
                    lookup[key] = str(row[1])
        except Exception:
            pass
    # thread_replies は posted_at を使う
    try:
        for row in conn.execute("SELECT id, posted_at FROM thread_replies").fetchall():
            key = str(row[0])
            if row[1]:
                lookup[key] = str(row[1])
    except Exception:
        pass
    return lookup


def main():
    import argparse
    parser = argparse.ArgumentParser(description="既存FTS5データのバッチベクトル化")
    parser.add_argument("--dry-run", action="store_true", help="件数確認のみ")
    parser.add_argument("--backfill", action="store_true",
                        help="vec_meta.created_atが空のレコードを各元テーブルから補完（ベクトル再生成なし）")
    args = parser.parse_args()

    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    # FTS5データ件数確認
    total = conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0]
    print(f"FTS5 entries: {total}")

    if args.backfill:
        _run_backfill(conn)
        conn.close()
        return

    if args.dry_run:
        # 既存ベクトル件数
        try:
            vec_count = conn.execute("SELECT COUNT(*) FROM vec_meta").fetchone()[0]
            print(f"Vec entries:  {vec_count}")
            print(f"Remaining:    {total - vec_count}")
        except Exception:
            print("Vec tables not yet created")
        conn.close()
        return

    # テーブル作成
    if not ensure_tables(conn):
        print("Error: sqlite-vec not available", file=sys.stderr)
        sys.exit(1)
    print("vec_index + vec_meta tables ready")

    # 既にベクトル化済みのsource_idを取得
    existing = set()
    try:
        rows = conn.execute("SELECT source_id FROM vec_meta").fetchall()
        existing = {r[0] for r in rows}
    except Exception:
        pass

    # FTS5データ取得
    rows = conn.execute(
        "SELECT source_type, source_id, parent_id, project, content"
        " FROM search_index"
    ).fetchall()

    # 未ベクトル化のものだけフィルタ
    pending = [(r[0], r[1], r[2], r[3], r[4]) for r in rows if r[1] not in existing]
    # thread_replies はテーブルから直接追加（search_index未登録分を含む全量カバー）
    reply_rows = conn.execute("SELECT id, thread_id, board, body FROM thread_replies").fetchall()
    pending += [("reply", str(r[0]), r[1] or "", r[2] or "", r[3] or "") for r in reply_rows if str(r[0]) not in existing]
    print(f"Already vectorized: {len(existing)}")
    print(f"Pending: {len(pending)}")

    if not pending:
        print("Nothing to do.")
        conn.close()
        return

    # モデルロード
    print(f"Loading model: {MODEL_NAME} ...")
    t0 = time.time()
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    print(f"Model loaded in {time.time() - t0:.1f}s")

    # 作成日時lookup構築
    created_at_lookup = _build_created_at_lookup(conn)
    print(f"Created_at lookup: {len(created_at_lookup)} entries")

    # バッチベクトル化
    t_start = time.time()
    done = 0
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        texts = ["文章: " + r[4] for r in batch]  # Ruri v3 passage prefix
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        for row, emb in zip(batch, embeddings):
            source_type, source_id, parent_id, project, _content = row
            vec_bytes = struct.pack(f"{len(emb)}f", *emb)

            conn.execute("DELETE FROM vec_index WHERE source_id = ?", (source_id,))
            conn.execute(
                "INSERT INTO vec_index (source_id, embedding) VALUES (?, ?)",
                (source_id, vec_bytes),
            )

            from botsu import now_iso
            created_at = created_at_lookup.get(source_id, "")
            conn.execute(
                "INSERT OR REPLACE INTO vec_meta"
                " (source_id, source_type, parent_id, project, created_at, model_name, vectorized_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (source_id, source_type, parent_id, project, created_at, MODEL_NAME, now_iso()),
            )

        conn.commit()
        done += len(batch)
        elapsed = time.time() - t_start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(pending) - done) / rate if rate > 0 else 0
        print(f"  {done}/{len(pending)} ({rate:.1f}/s, ETA {eta:.0f}s)")

    elapsed = time.time() - t_start
    print(f"\nDone: {done} vectors indexed in {elapsed:.1f}s")
    conn.close()


def _run_backfill(conn: sqlite3.Connection) -> None:
    """vec_meta.created_atが空のレコードを各元テーブルから補完する（ベクトル再生成なし）。"""
    try:
        empty_rows = conn.execute(
            "SELECT source_id FROM vec_meta WHERE created_at = '' OR created_at IS NULL"
        ).fetchall()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    print(f"Backfill対象: {len(empty_rows)}件")
    if not empty_rows:
        print("Nothing to backfill.")
        return

    lookup = _build_created_at_lookup(conn)
    print(f"Created_at lookup: {len(lookup)} entries")

    updated = 0
    missing = 0
    for (source_id,) in empty_rows:
        created_at = lookup.get(str(source_id), "")
        if created_at:
            conn.execute(
                "UPDATE vec_meta SET created_at = ? WHERE source_id = ?",
                (created_at, source_id),
            )
            updated += 1
        else:
            missing += 1

    conn.commit()
    print(f"Backfill完了: updated={updated}, lookup_miss={missing}")


if __name__ == "__main__":
    main()
