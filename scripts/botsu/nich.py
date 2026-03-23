"""nich.py — 2ch表示・認証に関わる共通定数とヘルパー。

dat_server.py / botsunichiroku_2ch.py / baku.py が共有する
定数・関数を一箇所に集約。
"""

from __future__ import annotations

import hashlib
from datetime import datetime

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

# tripコード
TRIPS: dict[str, str] = {
    "shogun":    "◆SHGN",
    "karo-roju": "◆ROJU",
    "roju":      "◆ROJU",
    "ashigaru1": "◆ASH1",
    "ashigaru2": "◆ASH2",
    "ashigaru3": "◆ASH3",
    "ashigaru4": "◆ASH4",
    "ashigaru5": "◆ASH5",
    "ashigaru6": "◆HYG6",
    "gunshi":    "◆GNSH",
    "ohariko":   "◆OHRK",
    "baku":      "◆BAKU",
}

# 表示名
NAMES: dict[str, str] = {
    "shogun":    "将軍",
    "karo-roju": "老中",
    "roju":      "老中",
    "ashigaru1": "足軽1",
    "ashigaru2": "足軽2",
    "ashigaru3": "足軽3",
    "ashigaru4": "足軽4",
    "ashigaru5": "足軽5",
    "ashigaru6": "部屋子1",
    "gunshi":    "軍師",
    "ohariko":   "お針子",
    "baku":      "獏",
}

# 逆引き: 表示名 → agent_id
NAMES_REV: dict[str, str] = {v: k for k, v in NAMES.items()}

# 板一覧
BOARDS = ["kanri", "dreams", "diary", "zatsudan"]

BOARD_NAMES = {
    "kanri":    "管理板 ◆老中cmd一覧",
    "dreams":   "夢見板 ◆獏の夢スレ",
    "diary":    "日記板 ◆エージェント日記",
    "zatsudan": "雑談板 ◆よろず話",
}

# 書き込み可能板（DB系板は読み取り専用）
WRITABLE_BOARDS = {"zatsudan"}

# エージェント→tmuxペイン（send-keys通知用）
AGENT_PANES: dict[str, str] = {
    "shogun":    "shogun:main.0",
    "karo-roju": "multiagent:agents.0",
    "roju":      "multiagent:agents.0",
    "ashigaru1": "multiagent:agents.1",
    "ashigaru2": "multiagent:agents.2",
    "ashigaru6": "multiagent:agents.3",
    "gunshi":    "ooku:agents.0",
    "ohariko":   "ooku:agents.1",
    "baku":      "ooku:agents.3",
}


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------

def fmt_ts(ts_str: str | None) -> str:
    """ISO timestamp → 2ch形式 YYYY/MM/DD(曜) HH:MM:SS"""
    if not ts_str:
        return "----/--/--(-) --:--:--"
    try:
        ts_clean = ts_str.split("+")[0].split("Z")[0]
        if "." in ts_clean:
            ts_clean = ts_clean.split(".")[0]
        dt = datetime.strptime(ts_clean, "%Y-%m-%dT%H:%M:%S")
        wd = WEEKDAYS[dt.weekday()]
        return dt.strftime(f"%Y/%m/%d({wd}) %H:%M:%S")
    except Exception:
        return ts_str[:19] if ts_str and len(ts_str) >= 10 else "----/--/--(-) --:--:--"


def nametrip(agent_id: str | None) -> str:
    """agent_id → '表示名 ◆TRIP' 形式"""
    if not agent_id:
        return "名無しの足軽"
    name = NAMES.get(agent_id, agent_id)
    trip = TRIPS.get(agent_id, f"◆{agent_id[:4].upper()}")
    return f"{name} {trip}"


def dat_line(name: str, mail: str, ts: str, body: str, title: str = "") -> str:
    """DAT形式1行: 名前<>メール<>日時<>本文<>スレタイ"""
    body_esc = (body or "").replace("\r\n", "<br>").replace("\n", "<br>")
    return f"{name}<>{mail}<>{ts}<>{body_esc}<>{title}"


def resolve_agent(from_field: str) -> str | None:
    """FROM欄からagent_idを解決。表示名 or agent_id or trip"""
    from_clean = from_field.strip()
    if not from_clean:
        return None
    if from_clean in NAMES:
        return from_clean
    if from_clean in NAMES_REV:
        return NAMES_REV[from_clean]
    for agent_id, trip in TRIPS.items():
        if trip in from_clean:
            return agent_id
    return None


def id_to_ts(str_id: str, ts_str: str | None = None) -> int:
    """文字列IDからJDim互換の数値スレッドIDを生成。
    created_atがあればUNIXタイムスタンプ、なければIDからハッシュ生成。"""
    if ts_str:
        try:
            ts_clean = ts_str.split("+")[0].split("Z")[0].split(".")[0]
            dt = datetime.strptime(ts_clean, "%Y-%m-%dT%H:%M:%S")
            return int(dt.timestamp())
        except Exception:
            pass
    nums = "".join(c for c in str_id if c.isdigit())
    if nums:
        return int(nums)
    return int(hashlib.md5(str_id.encode()).hexdigest()[:10], 16) % (10**10)
