---
name: pr-triage
description: Triage the user's GitHub pull-request review queue in the terminal, annotated with issue-tracker team and sprint. Use when the user runs /pr-triage, or asks what PRs need their review, what is blocking them, what is stuck in review, or what is in their review queue this sprint.
---

# pr-triage — terminal PR review triage

Replaces scanning GitHub notification email. Answers "what actually needs me?"

## Run it

```bash
pr-triage --json [flags]
```

Always add `--json`, even though a human running this in a real terminal would
not. The plain-text table truncates title (58 chars), collapses repo to its
short name, and drops the raw review `decision` and the `created`/`updated`
timestamps whenever they don't map to a tag — `--json` is the only mode with
full fidelity, and you are reporting to the user in chat, not printing to a
TTY. Pass the user's other flags through verbatim (`-t`, `-s`, `-w`, `-l`, `-r`,
`-a`, `--repo`, `--sort`, `--no-jira`, `--mine-only`/`--no-mine`; `--json` is
additive, not a replacement for these). With no other arguments, run it bare
plus `--json`. If `pr-triage` is not on PATH, fall back to
`python3 -m pr_triage` from the repo root.

| Flag | Meaning | Default |
|---|---|---|
| `-t, --team` | `-1` any review reaching them · `0` their review team · `1..N` or a name | `0` |
| `-s, --sprint` | tracker depth: `0` active sprints · `1` also closed/future | `0` |
| `-w, --weeks N` | only rows waiting N weeks or less | `0` (no limit) |
| `-l, --longest N` | N longest-blocked rows | `5` |
| `-r, --recent N` | N most recently requested | — |
| `-a, --all` | no row limit | off |
| `--repo NAME` | restrict to one repository | — |
| `--sort KEY` | `blocked` · `recent` · `updated` | `blocked` |
| `-v, --verbose` | extra metadata line per row | off |
| `--json` | machine-readable | off |
| `--no-jira` | skip tracker annotation, much faster | off |
| `--mine-only` / `--no-mine` | include or exclude their own PRs | both |

`man` and `man -v` print the built-in concise and full manuals — use these to
answer questions about the tool rather than guessing.

Timing: `--no-jira` returns in seconds. A full run takes up to a minute. `-t -1`
fetches every review request and takes ~20s for a large queue. Prefer `--no-jira`
when the user only wants the PR list, not team labels.

## Reading the output

`--json` returns `{"rows": [...], "summary": {...}}`. `rows` is ordered exactly
as the tool would render it (`bucket` groups them; do not re-sort). Fields per
row object:

| Field | Meaning |
|---|---|
| `bucket` | `direct` (named personally), `team` (routed to the team), `mine` (their own PR) |
| `repo` | full `owner/name` — do not shorten it |
| `number`, `title`, `url`, `author` | as-is; `title` is untruncated here, unlike the text renderer |
| `draft` | boolean |
| `decision` | raw GitHub review decision: `APPROVED`, `CHANGES_REQUESTED`, or `REVIEW_REQUIRED` (no review activity has happened at all yet — this is a real state, not "nothing to report") |
| `created`, `updated` | PR-level ISO timestamps — `updated` is last activity on the PR itself, a different signal from `blocked_since` |
| `blocked_since`, `age_days` | when review was requested from the user/team (or `created` for `mine`) — this is what "age" means everywhere in this tool, never `created` |
| `keys` | issue-tracker keys found in title/branch, e.g. `["TF-1234"]` |
| `team`, `sprint`, `status` | tracker annotation; `team` is `null` when unclassified |
| `matched` | true when this row matches an explicit `-t`/`--team` |

`summary` fields — use these verbatim, never recompute from `rows` (they cover
the pre-truncation queue, not just what's in `rows`):

| Field | Meaning |
|---|---|
| `hidden` | rows cut by `-l`/`-r` — nonzero means the queue is bigger than what's shown; tell the user, suggest `-a` |
| `filtered_out` | rows removed by `-w`/`--weeks` |
| `team_filter` | the `-t` value in effect, or `null` |
| `total_review`, `unclassified_review` | of all `direct`+`team` rows (excludes `mine`), how many have no tracker `team` |

Group by `bucket` in this order for display: `direct`, `team`, `mine`. Section
headings: **REQUESTED FROM YOU DIRECTLY**, **REQUESTED FROM @team** (or
**REVIEW REQUESTS REACHING YOU** if `-t -1`/any was used), **YOUR OPEN PRS**.

- Age is **time since review was requested from them or their team**
  (`blocked_since`/`age_days`), never `created`. A months-old PR routed
  yesterday reads `1d`. Treat ≥7 days as worth flagging, ≥14 as stale.
- Team column: `team` value, or `-` if `keys` is non-empty but `team` is null
  (has an issue key, not in a searched sprint), or `?` if `keys` is empty.
- `matched: true` rows float to the top of their bucket and get a `*` marker.
- Tags to display per row: `draft` if `draft`, `changes-req`/`approved` from
  `decision`, `sprint` if `sprint` is set, `status` lowercased/hyphenated if
  set. If none of those apply, still show `decision` raw (commonly
  `REVIEW_REQUIRED`) so a not-yet-reviewed PR isn't silently blank.

## Important behaviour

`-t` and `-s` **mark and sort — they never remove rows.** Most PRs carry no issue
key, so filtering on the tracker would hide real review requests; in testing, hard
filtering returned a single draft and hid the oldest blocked item.
`unclassified_review`/`total_review` in `summary` say how many rows could not be
classified, computed over the full pre-truncation queue — reproduce these, never
count only what you're displaying.

`-w`, `-l`, `-r` and `--repo` are real filters; `hidden`/`filtered_out` in
`summary` say how many rows that removed. Use `-a` for everything.

## Output format — mandatory, do not improvise

Every row in `rows` (subject to whatever `-l`/`-r`/`-a`/`-w`/`--repo` already
filtered) must be shown to the user. Do not summarise, truncate, cherry-pick "the
top few", or silently drop rows to keep the reply short — the whole point of this
tool is that nothing gets lost in a firehose, so the report must not recreate that
problem. Never decide on your own that a row isn't worth mentioning.

Render each `bucket` group as a heading, and under it, one block per row in
this exact structure:

```
- **`repo#number`** (`age`, `team`) — title  [tags]
  <url>  by <author>  <keys if present>
  updated <updated date>  ·  decision: <decision>
```

Rules:
- Keep `rows`' order — do not re-rank by your own judgment.
- `repo` is the full `owner/name`; do not shorten it.
- `title` is untruncated — never cut it short or add your own ellipsis.
- Always include `url`, `author`, and `keys` when non-empty on the metadata
  line, verbatim from the data. Never omit any of these.
- Always include a second metadata line with `updated` (as a date, not raw
  ISO) and the raw `decision` value, even when `decision` is already reflected
  in the tags — this is the only place `updated` (last activity on the PR
  itself, distinct from blocked-since age) is surfaced at all.
- Include every tag the row has (`draft`, `changes-req`, `approved`, `sprint`,
  tracker status, etc.) exactly as printed.
- Keep the team column value (team name, `-`, or `?`) exactly as printed.
- After the listing, reproduce the `summary` fields as prose (hidden count,
  filtered count, unclassified-of-total) — never silently drop this.
- After that, you may add ONE short closing line flagging anything genuinely
  time-sensitive (e.g. rows ≥14 days, or approved-and-ready rows). This is an
  addition, never a replacement for the full listing above.

## Configuration

`~/.config/pr-triage/config.toml` (see `config.example.toml`). Holds the GitHub
handle, review team, board ids and issue-key pattern. `man -v` prints the active
configuration, which is the quickest way to check what the tool is pointed at.

Requires `gh` (authenticated) and optionally `acli` for tracker annotation.
