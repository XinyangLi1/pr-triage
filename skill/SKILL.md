---
name: pr-triage
description: Triage the user's GitHub pull-request review queue in the terminal, annotated with issue-tracker team and sprint. Use when the user runs /pr-triage, or asks what PRs need their review, what is blocking them, what is stuck in review, or what is in their review queue this sprint.
---

# pr-triage — terminal PR review triage

Replaces scanning GitHub notification email. Answers "what actually needs me?"

## Run it

```bash
pr-triage [flags]
```

Pass the user's flags through verbatim. With no arguments, run it bare. If
`pr-triage` is not on PATH, fall back to `python3 -m pr_triage` from the repo root.

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

Three sections, most-actionable first:

- **REQUESTED FROM YOU DIRECTLY** — the user was named personally. Rare, act first.
- **REQUESTED FROM @team** — routed to their team; anyone can take it.
- **YOUR OPEN PRS** — their own PRs and review state.

Per row: age, team, `repo#number`, title, tags; then URL, author, issue keys.

- Age is **time since review was requested from them or their team**, not since the
  PR was opened. A months-old PR routed yesterday reads `1d`. Yellow ≥7d, red ≥14d.
- Team column: a team name, `-` (has an issue key, not in a searched sprint), or
  `?` (no issue key at all).
- `*` marks rows matching an explicit `-t`; they float to the top.
- Tags: `draft`, `changes-req`, `approved`, `sprint`, plus tracker status.

## Important behaviour

`-t` and `-s` **mark and sort — they never remove rows.** Most PRs carry no issue
key, so filtering on the tracker would hide real review requests; in testing, hard
filtering returned a single draft and hid the oldest blocked item. The footer
states how many rows could not be classified, so the gap is never silent.

`-w`, `-l`, `-r` and `--repo` are real filters. When rows are removed the footer
says how many. Use `-a` for everything.

## Interpreting for the user

Lead with direct requests and anything red (≥14d). Drafts and `approved` rows are
usually not action items — say so rather than listing them as work. If asked "what
should I pick up", prefer non-draft rows needing review, in their sprint if known.
Don't re-list every row the tool already printed; summarise and point at the top
few, and say plainly when nothing needs them.

If the team column is mostly `?`, say so — it means the tracker could not classify
the queue, not that the work is unimportant.

## Configuration

`~/.config/pr-triage/config.toml` (see `config.example.toml`). Holds the GitHub
handle, review team, board ids and issue-key pattern. `man -v` prints the active
configuration, which is the quickest way to check what the tool is pointed at.

Requires `gh` (authenticated) and optionally `acli` for tracker annotation.
