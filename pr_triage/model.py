"""The PullRequest record and the buckets it can arrive in."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .util import days_since, parse_ts


class Bucket(str, Enum):
    """Why a PR is in your queue. Ordered most- to least-actionable."""

    DIRECT = "direct"   # you were named personally
    TEAM = "team"       # routed to a team you belong to
    MINE = "mine"       # you opened it

    @property
    def rank(self) -> int:
        return {"direct": 0, "team": 1, "mine": 2}[self.value]


@dataclass
class PullRequest:
    bucket: Bucket
    repo: str
    number: int
    title: str
    url: str
    author: str
    draft: bool
    decision: str
    created: datetime | None
    updated: datetime | None
    #: When this PR started waiting on you -- see gh.blocked_since().
    since: datetime | None
    keys: tuple[str, ...] = ()

    # Filled in by the Jira layer; None means "could not be determined".
    team: str | None = None
    sprint: str | None = None
    status: str | None = None

    # Set during selection.
    matched: bool = False
    scoped: bool = False

    @property
    def ident(self) -> tuple[str, int]:
        return (self.repo, self.number)

    @property
    def age_days(self) -> float:
        return days_since(self.since)

    @property
    def short_repo(self) -> str:
        return self.repo.split("/")[-1]

    @property
    def actionable(self) -> bool:
        """Something a reviewer could act on right now."""
        return not self.draft and self.decision != "APPROVED"

    def team_label(self) -> str:
        if self.team:
            return self.team
        return "-" if self.keys else "?"

    def tags(self) -> list[str]:
        out: list[str] = []
        if self.draft:
            out.append("draft")
        if self.decision == "CHANGES_REQUESTED":
            out.append("changes-req")
        elif self.decision == "APPROVED":
            out.append("approved")
        if self.sprint:
            out.append("sprint")
        if self.status:
            out.append(self.status.lower().replace(" ", "-"))
        return out

    def to_dict(self) -> dict:
        return {
            "bucket": self.bucket.value,
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "author": self.author,
            "draft": self.draft,
            "decision": self.decision,
            "created": self.created.isoformat() if self.created else None,
            "updated": self.updated.isoformat() if self.updated else None,
            "blocked_since": self.since.isoformat() if self.since else None,
            "age_days": round(self.age_days, 2),
            "keys": list(self.keys),
            "team": self.team,
            "sprint": self.sprint,
            "status": self.status,
            "matched": self.matched,
        }
