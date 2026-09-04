"""Built-in manual: `pr-triage man` and `pr-triage man -v`."""

from __future__ import annotations

from .config import Config

CONCISE = """\
NAME
    pr-triage — triage your pull-request review queue in the terminal

SYNOPSIS
    pr-triage [-t TEAM] [-s DEPTH] [-w WEEKS] [-l N | -r N | -a]
              [--repo NAME] [--sort KEY] [-v] [--json] [--no-jira]
    pr-triage man [-v]

DESCRIPTION
    Lists the pull requests actually waiting on you, split into who asked:
    you personally, a team you belong to, and your own open PRs. Ages are
    measured from the moment review was requested from you — not from when
    the PR was opened.

OPTIONS
    -t, --team TEAM     -1 any review reaching you (widest)
                         0 your configured review team (default)
                         1..N or a name, e.g. -t billing
    -s, --sprint DEPTH   0 active sprints only (default, fast)
                         1 also closed and future sprints (slower)
    -w, --weeks N        only rows waiting N weeks or less (0 = no limit)
    -l, --longest N      N longest-blocked rows (default 5)
    -r, --recent N       N most recently requested
    -a, --all            no row limit
        --repo NAME      restrict to one repository
        --sort KEY       blocked | recent | updated
    -v, --verbose        one extra metadata line per row
        --json           machine-readable output
        --no-jira        skip issue-tracker annotation (much faster)
        --no-color       never emit ANSI colour
        --mine-only      only your own PRs
        --no-mine        omit your own PRs

EXIT STATUS
    0 success   1 configuration or upstream tool error

SEE ALSO
    pr-triage man -v   full manual, including why -t never filters
"""

VERBOSE = """\
NAME
    pr-triage — triage your pull-request review queue in the terminal

WHY THIS EXISTS
    On a large monorepo, review requests addressed to a broad owner team are
    expanded by GitHub to every member of that team. Your username then appears
    on hundreds of pull requests you have no stake in, which defeats mail rules
    keyed on your username and buries the handful of requests that are really
    yours. In the environment this tool was built for, the ratio measured:

        review-requested:<you>              161 open PRs
        team-review-requested:<your team>     9 open PRs
        user-review-requested:<you>           1 open PR

    An individual contributor usually cannot change CODEOWNERS, team settings
    or repository configuration. This tool needs none of that: it reads the
    same data from the API and sorts it locally.

BUCKETS
    REQUESTED FROM YOU DIRECTLY
        Someone named you personally (user-review-requested). Rare, and almost
        always the thing to do first.
    REQUESTED FROM @<team>
        Routed to a team you belong to. Anyone on the team can take it.
        With -t -1 this widens to every review request that reaches you,
        including owner-team fan-out.
    YOUR OPEN PRS
        PRs you authored, with their current review decision.

THE AGE COLUMN
    Age is time since review was requested from you or your team, taken from
    the ReviewRequestedEvent timeline — not since the PR was opened. A PR that
    has been open for months but was routed to your team yesterday reads 1d,
    because that is how long it has been your problem. Rows at or beyond 7 days
    are yellow; 14 days or more are red and bold.

THE TEAM COLUMN
    A team name    the issue key was found in that team's sprint
    -              the PR carries an issue key, but it is not in any sprint
                   searched at the current -s depth
    ?              the PR carries no issue key at all

WHY -t MARKS BUT NEVER FILTERS
    Classifying a PR by team requires an issue key in its title or branch, and
    that key must sit in a sprint belonging to a known team. In practice most
    PRs satisfy neither condition. When this was measured on the original
    monorepo, only 1 of 11 review items could be classified; hard filtering by
    team therefore hid the single oldest blocked PR and returned a lone draft.

    So -t and -s mark matching rows with * and float them to the top, and every
    other row still appears beneath. The footer always states how many rows
    could not be classified, so the gap is visible rather than silent.

    -w, -l, -r and --repo are ordinary filters and do remove rows. Whenever
    rows are removed, the footer says how many.

SPRINT DEPTH
    -s 0 (default) searches only active sprints. This is one JQL call per team
    and keeps a run fast.
    -s 1 additionally searches closed and future sprints, which classifies work
    that has left the current sprint. It is slower and still cannot classify an
    issue that was never in any sprint.

CONFIGURATION
    Looked up in order:
        $PR_TRIAGE_CONFIG
        ./pr-triage.toml
        ~/.config/pr-triage/config.toml

    See config.example.toml. No organisation-specific value is compiled into
    this program; handles, teams, repositories, boards and the issue-key regex
    all come from that file.

REQUIREMENTS
    gh     GitHub CLI, authenticated (gh auth login)
    acli   Atlassian CLI, authenticated — optional; without it, run --no-jira

PERFORMANCE
    GitHub data is one paginated GraphQL search per bucket. The REST search API
    is avoided because it allows only 30 requests per minute. Tracker
    annotation costs one JQL call per configured team, plus one for issue keys
    that no board claimed. --no-jira skips all of it.

EXAMPLES
    pr-triage                    5 longest-blocked rows in your team's queue
    pr-triage -a                 the entire queue
    pr-triage -t billing -a      float billing rows, keep the rest visible
    pr-triage -t -1 -w 1         everything that reached you in the last week
    pr-triage -r 10 --no-jira    10 most recent requests, GitHub only
    pr-triage --json | jq '.rows[]|select(.age_days>14)'
"""


def show(verbose: bool, cfg: Config | None = None) -> None:
    print(VERBOSE if verbose else CONCISE, end="")
    if verbose and cfg is not None:
        print("\nACTIVE CONFIGURATION\n")
        print(f"    source        {cfg.source}")
        print(f"    github user   {cfg.user}")
        print(f"    review team   {cfg.review_team or '(none)'}")
        print(f"    repositories  {', '.join(cfg.repos) or '(all)'}")
        print(f"    key pattern   {cfg.key_pattern}")
        teams = ", ".join(f"{i}:{t.name}" for i, t in enumerate(cfg.teams, 1))
        print(f"    teams         {teams or '(none)'}")
        print()
