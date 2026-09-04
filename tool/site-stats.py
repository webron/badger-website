#!/usr/bin/env python3
"""Print a readable summary of badger.fit's GoatCounter numbers.

The GoatCounter dashboard exists and works, but reading it is a chore. This
pulls the same aggregate figures over the JSON API and prints the five things
worth knowing: how many visits, which pages, where they came from, which
countries, and whether anyone tapped through to a store.

The API token is read from ~/.config/goatcounter/token (mode 600, outside every
repo) and is never printed. Create one at
https://badgerfit.goatcounter.com/user/api with "Read statistics" only.

Usage:
    tool/site-stats.py            # last 7 days
    tool/site-stats.py 30         # last 30 days
    tool/site-stats.py 90 --json  # raw JSON, for piping somewhere else
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

SITE = "https://badgerfit.goatcounter.com"
TOKEN_PATH = os.path.expanduser("~/.config/goatcounter/token")

# The store-link click events, in the order the badges appear on the page.
# These paths come from data-store-event in src/components/StoreBadges.astro;
# rename one there and it must be renamed here, or the click line goes quiet
# without failing.
STORE_EVENTS = {"store-play": "Google Play", "store-testflight": "TestFlight"}


def read_token() -> str:
    try:
        with open(TOKEN_PATH, encoding="utf-8") as fh:
            token = fh.read().strip()
    except FileNotFoundError:
        sys.exit(f"No token at {TOKEN_PATH}. See the docstring in this file.")
    if not token or token == "PASTE_TOKEN_HERE":
        sys.exit(f"{TOKEN_PATH} still holds the placeholder, not a real token.")
    return token


def get(endpoint: str, token: str, **params) -> dict:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(
        f"{SITE}/api/v0/{endpoint}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        # 401/403 means the token is wrong or lacks "Read statistics". Say which
        # endpoint failed: a token scoped to one permission fails partially, and
        # a bare "403" sends you looking at the wrong thing.
        sys.exit(f"{endpoint} failed: HTTP {exc.code} {exc.reason}")
    except urllib.error.URLError as exc:
        sys.exit(f"{endpoint} failed: {exc.reason}")


def rows(stats: list[dict], limit: int) -> list[tuple[str, int]]:
    out = [(s.get("name") or s.get("id") or "(unknown)", s.get("count", 0)) for s in stats]
    return [r for r in out if r[1] > 0][:limit]


def table(title: str, data: list[tuple[str, int]], empty: str) -> None:
    print(f"\n{title}")
    if not data:
        print(f"  {empty}")
        return
    width = max(len(str(count)) for _, count in data)
    for name, count in data:
        print(f"  {count:>{width}}  {name}")


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv[1:]
    days = int(args[0]) if args else 7

    token = read_token()
    end = date.today()
    start = end - timedelta(days=days - 1)
    window = {"start": start.isoformat(), "end": end.isoformat()}

    total = get("stats/total", token, **window)
    hits = get("stats/hits", token, limit=100, **window)
    refs = get("stats/toprefs", token, limit=10, **window)
    locations = get("stats/locations", token, limit=10, **window)

    # Events and pages share the hits list; the flag is what separates a store
    # click from a page someone read.
    all_hits = hits.get("hits", [])
    pages = [h for h in all_hits if not h.get("event")]
    events = {h.get("path"): h.get("count", 0) for h in all_hits if h.get("event")}

    if as_json:
        print(json.dumps(
            {"window": window, "total": total.get("total", 0),
             "pages": pages, "events": events,
             "referrers": refs.get("stats", []),
             "locations": locations.get("stats", [])},
            indent=2))
        return

    print(f"badger.fit  {start.isoformat()} to {end.isoformat()}  ({days} days)")
    print(f"\n  {total.get('total', 0)} page views")

    table("Pages",
          sorted(((p.get("path", "?"), p.get("count", 0)) for p in pages),
                 key=lambda r: -r[1])[:15],
          "Nothing yet.")

    table("Came from", rows(refs.get("stats", []), 10),
          "No referrers. Everyone typed the address or came from a private link.")

    table("Countries", rows(locations.get("stats", []), 10), "Nothing yet.")

    print("\nStore link taps")
    if not any(events.get(path) for path in STORE_EVENTS):
        print("  None yet.")
    else:
        views = total.get("total", 0)
        width = max(len(str(events.get(p, 0))) for p in STORE_EVENTS)
        for path, label in STORE_EVENTS.items():
            count = events.get(path, 0)
            share = f"  ({count / views:.1%} of page views)" if views else ""
            print(f"  {count:>{width}}  {label}{share}")
    print()


if __name__ == "__main__":
    main()
