#!/usr/bin/env python3
"""Fetch a GitHub user's public contribution calendar and save it as JSON.

Scrapes the public, unauthenticated HTML fragment GitHub serves at
    https://github.com/users/<username>/contributions
No API token is used or required.

Each day cell looks roughly like:
    <td ... data-date="2025-08-24" id="contribution-day-component-0-0"
        data-level="0" class="ContributionCalendar-day"></td>
    <tool-tip ... for="contribution-day-component-0-0" ...>
        No contributions on August 24th.
    </tool-tip>

We pair each `td.ContributionCalendar-day` with its matching `<tool-tip for=...>`
to recover the exact per-day contribution count (the td itself only carries a
coarse 0-4 "level", not the real number).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

GITHUB_USERNAME = "amanchikalapudi"
CONTRIBUTIONS_URL = "https://github.com/users/{username}/contributions"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "contributions.json"

USER_AGENT = (
    "Mozilla/5.0 (compatible; profile-readme-bot/1.0; "
    "+https://github.com/{username})"
)

# "12 contributions on August 24th." / "1 contribution on ..." / "No contributions on ..."
COUNT_RE = re.compile(r"^(No|[\d,]+)\s+contributions?", re.IGNORECASE)
# "12\n      contributions\n        in the last year"
TOTAL_RE = re.compile(r"([\d,]+)\s+contributions?\s+in the last year", re.IGNORECASE)


def fetch_html(username: str) -> str:
    url = CONTRIBUTIONS_URL.format(username=username)
    headers = {"User-Agent": USER_AGENT.format(username=username)}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_count(tooltip_text: str | None) -> int:
    if not tooltip_text:
        return 0
    match = COUNT_RE.match(tooltip_text.strip())
    if not match:
        return 0
    raw = match.group(1)
    if raw.lower() == "no":
        return 0
    return int(raw.replace(",", ""))


def parse_total(soup: BeautifulSoup) -> int:
    heading = soup.find(id="js-contribution-activity-description")
    if heading:
        match = TOTAL_RE.search(heading.get_text(" ", strip=True))
        if match:
            return int(match.group(1).replace(",", ""))
    return 0


def parse_contributions(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    raw_cells = []
    for td in soup.select("td.ContributionCalendar-day"):
        cell_id = td.get("id", "")
        date = td.get("data-date")
        level = td.get("data-level")
        if not date or level is None:
            continue

        tooltip = soup.find("tool-tip", attrs={"for": cell_id}) if cell_id else None
        count = parse_count(tooltip.get_text(" ", strip=True) if tooltip else None)
        raw_cells.append({"date": date, "level": int(level), "count": count})

    # Grid position (week column / weekday row) is derived from the date itself
    # rather than GitHub's `id="contribution-day-component-<row>-<col>"` markup,
    # since that internal numbering scheme isn't guaranteed stable.
    raw_cells.sort(key=lambda d: d["date"])
    days = []
    week_idx = -1
    for cell in raw_cells:
        weekday_idx = (datetime.strptime(cell["date"], "%Y-%m-%d").weekday() + 1) % 7  # Sun=0
        if weekday_idx == 0 or week_idx == -1:
            week_idx += 1
        days.append({**cell, "week": week_idx, "weekday": weekday_idx})
    max_week = week_idx

    total_from_heading = parse_total(soup)
    total = total_from_heading or sum(d["count"] for d in days)

    return {
        "username": GITHUB_USERNAME,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": total,
        "weeks": max_week + 1 if days else 0,
        "days": days,
    }


def main() -> int:
    username = sys.argv[1] if len(sys.argv) > 1 else GITHUB_USERNAME
    html = fetch_html(username)
    data = parse_contributions(html)

    if not data["days"]:
        print("error: found no contribution cells, GitHub markup may have changed", file=sys.stderr)
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {len(data['days'])} days ({data['total']} contributions) -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
