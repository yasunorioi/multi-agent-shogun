#!/usr/bin/env python3
"""
kanjou_ginmiyaku.py — 勘定吟味役 (v4.0 2F外部監査エージェント)

4モード:
  review  --thread <id>          外部監査 (MBP ollama qwen2.5:32b)
  scribe  --thread <id>          書記官 (kenshu_gate→没日録DB)
  herald  --thread <id>          伝令 (FAIL→任務板POST)
  search  --query <q> [--thread] RAG検索 (没日録DB + BBS DAT)

BBS API: http://localhost:8824
MBP:     ssh yasu@mbp.local  /usr/local/bin/ollama run qwen2.5:32b
"""

import argparse
import subprocess
import sys
import os
import urllib.parse
import urllib.request
import re

BBS_BASE   = "http://localhost:8824/bbs"
BBS_CGI    = "http://localhost:8824/bbs/test/bbs.cgi"
MBP_HOST   = "yasu@mbp.local"
OLLAMA_BIN = "/usr/local/bin/ollama"
OLLAMA_MODEL = "qwen2.5:32b"
AGENT_NAME = "勘定吟味役"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOTSUNI    = os.path.join(SCRIPT_DIR, "botsunichiroku.py")


# ============================================================
# BBS ユーティリティ
# ============================================================

def bbs_get_dat(board: str, thread_id: str) -> list[dict]:
    """DATを取得し投稿リストを返す。fields: no, name, mail, date, body, title"""
    url = f"{BBS_BASE}/{board}/dat/{thread_id}.dat"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            raw = r.read()
    except Exception as e:
        print(f"[ERROR] DAT取得失敗: {url} — {e}", file=sys.stderr)
        return []

    try:
        text = raw.decode("cp932")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")

    posts = []
    for i, line in enumerate(text.strip().split("\n"), 1):
        parts = line.split("<>")
        if len(parts) < 4:
            continue
        body = parts[3].replace("<br>", "\n").replace("<br />", "\n")
        posts.append({
            "no":    i,
            "name":  parts[0],
            "mail":  parts[1] if len(parts) > 1 else "",
            "date":  parts[2] if len(parts) > 2 else "",
            "body":  body,
            "title": parts[4] if len(parts) > 4 else "",
        })
    return posts


def bbs_post(board: str, thread_id: str, message: str) -> bool:
    """検収板等にレスを投稿する"""
    data = urllib.parse.urlencode({
        "bbs":     board,
        "key":     thread_id,
        "FROM":    AGENT_NAME,
        "MESSAGE": message,
        "time":    "0",
    }).encode()
    try:
        with urllib.request.urlopen(BBS_CGI, data=data, timeout=15) as r:
            resp = r.read().decode("cp932", errors="replace")
            if "書き込みました" in resp or "ＥＲＲＯＲ" not in resp:
                return True
            print(f"[WARN] BBS POST応答: {resp[:200]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[ERROR] BBS POST失敗: {e}", file=sys.stderr)
        return False


def bbs_search_dat(board: str, keyword: str) -> list[dict]:
    """板の全DATをキーワード検索。ヒットした投稿を返す"""
    subject_url = f"{BBS_BASE}/{board}/subject.txt"
    try:
        with urllib.request.urlopen(subject_url, timeout=10) as r:
            raw = r.read()
        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
    except Exception:
        return []

    results = []
    for line in text.strip().split("\n"):
        if not line:
            continue
        tid = line.split(".dat<>")[0]
        posts = bbs_get_dat(board, tid)
        for p in posts:
            if keyword.lower() in p["body"].lower() or keyword.lower() in p["title"].lower():
                results.append({"board": board, "thread": tid, **p})
    return results


# ============================================================
# ollama (MBP SSH)
# ============================================================

def ollama_ask(prompt: str, timeout: int = 120) -> str:
    """MBP ollamaにプロンプトを送り応答テキストを返す"""
    cmd = ["ssh", "-o", "ConnectTimeout=10", MBP_HOST,
           f"{OLLAMA_BIN} run {OLLAMA_MODEL}"]
    try:
        result = subprocess.run(
            cmd,
            input=prompt.encode(),
            capture_output=True,
            timeout=timeout,
        )
        raw = result.stdout.decode("utf-8", errors="replace")
        # 制御文字・プログレス行を除去
        clean_lines = []
        for line in raw.split("\n"):
            # ANSI エスケープシーケンス除去
            line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', line)
            line = re.sub(r'\x1b\[[?][0-9]*[lh]', '', line)
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', line)
            line = line.strip()
            if line and not line.startswith("⠋") and not line.startswith("⠹"):
                clean_lines.append(line)
        return "\n".join(clean_lines).strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT] ollama応答タイムアウト"
    except Exception as e:
        return f"[ERROR] ollama呼出し失敗: {e}"


# ============================================================
# A. review モード（外部監査）
# ============================================================

def mode_review(thread_id: str, board: str = "kenshu"):
    """検収板スレを読み、qwen2.5:32bでレビューし結果をレスで投稿"""
    print(f"[review] board={board} thread={thread_id}")

    posts = bbs_get_dat(board, thread_id)
    if not posts:
        print("[ERROR] スレ内容取得失敗", file=sys.stderr)
        sys.exit(1)

    # スレ内容をテキスト化
    thread_text = f"=== 検収板スレ {thread_id} ===\n"
    for p in posts:
        thread_text += f"\n[{p['no']}] {p['name']} ({p['date']})\n{p['body']}\n"

    prompt = f"""あなたはコードレビュアーです。以下は検収板（QAボード）のスレッドです。
納品物のdiff・テスト結果・自己レビューを確認し、以下の観点でレビューしてください。

【レビュー観点】
1. バグ・ロジックエラーの可能性
2. セキュリティ上の懸念
3. テスト充足度（境界値・異常系の抜け）
4. 要件との整合性
5. 総評（PASS推奨 / 要確認 / FAIL推奨）

回答は日本語で、200文字以内で簡潔にまとめてください。

{thread_text}
"""

    print("[review] ollama送信中...")
    response = ollama_ask(prompt)
    print(f"[review] ollama応答:\n{response}\n")

    message = f"[勘定吟味役 外部監査]\n{response}"
    if bbs_post(board, thread_id, message):
        print(f"[review] 検収板 thread={thread_id} にレス投稿完了")
    else:
        print("[review] BBS投稿失敗。結果はstdoutに出力済み", file=sys.stderr)


# ============================================================
# B. scribe モード（書記官）
# ============================================================

def mode_scribe(thread_id: str, board: str = "kenshu_gate"):
    """kenshu_gate板からverdict/reviewers/summaryを読み没日録DBに記録"""
    print(f"[scribe] board={board} thread={thread_id}")

    posts = bbs_get_dat(board, thread_id)
    if not posts:
        print("[ERROR] スレ内容取得失敗", file=sys.stderr)
        sys.exit(1)

    # kenshu_gate YAMLをパース（最後の投稿を優先）
    verdict = None
    reviewers = []
    summary = ""
    subtask_id = None
    cmd_id = None

    for p in reversed(posts):
        body = p["body"]
        # YAML-like フィールド抽出
        m_verdict   = re.search(r"verdict:\s*(PASS|FAIL|CONDITIONAL)", body)
        m_reviewers = re.search(r"reviewers:\s*\[([^\]]+)\]", body)
        m_summary   = re.search(r"summary:\s*[\"']?(.+?)[\"']?\s*$", body, re.M)
        m_subtask   = re.search(r"subtask_id:\s*(subtask_\d+)", body)
        m_cmd       = re.search(r"cmd_id:\s*(cmd_\d+)", body)

        if m_verdict and verdict is None:
            verdict = m_verdict.group(1)
        if m_reviewers and not reviewers:
            reviewers = [r.strip().strip('"\'') for r in m_reviewers.group(1).split(",")]
        if m_summary and not summary:
            summary = m_summary.group(1).strip()
        if m_subtask and not subtask_id:
            subtask_id = m_subtask.group(1)
        if m_cmd and not cmd_id:
            cmd_id = m_cmd.group(1)

        if verdict and reviewers and summary and subtask_id:
            break

    if not verdict:
        print("[scribe] verdictが見つかりません。kenshu_gate板を確認してください", file=sys.stderr)
        sys.exit(1)
    if not subtask_id:
        print("[scribe] subtask_idが見つかりません", file=sys.stderr)
        sys.exit(1)

    print(f"[scribe] subtask={subtask_id} verdict={verdict} reviewers={reviewers}")

    # 没日録DBにaudit record投入
    cmd = [
        sys.executable, BOTSUNI, "audit", "add", subtask_id,
        "--verdict", verdict,
        "--kenshu-thread", thread_id,
        "--reviewers", ",".join(reviewers) if reviewers else "kanjou_ginmiyaku",
        "--summary", summary or f"kenshu_gate thread={thread_id} verdict={verdict}",
    ]
    if cmd_id:
        cmd += ["--cmd", cmd_id]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[scribe] 没日録DB audit record投入完了: {result.stdout.strip()}")
    else:
        print(f"[scribe] audit add失敗: {result.stderr.strip()}", file=sys.stderr)
        print(f"[scribe] コマンド: {' '.join(cmd)}", file=sys.stderr)
        # subtask_1080でaudit add CLIが実装される。現時点ではエラーを報告して続行
        print("[scribe] ※ subtask_1080完了後に統合テスト予定", file=sys.stderr)


# ============================================================
# C. herald モード（伝令）
# ============================================================

def mode_herald(thread_id: str, board: str = "kenshu_gate"):
    """kenshu_gateのFAIL判定を検知し任務板にリジェクト通知をPOST"""
    print(f"[herald] board={board} thread={thread_id}")

    posts = bbs_get_dat(board, thread_id)
    if not posts:
        print("[ERROR] スレ内容取得失敗", file=sys.stderr)
        sys.exit(1)

    verdict = None
    subtask_id = None
    summary = ""
    findings = []

    for p in reversed(posts):
        body = p["body"]
        m_verdict = re.search(r"verdict:\s*(PASS|FAIL|CONDITIONAL)", body)
        m_subtask = re.search(r"subtask_id:\s*(subtask_\d+)", body)
        m_summary = re.search(r"summary:\s*[\"']?(.+?)[\"']?\s*$", body, re.M)
        m_findings = re.findall(r"-\s+(.+)", body)

        if m_verdict and verdict is None:
            verdict = m_verdict.group(1)
        if m_subtask and not subtask_id:
            subtask_id = m_subtask.group(1)
        if m_summary and not summary:
            summary = m_summary.group(1).strip()
        if m_findings and not findings:
            findings = m_findings

        if verdict and subtask_id:
            break

    print(f"[herald] verdict={verdict} subtask={subtask_id}")

    if verdict != "FAIL":
        print(f"[herald] verdict={verdict} — FAIL以外のため伝令不要。終了します。")
        return

    # 任務板にリジェクト通知POST
    findings_text = "\n".join(f"- {f}" for f in findings[:5]) if findings else "詳細はkenshu_gate参照"
    message = (
        f"[リジェクト通知] {subtask_id or 'subtask不明'}\n"
        f"verdict: FAIL\n"
        f"理由: {summary}\n"
        f"指摘:\n{findings_text}\n"
        f"kenshu_gate thread: {thread_id}\n"
        f"→ 修正後、検収板に再納品してください。"
    )

    if bbs_post("ninmu", thread_id, message):
        print(f"[herald] 任務板にリジェクト通知POST完了 (subtask={subtask_id})")
    else:
        print("[herald] 任務板POST失敗", file=sys.stderr)
        sys.exit(1)


# ============================================================
# D. search モード（RAG検索）
# ============================================================

def mode_search(query: str, thread_id: str | None = None, board: str = "kenshu"):
    """没日録DB + BBS DAT横断検索。--thread指定時は検収板にレスで投稿"""
    print(f"[search] query='{query}' thread={thread_id}")

    results = []

    # 没日録DB検索
    result = subprocess.run(
        [sys.executable, BOTSUNI, "search", query, "--limit", "5"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        results.append("【没日録DB検索結果】")
        results.append(result.stdout.strip()[:800])
    else:
        results.append("【没日録DB】ヒットなし")

    # BBS DAT検索（検収板・kenshu_gate）
    for search_board in ["kenshu", "kenshu_gate", "zatsudan"]:
        hits = bbs_search_dat(search_board, query)
        if hits:
            results.append(f"\n【BBS {search_board} 検索結果 ({len(hits)}件)】")
            for h in hits[:3]:
                snippet = h["body"][:120].replace("\n", " ")
                results.append(f"  [{h['board']}/{h['thread']} >>>{h['no']}] {snippet}...")

    output = "\n".join(results)
    print(output)

    if thread_id:
        message = f"[勘定吟味役 RAG検索] query='{query}'\n{output}"
        if bbs_post(board, thread_id, message):
            print(f"[search] 検収板 thread={thread_id} にレス投稿完了")
        else:
            print("[search] BBS投稿失敗。結果はstdoutに出力済み", file=sys.stderr)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="勘定吟味役 — v4.0 2F外部監査+書記+伝令+検索エージェント"
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # review
    p_review = sub.add_parser("review", help="外部監査 (MBP ollama qwen2.5:32b)")
    p_review.add_argument("--thread", required=True, help="検収板スレID")
    p_review.add_argument("--board", default="kenshu", help="板名 (default: kenshu)")

    # scribe
    p_scribe = sub.add_parser("scribe", help="書記官 (kenshu_gate→没日録DB)")
    p_scribe.add_argument("--thread", required=True, help="kenshu_gateスレID")
    p_scribe.add_argument("--board", default="kenshu_gate", help="板名 (default: kenshu_gate)")

    # herald
    p_herald = sub.add_parser("herald", help="伝令 (FAIL→任務板POST)")
    p_herald.add_argument("--thread", required=True, help="kenshu_gateスレID")
    p_herald.add_argument("--board", default="kenshu_gate", help="板名 (default: kenshu_gate)")

    # search
    p_search = sub.add_parser("search", help="RAG検索 (没日録DB + BBS DAT)")
    p_search.add_argument("--query", required=True, help="検索キーワード")
    p_search.add_argument("--thread", default=None, help="投稿先スレID (省略時はstdout)")
    p_search.add_argument("--board", default="kenshu", help="投稿先板名 (default: kenshu)")

    args = parser.parse_args()

    if args.mode == "review":
        mode_review(args.thread, args.board)
    elif args.mode == "scribe":
        mode_scribe(args.thread, args.board)
    elif args.mode == "herald":
        mode_herald(args.thread, args.board)
    elif args.mode == "search":
        mode_search(args.query, args.thread, args.board)


if __name__ == "__main__":
    main()
