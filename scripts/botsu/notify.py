"""notify — tmux send-keys 通知の共通モジュール。

reply add 等から呼ばれ、書き込みを他エージェントに通知する。
"""

from __future__ import annotations

import subprocess

from .nich import AGENT_PANES, NAMES, NAMES_REV

# @メンション時のみ通知するエージェント（ブロードキャスト対象外）
MENTION_ONLY: set[str] = {"shogun"}


def notify_post(board: str, thread_id: str, author_id: str, message: str) -> None:
    """書き込み通知。@メンション解析 + 全エージェントへの通知。"""
    preview = message.replace("\n", " ")[:80]
    agent_name = NAMES.get(author_id, author_id)

    # @メンション通知（優先）
    mentioned: set[str] = set()
    for aid in AGENT_PANES:
        if f"@{aid}" in message:
            mentioned.add(aid)
        display = NAMES.get(aid, "")
        if display and f"@{display}" in message:
            mentioned.add(aid)

    for aid in mentioned:
        if aid != author_id:
            pane = AGENT_PANES.get(aid)
            if pane:
                send_keys(
                    pane,
                    f"[{board}/{thread_id}] {agent_name}があなた宛に書き込み: {preview}"
                )

    # 自分以外の全エージェントに通知（MENTION_ONLYは除外）
    notify_msg = f"[2ch] {board}/{thread_id} に {agent_name} が書き込み: {preview}"
    for aid, pane in AGENT_PANES.items():
        if aid != author_id and aid not in mentioned and aid not in MENTION_ONLY:
            send_keys(pane, notify_msg)


def send_keys(pane: str, message: str) -> None:
    """tmux send-keys でメッセージを送信（2段階: テキスト + Enter）。"""
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, message[:500]],
            capture_output=True, timeout=3,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", pane, "Enter"],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass
