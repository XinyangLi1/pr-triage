"""GitHub access via the `gh` CLI.

One paginated GraphQL search per bucket. GraphQL is used rather than the REST
search endpoint because REST search is rate-limited to 30 requests/minute, and
because only GraphQL exposes the review-request timeline we need to compute how
long a PR has actually been waiting on us.
"""

from __future__ import annotations

import json

from .config import Config
from .model import Bucket, PullRequest
from .util import ToolError, parse_ts, run

PAGE = 100

_QUERY = """
query($q:String!,$after:String){
  search(query:$q,type:ISSUE,first:%d,after:$after){
    issueCount
    pageInfo{hasNextPage endCursor}
    nodes{
      ... on PullRequest{
        number title url isDraft createdAt updatedAt headRefName
        author{login} repository{nameWithOwner} reviewDecision
        timelineItems(last:20,itemTypes:[REVIEW_REQUESTED_EVENT]){
          nodes{... on ReviewRequestedEvent{createdAt requestedReviewer{
            ... on Team{slug} ... on User{login}}}}
        }
      }
    }
  }
}
""" % PAGE


def _search(query: str, limit: int) -> tuple[list[dict], int]:
    """Page through a GitHub search. Returns (nodes, total_reported_by_github)."""
    nodes: list[dict] = []
    cursor: str | None = None
    total = 0

    while True:
        args = ["gh", "api", "graphql", "-f", f"query={_QUERY}", "-f", f"q={query}"]
        if cursor:
            args += ["-f", f"after={cursor}"]

        doc = json.loads(run(args))
        if "errors" in doc:
            raise ToolError("GitHub GraphQL: " + json.dumps(doc["errors"])[:300])

        block = doc["data"]["search"]
        total = block.get("issueCount", 0)
        nodes.extend(n for n in block["nodes"] if n)

        page = block["pageInfo"]
        if not page["hasNextPage"] or len(nodes) >= limit:
            break
        cursor = page["endCursor"]

    return nodes[:limit], total


def blocked_since(node: dict, bucket: Bucket, targets: set[str]):
    """
    When this PR started waiting on us.

    Deliberately NOT the PR creation date. A long-lived PR routed to our team
    yesterday has been blocking us for one day, not for its whole life. We take
    the most recent review request aimed at us or at our team.
    """
    stamps = []
    for event in node.get("timelineItems", {}).get("nodes", []) or []:
        reviewer = event.get("requestedReviewer") or {}
        who = (reviewer.get("slug") or reviewer.get("login") or "").lower()
        if bucket is Bucket.MINE or who in targets:
            ts = parse_ts(event.get("createdAt"))
            if ts:
                stamps.append(ts)
    return max(stamps) if stamps else parse_ts(node.get("createdAt"))


def _to_pr(node: dict, bucket: Bucket, cfg: Config, targets: set[str]) -> PullRequest:
    text = f"{node['title']} {node.get('headRefName') or ''}"
    keys = tuple(sorted({m.upper() for m in cfg.key_re.findall(text)}))
    return PullRequest(
        bucket=bucket,
        repo=node["repository"]["nameWithOwner"],
        number=node["number"],
        title=node["title"].strip(),
        url=node["url"],
        author=(node.get("author") or {}).get("login", "?"),
        draft=bool(node["isDraft"]),
        decision=node.get("reviewDecision") or "REVIEW_REQUIRED",
        created=parse_ts(node.get("createdAt")),
        updated=parse_ts(node.get("updatedAt")),
        since=blocked_since(node, bucket, targets),
        keys=keys,
    )


def build_queries(cfg: Config, team_scope: str) -> dict[Bucket, str]:
    """
    team_scope:
      "team" -- restrict the shared bucket to the configured review team
      "any"  -- every review request reaching you, team-expanded included
    """
    base = "is:open is:pr"
    repos = cfg.repo_filter()
    if repos:
        base = f"{base} {repos}"

    queries = {
        Bucket.DIRECT: f"{base} user-review-requested:{cfg.user}",
        Bucket.MINE: f"{base} author:{cfg.user}",
    }

    if team_scope == "team" and cfg.review_team:
        queries[Bucket.TEAM] = f"{base} team-review-requested:{cfg.review_team}"
    else:
        # No review team configured, or the user asked for everything.
        queries[Bucket.TEAM] = f"{base} review-requested:{cfg.user}"

    return queries


def collect(cfg: Config, team_scope: str) -> tuple[list[PullRequest], dict[str, int]]:
    """
    Fetch and de-duplicate. A PR reachable through more than one bucket keeps the
    most actionable one, so a personal request is never demoted to a team request.
    """
    targets = {cfg.user.lower()}
    if cfg.review_team:
        targets.add(cfg.review_team.split("/")[-1].lower())

    seen: dict[tuple[str, int], PullRequest] = {}
    totals: dict[str, int] = {}

    for bucket, query in build_queries(cfg, team_scope).items():
        nodes, reported = _search(query, cfg.max_results)
        totals[bucket.value] = reported
        for node in nodes:
            pr = _to_pr(node, bucket, cfg, targets)
            existing = seen.get(pr.ident)
            if existing is None or pr.bucket.rank < existing.bucket.rank:
                seen[pr.ident] = pr

    return list(seen.values()), totals
