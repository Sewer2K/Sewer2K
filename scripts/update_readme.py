"""
Regenerates the "Featured Projects" section of README.md from live GitHub
data, so renamed/deleted/archived repos never leave a stale, dead link
behind. Run by .github/workflows/update-readme.yml on a schedule.

Selection rules:
  - Only the user's own, non-fork, non-archived, public repositories.
  - Sorted by star count (then recency) and capped at MAX_FEATURED.
  - A small exclusion list + keyword filter keeps security-sensitive /
    off-brand tooling out of the auto-generated portfolio section even if
    it happens to have stars.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

USERNAME = os.environ.get("GH_USERNAME", "Sewer2K")
TOKEN = os.environ.get("GH_TOKEN")
MAX_FEATURED = 4
README_PATH = "README.md"

START_MARKER = "<!--START_SECTION:pinned-->"
END_MARKER = "<!--END_SECTION:pinned-->"

# Repos that should never appear in the auto-generated portfolio section,
# regardless of star count.
EXCLUDE_REPOS = {
    "toxnetv2",
    "vuln-scanner-exploit-combo",
    "nervnet",
    "valtrig",
    "api-key-scraper-for-popular-llms",
    "xss-tool-list-",
}

# Secondary keyword safety net, in case a future repo covers similar
# ground before anyone remembers to add it to EXCLUDE_REPOS above.
BLOCKED_KEYWORDS = [
    "botnet", "c2 framework", "exploit module", "ddos", "payload",
    "backdoor", "keylogger", "triggerbot", "aimbot", "wallhack", "malware",
    "leaked api key", "api key scraper", "credential harvest", "stealer",
    "brute force", "ransomware", "xss tool", "sql injection tool",
]


def api_get(path: str):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USERNAME}-readme-bot")
    if TOKEN:
        req.add_header("Authorization", f"token {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def is_blocked(repo: dict) -> bool:
    name = repo["name"].lower()
    if name in EXCLUDE_REPOS:
        return True
    desc = (repo.get("description") or "").lower()
    return any(kw in desc for kw in BLOCKED_KEYWORDS)


def fetch_candidate_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        batch = api_get(f"/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    candidates = [
        r for r in repos
        if not r.get("fork") and not r.get("archived") and not r.get("private")
        and not is_blocked(r)
    ]
    candidates.sort(
        key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at", "")),
        reverse=True,
    )
    return candidates[:MAX_FEATURED]


def build_cell(repo: dict) -> str:
    name = repo["name"]
    url = repo["html_url"]
    desc = repo.get("description") or "No description provided."
    lang = repo.get("language")
    lang_tag = f"`{lang}`  \n" if lang else ""
    return (
        f"**[{name}]({url})**\n"
        f"{desc}\n\n"
        f"{lang_tag}"
        f"[![Stars](https://img.shields.io/github/stars/{USERNAME}/{name}?style=flat&color=6c5ce7&label=%E2%98%85)]({url}/stargazers)"
        f" [![Forks](https://img.shields.io/github/forks/{USERNAME}/{name}?style=flat&color=6c5ce7&label=forks)]({url}/forks)"
    )


def build_section(repos: list[dict]) -> str:
    if not repos:
        return "_No public repositories to feature yet._"

    cells = [build_cell(r) for r in repos]
    rows = []
    for i in range(0, len(cells), 2):
        pair = cells[i:i + 2]
        if len(pair) == 1:
            pair.append("")
        rows.append(
            "<tr>\n"
            f"<td width=\"50%\" valign=\"top\">\n\n{pair[0]}\n\n</td>\n"
            f"<td width=\"50%\" valign=\"top\">\n\n{pair[1]}\n\n</td>\n"
            "</tr>"
        )
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def main() -> None:
    if not os.path.exists(README_PATH):
        print(f"{README_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        re.escape(START_MARKER) + r"(.*?)" + re.escape(END_MARKER),
        re.DOTALL,
    )
    if not pattern.search(content):
        print("Marker comments not found in README.md — nothing to update.")
        return

    repos = fetch_candidate_repos()
    section = build_section(repos)
    replacement = f"{START_MARKER}\n\n{section}\n\n{END_MARKER}"
    new_content = pattern.sub(replacement, content)

    if new_content != content:
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"README.md updated with {len(repos)} featured repo(s).")
    else:
        print("No changes needed.")


if __name__ == "__main__":
    main()
