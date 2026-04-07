#!/usr/bin/env python3
"""kenshu_auto.py — 検収フロー自動化CLI (老中用)

Phase 3 PDCA自動回転の老中側ツール。
2F合議トリガー、gate判定、scribe/herald/merge を半自動で実行。

Usage:
    # 2F合議トリガー（お針子・軍師にsend-keys + 勘定吟味役review自動起動）
    python3 scripts/kenshu_auto.py trigger --thread 1094

    # gate判定（kenshu_gate POST + scribe + merge/herald）
    python3 scripts/kenshu_auto.py gate --thread 1094 --subtask subtask_1094 \\
        --cmd cmd_499 --verdict PASS --severity S4

    # レビュー状況確認
    python3 scripts/kenshu_auto.py status --thread 1094
"""

import argparse
import subprocess
import sys
import urllib.parse
import urllib.request

BBS_BASE = "http://localhost:8824"
SHOGUN_DIR = "/home/yasu/multi-agent-shogun"

# tmuxペイン定数
PANES = {
    "ohariko": "ooku:agents.1",
    "gunshi": "ooku:agents.0",
}


def send_keys(pane: str, message: str) -> bool:
    """tmux send-keys (2段階: テキスト + Enter)"""
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, message[:500]],
            capture_output=True, timeout=3,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "Enter"],
            capture_output=True, timeout=3,
        )
        return True
    except Exception as e:
        print(f"[WARN] send-keys失敗 ({pane}): {e}", file=sys.stderr)
        return False


def bbs_post(board: str, subject: str, message: str, thread_id: str = "") -> bool:
    """BBS POST (agent-swarm 2ch互換API)"""
    data = urllib.parse.urlencode({
        "bbs": board,
        "FROM": "老中 ◆ROJU",
        "MESSAGE": message,
        "subject": subject,
        "time": "0",
    }).encode()
    if thread_id:
        data = urllib.parse.urlencode({
            "bbs": board,
            "key": thread_id,
            "FROM": "老中 ◆ROJU",
            "MESSAGE": message,
            "time": "0",
        }).encode()
    try:
        req = urllib.request.Request(f"{BBS_BASE}/test/bbs.cgi", data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[ERROR] BBS POST失敗: {e}", file=sys.stderr)
        return False


def get_thread_posts(board: str, thread_id: str) -> list[str]:
    """スレッドの投稿者リストを取得"""
    try:
        url = f"{BBS_BASE}/test/read.cgi/{board}/{thread_id}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        # Shift_JIS → UTF-8 (agent-swarm BBSはShift_JIS)
        for enc in ("utf-8", "shift_jis", "cp932"):
            try:
                content = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            content = raw.decode("utf-8", errors="replace")
        import re
        return re.findall(r"(\S+)\s*◆\w+", content)
    except Exception:
        return []


def cmd_trigger(args):
    """2F合議トリガー: お針子・軍師にsend-keys + 勘定吟味役review自動起動"""
    thread = args.thread
    print(f"[trigger] kenshu thread={thread} 2F合議トリガー発火")

    # お針子・軍師に検収依頼
    for agent, pane in PANES.items():
        msg = (
            f"kenshu板thread:{thread}検収依頼(自動トリガー)。"
            f"検収板(kenshu)にreplyでチェック結果を投稿せよ。"
        )
        ok = send_keys(pane, msg)
        status = "✅" if ok else "❌"
        print(f"  {status} {agent} ({pane})")

    # 勘定吟味役 auto-review
    print(f"  ⏳ 勘定吟味役 review 実行中...")
    result = subprocess.run(
        ["python3", f"{SHOGUN_DIR}/scripts/kanjou_ginmiyaku.py", "review", "--thread", thread],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        print(f"  ✅ 勘定吟味役 review完了")
    else:
        print(f"  ⚠️  勘定吟味役 review失敗(MBPスリープ?): {result.stderr[:100]}")

    print(f"\n[trigger] 完了。レビュー到着後に gate コマンドで判定せよ:")
    print(f"  python3 scripts/kenshu_auto.py gate --thread {thread} --subtask <ID> --cmd <CMD> --verdict PASS")


def cmd_status(args):
    """レビュー状況確認: kenshu板の投稿者一覧"""
    thread = args.thread
    posters = get_thread_posts("kenshu", thread)
    print(f"[status] kenshu thread={thread} 投稿者: {len(posters)}名")
    for p in posters:
        print(f"  - {p}")

    expected = {"足軽", "勘定吟味役", "お針子", "軍師"}
    found = set()
    for p in posters:
        for e in expected:
            if e in p:
                found.add(e)
    missing = expected - found - {"足軽"}  # 足軽は納品者なので必ずいる
    if missing:
        print(f"\n  未着: {', '.join(missing)}")
    else:
        print(f"\n  ✅ 全レビュアー投稿済み。gate判定可能。")


def cmd_gate(args):
    """gate判定: kenshu_gate POST + scribe + merge/herald"""
    thread = args.thread
    subtask = args.subtask
    cmd_id = args.cmd
    verdict = args.verdict.upper()
    severity = args.severity

    print(f"[gate] subtask={subtask} verdict={verdict} severity={severity}")

    # kenshu_gate POST
    message = f"""subtask_id: {subtask}
cmd_id: {cmd_id}
verdict: {verdict}
severity: {severity}
reviewers:
  - ohariko
  - gunshi
  - kanjou_ginmiyaku
minimum_reviews: 2
summary: 自動gate判定(kenshu_auto.py)
findings: []
tiebreaker: null"""

    subject = f"{subtask} {verdict}判定"
    ok = bbs_post("kenshu_gate", subject, message)
    if not ok:
        print("[ERROR] kenshu_gate POST失敗。手動で投稿せよ。")
        return

    # kenshu_gate thread_idを取得
    import time
    time.sleep(2)
    try:
        url = f"{BBS_BASE}/kenshu_gate/subject.txt"
        with urllib.request.urlopen(url, timeout=5) as resp:
            lines = resp.read().decode("utf-8", errors="replace").splitlines()
        gate_thread = None
        for line in lines:
            if subtask in line:
                gate_thread = line.split(".dat")[0]
                break
    except Exception:
        gate_thread = None

    if not gate_thread:
        print("[WARN] kenshu_gate thread_id取得失敗。手動でscribeせよ。")
        return

    print(f"  ✅ kenshu_gate POST完了 (thread={gate_thread})")

    # scribe実行
    import time
    time.sleep(2)
    result = subprocess.run(
        ["python3", f"{SHOGUN_DIR}/scripts/kanjou_ginmiyaku.py", "scribe", "--thread", gate_thread],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        print(f"  ✅ scribe完了: {result.stdout.strip().split(chr(10))[-1]}")
    else:
        print(f"  ⚠️  scribe失敗: {result.stderr[:100]}")

    if verdict == "PASS":
        # ブランチ名推定
        branch = f"worktree-{subtask.replace('subtask_', 'subtask-')}"
        print(f"\n  [PASS] マージコマンド:")
        print(f"    git merge {branch} --no-edit")
        print(f"    git worktree remove /tmp/worktree-{subtask.replace('subtask_', 'subtask-')} 2>/dev/null || true")
    elif verdict == "FAIL":
        # herald実行
        result = subprocess.run(
            ["python3", f"{SHOGUN_DIR}/scripts/kanjou_ginmiyaku.py", "herald", "--thread", gate_thread],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print(f"  ✅ herald完了(任務板に差し戻し通知)")
        else:
            print(f"  ⚠️  herald失敗: {result.stderr[:100]}")

    print(f"\n[gate] 完了。")


def main():
    parser = argparse.ArgumentParser(description="検収フロー自動化CLI (Phase 3)")
    sub = parser.add_subparsers(dest="command")

    # trigger
    p_trigger = sub.add_parser("trigger", help="2F合議トリガー発火")
    p_trigger.add_argument("--thread", required=True, help="kenshu板のスレッドID")

    # status
    p_status = sub.add_parser("status", help="レビュー状況確認")
    p_status.add_argument("--thread", required=True, help="kenshu板のスレッドID")

    # gate
    p_gate = sub.add_parser("gate", help="gate判定(POST+scribe+merge/herald)")
    p_gate.add_argument("--thread", required=True, help="kenshu板のスレッドID")
    p_gate.add_argument("--subtask", required=True, help="subtask ID")
    p_gate.add_argument("--cmd", required=True, help="cmd ID")
    p_gate.add_argument("--verdict", required=True, choices=["PASS", "FAIL", "CONDITIONAL"])
    p_gate.add_argument("--severity", default="S4", choices=["S1", "S2", "S3", "S4"])

    args = parser.parse_args()
    if args.command == "trigger":
        cmd_trigger(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "gate":
        cmd_gate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
