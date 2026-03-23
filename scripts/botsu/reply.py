"""reply サブコマンド — thread_replies テーブルへのレス投稿・一覧表示。"""

from datetime import datetime

from . import get_connection, now_iso
from .notify import notify_post


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
    conn.commit()
    conn.close()

    if notify:
        notify_post(board, thread_id, agent, body)

    return reply_id


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
