"""counter サブコマンド — カウンター管理。"""

from . import get_connection, next_counter, print_table, print_json, row_to_dict


def counter_next(args) -> None:
    conn = get_connection()
    val = next_counter(conn, args.name)
    conn.close()

    if args.name == "cmd_id":
        print(f"cmd_{val:03d}")
    elif args.name == "subtask_id":
        print(f"subtask_{val:03d}")
    else:
        print(f"{args.name} = {val}")


def counter_show(args) -> None:
    conn = get_connection()
    rows = conn.execute("SELECT name, value FROM counters ORDER BY name").fetchall()
    conn.close()

    if args.json:
        print_json([row_to_dict(r) for r in rows])
        return

    if not rows:
        print("No counters found.")
        return

    headers = ["NAME", "VALUE", "NEXT_ID"]
    table_rows = []
    for r in rows:
        name = r["name"]
        val = r["value"]
        if name == "cmd_id":
            next_id = f"cmd_{val + 1:03d}"
        elif name == "subtask_id":
            next_id = f"subtask_{val + 1:03d}"
        else:
            next_id = str(val + 1)
        table_rows.append([name, str(val), next_id])
    print_table(headers, table_rows, [14, 8, 16])
