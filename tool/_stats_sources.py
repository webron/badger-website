"""Fetch badger.fit's numbers from every source that has them.

Each source returns plain dicts and lists, so the callers (a text summary and an
HTML report) share one definition of what a figure means. Adding Play Console or
App Store Connect later means adding a fetcher here, not touching the renderers.

Every source is allowed to be absent. A missing credential, a revoked token or a
new property with no data yet returns an `error` or an empty list rather than
raising, because a weekly report that dies on one bad source tells you less than
one that prints the rest and says which part is missing.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

# --- GoatCounter -----------------------------------------------------------

GC_SITE = "https://badgerfit.goatcounter.com"
GC_TOKEN_PATH = os.path.expanduser("~/.config/goatcounter/token")

# The store-link click events, named by data-store-event in
# src/components/StoreBadges.astro. Renaming one there means renaming it here.
# store-testflight is retired but kept, so taps recorded before the App Store
# listing existed do not silently vanish from the history.
STORE_EVENTS = {
    "store-appstore": "App Store",
    "store-play": "Google Play",
    "store-testflight": "TestFlight (retired)",
}

# --- Search Console --------------------------------------------------------

SC_KEY_PATH = os.path.expanduser("~/.config/badger-stats/search-console.json")
SC_PROPERTY = "https://badger.fit/"
SC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def utc_window(days: int) -> tuple[date, date]:
    """The reporting window, anchored to UTC.

    Both APIs work in UTC-ish days while the local machine may be a day behind,
    so building a window from the local date silently drops today and reports a
    confident zero. Anchor to UTC and let the callers pad the end if they need.
    """
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=days - 1), today


def _get_json(url: str, headers: dict, data: bytes | None = None, timeout: int = 30):
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def goatcounter(days: int) -> dict:
    """Page views, top pages, referrers, countries and store taps."""
    try:
        with open(GC_TOKEN_PATH, encoding="utf-8") as fh:
            token = fh.read().strip()
    except FileNotFoundError:
        return {"error": f"No GoatCounter token at {GC_TOKEN_PATH}."}
    if not token or token == "PASTE_TOKEN_HERE":
        return {"error": f"{GC_TOKEN_PATH} still holds the placeholder."}

    start, today = utc_window(days)
    # The end is padded by a day: GoatCounter's returned range runs one day
    # behind the requested one, so asking for exactly today omits it.
    params = {"start": start.isoformat(), "end": (today + timedelta(days=1)).isoformat()}
    headers = {"Authorization": f"Bearer {token}"}

    def call(endpoint: str, **extra):
        query = urllib.parse.urlencode({**params, **extra})
        return _get_json(f"{GC_SITE}/api/v0/{endpoint}?{query}", headers)

    try:
        total = call("stats/total")
        hits = call("stats/hits", limit=100)
        refs = call("stats/toprefs", limit=10)
        locations = call("stats/locations", limit=10)
    except urllib.error.HTTPError as exc:
        return {"error": f"GoatCounter API returned HTTP {exc.code} {exc.reason}."}
    except urllib.error.URLError as exc:
        return {"error": f"GoatCounter unreachable: {exc.reason}"}

    all_hits = hits.get("hits", [])
    return {
        "start": start.isoformat(),
        "end": today.isoformat(),
        "views": total.get("total", 0),
        "daily": [(s["day"], s["daily"]) for s in total.get("stats", [])],
        "pages": sorted(
            ((h.get("path", "?"), h.get("count", 0)) for h in all_hits if not h.get("event")),
            key=lambda r: -r[1],
        ),
        "events": {h.get("path"): h.get("count", 0) for h in all_hits if h.get("event")},
        "referrers": _named(refs.get("stats", [])),
        "countries": _named(locations.get("stats", [])),
    }


def _named(stats: list[dict]) -> list[tuple[str, int]]:
    # GoatCounter returns an empty name for traffic with no referrer. That is
    # not "unknown", it is someone who typed the address, followed a private
    # link, or came from an app that strips the header, so name it as such.
    rows = [(s.get("name") or s.get("id") or "(direct)", s.get("count", 0)) for s in stats]
    return [r for r in rows if r[1] > 0]


def search_console(days: int) -> dict:
    """The search terms people actually used, and where badger.fit ranked.

    This is the one thing analytics cannot tell you: GoatCounter can only say
    "came from Google", never which query. Search Console lags about two days,
    so the window ends earlier than the GoatCounter one on purpose.
    """
    if not os.path.exists(SC_KEY_PATH):
        return {"error": f"No Search Console key at {SC_KEY_PATH}."}

    try:
        from _google_auth import access_token
        token = access_token(SC_KEY_PATH, SC_SCOPE)
    except Exception as exc:  # noqa: BLE001 - any auth failure is the same story here
        return {"error": f"Search Console auth failed: {exc}"}

    start, today = utc_window(days)
    # Google's own data is 2-3 days behind; asking up to today just returns
    # partial days that read as a decline.
    end = today - timedelta(days=2)
    if end < start:
        end = start

    site = urllib.parse.quote(SC_PROPERTY, safe="")
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def query(dimension: str, limit: int = 25) -> list[dict]:
        body = json.dumps({
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": [dimension],
            "rowLimit": limit,
        }).encode()
        return _get_json(url, headers, body).get("rows", [])

    try:
        queries = query("query")
        pages = query("page", limit=15)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        return {"error": f"Search Console returned HTTP {exc.code}: {detail}"}
    except urllib.error.URLError as exc:
        return {"error": f"Search Console unreachable: {exc.reason}"}

    def rows(raw: list[dict]) -> list[dict]:
        return [{
            "key": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "position": r.get("position", 0),
        } for r in raw]

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "clicks": sum(r.get("clicks", 0) for r in queries),
        "impressions": sum(r.get("impressions", 0) for r in queries),
        "queries": rows(queries),
        "pages": rows(pages),
    }
