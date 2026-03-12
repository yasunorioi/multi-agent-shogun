"""sanitizer.py — 外部検索結果のTier1正規表現フィルタ

高札v2の外部検索結果（Web/X）からノイズ・危険コンテンツを除去する。
構造的分離（情報層と実行層が別）が前提のため、Tier1正規表現で十分。

Design: kosatsu_v2_bridgehead.md §K
"""

import re

# --- Tier 1: 正規表現フィルタパターン ---

# スパム・宣伝パターン
_SPAM_PATTERNS = [
    re.compile(r"(?i)(buy now|click here|subscribe|limited offer|free trial)"),
    re.compile(r"(?i)(viagra|casino|crypto.?trading|forex.?signal)"),
    re.compile(r"(?i)(earn \$?\d+.*per (day|hour|month))"),
]

# プロンプトインジェクション防御
_INJECTION_PATTERNS = [
    re.compile(r"(?i)(ignore (previous|above|all) instructions?)"),
    re.compile(r"(?i)(you are now|act as|pretend to be|roleplay)"),
    re.compile(r"(?i)(system prompt|SYSTEM:|<\|im_start\|>)"),
    re.compile(r"(?i)(do not follow|disregard|forget everything)"),
]

# 明らかに無関係なコンテンツ
_NOISE_PATTERNS = [
    re.compile(r"(?i)(cookie policy|privacy policy|terms of service|accept cookies)"),
    re.compile(r"(?i)(sign up|log ?in|register now|create account)"),
]


def sanitize_external_result(result: dict) -> dict | None:
    """外部検索結果をサニタイズする。

    Args:
        result: {"source": str, "title": str, "snippet": str, "url": str}

    Returns:
        サニタイズ済みresult。フィルタ対象の場合はNone。
    """
    text = f"{result.get('title', '')} {result.get('snippet', '')}"

    # スパムチェック
    for pattern in _SPAM_PATTERNS:
        if pattern.search(text):
            return None

    # インジェクションチェック
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return None

    # ノイズチェック
    for pattern in _NOISE_PATTERNS:
        if pattern.search(text):
            return None

    # HTMLタグ除去
    snippet = result.get("snippet", "")
    snippet = re.sub(r"<[^>]+>", "", snippet)
    snippet = re.sub(r"\s+", " ", snippet).strip()

    # 500文字で切り詰め
    if len(snippet) > 500:
        snippet = snippet[:497] + "..."

    return {
        "source": result.get("source", "web"),
        "title": re.sub(r"<[^>]+>", "", result.get("title", "")).strip()[:200],
        "snippet": snippet,
        "url": result.get("url", ""),
    }
