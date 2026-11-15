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
import math
import urllib.error
import urllib.parse
from datetime import date, timedelta

from _stats_sources import (
    GC_SITE, GC_TOKEN_PATH, SC_KEY_PATH, SC_PROPERTY, SC_SCOPE, _get_json,
    utc_window,
)

# ~1 Google click a day: 14 days often holds too few clicks to judge, 28 holds
# ~20. The cost is latency: the comparison flags a counter dead for most of
# the window, so the zero-days rule below covers a sudden outage.
WINDOW_DAYS = 28
# A run of this many complete UTC days with no page views at all is flagged.
# At ~8 views a day a healthy counter has about a 1-in-9-million chance of it.
ZERO_RUN_DAYS = 2
# Search Console finalizes about two days behind; the window ends there.
SC_LAG_DAYS = 2
# GoatCounter's Google visits are treated as a Poisson draw around a share of
# Google's clicks. Live data runs above 100% (GoatCounter's "Google" also counts
# the Google app and Discover); half is the deliberately low assumption, so a
# healthy week has to be very unlucky to be flagged.
EXPECTED_SHARE = 0.5
# Flag only when a count this low would happen less than 1 week in 100 if
# GoatCounter were healthy. At ~1 click a day that means: 10+ clicks and zero
# Google visits, or 14 clicks and at most one.
ALARM_P = 0.01


def poisson_cdf(k: int, lam: float) -> float:
    """P(X <= k) for X ~ Poisson(lam). Stdlib only."""
    term = total = math.exp(-lam)
    for i in range(1, k + 1):
        term *= lam / i
        total += term
    return total


def compare(sc_clicks: int, gc_google: int, start: str, end: str) -> dict:
    """{"flag": bool, "line": str} for the Website panel. Pure; no network."""
    span = f"{start} to {end}"
    lam = sc_clicks * EXPECTED_SHARE
    if poisson_cdf(0, lam) >= ALARM_P:
        return {"flag": False,
                "line": f"Tracking check: Google reported {sc_clicks} clicks ({span}), "
                        f"too few to compare with GoatCounter."}
    if poisson_cdf(gc_google, lam) < ALARM_P:
        return {"flag": True,
                "line": f"Tracking check: Google reported {sc_clicks} clicks ({span}) "
                        f"but GoatCounter saw only {gc_google} visits from Google. "
                        f"GoatCounter may have stopped counting."}
    return {"flag": False,
            "line": f"Tracking check: OK. Google reported {sc_clicks} clicks and "
                    f"GoatCounter saw {gc_google} visits from Google ({span})."}


def zero_run(daily: list[tuple[str, int]]) -> list[str]:
    """Days in the latest run of zero page views, if it is ZERO_RUN_DAYS or longer.

    `daily` is GoatCounter's (day, views) series oldest first; the last entry is
    today, still in progress, so it is left out.
    """
    run: list[str] = []
    for day, views in daily[:-1]:
        run = run + [day] if views == 0 else []
    return run if len(run) >= ZERO_RUN_DAYS else []


def zero_run_line(days: list[str]) -> str:
    return (f"GoatCounter recorded no page views from {days[0]} to {days[-1]} (UTC). "
            f"Either nobody visited or the counter is down. A phone visit on mobile "
            f"data (Ron's home IP is ignored) shows which.")


def is_google_search(name: str | None) -> bool:
    """GoatCounter's "Google" row, regional google.* domains, the Google app.

    Gmail, Docs and Translate also live on google.com but are not search, and
    counting them could hide a partial loss.
    """
    n = (name or "").lower()
    if n == "google" or "googlequicksearchbox" in n:
        return True
    host = n.split("://")[-1].split("/")[0]
    return host.startswith(("google.", "www.google."))


def google_visits(referrers: list[dict]) -> int:
    """Sum GoatCounter referrer rows that are Google search."""
    return sum(r.get("count", 0) for r in referrers if is_google_search(r.get("name")))


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
        return {"error": f"Tracking check skipped: could not load the GoatCounter token or get a Search Console token ({type(exc).__name__})."}

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
