# Design

Why this tool is shaped the way it is. Every decision below came from measuring a
real queue, and several of them overturned the design that was originally
specified.

## 1. The problem

A monorepo with a broad owner team — call it `@org/team-owner-reviewers` — attached
to many CODEOWNERS paths. GitHub expands a team review request to every member, so
each member's username lands on every such PR.

Downstream, a common coping strategy is a mail rule: deliver GitHub notifications
to the inbox only when the body contains your username, archive everything else.
That rule stops working, in two ways at once:

1. **It admits too much.** The username is on hundreds of PRs, so the filter passes
   nearly everything.
2. **It splits conversations.** Some messages in a thread (CI/Actions mail) carry no
   username, so they are archived while their siblings are delivered. Threads
   fragment across folders.

Measured on the originating environment:

| Query | Open PRs |
|---|---|
| `review-requested:<user>` | 161 |
| `team-review-requested:<narrow squad>` | 9 |
| `user-review-requested:<user>` | 1 |

The 161 is almost entirely owner-team fan-out. The signal is the 9 and the 1.

**Constraint:** the intended user is an individual contributor and cannot change
CODEOWNERS, team membership, or repository settings. Every remedy must be local.

## 2. Why a terminal tool rather than a mail rule

The mail rule is trying to reconstruct, from message bodies, a distinction the API
exposes directly. `user-review-requested:` and `team-review-requested:` separate
personal asks from team fan-out exactly and for free. Once that query exists, the
inbox is redundant for triage — so the tool replaces the queue rather than
filtering it, and the correct follow-up is to turn the notification mail off
entirely rather than filter it harder.

## 3. The decision that shaped everything: the tracker annotates, never filters

The original specification had `--team` and `--sprint` as query filters: show me
billing work in the current sprint. That is the natural design, and it is wrong
here.

Linking a PR to a tracker issue requires an issue key in the title or branch name.
Measured on the queue:

- 6 open PRs addressed to the narrow squad in the main repo
- **2** carried an issue key anywhere in title or branch
- **1** was also in an active sprint

So `--team billing --sprint current`, implemented as a filter, returned **one pull
request, and it was a draft**. The four PRs it hid included the oldest blocked item
in the queue.

A second route was investigated and rejected: classifying by changed files against
CODEOWNERS. It cannot work, because CODEOWNERS only ever names the *combined*
squad — there is no path-level split between the sub-teams anywhere in the repo.
A third route, the Jira `Team` field, is empty on the relevant issues.

Therefore:

> `-t` and `-s` mark matching rows with `*` and sort them to the top. They never
> remove a row. `-w`, `-l`, `-r` and `--repo` are ordinary filters and do remove
> rows; whenever they do, the footer says how many.

This is the difference between a tool that says "nothing to do" and one that says
"one match, and here are ten other things also waiting on you."

**Counts are computed before truncation.** An early version reported "3 of 4
unclassified" while the row cap had already hidden eight rows — a footer that
describes only what survived truncation is worse than no footer.

## 4. Age means time-since-requested, not time-since-opened

The obvious implementation of "longest blocked" sorts on `createdAt`. That
overstates badly: one PR in the sample was opened 72 days before it was ever routed
to this team.

Instead the tool reads the `ReviewRequestedEvent` timeline and takes the most recent
request aimed at the user or their team. The 72-day row becomes a 7-day row, which
is the honest answer to "how long has this been mine?"

This is the main reason the tool uses GraphQL. The REST search API does not expose
the timeline, and is capped at 30 requests/minute besides.

## 5. Buckets, not one flat list

Three query buckets, ranked by how much they oblige the user:

| Bucket | Query | Meaning |
|---|---|---|
| `DIRECT` | `user-review-requested:` | named personally — rare, act first |
| `TEAM` | `team-review-requested:` | anyone on the squad can take it |
| `MINE` | `author:` | your own PRs and their state |

De-duplication keeps the most actionable bucket, so a personal request is never
demoted to a team request.

`-t -1` swaps the `TEAM` query for the unfiltered `review-requested:`, deliberately
exposing the full firehose for the rare case where that is what you want. It
paginates, because that result set exceeds one page.

### 5a. Display order is a fixed 4-tier split, not 3 buckets

Once `TEAM` rows exist, a second cut matters as much as the bucket itself:
whether the tracker could actually place the PR on a team's board (`team`
is non-null) or not. Early testing put every `TEAM` row in one section, with
`-t` marking matches — and the marked rows still had to be found by eye among
a majority of unclassifiable ones. The fix was to split `TEAM` into two
sections by classification and interleave them with `MINE`, always, not just
when `-t` is passed:

1. `DIRECT`
2. `TEAM` where `team` is set — "on a team board"
3. `MINE`
4. `TEAM` where `team` is null — "unclassified"

This order is unconditional: it does not depend on whether `-t`/`-s` were
passed. `-t` still marks and floats matches, but only *within* tier 2 — it
never changes which of the four tiers comes first. The rationale mirrors §3:
classification should organize the view by default, not only on request, and
the rows the tracker couldn't place should never be mixed in with the ones it
could — that's what made the `*` marker necessary to scan for in the first
place. When one of tiers 2/4 is empty (all `--no-jira` runs land here, since
`team` is always null), it collapses back to a single plain team section in
the same slot, which is the pre-split behaviour.

## 6. Sprint depth is a cost dial, not a filter

`-s 0` searches active sprints only: one JQL call per team. `-s 1` adds closed and
future sprints, classifying work that has left the current sprint.

An earlier iteration derived team membership *only* from active sprints, which made
"all sprints" logically incapable of widening the result — the label it would have
needed did not exist. Splitting lookup depth from row selection fixed that.

Honest limit: on the sample data `-s 1` classified nothing extra, because the two
unclassified keys were (a) in no sprint at all and (b) in a sprint on a third
team's board. The feature is correct; the data simply does not reward it here.

## 7. Configuration is external

No handle, team, repository, board id or project key appears in the source. All of
it loads from TOML found at `$PR_TRIAGE_CONFIG`, `./pr-triage.toml`, or
`~/.config/pr-triage/config.toml`, and real config filenames are gitignored.

This serves two ends: the repository is safe to publish, and another team can adopt
the tool by writing a config file rather than editing code.

`sprint_prefix` deserves its own note. Classification cannot key off board
membership, because a board commonly lists other teams' sprints — one board in the
sample returned both squads' sprints. Sprint *names* carry the owning team, so the
prefix is the discriminator.

## 8. Module layout

```
pr_triage/
  config.py   TOML loading, validation, Team/Config records
  util.py     subprocess wrapper, timestamp helpers
  model.py    PullRequest record and Bucket enum
  gh.py       GraphQL search, pagination, blocked-since computation
  jira.py     acli wrappers, sprint resolution, annotation
  select.py   filtering, marking, ordering, capping
  render.py   terminal output, colour policy
  man.py      built-in manual
  cli.py      argument parsing and orchestration
```

`gh.py` and `jira.py` are the only modules that shell out. `select.py` is pure and
therefore the easy place to change policy. A tracker outage degrades to a
GitHub-only view with a warning on stderr; it never takes the queue down.

## 9. Things deliberately not done

- **No caching.** Runs are seconds; a stale review queue is worse than a slow one.
- **No write operations.** The tool never approves, comments, or requests review.
  Read-only means it can be run without thought.
- **No dashboard.** The premise is that the answer belongs in the terminal, next to
  the work, rather than in another surface to check.
- **No tracker-only rows.** Sprint items with no PR are a standup view, a different
  job from a review queue.
