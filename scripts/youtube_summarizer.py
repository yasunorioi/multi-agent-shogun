"""scripts/youtube_summarizer.py — YouTube字幕取得+Haiku要約 汎用モジュール

使用方法:
    # CLIで直接実行
    python3 scripts/youtube_summarizer.py "https://www.youtube.com/watch?v=xxx"

    # モジュールとしてimport
    from youtube_summarizer import summarize_video
    result = summarize_video("https://www.youtube.com/watch?v=xxx", lang="ja")
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]

# === 設定 ===
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", os.getenv("HAIKU_BASE_URL", "https://api.anthropic.com"))
HAIKU_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HAIKU_MODEL = "claude-haiku-4-5-20251001"
YT_DLP_BIN = "/usr/bin/yt-dlp"
SUBTITLE_MAX_CHARS = 8000   # Haiku入力上限（字幕が長すぎる場合に切り詰め）
DEFAULT_LANG = "ja"


# === VTT → プレーンテキスト変換 ===

def _parse_vtt(vtt_text: str) -> str:
    """WebVTT形式テキストをプレーンテキストに変換する。

    タイムスタンプ行・WEBVTT/NOTE/空行を除去し、重複行を削除する。

    Args:
        vtt_text: VTTファイル全文

    Returns:
        重複除去済みプレーンテキスト
    """
    lines = vtt_text.splitlines()
    seen: set[str] = set()
    result: list[str] = []

    for line in lines:
        line = line.strip()
        # ヘッダ・メタデータ・空行を除去
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        # タイムスタンプ行を除去 (例: 00:00:01.000 --> 00:00:03.000)
        if re.match(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[.,]\d{3}", line):
            continue
        # position/align/line タグ付きタイムスタンプも除去
        if "-->" in line:
            continue
        # インラインタイムスタンプタグを除去 (<00:00:01.000>)
        line = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", line)
        # HTMLタグを除去 (<c>, </c> 等)
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line:
            continue
        # 重複行除去
        if line in seen:
            continue
        seen.add(line)
        result.append(line)

    return "\n".join(result)


# === 字幕取得 ===

def get_subtitles(video_url: str, lang: str = DEFAULT_LANG) -> str:
    """yt-dlpで字幕を取得してプレーンテキストを返す。

    字幕なし・取得失敗時は空文字列を返す（例外は発生させない）。

    Args:
        video_url: YouTube動画URL
        lang: 字幕言語コード（デフォルト: "ja"）

    Returns:
        プレーンテキスト化した字幕。取得失敗時は空文字列。
    """
    with tempfile.TemporaryDirectory(prefix="baku_yt_subs_") as tmpdir:
        # yt-dlp実行: 自動字幕 + 手動字幕 両方試行
        cmd = [
            YT_DLP_BIN,
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", lang,
            "--sub-format", "vtt",
            "--skip-download",
            "--no-playlist",
            "--output", str(Path(tmpdir) / "subtitle"),
            "--quiet",
            video_url,
        ]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            time.sleep(1)  # YouTube rate limit対策
        except subprocess.TimeoutExpired:
            return ""
        except FileNotFoundError:
            return ""

        # .vttファイルを検索
        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            # 言語コードが異なる場合も探索（例: ja-orig.vtt, ja-JP.vtt）
            vtt_files = list(Path(tmpdir).glob(f"*.{lang}*.vtt"))
        if not vtt_files:
            return ""

        # 最初に見つかったVTTファイルを使用
        vtt_text = vtt_files[0].read_text(encoding="utf-8", errors="replace")
        return _parse_vtt(vtt_text)


# === Haiku要約 ===

def summarize_transcript(text: str, max_tokens: int = 300) -> str:
    """Haiku APIで字幕テキストを要約する。

    空文字列入力時はAPI呼び出しなしで空文字列を返す（NullClaw対応）。

    Args:
        text: 字幕プレーンテキスト
        max_tokens: Haiku最大出力トークン数

    Returns:
        要約テキスト。API未設定・空入力時は空文字列。
    """
    if not text:
        return ""
    if not HAIKU_API_KEY:
        return ""

    # 入力が長すぎる場合は切り詰め
    truncated = text[:SUBTITLE_MAX_CHARS]
    if len(text) > SUBTITLE_MAX_CHARS:
        truncated += "\n\n（字幕が長いため冒頭部分のみ使用）"

    system_prompt = "あなたは動画字幕の要約専門家でございます。簡潔かつ正確に内容を要約してください。"
    user_msg = f"以下の動画字幕を要約せよ。3〜5文程度で主要な内容と知見をまとめよ。\n\n{truncated}"

    try:
        if OpenAI is None:
            return ""
        client = OpenAI(
            base_url=f"{ANTHROPIC_BASE_URL}/v1",
            api_key=HAIKU_API_KEY,
        )
        response = client.chat.completions.create(
            model=HAIKU_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"WARN: Haiku要約失敗: {e}", file=sys.stderr)
        return ""


# === 統合インターフェース ===

def summarize_video(video_url: str, lang: str = DEFAULT_LANG) -> dict:
    """YouTube動画URLから字幕取得→要約を一括実行する。

    Args:
        video_url: YouTube動画URL
        lang: 字幕言語コード（デフォルト: "ja"）

    Returns:
        成功時: {"url": url, "subtitles_length": N, "summary": "...",
                 "lang": lang, "summarized_at": "ISO8601"}
        字幕なし: {"url": url, "error": "no_subtitles", "lang": lang}
    """
    subtitles = get_subtitles(video_url, lang=lang)
    if not subtitles:
        return {"url": video_url, "error": "no_subtitles", "lang": lang}

    summary = summarize_transcript(subtitles)
    return {
        "url": video_url,
        "subtitles_length": len(subtitles),
        "summary": summary,
        "lang": lang,
        "summarized_at": datetime.now().isoformat(),
    }


# === CLI ===

def main() -> None:
    if len(sys.argv) < 2:
        print("使用方法: python3 scripts/youtube_summarizer.py <YouTube URL> [lang]", file=sys.stderr)
        sys.exit(1)

    video_url = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_LANG

    result = summarize_video(video_url, lang=lang)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
