"""Jira access via the Atlassian CLI (`acli`).

Jira is strictly an *annotation* layer. It never decides which pull requests you
see -- see DESIGN.md for the measurements behind that rule.

Only issue keys already found on a pull request are ever looked up, and each
team costs a single JQL call, so annotation stays cheap.
"""

from __future__ import annotations

import json

from .config import Config, Team
from .util import ToolError, run

#: Cap on how many sprints feed one `sprint in (...)` clause, to keep JQL short.
MAX_SPRINTS = 40


def _search(jql: str, fields: str = "key,status") -> list[dict]:
    out = run(["acli", "jira", "workitem", "search",
               "--jql", jql, "--fields", fields, "--json"])
    data = json.loads(out or "[]")
    return data if isinstance(data, list) else data.get("issues", [])


def _sprints(team: Team, states: str) -> list[tuple[int, str]]:
    """Sprints on this team's board, filtered to the ones the team actually owns."""
    if not team.board:
        return []
    try:
        raw = run(["acli", "jira", "board", "list-sprints",
                   "--id", str(team.board), "--state", states, "--json"])
    except ToolError:
        return []

    sprints = json.loads(raw or "{}").get("sprints", []) or []
    owned = [(s["id"], s.get("name", "")) for s in sprints
             if team.owns_sprint(s.get("name", ""))]
    # Most recent first; ids increase over time.
    owned.sort(key=lambda pair: pair[0], reverse=True)
    return owned[:MAX_SPRINTS]


def _status_of(issue: dict) -> str | None:
    return ((issue.get("fields") or {}).get("status") or {}).get("name")


def annotate(prs, cfg: Config, depth: int) -> list[str]:
    """
    Attach team / sprint / status to each PR that carries an issue key.

    depth 0 -- active sprints only (fast, the default)
    depth 1 -- also closed and future sprints, which classifies issues that have
               left the current sprint but still belong to a known team

    Returns a list of human-readable warnings; annotation is best-effort and a
    Jira outage must never take the PR queue down with it.
    """
    warnings: list[str] = []
    keys = sorted({k for pr in prs for k in pr.keys})
    if not keys or not cfg.teams:
        return warnings

    states = "active" if depth == 0 else "active,closed,future"
    key_clause = ",".join(keys)
    resolved: dict[str, dict] = {}

    for team in cfg.teams:
        sprints = _sprints(team, states)
        if not sprints:
            continue
        ids = ",".join(str(sid) for sid, _ in sprints)
        names = {sid: name for sid, name in sprints}
        try:
            issues = _search(f"key in ({key_clause}) AND sprint in ({ids})")
        except ToolError as exc:
            warnings.append(f"Jira lookup failed for {team.name}: {exc}")
            continue

        for issue in issues:
            key = issue.get("key")
            if key and key not in resolved:
                resolved[key] = {
                    "team": team.name,
                    "sprint": next(iter(names.values()), None),
                    "status": _status_of(issue),
                }

    # Keys we could not place on a board still deserve a status, so the caller can
    # tell "no such issue" apart from "issue exists, team unknown".
    missing = [k for k in keys if k not in resolved]
    if missing:
        try:
            for issue in _search(f"key in ({','.join(missing)})"):
                key = issue.get("key")
                if key:
                    resolved[key] = {"team": None, "sprint": None,
                                     "status": _status_of(issue)}
        except ToolError as exc:
            warnings.append(f"Jira status lookup failed: {exc}")

    for pr in prs:
        for key in pr.keys:
            info = resolved.get(key)
            if not info:
                continue
            pr.status = pr.status or info.get("status")
            if info.get("team"):
                pr.team = info["team"]
                pr.sprint = info["sprint"]
                break

    return warnings
