"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, config, gh, jira, man, render, select
from .config import Config, ConfigError
from .util import ToolError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pr-triage",
        description="Triage your pull-request review queue in the terminal.",
        epilog="Run `pr-triage man` for the manual, `pr-triage man -v` for detail.",
        add_help=True,
    )
    p.add_argument("-t", "--team", default="0", metavar="TEAM",
                   help="-1 any review reaching you; 0 your review team "
                        "(default); 1..N or a team name")
    p.add_argument("-s", "--sprint", type=int, choices=(0, 1), default=0,
                   metavar="DEPTH",
                   help="tracker lookup depth: 0 active sprints (default), "
                        "1 also closed/future")
    p.add_argument("-w", "--weeks", type=int, default=0, metavar="N",
                   help="only rows waiting N weeks or less (0 = no limit)")

    cap = p.add_mutually_exclusive_group()
    cap.add_argument("-l", "--longest", type=int, metavar="N",
                     help="N longest-blocked rows (default 5)")
    cap.add_argument("-r", "--recent", type=int, metavar="N",
                     help="N most recently requested rows")
    cap.add_argument("-a", "--all", action="store_true", help="no row limit")

    p.add_argument("--repo", metavar="NAME", help="restrict to one repository")
    p.add_argument("--sort", choices=select.SORTS, help="explicit sort key")

    mine = p.add_mutually_exclusive_group()
    mine.add_argument("--mine-only", action="store_true", help="only your own PRs")
    mine.add_argument("--no-mine", action="store_true", help="omit your own PRs")

    p.add_argument("-v", "--verbose", action="store_true",
                   help="extra metadata line per row")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--no-jira", action="store_true",
                   help="skip issue-tracker annotation")
    p.add_argument("--no-color", action="store_true", help="never emit colour")
    p.add_argument("-c", "--config", metavar="PATH", help="explicit config file")
    p.add_argument("--version", action="version", version=f"pr-triage {__version__}")
    return p


def resolve_team(raw: str, cfg: Config) -> tuple[str | None, str]:
    """
    Map --team onto (team_name_to_mark, github_scope).

    Returns team_name None when no marking should happen.
    """
    value = raw.strip()
    if value in ("-1", "any"):
        return None, "any"
    if value in ("0", "all", ""):
        return None, "team"

    if value.lstrip("-").isdigit():
        idx = int(value)
        if not 1 <= idx <= len(cfg.teams):
            raise SystemExit(
                f"pr-triage: --team {value} is out of range; configured teams are "
                + (", ".join(f"{i}={t.name}" for i, t in enumerate(cfg.teams, 1))
                   or "(none)")
            )
        return cfg.teams[idx - 1].name, "team"

    team = cfg.team_by_name(value)
    if not team:
        raise SystemExit(
            f"pr-triage: unknown team {value!r}; configured teams are "
            + (", ".join(t.name for t in cfg.teams) or "(none)")
        )
    return team.name, "team"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # `man` / `man -v` is a subcommand, deliberately outside argparse so it works
    # even when configuration is missing or broken.
    if argv and argv[0] == "man":
        wants_detail = any(a in ("-v", "--verbose") for a in argv[1:])
        cfg = None
        try:
            cfg = config.load()
        except ConfigError:
            pass
        man.show(wants_detail, cfg)
        return 0

    args = build_parser().parse_args(argv)

    try:
        cfg = config.load(args.config)
    except ConfigError as exc:
        print(f"pr-triage: {exc}", file=sys.stderr)
        return 1

    team_name, scope = resolve_team(args.team, cfg)

    if args.recent is not None:
        sort, limit = "recent", args.recent
    elif args.longest is not None:
        sort, limit = "blocked", args.longest
    else:
        sort, limit = "blocked", 0 if args.all else 5
    if args.all:
        limit = 0
    if args.sort:
        sort = args.sort

    try:
        prs, totals = gh.collect(cfg, scope)
    except ToolError as exc:
        print(f"pr-triage: GitHub unavailable: {exc}", file=sys.stderr)
        return 1

    warnings: list[str] = []
    if cfg.jira_enabled and not args.no_jira:
        try:
            warnings = jira.annotate(prs, cfg, args.sprint)
        except ToolError as exc:
            warnings = [f"tracker unavailable, showing GitHub only: {exc}"]

    if args.mine_only:
        prs = [p for p in prs if p.bucket.value == "mine"]

    sel = select.apply(
        prs, team=team_name, weeks=args.weeks, repo=args.repo,
        sort=sort, limit=limit, include_mine=not args.no_mine,
    )

    for warning in warnings:
        print(f"pr-triage: {warning}", file=sys.stderr)

    if args.json:
        print(json.dumps([p.to_dict() for p in sel.shown], indent=2))
        return 0

    render.render(
        sel,
        paint=render.make_painter(args.no_color),
        review_team=cfg.review_team,
        scope=scope,
        verbose=args.verbose,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
