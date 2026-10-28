"""Refresh public profile statistics using only Python's standard library."""
import collections
import datetime
import html
import json
import os
from pathlib import Path
import urllib.request

username = "NoyanAziz"
headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
if os.environ.get("GH_TOKEN"):
    headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
repos = []
page = 1
while True:
    req = urllib.request.Request(f"https://api.github.com/users/{username}/repos?per_page=100&page={page}", headers=headers)
    with urllib.request.urlopen(req) as response:
        batch = json.load(response)
    repos.extend(batch)
    if len(batch) < 100:
        break
    page += 1
projects = [r for r in repos if not r["fork"] and r["name"].lower() != username.lower()]
languages = collections.Counter(r["language"] for r in projects if r["language"])
date = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y")
stats = [(len(repos), "Public repositories"), (len(projects), "Original projects"), (sum(r["fork"] for r in repos), "Forks"), (len(languages), "Project languages")]
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="236" viewBox="0 0 800 236" role="img" aria-labelledby="title desc">', '<title id="title">Public work at a glance</title>', '<desc id="desc">' + html.escape(', '.join(f'{v} {label}' for v, label in stats)) + '. Primary languages counted by original project.</desc>', '<style>text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;fill:#1f2328}.label{fill:#59636e;font-size:14px}.value{font-size:32px;font-weight:600}@media(prefers-color-scheme:dark){text{fill:#f0f6fc}.label{fill:#9198a1}.bg{fill:#0d1117;stroke:#3d444d}.track{fill:#212830}}</style>', '<rect class="bg" x=".5" y=".5" width="799" height="235" rx="10" fill="#fff" stroke="#d1d9e0"/>']
for i,(value,label) in enumerate(stats):
    x = 24 + 196*i
    parts.append(f'<text class="value" x="{x}" y="53">{value}</text><text class="label" x="{x}" y="80">{label}</text>')
parts.append('<text x="24" y="123" font-size="14" font-weight="600">Primary languages · original projects</text>')
colors = ['#3178c6','#d9b52c','#b07219','#5e74cc']
x = 24
total = sum(languages.values()) or 1
for i,(language,count) in enumerate(languages.most_common()):
    width = 752*count/total
    color = colors[i%len(colors)]
    parts.append(f'<rect x="{x}" y="140" width="{width}" height="8" fill="{color}"/>')
    lx = 24+i*240
    parts.append(f'<circle cx="{lx+4}" cy="173" r="4" fill="{color}"/><text class="label" x="{lx+16}" y="178">{html.escape(language)} · {count} project'+('s' if count!=1 else '')+'</text>')
    x += width
parts.append(f'<text class="label" x="24" y="214">Public GitHub data · updated {date} UTC · forks and profile excluded from project counts</text></svg>')
out = Path(__file__).resolve().parents[1]/'assets'/'work-stats.svg'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(''.join(parts))
