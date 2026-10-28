"""Read commit authorship independently of PR ownership. Never write raw API data."""
import datetime as dt
import json
import urllib.parse
import urllib.request

COMMIT_FIELDS = """oid authoredDate additions deletions
author { user { login } } parents(first:1) { totalCount }
repository { isPrivate }
"""


class GitHub:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}", "User-Agent": "profile-activity",
                        "Accept": "application/vnd.github+json", "Content-Type": "application/json"}

    def request(self, path, payload=None):
        request = urllib.request.Request("https://api.github.com/" + path,
            data=None if payload is None else json.dumps(payload).encode(), headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except Exception:
            raise RuntimeError("GitHub activity request failed; previous snapshot kept unchanged.") from None

    def graphql(self, query, **variables):
        result = self.request("graphql", {"query": query, "variables": variables})
        if result.get("errors"):
            raise RuntimeError("Incomplete GraphQL activity response; previous snapshot kept unchanged.")
        return result["data"]


def search_authored_commits(api, login, start, end):
    """Split windows rather than silently accepting GitHub's 1,000-result ceiling."""
    query = f"author:{login} author-date:{start.isoformat()}..{end.isoformat()}"
    def page(number):
        result = api.request("search/commits?" + urllib.parse.urlencode(
            {"q": query, "per_page": 100, "page": number}))
        if result.get("incomplete_results"):
            raise RuntimeError("Commit search incomplete; previous snapshot kept unchanged.")
        return result
    first = page(1)
    if first["total_count"] > 1000:
        if start == end:
            raise RuntimeError("Commit search exceeds daily limit; previous snapshot kept unchanged.")
        middle = start + (end-start)//2
        yield from search_authored_commits(api, login, start, middle)
        yield from search_authored_commits(api, login, middle+dt.timedelta(days=1), end)
        return
    yield from first["items"]
    for number in range(2, (first["total_count"]+99)//100+1):
        yield from page(number)["items"]


def candidate_repositories(api, login, start, own_prs, search_items, include_private):
    """Discover recent work without restricting PRs to the profile owner's authorship."""
    repos = {}
    for item in search_items:
        repos[item["repository"]["full_name"]] = item["repository"]["private"]
    for pr in own_prs:
        if pr["createdAt"][:10] >= start or (pr["mergedAt"] or "")[:10] >= start:
            repos[pr["repository"]["nameWithOwner"]] = pr["repository"]["isPrivate"]
    cursor = None
    while True:
        connection = api.graphql("""query($login:String!, $cursor:String) {
          user(login:$login) { repositoriesContributedTo(first:100,after:$cursor,
            includeUserRepositories:true,contributionTypes:[COMMIT,PULL_REQUEST]) {
            nodes { nameWithOwner isPrivate } pageInfo { hasNextPage endCursor }
          } }
        }""", login=login, cursor=cursor)["user"]["repositoriesContributedTo"]
        for repo in connection["nodes"]:
            repos[repo["nameWithOwner"]] = repo["isPrivate"]
        if not connection["pageInfo"]["hasNextPage"]:
            break
        cursor = connection["pageInfo"]["endCursor"]
    # Membership also finds private work not yet merged/indexed or attached to our own PR.
    if include_private:
        page = 1
        while True:
            batch = api.request(f"user/repos?per_page=100&page={page}&affiliation=owner,collaborator,organization_member")
            for repo in batch:
                if repo["private"] and (repo["pushed_at"] or "")[:10] >= start:
                    repos[repo["full_name"]] = True
            if len(batch) < 100:
                break
            page += 1
    return {name for name, private in repos.items() if include_private or not private}


def repository_prs(api, name, start):
    owner, repo = name.split("/", 1)
    cursor = None
    while True:
        connection = api.graphql("""query($owner:String!, $repo:String!, $cursor:String) {
          repository(owner:$owner,name:$repo) {
            pullRequests(first:25,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes { id updatedAt author { login } mergeCommit { oid }
                commits(first:100) { pageInfo { hasNextPage endCursor }
                  nodes { commit { """ + COMMIT_FIELDS + """ } }
                }
              }
            }
          }
        }""", owner=owner, repo=repo, cursor=cursor)["repository"]["pullRequests"]
        for pr in connection["nodes"]:
            if pr["updatedAt"][:10] < start:
                return
            commits = pr["commits"]
            rows = [n["commit"] for n in commits["nodes"]]
            while commits["pageInfo"]["hasNextPage"]:
                commits = api.graphql("""query($id:ID!, $cursor:String) {
                  node(id:$id) { ... on PullRequest { commits(first:100,after:$cursor) {
                    pageInfo { hasNextPage endCursor } nodes { commit { """ + COMMIT_FIELDS + """ } }
                  } } }
                }""", id=pr["id"], cursor=commits["pageInfo"]["endCursor"])["node"]["commits"]
                rows.extend(n["commit"] for n in commits["nodes"])
            yield pr, rows
        if not connection["pageInfo"]["hasNextPage"]:
            break
        cursor = connection["pageInfo"]["endCursor"]


def is_authored_this_year(commit, login, now, include_private):
    author = ((commit.get("author") or {}).get("user") or {}).get("login", "")
    date = dt.datetime.fromisoformat(commit["authoredDate"].replace("Z", "+00:00"))
    start = dt.datetime(now.year, 1, 1, tzinfo=dt.timezone.utc)
    return (author.casefold() == login.casefold() and start <= date <= now
            and commit["parents"]["totalCount"] <= 1
            and (include_private or not commit["repository"]["isPrivate"]))


def summarize(commits, contributions, excluded, login, now, include_private):
    unique = {c["oid"]: c for c in commits if c["oid"] not in excluded
              and is_authored_this_year(c, login, now, include_private)}
    # Each PR contributes once, even when several of our commits appear in it.
    contributed = {pr_id: owner for pr_id, owner, oids in contributions if set(oids) & unique.keys()}
    return {"commits_authored": len(unique),
            "lines_added": sum(c["additions"] for c in unique.values()),
            "lines_deleted": sum(c["deletions"] for c in unique.values()),
            "prs_contributed": len(contributed),
            "others_prs_contributed": sum(owner.casefold() != login.casefold() for owner in contributed.values())}


def collect(token, own_prs, now, include_private, login="NoyanAziz"):
    api = GitHub(token)
    start = dt.date(now.year, 1, 1)
    items = list(search_authored_commits(api, login, start, now.date()))
    nodes = {}
    for item in items:
        if include_private or not item["repository"]["private"]:
            nodes[item["node_id"]] = item
    commits = []
    ids = list(nodes)
    for offset in range(0, len(ids), 50):
        result = api.graphql("query($ids:[ID!]!) { nodes(ids:$ids) { ... on Commit { " + COMMIT_FIELDS + " } } }",
                             ids=ids[offset:offset+50])["nodes"]
        if any(c is None for c in result):
            raise RuntimeError("Commit details missing; previous snapshot kept unchanged.")
        commits.extend(result)
    repos = candidate_repositories(api, login, start.isoformat(), own_prs, items, include_private)
    contributions = []
    excluded = set()
    for index, repo in enumerate(sorted(repos), 1):
        for pr, rows in repository_prs(api, repo, start.isoformat()):
            oids = {c["oid"] for c in rows}
            # A squash result is synthetic if it wasn't a commit on the original PR.
            # Keep original authored work; don't count the squash result a second time.
            if pr["mergeCommit"] and pr["mergeCommit"]["oid"] not in oids:
                excluded.add(pr["mergeCommit"]["oid"])
            commits.extend(rows)
            contributions.append((pr["id"], (pr["author"] or {}).get("login", ""), oids))
        print(f"Scanned PR history in repository {index}/{len(repos)} (names withheld).", flush=True)
    return summarize(commits, contributions, excluded, login, now, include_private)
