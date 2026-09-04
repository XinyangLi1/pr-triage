"""Filtering, ordering and capping.

Design rule, measured rather than assumed: the issue-tracker axis (team) only
*marks and re-orders* rows -- it never removes them. Most pull requests in a
monorepo carry no issue key at all, so filtering on the tracker silently hides
real review requests. See DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Bucket, PullRequest
from .util import NOW

SORTS = ("blocked", "recent", "updated")


@dataclass
class Selection:
    shown: list[PullRequest]
    hidden: int
    #: Counts over the full pre-truncation queue, so footers never lie.
    total_review: int = 0
    unclassified_review: int = 0
    filtered_out: int = 0
    team_filter: str | None = None


def apply(prs: list[PullRequest], *, team: str | None, weeks: int,
          repo: str | None, sort: str, limit: int,
          include_mine: bool = True) -> Selection:
    pool = list(prs)

    if not include_mine:
        pool = [p for p in pool if p.bucket is not Bucket.MINE]

    if repo:
        needle = repo.lower()
        pool = [p for p in pool
                if needle in p.repo.lower() or needle == p.short_repo.lower()]

    before_window = len(pool)
    if weeks:
        cutoff = weeks * 7
        pool = [p for p in pool if p.age_days <= cutoff]
    filtered_out = before_window - len(pool)

    # Team marks, never removes.
    for pr in pool:
        pr.scoped = team is not None
        pr.matched = bool(team and pr.team == team)

    review = [p for p in pool if p.bucket is not Bucket.MINE]
    stats = {
        "total_review": len(review),
        "unclassified_review": sum(1 for p in review if not p.team),
        "filtered_out": filtered_out,
        "team_filter": team,
    }

    if sort == "recent":
        pool.sort(key=lambda p: p.since or NOW, reverse=True)
    elif sort == "updated":
        pool.sort(key=lambda p: p.updated or NOW, reverse=True)
    else:  # blocked: longest-waiting first
        pool.sort(key=lambda p: p.since or NOW)

    if team:
        # Matches float up without evicting anything below them.
        pool.sort(key=lambda p: not p.matched)

    hidden = 0
    if limit and limit > 0 and len(pool) > limit:
        hidden = len(pool) - limit
        pool = pool[:limit]

    return Selection(shown=pool, hidden=hidden, **stats)
