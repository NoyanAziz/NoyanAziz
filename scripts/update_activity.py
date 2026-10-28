"""Generate anonymous commit and PR aggregates, never repository names or PR titles.

Public-only by default. INCLUDE_PRIVATE=true explicitly includes private totals.
GH_TOKEN must have access to all repositories intended to be counted.
"""
import datetime as dt
import html
import json
import os
from pathlib import Path
import urllib.request

QUERY = """query($login:String!, $cursor:String) {
  user(login:$login) {
    pullRequests(first:100, after:$cursor, orderBy:{field:CREATED_AT,direction:DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { createdAt mergedAt repository { nameWithOwner isPrivate } }
    }
  }
}"""


def fetch_prs(token, login="NoyanAziz"):
    cursor = None
    while True:
        payload = {"query": QUERY, "variables": {"login": login, "cursor": cursor}}
        request = urllib.request.Request(
            "https://api.github.com/graphql", data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "User-Agent": "profile-activity",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        if result.get("errors"):
            raise RuntimeError("GitHub returned GraphQL errors; previous stats kept unchanged.")
        connection = result["data"]["user"]["pullRequests"]
        yield from connection["nodes"]
        if not connection["pageInfo"]["hasNextPage"]:
            break
        next_cursor = connection["pageInfo"]["endCursor"]
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("Invalid pagination cursor; previous stats kept unchanged.")
        cursor = next_cursor


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def aggregate(prs, now, include_private=False):
    start = dt.datetime(now.year, 1, 1, tzinfo=dt.timezone.utc)
    monday = now.date() - dt.timedelta(days=now.weekday())
    weeks = [{"start": (monday-dt.timedelta(weeks=11-i)).isoformat(), "opened": 0}
             for i in range(12)]
    week_index = {w["start"]: w for w in weeks}
    opened = merged = 0
    for pr in prs:
        if pr["repository"]["isPrivate"] and not include_private:
            continue
        created = timestamp(pr["createdAt"])
        if start <= created <= now:
            opened += 1
        if created <= now:
            week = (created.date()-dt.timedelta(days=created.weekday())).isoformat()
            if week in week_index:
                week_index[week]["opened"] += 1
        if pr["mergedAt"] and start <= timestamp(pr["mergedAt"]) <= now:
            merged += 1
    return {"year": now.year, "updated_at": now.isoformat(),
            "scope": "Public + accessible private work" if include_private else "Public work only",
            "lines_added": 0, "lines_deleted": 0,
            "commits_authored": 0, "prs_contributed": 0, "others_prs_contributed": 0,
            "prs_opened": opened, "prs_merged": merged, "weeks": weeks}


def compact_number(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return str(value)


def svg(data):
    esc = html.escape
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="458" viewBox="0 0 800 458" role="img" aria-labelledby="activity-title activity-desc">',
             f'<title id="activity-title">{data["year"]} engineering activity</title>',
             '<desc id="activity-desc">'+esc(f'{data["scope"]}. {data["lines_added"]:,} lines added and {data["lines_deleted"]:,} deleted in authored non-merge commits this year, including work on others’ PRs. {data["prs_opened"]} PRs opened and {data["prs_merged"]} merged this year. Weekly PRs opened: '+', '.join(f'{w["start"]}: {w["opened"]}' for w in data['weeks']))+'</desc>',
             '<style>text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;fill:#1f2328}.secondary{fill:#59636e}.bg{fill:#fff;stroke:#d1d9e0}.grid{stroke:#d1d9e0}.bar{fill:#0969da}.added{fill:#1a7f37}.deleted{fill:#cf222e}@media(prefers-color-scheme:dark){text{fill:#f0f6fc}.secondary{fill:#9198a1}.bg{fill:#0d1117;stroke:#3d444d}.grid{stroke:#3d444d}.bar{fill:#58a6ff}.added{fill:#3fb950}.deleted{fill:#f85149}}</style>',
             '<rect class="bg" x=".5" y=".5" width="799" height="457" rx="10"/>',
             f'<text x="24" y="33" font-size="18" font-weight="600">{data["year"]} · Engineering activity</text>',
             f'<text class="secondary" x="24" y="57" font-size="12">{esc(data["scope"])} · through {data["updated_at"][:10]} UTC</text>']
    stats = [(data['lines_added'],'Lines added','added'), (data['lines_deleted'],'Lines deleted','deleted'),
             (data['prs_opened'],'PRs opened',''), (data['prs_merged'],'PRs merged','')]
    for i,(n,label,cls) in enumerate(stats):
        x = 24+196*i
        parts.append(f'<text x="{x}" y="106" font-size="29" font-weight="600" class="{cls}"><title>{n:,}</title>{compact_number(n)}</text><text class="secondary" x="{x}" y="130" font-size="14">{label}</text>')
    parts.extend(['<text class="secondary" x="24" y="157" font-size="12">Lines = authored non-merge commit diffs, including work on others’ PRs.</text>',
                  '<text x="24" y="191" font-size="15" font-weight="600">PRs opened per week · last 12 weeks</text>'])
    maximum = max(1, max(w['opened'] for w in data['weeks']))
    for v in [0, maximum]:
        y = 330-100*v/maximum
        parts.append(f'<line class="grid" x1="48" x2="776" y1="{y}" y2="{y}"/><text class="secondary" x="34" y="{y+4}" text-anchor="end" font-size="12">{v}</text>')
    for i,w in enumerate(data['weeks']):
        x = 50+i*60
        h = 100*w['opened']/maximum
        label = dt.date.fromisoformat(w['start']).strftime('%b %d')
        parts.append(f'<g><title>Week of {label}: {w["opened"]} PRs opened</title><rect class="bar" x="{x+8}" y="{330-h}" width="38" height="{h}" rx="3"/><text x="{x+27}" y="{max(219,322-h)}" text-anchor="middle" font-size="13">{w["opened"]}</text><text class="secondary" x="{x+27}" y="351" text-anchor="middle" font-size="11">{label}</text></g>')
    parts.append('<text class="secondary" x="48" y="380" font-size="12">Week starting Monday (UTC) · final week is partial</text>')
    parts.append(f'<text x="24" y="410" font-size="14">{data["commits_authored"]:,} authored commits · {data["prs_contributed"]:,} PRs contributed to · {data["others_prs_contributed"]:,} opened by others</text>')
    parts.append('<text class="secondary" x="24" y="438" font-size="12">Accessible work only · anonymous totals · no private repository names.</text></svg>')
    return ''.join(parts)


def main():
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN is required to refresh activity statistics.")
    now = dt.datetime.now(dt.timezone.utc)
    from commit_activity import collect
    include_private = os.environ.get("INCLUDE_PRIVATE", "false").lower() == "true"
    prs = list(fetch_prs(token))
    data = aggregate(prs, now, include_private)
    data.update(collect(token, prs, now, include_private))
    assets = Path(__file__).resolve().parents[1]/"assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets/"activity.svg").write_text(svg(data))
    (assets/"activity.json").write_text(json.dumps(data, indent=2)+"\n")
    print(f"Activity refreshed ({data['scope']}); only anonymous aggregates saved.")


if __name__ == "__main__":
    main()
