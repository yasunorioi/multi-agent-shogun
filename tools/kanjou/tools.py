"""勘定吟味役 — ツール実装（全て読み取り専用）

1. DBQueryTool   — 没日録DB CLIラッパー
2. KousatsuAPITool — 高札API (localhost:8080) クライアント
3. FileReadTool  — 安全なファイル読み取り
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

import httpx

# ---------- Constants ----------

BOTSUNICHIROKU_CLI = "scripts/botsunichiroku.py"
PROJECT_ROOT = Path("/home/yasu/multi-agent-shogun")
KOUSATSU_BASE = "http://localhost:8080"
KOUSATSU_TIMEOUT = 5.0

# subtask_id validation: subtask_\d+
_SUBTASK_RE = re.compile(r"^subtask_\d+$")
# cmd_id validation: cmd_\d+
_CMD_RE = re.compile(r"^cmd_\d+$")
# worker_id validation: ashigaru\d+ or ohariko
_WORKER_RE = re.compile(r"^(ashigaru\d+|ohariko)$")


# ---------- DBQueryTool ----------

class DBQueryTool:
    """没日録DB (data/botsunichiroku.db) 読み取り専用ツール."""

    def subtask_show(self, subtask_id: str) -> Optional[str]:
        if not _SUBTASK_RE.match(subtask_id):
            return None
        return self._run_cli("subtask", "show", subtask_id)

    def report_list(self, subtask_id: str) -> Optional[str]:
        if not _SUBTASK_RE.match(subtask_id):
            return None
        return self._run_cli("report", "list", "--subtask", subtask_id)

    def cmd_show(self, cmd_id: str) -> Optional[str]:
        if not _CMD_RE.match(cmd_id):
            return None
        return self._run_cli("cmd", "show", cmd_id)

    def _run_cli(self, *args: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["python3", str(PROJECT_ROOT / BOTSUNICHIROKU_CLI), *args],
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None


# ---------- KousatsuAPITool ----------

class KousatsuAPITool:
    """高札API (http://localhost:8080) クライアント（読み取り専用）."""

    def __init__(self, base_url: str = KOUSATSU_BASE, timeout: float = KOUSATSU_TIMEOUT):
        self._base_url = base_url
        self._timeout = timeout

    def health(self) -> bool:
        try:
            r = httpx.get(f"{self._base_url}/health", timeout=self._timeout)
            return r.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    def search_similar(self, subtask_id: str) -> Optional[dict]:
        if not _SUBTASK_RE.match(subtask_id):
            return None
        return self._get("/search/similar", params={"subtask_id": subtask_id})

    def audit_history(self, worker_id: str) -> Optional[dict]:
        if not _WORKER_RE.match(worker_id):
            return None
        return self._get("/audit/history", params={"worker": worker_id})

    def check_coverage(self, cmd_id: str) -> Optional[dict]:
        if not _CMD_RE.match(cmd_id):
            return None
        return self._get("/check/coverage", params={"cmd_id": cmd_id})

    def _get(self, endpoint: str, params: dict | None = None) -> Optional[dict]:
        try:
            r = httpx.get(
                f"{self._base_url}{endpoint}",
                params=params or {},
                timeout=self._timeout,
            )
            if r.status_code == 200:
                return r.json()
            return None
        except (httpx.ConnectError, httpx.TimeoutException, ValueError):
            return None


# ---------- FileReadTool ----------

class FileReadTool:
    """安全なファイル読み取り。PROJECT_ROOT配下のみ許可."""

    def __init__(self, allowed_root: Path = PROJECT_ROOT):
        self._allowed_root = allowed_root.resolve()

    def read(self, path: str) -> Optional[str]:
        try:
            resolved = Path(path).resolve()
            if not str(resolved).startswith(str(self._allowed_root)):
                return None
            if not resolved.is_file():
                return None
            return resolved.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            return None
