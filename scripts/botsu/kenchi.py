"""kenchi サブコマンド — 検地帳（リソース台帳）管理。"""

import sqlite3
import sys

from . import get_connection, now_iso, print_table, print_json, row_to_dict


KENCHI_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS kenchi (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT NOT NULL,
    path        TEXT NOT NULL,
    depends_on  TEXT,
    called_by   TEXT,
    added_at    TEXT NOT NULL,
    updated_at  TEXT,
    notes       TEXT
)
"""

KENCHI_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_kenchi_category ON kenchi(category)",
    "CREATE INDEX IF NOT EXISTS idx_kenchi_name ON kenchi(name)",
]


def ensure_kenchi_table(conn: sqlite3.Connection) -> None:
    """Create kenchi table if it doesn't exist."""
    conn.execute(KENCHI_TABLE_SQL)
    for idx_sql in KENCHI_INDEXES_SQL:
        conn.execute(idx_sql)


def kenchi_add(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)

    existing = conn.execute("SELECT id FROM kenchi WHERE id = ?", (args.id,)).fetchone()
    if existing:
        conn.close()
        print(f"Error: kenchi '{args.id}' already exists. Use 'kenchi update' to modify.", file=sys.stderr)
        sys.exit(1)

    ts = now_iso()
    conn.execute(
        "INSERT INTO kenchi (id, name, category, description, path, depends_on, called_by, added_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (args.id, args.name, args.category, args.description, args.path, args.depends_on, args.called_by, ts, args.notes),
    )
    conn.commit()
    conn.close()
    print(f"Created: kenchi '{args.id}' ({args.category})")


def kenchi_list(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    query = "SELECT id, name, category, description, path, depends_on, called_by, added_at, updated_at FROM kenchi WHERE 1=1"
    params: list = []

    if args.category:
        query += " AND category = ?"
        params.append(args.category)

    query += " ORDER BY category, id"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No kenchi entries found.")
        return

    headers = ["ID", "NAME", "CATEGORY", "DESCRIPTION", "PATH"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["name"],
            r["category"],
            (r["description"] or "")[:40],
            r["path"],
        ])
    print_table(headers, table_rows, [28, 20, 10, 40, 30])


def kenchi_show(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    row = conn.execute("SELECT * FROM kenchi WHERE id = ?", (args.id,)).fetchone()
    conn.close()

    if not row:
        print(f"Error: kenchi '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print_json(row_to_dict(row))
        return

    d = row_to_dict(row)
    print(f"=== 検地帳: {d['id']} ===")
    print(f"  Name:        {d['name']}")
    print(f"  Category:    {d['category']}")
    print(f"  Description: {d['description']}")
    print(f"  Path:        {d['path']}")
    print(f"  Depends on:  {d.get('depends_on') or '-'}")
    print(f"  Called by:    {d.get('called_by') or '-'}")
    print(f"  Added:       {d['added_at']}")
    print(f"  Updated:     {d.get('updated_at') or '-'}")
    print(f"  Notes:       {d.get('notes') or '-'}")


def kenchi_update(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)

    existing = conn.execute("SELECT id FROM kenchi WHERE id = ?", (args.id,)).fetchone()
    if not existing:
        conn.close()
        print(f"Error: kenchi '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)

    updates = []
    params: list = []

    if args.name:
        updates.append("name = ?")
        params.append(args.name)
    if args.category:
        updates.append("category = ?")
        params.append(args.category)
    if args.description:
        updates.append("description = ?")
        params.append(args.description)
    if args.path:
        updates.append("path = ?")
        params.append(args.path)
    if args.depends_on is not None:
        updates.append("depends_on = ?")
        params.append(args.depends_on)
    if args.called_by is not None:
        updates.append("called_by = ?")
        params.append(args.called_by)
    if args.notes is not None:
        updates.append("notes = ?")
        params.append(args.notes)

    if not updates:
        conn.close()
        print("Nothing to update.")
        return

    updates.append("updated_at = ?")
    params.append(now_iso())
    params.append(args.id)

    conn.execute(f"UPDATE kenchi SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    print(f"Updated: kenchi '{args.id}'")


def kenchi_search(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    keyword = f"%{args.keyword}%"
    rows = conn.execute(
        "SELECT id, name, category, description, path, depends_on, called_by, added_at FROM kenchi WHERE id LIKE ? OR name LIKE ? OR description LIKE ? OR notes LIKE ? ORDER BY category, id",
        (keyword, keyword, keyword, keyword),
    ).fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print(f"No kenchi entries found for: {args.keyword}")
        return

    headers = ["ID", "NAME", "CATEGORY", "DESCRIPTION", "PATH"]
    table_rows = []
    for r in rows:
        table_rows.append([
            r["id"],
            r["name"],
            r["category"],
            (r["description"] or "")[:40],
            r["path"],
        ])
    print_table(headers, table_rows, [28, 20, 10, 40, 30])


def kenchi_delete(args) -> None:
    conn = get_connection()
    ensure_kenchi_table(conn)
    cursor = conn.execute("DELETE FROM kenchi WHERE id = ?", (args.id,))
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        print(f"Error: kenchi '{args.id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"Deleted: kenchi '{args.id}'")
