# pr-triage

Triage your pull-request review queue in the terminal, instead of in your inbox.

On a large monorepo, review requests addressed to a broad owner team get expanded
by GitHub to **every member of that team**. Your username then appears on hundreds
of pull requests you have no stake in. Mail rules keyed on your username stop
discriminating, notification volume becomes unreadable, and the handful of requests
that are genuinely yours get buried.

In the environment this was built for, the measured ratio was:

| Query | Open PRs |
|---|---|
| `review-requested:<you>` | **161** |
| `team-review-requested:<your squad>` | **9** |
| `user-review-requested:<you>` | **1** |

An individual contributor usually **cannot** change CODEOWNERS, team settings, or
repository configuration to fix this. `pr-triage` needs none of that — it reads the
same data from the API and sorts it locally.

```
REQUESTED FROM YOU DIRECTLY  (1)
    8h  ?         infra-flags#2628           Remove production segment inclusion  [approved]
       https://github.com/acme/infra-flags/pull/2628  by someone

REQUESTED FROM @team-your-squad  (10)
 * 10h  billing   monorepo#31290             Move formatted copy to the frontend  [draft,sprint]
       https://github.com/acme/monorepo/pull/31290  by someone  PROJ-38203
  116d  ?         infra-flags#2317           [COMPLIANCE] Add/Update copyright headers
       https://github.com/acme/infra-flags/pull/2317  by a-bot
```

## What makes it different

**Age is time since review was requested from you** — read off the
`ReviewRequestedEvent` timeline, not the PR creation date. A pull request open for
three months but routed to your team yesterday reads `1d`, because that is how long
it has actually been your problem. In testing this changed one row from "72 days
stale" to "7 days", which is the difference between noise and a real signal.

**The issue tracker annotates; it never filters.** See [DESIGN.md](DESIGN.md) — this
is the single most important design decision, and it was made from measurements
rather than taste.

**Nothing organisation-specific is compiled in.** Handles, teams, repositories,
board ids and the issue-key pattern all live in a config file outside the repo.

## Requirements

- Python 3.11+ (uses stdlib `tomllib`)
- [`gh`](https://cli.github.com) — authenticated via `gh auth login`
- [`acli`](https://developer.atlassian.com/cloud/acli/) — optional; without it, pass `--no-jira`

## Install

```bash
git clone <this-repo> ~/Documents/pr-triage
mkdir -p ~/.config/pr-triage
cp ~/Documents/pr-triage/config.example.toml ~/.config/pr-triage/config.toml
$EDITOR ~/.config/pr-triage/config.toml

# put it on PATH
ln -s ~/Documents/pr-triage/bin/pr-triage ~/.local/bin/pr-triage
pr-triage man
```

### As a Claude Code skill

```bash
ln -s ~/Documents/pr-triage/skill ~/.claude/skills/pr-triage
```

Then `/pr-triage` in Claude Code. Rename the symlink and the `name:` field in
`skill/SKILL.md` if you prefer a different invocation.

## Configuration

See [`config.example.toml`](config.example.toml). The essentials:

```toml
[github]
user = "your-gh-username"
review_team = "your-org/team-your-squad"   # the narrow team you care about

[jira]
key_pattern = "PROJ-\\d+"

[[jira.teams]]
name = "billing"
board = 1234
sprint_prefix = "team-billing:"
```

Two things that are easy to get wrong:

- **`review_team` should be your narrow squad, not the broad owner team.** The
  owner team is the thing generating the noise; pointing at it reproduces the
  problem in your terminal.
- **`sprint_prefix` is matched against sprint *names*, not board membership.** A
  Jira board frequently lists other teams' sprints too, so board id alone
  misclassifies. If your sprints are named `team-billing: 2026 Q3 Sprint 5`, the
  prefix is `team-billing:`.

## Usage

```
pr-triage [-t TEAM] [-s DEPTH] [-w WEEKS] [-l N | -r N | -a]
          [--repo NAME] [--sort KEY] [-v] [--json] [--no-jira]
pr-triage man [-v]
```

| Flag | Meaning | Default |
|---|---|---|
| `-t, --team` | `-1` any review reaching you · `0` your review team · `1..N` or a name | `0` |
| `-s, --sprint` | tracker depth: `0` active sprints · `1` also closed/future | `0` |
| `-w, --weeks N` | only rows waiting N weeks or less | `0` (no limit) |
| `-l, --longest N` | N longest-blocked rows | `5` |
| `-r, --recent N` | N most recently requested | — |
| `-a, --all` | no row limit | off |
| `--repo NAME` | restrict to one repository | — |
| `--sort KEY` | `blocked` · `recent` · `updated` | `blocked` |
| `-v, --verbose` | extra metadata line per row | off |
| `--json` | machine-readable | off |
| `--no-jira` | skip tracker annotation (much faster) | off |
| `--no-color` | never emit ANSI colour | auto |
| `--mine-only` / `--no-mine` | include or exclude your own PRs | both shown |

### Examples

```bash
pr-triage                      # 5 longest-blocked rows in your team's queue
pr-triage -a                   # the whole queue
pr-triage -t billing -a        # float billing rows, keep everything else visible
pr-triage -t -1 -w 1           # everything that reached you in the last week
pr-triage -r 10 --no-jira      # 10 most recent requests, GitHub only, fast
pr-triage --json | jq '.rows[] | select(.age_days > 14)'
```

## Reading the output

Three sections, most-actionable first: **direct requests** (someone named you),
**team requests** (anyone on the team can take it), **your own PRs**.

The team column reads `-` when a PR has an issue key that is not in any searched
sprint, and `?` when it has no issue key at all. Rows at or beyond 7 days are
yellow, 14 days red. `*` marks rows matching an explicit `-t`.

## Performance

GitHub is one paginated GraphQL search per bucket — the REST search API is avoided
because it is capped at 30 requests/minute. Tracker annotation is one JQL call per
configured team. Typical runs: `--no-jira` a few seconds, full run under a minute,
`-t -1` (fetching every review request) around 20 seconds for ~160 PRs.

## Limitations

Team classification requires an issue key in the PR title or branch, **and** that
issue must sit in a sprint on a configured board. In the original environment only
3 of 13 rows met both conditions. This is a property of how people name branches,
not a bug — and it is exactly why `-t` marks rather than filters. The footer always
reports how many rows could not be classified.

## Licence

MIT.
