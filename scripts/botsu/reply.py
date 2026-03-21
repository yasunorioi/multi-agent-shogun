"""reply サブコマンド — thread_replies テーブルへのレス投稿・一覧表示。"""

from datetime import datetime

from . import get_connection, now_iso


def reply_add(args) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO thread_replies (thread_id, board, author, body, posted_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (args.thread_id, args.board, args.agent, args.body, now_iso()),
    )
    row = conn.execute("SELECT last_insert_rowid()").fetchone()
    reply_id = row[0]
    conn.commit()
    conn.close()
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
