"""Is GoatCounter still counting? Checked against Search Console.

Search Console counts Google clicks on Google's side; GoatCounter sees the
same visits arrive with a Google referrer on ours. The two never match exactly
(content blockers hide some visits from GoatCounter, and the day boundaries
differ), but when Google reports clicks and GoatCounter saw almost none of
them, the counter is broken, not the traffic.

Ron's home IP is on GoatCounter's ignore list, so a test visit from home never
counts. This comparison is the check that needs no visit at all.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
from datetime import date, timedelta

from _stats_sources import (
    GC_SITE, GC_TOKEN_PATH, SC_KEY_PATH, SC_PROPERTY, SC_SCOPE, _get_json,
    utc_window,
)

WINDOW_DAYS = 14
# Search Console finalizes about two days behind; the window ends there.
SC_LAG_DAYS = 2
# Below this many Google clicks a gap is just noise: one blocked visitor
# would read as a third of the traffic missing.
MIN_CLICKS = 4
# GoatCounter may see as few as a third of Google's clicks before it is flagged.
# Blockers and stripped referrers cost some, never two thirds.
MIN_SHARE = 1 / 3


def compare(sc_clicks: int, gc_google: int, start: str, end: str) -> dict:
    """{"flag": bool, "line": str} for the Website panel. Pure; no network."""
    span = f"{start} to {end}"
    if sc_clicks < MIN_CLICKS:
        return {"flag": False,
                "line": f"Tracking check: Google reported {sc_clicks} clicks ({span}), "
                        f"too few to compare with GoatCounter."}
    if gc_google < sc_clicks * MIN_SHARE:
        return {"flag": True,
                "line": f"Tracking check: Google reported {sc_clicks} clicks ({span}) "
                        f"but GoatCounter saw only {gc_google} visits from Google. "
                        f"GoatCounter may have stopped counting."}
    return {"flag": False,
            "line": f"Tracking check: OK. Google reported {sc_clicks} clicks and "
                    f"GoatCounter saw {gc_google} visits from Google ({span})."}


def google_visits(referrers: list[dict]) -> int:
    """Sum GoatCounter referrer rows that are Google (search, app, regional domains)."""
    return sum(r.get("count", 0) for r in referrers
               if "google" in (r.get("name") or "").lower())


def _window(today: date | None = None) -> tuple[date, date]:
    if today is None:
        _, today = utc_window(1)
    end = today - timedelta(days=SC_LAG_DAYS)
    return end - timedelta(days=WINDOW_DAYS - 1), end


def check() -> dict:
    """Fetch both sides and compare. Returns {"error": ...} on any failure."""
    start, end = _window()
    try:
        with open(GC_TOKEN_PATH, encoding="utf-8") as fh:
            gc_token = fh.read().strip()
        from _google_auth import access_token
        sc_token = access_token(SC_KEY_PATH, SC_SCOPE)
    except Exception as exc:  # noqa: BLE001 - one line in the panel, never a crash
        return {"error": f"Tracking check skipped: no credentials ({type(exc).__name__})."}

    try:
        site = urllib.parse.quote(SC_PROPERTY, safe="")
        # No dimensions: the total includes clicks on anonymized queries, which
        # a per-query sum silently drops.
        body = json.dumps({"startDate": start.isoformat(),
                           "endDate": end.isoformat()}).encode()
        sc = _get_json(
            f"https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query",
            {"Authorization": f"Bearer {sc_token}", "Content-Type": "application/json"}, body)
        rows = sc.get("rows", [])
        sc_clicks = int(rows[0].get("clicks", 0)) if rows else 0

        # GoatCounter's returned range runs a day behind the requested one, so
        # the end is padded by a day (same as goatcounter() in _stats_sources).
        query = urllib.parse.urlencode({"start": start.isoformat(),
                                        "end": (end + timedelta(days=1)).isoformat(),
                                        "limit": 100})
        refs = _get_json(f"{GC_SITE}/api/v0/stats/toprefs?{query}",
                         {"Authorization": f"Bearer {gc_token}"})
        gc_google = google_visits(refs.get("stats", []))
    except (urllib.error.URLError, ValueError, KeyError) as exc:
        return {"error": f"Tracking check failed ({type(exc).__name__})."}

    return compare(sc_clicks, gc_google, start.isoformat(), end.isoformat())
