#!/usr/bin/env python3
"""
inbox_read.py — YAML inbox 読み取り + Drain-on-Read ロジック

環境変数で設定を受け取る（inbox_read.sh から呼び出される）:
  INBOX_FILE   - 対象YAMLファイルのパス
  SECTION_KEY  - YAMLのリストキー (reports / audit_queue / tasks)
  FORMAT       - 出力形式 summary|yaml|json (default: summary)
  UNREAD_ONLY  - true: 未読のみ表示 (default: false)
  MARK_READ    - true: 表示エントリを read:true に更新 (default: false)
  DRAIN        - true: read:true エントリを削除 (default: false)
  DRY_RUN      - true: DRAIN/MARK_READ の実削除をスキップ (default: false)
  SCRIPT_DIR   - リポジトリルートパス (DB存在チェック用)

exit codes:
  0 = 成功（エントリあり）
  1 = エントリなし
  2 = エラー
"""
import os
import sys
import json
import subprocess
import tempfile
import yaml

INBOX_FILE  = os.environ["INBOX_FILE"]
SECTION_KEY = os.environ["SECTION_KEY"]
FORMAT      = os.environ.get("FORMAT", "summary")
UNREAD_ONLY = os.environ.get("UNREAD_ONLY", "false") == "true"
MARK_READ   = os.environ.get("MARK_READ",  "false") == "true"
DRAIN       = os.environ.get("DRAIN",      "false") == "true"
DRY_RUN     = os.environ.get("DRY_RUN",    "false") == "true"
SCRIPT_DIR  = os.environ.get("SCRIPT_DIR", ".")


# ─── DB存在チェック ────────────────────────────────────────────────────────────

def is_in_db(subtask_id: str) -> bool:
    """没日録DBにsubtask_idが存在するか確認する。"""
    if not subtask_id or subtask_id == "stophook_notification":
        return True  # 通知エントリはDBチェック不要
    if not subtask_id.startswith("subtask_"):
        return True  # 不明なIDはdrain可として扱う（保守的でない方向）

    try:
        result = subprocess.run(
            ["python3", os.path.join(SCRIPT_DIR, "scripts", "botsunichiroku.py"),
             "subtask", "show", subtask_id],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False  # チェック失敗 → drain不可


# ─── drain対象か判定 ──────────────────────────────────────────────────────────

def can_drain(entry: dict, section_key: str) -> bool:
    """エントリがdrain可能かを判定する。"""
    if entry.get("read") is not True:
        return False
    # tasksセクションは status:done のもののみ
    if section_key == "tasks" and entry.get("status") != "done":
        return False
    subtask_id = entry.get("subtask_id", "")
    return is_in_db(subtask_id)


# ─── 出力フォーマット ─────────────────────────────────────────────────────────

def format_summary(entries: list, section_key: str) -> str:
    lines = []
    for i, e in enumerate(entries, 1):
        sid    = e.get("subtask_id") or e.get("request_id") or "?"
        worker = e.get("worker") or e.get("assigned_by") or ""
        ts     = e.get("reported_at") or e.get("assigned_at") or e.get("timestamp") or ""
        status = e.get("status") or ("read" if e.get("read") else "unread")
        read_flag = "✓" if e.get("read") else "●"
        summary = (e.get("summary") or e.get("description") or "").strip()
        first_line = summary.split("\n")[0][:80] if summary else ""

        line = f"[{i}] {read_flag} {sid}"
        if worker:
            line += f" ({worker})"
        if ts:
            line += f" @ {ts}"
        line += f" [{status}]"
        if first_line:
            line += f"\n    {first_line}"
        lines.append(line)
    return "\n".join(lines)


# ─── メイン ──────────────────────────────────────────────────────────────────

def main():
    # ファイル読み込み
    try:
        with open(INBOX_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"ERROR: {INBOX_FILE} が見つかりません", file=sys.stderr)
        sys.exit(2)
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse失敗: {e}", file=sys.stderr)
        sys.exit(2)

    entries = data.get(SECTION_KEY) or []

    # 対象エントリを決定
    if UNREAD_ONLY:
        display_entries = [e for e in entries if not e.get("read")]
    else:
        display_entries = list(entries)

    if not display_entries:
        sys.exit(1)

    # ─── 出力 ───
    if FORMAT == "json":
        print(json.dumps(display_entries, ensure_ascii=False, indent=2))
    elif FORMAT == "yaml":
        print(yaml.dump(display_entries, allow_unicode=True,
                        default_flow_style=False).rstrip())
    else:  # summary
        print(format_summary(display_entries, SECTION_KEY))

    # ─── MARK_READ ───
    if MARK_READ:
        display_ids = {id(e) for e in display_entries}
        modified = False
        for e in entries:
            if id(e) in display_ids and not e.get("read"):
                if not DRY_RUN:
                    e["read"] = True
                modified = True
        if modified and not DRY_RUN:
            _atomic_write(INBOX_FILE, data)
        elif DRY_RUN and modified:
            print("[DRY-RUN] --mark-read: 上記エントリを read:true に更新します（実行は省略）",
                  file=sys.stderr)

    # ─── DRAIN ───
    if DRAIN:
        drainable     = [e for e in entries if can_drain(e, SECTION_KEY)]
        not_drainable = [e for e in entries if e not in drainable or
                         (e.get("read") and not can_drain(e, SECTION_KEY))]

        if not drainable:
            print("[drain] drain対象なし", file=sys.stderr)
        else:
            drain_count = len(drainable)
            if DRY_RUN:
                print(f"[DRY-RUN] --drain: {drain_count}件を削除します（実行は省略）",
                      file=sys.stderr)
                for e in drainable:
                    sid = e.get("subtask_id") or "?"
                    print(f"  - {sid}", file=sys.stderr)
            else:
                # drain実行: drainable を除外した新しいリストで上書き
                drain_set = {id(e) for e in drainable}
                new_entries = [e for e in entries if id(e) not in drain_set]
                data[SECTION_KEY] = new_entries
                _atomic_write(INBOX_FILE, data)
                print(f"[drain] {drain_count}件削除完了（残: {len(new_entries)}件）",
                      file=sys.stderr)

    sys.exit(0)


def _atomic_write(path: str, data: dict):
    """tmpfile + os.replace による atomic write。"""
    dir_ = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_ or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
