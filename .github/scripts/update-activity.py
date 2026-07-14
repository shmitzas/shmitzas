#!/usr/bin/env python3
"""Regenerate activity.svg with the last 12 months of GitHub contribution counts.

Queries GitHub's GraphQL contributionsCollection for the target user, buckets
day counts by YYYY-MM, keeps the 12 most recent months, and renders a bar
chart matching the shmitzas profile aesthetic.

Token resolution (in order):
  1. GH_TOKEN env var
  2. GITHUB_TOKEN env var (workflow default)
  3. `gh auth token` (for local runs)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

USER = "shmitzas"
SVG_PATH = Path(__file__).resolve().parents[2] / "activity.svg"

GRAPHQL = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def resolve_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, check=True,
        )
        token = result.stdout.strip()
        if token:
            return token
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    raise SystemExit("No token: set GH_TOKEN or run `gh auth login` first")


def fetch(user: str, token: str) -> dict:
    body = json.dumps({"query": GRAPHQL, "variables": {"login": user}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{user}-profile-activity",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    if not payload.get("data", {}).get("user"):
        raise SystemExit(f"User '{user}' not found or not visible")
    return payload


def aggregate(payload: dict) -> tuple[list[tuple[str, int]], int]:
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    by_month: dict[str, int] = {}
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            ym = day["date"][:7]
            by_month[ym] = by_month.get(ym, 0) + int(day["contributionCount"])
    ordered = sorted(by_month.items())
    last12 = ordered[-12:] if len(ordered) >= 12 else ordered
    return last12, int(cal["totalContributions"])


def build_bars(months: list[tuple[str, int]]) -> str:
    if not months:
        return ""
    max_val = max((c for _, c in months), default=1) or 1
    threshold = max_val * 0.75  # top-quartile months get green highlight
    max_h = 125.0
    baseline = 225.0
    bars: list[str] = []
    for i, (ym, count) in enumerate(months):
        col_center = 105 + i * 90
        bar_x = col_center - 30
        raw_h = (count / max_val) * max_h
        h = max(raw_h, 3.0) if count > 0 else 0.0
        y = baseline - h
        month_num = int(ym.split("-")[1])
        label = MONTH_ABBR[month_num - 1]
        highlight = count >= threshold and count > 0
        fill = "#19ee19" if highlight else "#0dcaf0"
        fill_op = "0.4" if highlight else "0.55"
        stroke = "#19ee19" if highlight else "#0dcaf0"
        stroke_op = "0.75" if highlight else "0.85"
        # count text above bar (only if bar tall enough to sit under it)
        count_y = max(y - 8, 88)
        bars.append(
            f'    <g>\n'
            f'      <rect x="{bar_x}" y="{y:.2f}" width="60" height="{h:.2f}" rx="2" ry="2" '
            f'fill="{fill}" fill-opacity="{fill_op}" stroke="{stroke}" stroke-opacity="{stroke_op}" stroke-width="1"/>\n'
            f'      <text x="{col_center}" y="{count_y:.2f}" text-anchor="middle" '
            f'font-family="\'Roboto\',\'Segoe UI\',Arial,sans-serif" '
            f'font-size="11" font-weight="700" fill="#ffffff" opacity="0.75">{count}</text>\n'
            f'      <text x="{col_center}" y="248" text-anchor="middle" '
            f'font-family="\'Roboto\',\'Segoe UI\',Arial,sans-serif" '
            f'font-size="12" font-weight="700" fill="#ffffff" opacity="0.55" letter-spacing="2">{label}</text>\n'
            f'    </g>'
        )
    return "\n".join(bars)


def build_svg(months: list[tuple[str, int]], total: int) -> str:
    total_str = f"{total:,}"
    bars = build_bars(months)
    range_label = ""
    if months:
        first_ym = months[0][0]
        last_ym = months[-1][0]
        first_year = first_ym.split("-")[0][2:]
        last_year = last_ym.split("-")[0][2:]
        first_mo = MONTH_ABBR[int(first_ym.split("-")[1]) - 1].upper()
        last_mo = MONTH_ABBR[int(last_ym.split("-")[1]) - 1].upper()
        range_label = f"{first_mo} '{first_year} — {last_mo} '{last_year}"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 280" role="img" aria-label="Contribution activity — last 12 months. {total_str} contributions total.">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f1621"/>
      <stop offset="100%" stop-color="#060912"/>
    </linearGradient>
    <linearGradient id="line" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0dcaf0" stop-opacity="0"/>
      <stop offset="50%" stop-color="#0dcaf0" stop-opacity="1"/>
      <stop offset="100%" stop-color="#0dcaf0" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="glowCyan" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#0dcaf0" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#0dcaf0" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowGreen" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#19ee19" stop-opacity="0.05"/>
      <stop offset="100%" stop-color="#19ee19" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="1200" height="280" rx="24" ry="24" fill="url(#bg)"/>

  <circle cx="300" cy="140" r="280" fill="url(#glowCyan)"/>
  <circle cx="900" cy="140" r="280" fill="url(#glowCyan)"/>
  <circle cx="600" cy="140" r="320" fill="url(#glowGreen)"/>

  <rect x="0.5" y="0.5" width="1199" height="279" rx="24" ry="24"
        fill="none" stroke="#0dcaf0" stroke-opacity="0.28" stroke-width="1"/>

  <rect x="0" y="0" width="1200" height="3" fill="url(#line)">
    <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" repeatCount="indefinite"/>
  </rect>

  <circle cx="40" cy="40" r="3" fill="#0dcaf0" opacity="0.5">
    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="4s" repeatCount="indefinite"/>
  </circle>
  <circle cx="1160" cy="40" r="3" fill="#0dcaf0" opacity="0.5">
    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="4.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="40" cy="240" r="3" fill="#0dcaf0" opacity="0.5">
    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="4.2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="1160" cy="240" r="3" fill="#0dcaf0" opacity="0.5">
    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="4.8s" repeatCount="indefinite"/>
  </circle>

  <!-- Header left: label + range -->
  <g transform="translate(40, 48)" font-family="'Roboto','Segoe UI',Arial,sans-serif">
    <text x="0" y="10" font-size="16" fill="#19ee19">★</text>
    <text x="22" y="10" font-size="12" font-weight="700" fill="#ffffff" opacity="0.55" letter-spacing="3">ACTIVITY · {range_label}</text>
  </g>

  <!-- Header right: total contributions -->
  <text x="1160" y="55" text-anchor="end" font-family="'Roboto','Segoe UI',Arial,sans-serif">
    <tspan font-size="22" font-weight="900" fill="#ffffff">{total_str}</tspan>
    <tspan dx="8" font-size="11" font-weight="700" fill="#ffffff" opacity="0.55" letter-spacing="3">CONTRIBUTIONS</tspan>
  </text>

  <!-- Baseline -->
  <line x1="60" y1="225" x2="1140" y2="225" stroke="#0dcaf0" stroke-opacity="0.2" stroke-width="1"/>

  <!-- Bars -->
  <g>
{bars}
  </g>
</svg>
'''


def main() -> None:
    token = resolve_token()
    payload = fetch(USER, token)
    months, total = aggregate(payload)
    print(
        f"total_contributions={total} "
        f"months={len(months)} "
        f"range={months[0][0] if months else '?'}..{months[-1][0] if months else '?'}"
    )
    svg = build_svg(months, total)
    SVG_PATH.write_text(svg, encoding="utf-8")
    print(f"activity.svg written -> {SVG_PATH}")


if __name__ == "__main__":
    main()
