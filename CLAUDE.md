# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

`pr-triage` is a read-only CLI that lists the pull requests actually waiting on the
user, split by who asked. Read [DESIGN.md](DESIGN.md) before changing behaviour —
most of the surprising decisions are load-bearing and were made from measurements.

## Invariants — do not break these without discussing it

1. **The issue tracker annotates; it never filters.** `-t` and `-s` mark rows with
   `*` and re-order them. They must never remove a row. Most PRs carry no issue
   key, so filtering on the tracker silently hides real review requests. This was
   measured: hard filtering returned 1 draft PR out of a queue of 11 and hid the
   oldest blocked item.

2. **Age is time since review was requested, never since the PR was opened.**
   `gh.blocked_since()` reads the `ReviewRequestedEvent` timeline. Substituting
   `createdAt` overstates by months on long-lived PRs.

3. **Footer counts are computed before truncation.** `select.Selection` carries
   `total_review` / `unclassified_review` for exactly this reason. A count that
   describes only the surviving rows is a bug.

4. **No organisation-specific value in the source.** No usernames, org names,
   repository names, board ids, project keys, or tracker URLs. Everything comes
   from config. The repo must stay publishable.

5. **Read-only.** The tool never approves, comments, merges, or requests review.

6. **A tracker outage degrades gracefully.** Jira failures produce a stderr warning
   and a GitHub-only view; they never abort the run.

## Layout

| File | Responsibility |
|---|---|
| `pr_triage/config.py` | TOML loading and validation |
| `pr_triage/util.py` | subprocess wrapper, timestamps |
| `pr_triage/model.py` | `PullRequest`, `Bucket` |
| `pr_triage/gh.py` | GraphQL search, pagination, blocked-since |
| `pr_triage/jira.py` | `acli` wrappers, sprint resolution |
| `pr_triage/select.py` | filter / mark / sort / cap — pure, no I/O |
| `pr_triage/render.py` | terminal output and colour policy |
| `pr_triage/man.py` | built-in manual |
| `pr_triage/cli.py` | argparse and orchestration |

Only `gh.py` and `jira.py` shell out. Prefer putting policy changes in `select.py`,
which is pure and easy to reason about.

## Conventions

- Standard library only. No third-party runtime dependencies — `tomllib` is stdlib
  on Python 3.11+.
- Type hints on public functions; `from __future__ import annotations` at the top.
- Comments explain *why*, not *what*. Several non-obvious choices already carry a
  short rationale — keep that style and do not strip them.
- Colour only to a TTY, and never under `--no-color` or `NO_COLOR`.
- User-facing errors go to stderr prefixed `pr-triage:` and exit 1.

## Testing

There is no automated suite — the tool's inputs are two live APIs, and mocking them
would mostly assert that the mocks match themselves. Verify changes by running
against a real account:

```bash
python3 -m pr_triage --no-jira -a        # fast path, GitHub only
python3 -m pr_triage -a                  # full path with annotation
python3 -m pr_triage -t <name> -a        # marking and float-to-top
python3 -m pr_triage -t -1 --no-jira -a  # pagination beyond one page
python3 -m pr_triage --json | jq .       # schema stays valid
python3 -m pr_triage man -v              # manual and active config
python3 -m compileall -q pr_triage
```

Error paths worth re-checking after touching `cli.py` or `config.py`:

```bash
python3 -m pr_triage -t nosuch                       # unknown team name
python3 -m pr_triage -t 99                           # index out of range
PR_TRIAGE_CONFIG=/nope.toml python3 -m pr_triage     # missing config
python3 -m pr_triage -l 3 -r 3                       # mutually exclusive
```

When adding a flag, update all four of: `cli.build_parser()`, the `man.CONCISE` and
`man.VERBOSE` texts, the README flag table, and `skill/SKILL.md`.

## Gotchas

- A Jira board often lists **other teams' sprints**. Classification keys off
  `sprint_prefix` against the sprint *name*, never board membership.
- GraphQL `search` caps at 100 nodes per page; `gh._search()` paginates and
  `config.max_results` bounds the total.
- Never commit `pr-triage.toml` or `config.toml` — both are gitignored.
