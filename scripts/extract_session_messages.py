#!/usr/bin/env python3
"""
Extract human and AI messages from Claude Code JSONL session logs.

Reads all .jsonl files in the specified directory and extracts:
- Human messages: type=="user", content is a string (not list/tool_result)
- AI messages: type=="assistant", content is a string or list with "text" entries

Outputs:
- /tmp/split_human_messages.txt
- /tmp/spirit_ai_messages.txt
"""

import json
import glob
import os
import sys
from datetime import datetime


def extract_session_date(filepath):
    """Extract session date from the first timestamped entry in the file."""
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ts = obj.get("timestamp")
                if ts:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d")
            except (json.JSONDecodeError, ValueError):
                continue
    return "unknown-date"


def escape_newlines(text):
    """Replace newlines with \\n so each message stays on one line."""
    return text.replace("\n", "\\n").replace("\r", "")


def extract_ai_text_from_content(content):
    """Extract text from assistant message content (string or list)."""
    texts = []
    if isinstance(content, str):
        stripped = content.strip()
        if stripped:
            texts.append(stripped)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "").strip()
                if text:
                    texts.append(text)
    return texts


def process_files(directory):
    """Process all JSONL files and extract messages."""
    pattern = os.path.join(directory, "*.jsonl")
    files = sorted(glob.glob(pattern))

    total_sessions = len(files)
    total_human = 0
    total_ai = 0
    all_dates = []

    human_messages = []
    ai_messages = []

    for file_idx, filepath in enumerate(files, 1):
        session_date = extract_session_date(filepath)
        session_id = os.path.basename(filepath).replace(".jsonl", "")
        if session_date != "unknown-date":
            all_dates.append(session_date)

        if file_idx % 50 == 0:
            print(f"  Processing file {file_idx}/{total_sessions}...", file=sys.stderr)

        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = obj.get("type")
                message = obj.get("message", {})
                if not isinstance(message, dict):
                    continue

                role = message.get("role")
                content = message.get("content")

                # Human messages: type=="user", content is a string (not list)
                if entry_type == "user" and role == "user" and isinstance(content, str):
                    text = content.strip()
                    if text:
                        human_messages.append(
                            f"[{session_date}] {escape_newlines(text)}"
                        )
                        total_human += 1

                # AI messages: type=="assistant", extract text entries
                elif entry_type == "assistant" and role == "assistant":
                    texts = extract_ai_text_from_content(content)
                    for text in texts:
                        ai_messages.append(
                            f"[{session_date}] {escape_newlines(text)}"
                        )
                        total_ai += 1

    return {
        "total_sessions": total_sessions,
        "total_human": total_human,
        "total_ai": total_ai,
        "all_dates": all_dates,
        "human_messages": human_messages,
        "ai_messages": ai_messages,
    }


def main():
    directory = "/home/yasu/.claude/projects/-home-yasu-multi-agent-shogun"

    print(f"Scanning JSONL files in: {directory}", file=sys.stderr)
    results = process_files(directory)

    # Write human messages
    human_out = "/tmp/split_human_messages.txt"
    with open(human_out, "w", encoding="utf-8") as f:
        for msg in results["human_messages"]:
            f.write(msg + "\n")
    print(f"Written: {human_out}", file=sys.stderr)

    # Write AI messages
    ai_out = "/tmp/spirit_ai_messages.txt"
    with open(ai_out, "w", encoding="utf-8") as f:
        for msg in results["ai_messages"]:
            f.write(msg + "\n")
    print(f"Written: {ai_out}", file=sys.stderr)

    # Summary stats
    dates = sorted(results["all_dates"])
    date_range_start = dates[0] if dates else "N/A"
    date_range_end = dates[-1] if dates else "N/A"

    print("\n" + "=" * 60)
    print("SESSION LOG EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total sessions:        {results['total_sessions']}")
    print(f"Total human messages:  {results['total_human']}")
    print(f"Total AI messages:     {results['total_ai']}")
    print(f"Date range:            {date_range_start} to {date_range_end}")
    print(f"Output (human):        {human_out}")
    print(f"Output (AI):           {ai_out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
