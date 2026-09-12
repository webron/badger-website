#!/usr/bin/env python3
"""Print badger.fit's numbers as readable text.

The GoatCounter and Search Console dashboards both work; reading them is the
chore. This prints the six things worth knowing in one screen: page views, top
pages, referrers, countries, store-link taps, and the search terms people used
to find the site.

Credentials, both outside every repo and never printed:
  ~/.config/goatcounter/token            GoatCounter, "Read statistics" only
  ~/.config/badger-stats/search-console.json   a read-only service-account key

Usage:
    tool/site-stats.py            # last 7 days
    tool/site-stats.py 30         # last 30 days
    tool/site-stats.py --json     # raw, for piping

For the weekly HTML version, see tool/weekly-report.py.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from _stats_sources import STORE_EVENTS, goatcounter, search_console  # noqa: E402


def table(title: str, data: list[tuple[str, int]], empty: str, limit: int = 15) -> None:
    print(f"\n{title}")
    data = data[:limit]
    if not data:
        print(f"  {empty}")
        return
    width = max(len(str(count)) for _, count in data)
    for name, count in data:
        print(f"  {count:>{width}}  {name}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    days = int(args[0]) if args else 7

    gc = goatcounter(days)
    # Search Console needs a longer window to say anything useful: a small site
    # gets few clicks a week, and its data also lags a couple of days.
    sc = search_console(max(days, 28))

    if "--json" in sys.argv[1:]:
        print(json.dumps({"goatcounter": gc, "search_console": sc}, indent=2))
        return

    if "error" in gc:
        print(f"GoatCounter: {gc['error']}")
    else:
        print(f"badger.fit  {gc['start']} to {gc['end']} UTC  ({days} days)")
        plural = "" if gc["views"] == 1 else "s"
        print(f"\n  {gc['views']} page view{plural}")
        table("Pages", gc["pages"], "Nothing yet.")
        table("Came from", gc["referrers"],
              "No referrers. Everyone typed the address or came from a private link.", 10)
        table("Countries", gc["countries"], "Nothing yet.", 10)

        print("\nStore link taps")
        taps = [(label, gc["events"].get(path, 0)) for path, label in STORE_EVENTS.items()]
        # A retired affordance with no history is noise, not information.
        taps = [t for t in taps if t[1] or "retired" not in t[0]]
        if not any(count for _, count in taps):
            print("  None yet.")
        else:
            width = max(len(str(c)) for _, c in taps)
            for label, count in taps:
                share = f"  ({count / gc['views']:.1%} of page views)" if gc["views"] else ""
                print(f"  {count:>{width}}  {label}{share}")

    print()
    if "error" in sc:
        print(f"Search Console: {sc['error']}")
    else:
        print(f"Google search  {sc['start']} to {sc['end']}  "
              f"({sc['clicks']} clicks, {sc['impressions']} impressions)")
        if not sc["queries"]:
            print("  Nothing yet. Google needs a few days after verification, "
                  "and then a few more to gather enough to show.")
        else:
            for row in sc["queries"][:15]:
                print(f"  {row['clicks']:>3} clicks  {row['impressions']:>5} shown  "
                      f"avg #{row['position']:.1f}  {row['key']}")
    print()


if __name__ == "__main__":
    main()
