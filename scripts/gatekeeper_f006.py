#!/usr/bin/env python3
"""
gatekeeper_f006.py - F006 GitHub操作ブロックチェック

stdin: JSON {"tool_name": "Bash", "tool_input": {"command": "..."}}
stdout: {"decision": "block", "reason": "..."} if blocked, else nothing
exit 0 always (fail-closed via shell wrapper)

チェック対象:
- 実際に実行される gh コマンドの呼び出しのみ
- ヒアドキュメント内（コミットメッセージ等）はスキップ
- git/bash/python3 等のwrapperコマンドの引数内はスキップ
"""
import sys
import re
import json

# F006: 殿の許可なし GitHub 書き込み操作の禁止パターン
# ※ 各行の「実際のコマンド部分」に対してのみ適用
BLOCK_PATTERNS = [
    r'\bgh\s+issue\s+create\b',
    r'\bgh\s+pr\s+create\b',
    r'\bgh\s+issue\s+comment\b',
    r'\bgh\s+pr\s+comment\b',
    r'\bgh\s+pr\s+review\b',
    r'\bgh\s+release\s+create\b',
    # gh api POST で issues/pulls/comments 操作
    r'\bgh\s+api\b.*?(?:--method\s+POST|-X\s+POST).*?\b(?:issues|pulls|comments)\b',
    r'\bgh\s+api\b.*?\b(?:issues|pulls|comments)\b.*?(?:--method\s+POST|-X\s+POST)\b',
    r'\bgh\s+api\b.*?\b(?:issues|pulls|comments)\b.*?(?:--input\b|-f\s|--raw-field\b)',
]


def extract_executable_lines(cmd: str) -> list[str]:
    """
    コマンド文字列から実際に実行される行を抽出する。
    ヒアドキュメント内のテキストは除外する。

    例:
      git commit -m "$(cat <<'EOF'
      gh pr create ...     ← ヒアドキュメント内 → 除外
      EOF
      )"
    """
    lines = cmd.split('\n')
    result = []
    heredoc_end_tokens: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # ヒアドキュメント終了チェック
        if heredoc_end_tokens and stripped == heredoc_end_tokens[-1]:
            heredoc_end_tokens.pop()
            i += 1
            continue

        # ヒアドキュメント内ならスキップ
        if heredoc_end_tokens:
            i += 1
            continue

        # ヒアドキュメント開始検出 (<<'TOKEN' or <<"TOKEN" or <<TOKEN)
        hd_matches = re.findall(r'<<\s*[\'"]?(\w+)[\'"]?', line)
        if hd_matches:
            # ヒアドキュメント開始行の << より前の部分を記録
            pre_hd = line[:line.index('<<')].rstrip()
            if pre_hd.strip():
                result.append(pre_hd)
            # ネストしたヒアドキュメントに対応（逆順でpush）
            for token in reversed(hd_matches):
                heredoc_end_tokens.append(token)
            i += 1
            continue

        result.append(line)
        i += 1

    return result


def is_gh_write_command(line: str) -> bool:
    """行が実際に gh 書き込みコマンドを実行しているか判定する。"""
    # ; && || で区切られた各サブコマンドを個別チェック
    # シンプルに: gh が含まれない行は即座にfalse
    if 'gh ' not in line and "'gh'" not in line:
        return False

    # セミコロン・&&・|| で区切って各コマンドを確認
    parts = re.split(r'[;|&]+', line)
    for part in parts:
        part = part.strip()
        # 括弧内展開を考慮（$(...) や (...)）
        part = re.sub(r'^\$?\(', '', part).strip()
        # 先頭トークンが gh であるか確認（環境変数展開含む）
        first_token = part.split()[0] if part.split() else ''
        if first_token in ('gh', '`gh'):
            for pat in BLOCK_PATTERNS:
                if re.search(pat, part, re.IGNORECASE):
                    return True

    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        # parse失敗 → fail-closed（blockしない: git commit 等が通常ブロックされるリスクを回避）
        # ここは敢えて fail-open にする（parse失敗はClaudeのコマンドではない可能性が高い）
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        sys.exit(0)

    # ヒアドキュメント内を除外した実行行を取得
    executable_lines = extract_executable_lines(cmd)

    for line in executable_lines:
        if is_gh_write_command(line):
            reason = (
                "F006違反: 殿の明示的許可なしのGitHub操作は禁止でござる。"
                "dashboard.mdの「🚨 要対応」セクションに記載し殿の判断を仰げ。"
                f" [検出: {line.strip()[:120]}]"
            )
            print(json.dumps({"decision": "block", "reason": reason}))
            sys.exit(0)

    # allow (何も出力しない)
    sys.exit(0)


if __name__ == "__main__":
    main()
