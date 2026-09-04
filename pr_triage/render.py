"""Terminal rendering.

Colour is emitted only to a TTY, and suppressed entirely under --no-color or
NO_COLOR (https://no-color.org), so piped output stays clean.
"""

from __future__ import annotations

import os
import sys

from .model import Bucket
from .select import Selection

_CODES = {
    "red": "\033[31m", "yellow": "\033[33m", "green": "\033[32m",
    "cyan": "\033[36m", "dim": "\033[2m", "bold": "\033[1m", "reset": "\033[0m",
}

WARN_DAYS = 7
STALE_DAYS = 14


class Painter:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        return "".join(_CODES[s] for s in styles) + text + _CODES["reset"]


def make_painter(no_color: bool, stream=sys.stdout) -> Painter:
    if no_color or os.environ.get("NO_COLOR"):
        return Painter(False)
    return Painter(stream.isatty())


def _age(days: float) -> str:
    if days >= 1:
        return f"{days:.0f}d"
    return f"{days * 24:.0f}h"


def _age_styles(days: float) -> tuple[str, ...]:
    if days >= STALE_DAYS:
        return ("red", "bold")
    if days >= WARN_DAYS:
        return ("yellow",)
    return ("dim",)


def _title(bucket: Bucket, review_team: str | None, scope: str) -> str:
    if bucket is Bucket.DIRECT:
        return "REQUESTED FROM YOU DIRECTLY"
    if bucket is Bucket.MINE:
        return "YOUR OPEN PRS"
    if scope == "any" or not review_team:
        return "REVIEW REQUESTS REACHING YOU"
    return f"REQUESTED FROM @{review_team.split('/')[-1]}"


def render(sel: Selection, *, paint: Painter, review_team: str | None,
           scope: str, verbose: bool) -> None:
    if not sel.shown:
        print("\nNothing in the queue matches those filters.\n")
        return

    print()
    for bucket in (Bucket.DIRECT, Bucket.TEAM, Bucket.MINE):
        rows = [p for p in sel.shown if p.bucket is bucket]
        if not rows:
            continue

        print(paint(f"{_title(bucket, review_team, scope)}  ({len(rows)})",
                    "bold", "cyan"))

        for pr in rows:
            mark = paint("*", "green") if pr.matched else " "
            age = paint(_age(pr.age_days).rjust(4), *_age_styles(pr.age_days))
            tags = pr.tags()
            tag_text = paint("  [" + ",".join(tags) + "]", "dim") if tags else ""
            ref = f"{pr.short_repo}#{pr.number}"
            print(f" {mark}{age}  {pr.team_label():<9.9} {ref:<26.26} "
                  f"{pr.title[:58]}{tag_text}")

            meta = f"       {pr.url}"
            if verbose:
                meta += f"\n       by {pr.author}"
                if pr.keys:
                    meta += f"  keys={','.join(pr.keys)}"
                if pr.sprint:
                    meta += f"  sprint={pr.sprint}"
                meta += f"  decision={pr.decision.lower()}"
            else:
                meta += f"  by {pr.author}"
                if pr.keys:
                    meta += f"  {','.join(pr.keys)}"
            print(paint(meta, "dim"))
        print()

    _footer(sel, paint)


def _footer(sel: Selection, paint: Painter) -> None:
    if sel.hidden:
        print(paint(f"  +{sel.hidden} more not shown — use -a/--all to see every row",
                    "yellow"))
    if sel.filtered_out:
        print(paint(f"  {sel.filtered_out} row(s) outside the time window", "dim"))
    if sel.team_filter and sel.total_review:
        print(paint(
            f"  {sel.unclassified_review} of {sel.total_review} review items have "
            "no tracker team (no issue key, or outside the searched sprints) — "
            "ranked below the matches, never dropped.", "dim"))
    if sel.hidden or sel.filtered_out or sel.team_filter:
        print()
