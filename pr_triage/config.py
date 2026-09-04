"""Configuration loading.

All org-specific values -- GitHub handle, review team, Jira boards, issue-key
pattern -- live in a TOML file outside this repo, so the code itself carries no
company-specific data and is safe to publish.

Search order (first hit wins):
    $PR_TRIAGE_CONFIG
    ./pr-triage.toml
    ~/.config/pr-triage/config.toml
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_ENV = "PR_TRIAGE_CONFIG"
SEARCH_PATHS = (
    Path("pr-triage.toml"),
    Path.home() / ".config" / "pr-triage" / "config.toml",
)


class ConfigError(Exception):
    """Raised when configuration is missing or malformed."""


@dataclass(frozen=True)
class Team:
    """One sub-team, distinguishable only inside the issue tracker."""

    name: str
    board: int | None = None
    sprint_prefix: str = ""

    def owns_sprint(self, sprint_name: str) -> bool:
        """A board may list other teams' sprints, so match on the name prefix."""
        if not self.sprint_prefix:
            return False
        return sprint_name.lower().startswith(self.sprint_prefix.lower())


@dataclass(frozen=True)
class Config:
    user: str
    review_team: str | None = None
    repos: tuple[str, ...] = ()
    jira_enabled: bool = False
    key_pattern: str = r"[A-Z][A-Z0-9]+-\d+"
    teams: tuple[Team, ...] = ()
    max_results: int = 300
    source: Path | None = None

    @property
    def key_re(self) -> re.Pattern[str]:
        return re.compile(rf"\b({self.key_pattern})\b", re.IGNORECASE)

    def team_by_name(self, name: str) -> Team | None:
        want = name.strip().lower()
        return next((t for t in self.teams if t.name.lower() == want), None)

    def repo_filter(self) -> str:
        """GitHub search fragment restricting to configured repos, if any."""
        return " ".join(f"repo:{r}" for r in self.repos)


def _resolve_path(explicit: str | None = None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_file():
            raise ConfigError(f"config file not found: {p}")
        return p

    env = os.environ.get(CONFIG_ENV)
    if env:
        p = Path(env).expanduser()
        if not p.is_file():
            raise ConfigError(f"{CONFIG_ENV} points at a missing file: {p}")
        return p

    for candidate in SEARCH_PATHS:
        p = candidate.expanduser()
        if p.is_file():
            return p

    raise ConfigError(
        "no config found. Copy config.example.toml to "
        "~/.config/pr-triage/config.toml and fill it in, or set "
        f"{CONFIG_ENV}."
    )


def load(explicit: str | None = None) -> Config:
    path = _resolve_path(explicit)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML -- {exc}") from exc

    gh = raw.get("github") or {}
    user = gh.get("user")
    if not user:
        raise ConfigError(f"{path}: [github] user is required")

    jira = raw.get("jira") or {}
    teams = tuple(
        Team(
            name=str(t["name"]),
            board=t.get("board"),
            sprint_prefix=str(t.get("sprint_prefix", "")),
        )
        for t in jira.get("teams", [])
        if t.get("name")
    )

    pattern = str(jira.get("key_pattern", r"[A-Z][A-Z0-9]+-\d+"))
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ConfigError(f"{path}: [jira] key_pattern is not a valid regex -- {exc}") from exc

    return Config(
        user=str(user),
        review_team=gh.get("review_team") or None,
        repos=tuple(str(r) for r in gh.get("repos", [])),
        jira_enabled=bool(jira.get("enabled", bool(teams))),
        key_pattern=pattern,
        teams=teams,
        max_results=int(gh.get("max_results", 300)),
        source=path,
    )
