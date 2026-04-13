"""reply サブコマンド — thread_replies テーブルへのレス投稿・一覧表示。

Phase 0 CLI拡張: list-for / list-unread (cmd_441 subtask_979)
"""

from datetime import datetime

from . import get_connection, now_iso, fts5_upsert, vec_upsert_if_available
from .notify import notify_post


# ---------------------------------------------------------------------------
# 未読管理テーブル（自動作成）
# ---------------------------------------------------------------------------

def _ensure_watermarks(conn) -> None:
    """read_watermarksテーブルが存在しなければ作成。"""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS read_watermarks ("
        "  agent_id TEXT NOT NULL,"
        "  board    TEXT NOT NULL,"
        "  last_read_id INTEGER NOT NULL DEFAULT 0,"
        "  updated_at TEXT,"
        "  PRIMARY KEY (agent_id, board)"
        ")"
    )


def _get_watermark(conn, agent_id: str, board: str) -> int:
    """指定エージェント・板の最終既読reply IDを取得。"""
    _ensure_watermarks(conn)
    row = conn.execute(
        "SELECT last_read_id FROM read_watermarks WHERE agent_id = ? AND board = ?",
        (agent_id, board),
    ).fetchone()
    return row["last_read_id"] if row else 0


def _update_watermark(conn, agent_id: str, board: str, last_id: int) -> None:
    """既読位置を更新。"""
    _ensure_watermarks(conn)
    conn.execute(
        "INSERT INTO read_watermarks (agent_id, board, last_read_id, updated_at)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(agent_id, board) DO UPDATE"
        " SET last_read_id = MAX(last_read_id, excluded.last_read_id),"
        "     updated_at = excluded.updated_at",
        (agent_id, board, last_id, now_iso()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Core functions (args-free)
# ---------------------------------------------------------------------------

def do_reply_add(thread_id: str, board: str, agent: str, body: str,
                 notify: bool = True) -> int:
    """argsに依存しないレス投稿関数。reply_idを返す。notify=Trueでsend-keys通知も発火。"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO thread_replies (thread_id, board, author, body, posted_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (thread_id, board, agent, body, now_iso()),
    )
    row = conn.execute("SELECT last_insert_rowid()").fetchone()
    reply_id = row[0]
    fts5_upsert(conn, "reply", str(reply_id), thread_id, board, agent, "", body or "")
    vec_upsert_if_available(conn, str(reply_id), "reply", body or "", thread_id, board)
    conn.commit()
    conn.close()

    if notify:
        notify_post(board, thread_id, agent, body)

    return reply_id


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------

def reply_add(args) -> None:
    reply_id = do_reply_add(args.thread_id, args.board, args.agent, args.body)
    print(f"Posted: reply #{reply_id} (thread={args.thread_id}, board={args.board}, author={args.agent})")


def reply_list(args) -> None:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, author, body, posted_at FROM thread_replies"
        " WHERE thread_id = ? ORDER BY id LIMIT ?",
        (args.thread_id, args.limit),
    ).fetchall()
    conn.close()

    if not rows:
        print(f"(no replies in thread '{args.thread_id}')")
        return

    for r in rows:
        ts = r["posted_at"] or ""
        author = r["author"] or "名無し"
        body = (r["body"] or "").replace("\n", " ")
        print(f"  #{r['id']} [{author}] {ts[:19]}  {body[:100]}")


def reply_list_for(args) -> None:
    """指定エージェント宛の@メンションを含むレスを一覧表示。"""
    agent = args.agent.lstrip("@")
    board = args.board
    limit = args.limit

    conn = get_connection()

    if args.unread:
        watermark = _get_watermark(conn, agent, board)
        rows = conn.execute(
            "SELECT id, thread_id, author, body, posted_at FROM thread_replies"
            " WHERE board = ? AND id > ?"
            " AND (body LIKE ? OR body LIKE ?)"
            " ORDER BY id LIMIT ?",
            (board, watermark, f"%@{agent}%", f"%@{agent} %", limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, thread_id, author, body, posted_at FROM thread_replies"
            " WHERE board = ? AND (body LIKE ? OR body LIKE ?)"
            " ORDER BY id DESC LIMIT ?",
            (board, f"%@{agent}%", f"%@{agent} %", limit),
        ).fetchall()

    conn.close()

    if not rows:
        label = "未読" if args.unread else ""
        print(f"({agent}宛の{label}レスは{board}板にありません)")
        return

    print(f"--- {board}板 @{agent} 宛 {'(未読)' if args.unread else ''} ---")
    for r in rows:
        ts = (r["posted_at"] or "")[:19]
        author = r["author"] or "名無し"
        body = (r["body"] or "").replace("\n", " ")
        print(f"  #{r['id']} [{r['thread_id']}] {author} {ts}  {body[:100]}")

    if args.mark_read:
        max_id = max(r["id"] for r in rows)
        conn = get_connection()
        _update_watermark(conn, agent, board, max_id)
        conn.close()
        print(f"(既読マーク更新: #{max_id}まで)")


def reply_list_unread(args) -> None:
    """指定板の未読レス一覧を表示。--agent指定で特定エージェント視点。"""
    agent = args.agent
    board = args.board
    limit = args.limit

    conn = get_connection()
    watermark = _get_watermark(conn, agent, board)

    rows = conn.execute(
        "SELECT id, thread_id, author, body, posted_at FROM thread_replies"
        " WHERE board = ? AND id > ?"
        " ORDER BY id LIMIT ?",
        (board, watermark, limit),
    ).fetchall()
    conn.close()

    if not rows:
        print(f"({board}板に{agent}の未読レスはありません)")
        return

    print(f"--- {board}板 未読 ({agent}視点, watermark=#{watermark}) ---")
    for r in rows:
        ts = (r["posted_at"] or "")[:19]
        author = r["author"] or "名無し"
        body = (r["body"] or "").replace("\n", " ")
        print(f"  #{r['id']} [{r['thread_id']}] {author} {ts}  {body[:100]}")
    print(f"({len(rows)}件の未読)")

    if args.mark_read:
        max_id = max(r["id"] for r in rows)
        conn = get_connection()
        _update_watermark(conn, agent, board, max_id)
        conn.close()
        print(f"(既読マーク更新: #{max_id}まで)")
