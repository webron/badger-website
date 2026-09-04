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

# --- Play Console ----------------------------------------------------------

PLAY_KEY_PATH = os.path.expanduser("~/.config/badger-stats/play-reporter.json")
PLAY_PACKAGE = "fit.badger.app"
# Google Play writes the bulk reports into a bucket it owns, not one of ours.
# The id is the developer account, visible in Play Console under Download
# reports; read access is granted there, not through project IAM.
PLAY_BUCKET = "pubsite_prod_7099366008570025106"
PLAY_SCOPE = "https://www.googleapis.com/auth/devstorage.read_only"
PLAY_REPORTING_SCOPE = "https://www.googleapis.com/auth/playdeveloperreporting"

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


def _gcs_object(bucket: str, name: str, token: str) -> bytes:
    """Download one object through the JSON API.

    google-cloud-storage would be four more packages for one GET, and this runs
    on a timer where a dependency that rots is worse than a few lines here.
    """
    url = (f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/"
           f"{urllib.parse.quote(name, safe='')}?alt=media")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _play_csv(raw: bytes) -> list[dict]:
    """Parse one Play bulk report.

    These files are UTF-16 with a BOM, not UTF-8. Decoding them as UTF-8 either
    throws or yields text full of NUL bytes that silently matches nothing, so
    the encoding is named explicitly rather than guessed.
    """
    import csv
    import io as _io

    text = raw.decode("utf-16")
    return list(csv.DictReader(_io.StringIO(text)))


def play(days: int) -> dict:
    """Installs, uninstalls and where store visits came from.

    Play's bulk reports are monthly CSVs and lag a few days behind, which is why
    this reads the current month and the one before it and then filters, rather
    than trusting either file to cover the window on its own.
    """
    if not os.path.exists(PLAY_KEY_PATH):
        return {"error": f"No Play reporting key at {PLAY_KEY_PATH}."}

    try:
        from _google_auth import access_token
        token = access_token(PLAY_KEY_PATH, PLAY_SCOPE)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Play auth failed: {exc}"}

    start, today = utc_window(days)
    months = sorted({d.strftime("%Y%m") for d in (start, today)})

    installs: list[dict] = []
    sources: list[dict] = []
    missing = []
    for month in months:
        for kind, sink in (
            (f"stats/installs/installs_{PLAY_PACKAGE}_{month}_overview.csv", installs),
            (f"stats/store_performance/total_store_performance_{PLAY_PACKAGE}_{month}_traffic_source.csv", sources),
        ):
            try:
                sink.extend(_play_csv(_gcs_object(PLAY_BUCKET, kind, token)))
            except urllib.error.HTTPError as exc:
                if exc.code == 403:
                    return {"error": (
                        "Play reporting key cannot read the bulk reports. Grant "
                        "'View app information and download bulk reports' to "
                        "play-reporter@badger-1040f.iam.gserviceaccount.com in "
                        "Play Console, Users and permissions.")}
                # A month with no file yet is normal early in a month, not an error.
                missing.append(kind.rsplit("/", 1)[-1])
            except urllib.error.URLError as exc:
                return {"error": f"Play reports unreachable: {exc.reason}"}

    def in_window(row: dict) -> bool:
        day = row.get("Date", "")
        return bool(day) and start.isoformat() <= day <= today.isoformat()

    rows = [r for r in installs if in_window(r)]

    def total(column: str) -> int:
        return sum(int(r.get(column) or 0) for r in rows)

    by_source: dict[str, int] = {}
    for row in sources:
        if not in_window(row):
            continue
        key = row.get("Traffic source") or "(unknown)"
        by_source[key] = by_source.get(key, 0) + int(row.get("Total store acquisitions") or 0)

    # "Active Device Installs" is a running figure, not a daily one, so the
    # newest row is the current number rather than anything summed.
    active = int(rows[-1].get("Active Device Installs") or 0) if rows else 0

    return {
        "start": start.isoformat(),
        "end": rows[-1]["Date"] if rows else today.isoformat(),
        "installs": total("Daily Device Installs"),
        "uninstalls": total("Daily Device Uninstalls"),
        "active": active,
        "daily": [(r["Date"], int(r.get("Daily Device Installs") or 0)) for r in rows],
        "sources": sorted(by_source.items(), key=lambda kv: -kv[1]),
        "missing": missing,
    }


def play_quality() -> dict:
    """Crash and ANR rates, the warning light rather than a growth figure.

    This comes from the Play Developer Reporting API, which the publishing
    service account can already read, so it needs no extra grant.
    """
    key = "/Users/ron/Development/badger-fit/tools/play_publish/play-service-account.json"
    if not os.path.exists(key):
        return {"error": "Play publishing key not found; cannot read quality metrics."}
    try:
        from _google_auth import access_token
        token = access_token(key, PLAY_REPORTING_SCOPE)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Play reporting auth failed: {exc}"}

    base = f"https://playdeveloperreporting.googleapis.com/v1beta1/apps/{PLAY_PACKAGE}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # The API rejects a timeline without explicit bounds AND rejects an end date
    # past its own freshness, which moves. So ask each metric set how fresh it
    # is and use that, rather than hardcoding a guess that breaks the week Play
    # runs late.
    start, _ = utc_window(31)

    def date_obj(d):
        return {"year": d.year, "month": d.month, "day": d.day}

    def freshest(metric_set: str):
        info = _get_json(f"{base}/{metric_set}", headers)
        for entry in info.get("freshnessInfo", {}).get("freshnesses", []):
            if entry.get("aggregationPeriod") == "DAILY":
                return entry.get("latestEndTime", {})
        return None

    out: dict = {}
    problems = []
    for label, metric_set, metric in (
        ("crash rate", "crashRateMetricSet", "crashRate7dUserWeighted"),
        ("ANR rate", "anrRateMetricSet", "anrRate7dUserWeighted"),
    ):
        try:
            end_time = freshest(metric_set)
        except urllib.error.HTTPError as exc:
            problems.append(f"{label}: HTTP {exc.code} reading freshness")
            continue
        if not end_time:
            continue

        body = json.dumps({
            "metrics": [metric],
            "dimensions": [],
            "timelineSpec": {
                "aggregationPeriod": "DAILY",
                "startTime": date_obj(start),
                "endTime": {k: end_time[k] for k in ("year", "month", "day") if k in end_time},
            },
            "pageSize": 60,
        }).encode()
        try:
            rows = _get_json(f"{base}/{metric_set}:query", headers, body).get("rows", [])
        except urllib.error.HTTPError as exc:
            problems.append(f"{label}: HTTP {exc.code} {exc.read().decode(errors='replace')[:120]}")
            continue
        values = [r["metrics"][0]["decimalValue"]["value"] for r in rows
                  if r.get("metrics") and r["metrics"][0].get("decimalValue")]
        if values:
            out[label] = float(values[-1])

    if out:
        return out
    # Distinguish "the call failed" from "the app is too quiet to have a rate".
    # Conflating the two is how a broken query gets read as a healthy app.
    if problems:
        return {"error": "; ".join(problems)}
    return {"empty": "No crash or ANR rate yet. Play needs a minimum number of "
                     "sessions before it reports one."}
