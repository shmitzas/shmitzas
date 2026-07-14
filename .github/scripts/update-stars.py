#!/usr/bin/env python3
"""Refresh stars.svg with the current total stars and starred-repo count.

Reads shmitzas's public source repos via the GitHub REST API, filters out
forks, and patches the two <text> nodes with id="stars-count" and
id="repos-count" in stars.svg.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

USER = "shmitzas"
SVG_PATH = Path(__file__).resolve().parents[2] / "stars.svg"


def fetch_all_repos(user: str, token: str | None) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{user}/repos?per_page=100&type=owner&page={page}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{user}-profile-stars",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read())
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def patch_svg(svg: str, stars_count: int, repos_count: int) -> str:
    def sub(pattern: str, value: str, text: str) -> str:
        new_text, n = re.subn(pattern, value, text, count=1, flags=re.DOTALL)
        if n != 1:
            raise SystemExit(f"Marker not found (or matched more than once): {pattern}")
        return new_text

    svg = sub(
        r'(<text[^>]*\bid="stars-count"[^>]*>)[^<]*(</text>)',
        rf'\g<1>{stars_count}\g<2>',
        svg,
    )
    svg = sub(
        r'(<text[^>]*\bid="repos-count"[^>]*>)[^<]*(</text>)',
        rf'\g<1>{repos_count}\g<2>',
        svg,
    )
    return svg


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repos = fetch_all_repos(USER, token)
    source_repos = [r for r in repos if not r.get("fork")]
    total_stars = sum(int(r.get("stargazers_count", 0)) for r in source_repos)
    starred_count = sum(1 for r in source_repos if int(r.get("stargazers_count", 0)) > 0)

    print(f"repos_total={len(repos)} source_repos={len(source_repos)} total_stars={total_stars} starred_count={starred_count}")

    svg = SVG_PATH.read_text(encoding="utf-8")
    new_svg = patch_svg(svg, total_stars, starred_count)
    if new_svg == svg:
        print("stars.svg already up to date")
        return
    SVG_PATH.write_text(new_svg, encoding="utf-8")
    print(f"stars.svg updated -> {SVG_PATH}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:  # pragma: no cover
        print(f"HTTP error: {e.code} {e.reason}", file=sys.stderr)
        raise
