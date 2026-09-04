"""Shared helpers: subprocess execution and time handling."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc)


class ToolError(Exception):
    """An external CLI (gh / acli) failed or is missing."""


def run(cmd: list[str], timeout: int = 240) -> str:
    """Run a command and return stdout, raising ToolError on any failure."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ToolError(f"{cmd[0]} not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"{cmd[0]} timed out after {timeout}s") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        msg = detail[0] if detail else f"exit {proc.returncode}"
        raise ToolError(f"{cmd[0]}: {msg[:300]}")
    return proc.stdout


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def days_since(when: datetime | None) -> float:
    if not when:
        return 0.0
    return (NOW - when).total_seconds() / 86400
