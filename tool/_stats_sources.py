"""Fetch badger.fit's numbers from every source that has them.

Each source returns plain dicts and lists, so the callers (a text summary and an
HTML report) share one definition of what a figure means. Four places have
numbers about Badger - the website, Google search, Play and the App Store - and
each is a fetcher here rather than anything the renderers know about.

Every source is allowed to be absent. A missing credential, a revoked token or a
new property with no data yet returns an `error` or an empty list rather than
raising, because a weekly report that dies on one bad source tells you less than
one that prints the rest and says which part is missing.
"""

from __future__ import annotations

import json
import os
import time
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

# --- App Store --------------------------------------------------------------

ASC_APP_ID = "6782743069"
ASC_BUNDLE_ID = "fit.badger.app"
ASC_API = "https://api.appstoreconnect.apple.com"
# The key fastlane already publishes with, and the dotenv holding its two ids.
# Reusing them means no second App Store credential to create, rotate or leak.
ASC_KEY_PATH = "/Users/ron/Development/badger-fit/ios/fastlane/asc_api_key.p8"
ASC_ENV_PATH = "/Users/ron/Development/badger-fit/ios/fastlane/.env"
# The one thing that lives nowhere else. The vendor number is not in any API:
# App Store Connect shows it under Payments and Financial Reports, and the
# sales report endpoint refuses to answer without it.
ASC_CONFIG_PATH = os.path.expanduser("~/.config/badger-stats/app-store.json")
# Apple publishes a day's sales report the following day. Asking for a date it
# has not written yet returns the same 404 as a genuinely quiet day, so the
# most recent days are dropped rather than drawn as a collapse.
ASC_REPORT_LAG_DAYS = 2
# Badger's first day on the App Store. Every date before it is a guaranteed 404,
# and asking anyway costs thirty round trips a run for no number.
ASC_FIRST_RELEASE = date(2026, 9, 9)
# A 404 from the sales endpoint is its ordinary answer for a day with nothing
# in it, not a blip, so it must not be retried the way GoatCounter's is.
SALES_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# The public storefront record. No key, no rate limit worth worrying about, and
# it carries the two figures the authenticated API does not expose at all: the
# lifetime star average and how many people left one.
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"



def utc_window(days: int) -> tuple[date, date]:
    """The reporting window, anchored to UTC.

    Both APIs work in UTC-ish days while the local machine may be a day behind,
    so building a window from the local date silently drops today and reports a
    confident zero. Anchor to UTC and let the callers pad the end if they need.
    """
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=days - 1), today


# Statuses worth trying again. A weekly report runs once, unattended, so a
# one-second blip at the wrong moment blanks a whole section until the next
# Monday. 429 is GoatCounter's rate limiter (4 requests a second, and the
# GoatCounter fetcher makes four in a row). 5xx is the far side having a bad
# moment. 404 is here because it was observed once on 2026-09-07 from an
# endpoint that answered normally minutes later, which a real missing resource
# does not do. Everything else - 400, 401, 403 - is a configuration answer, and
# retrying it only delays a message the reader needs to see.
RETRY_STATUSES = frozenset({404, 429, 500, 502, 503, 504})
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 1.5  # seconds, doubled per attempt


def _retry_after(exc: urllib.error.HTTPError, fallback: float) -> float:
    """How long to wait, preferring what the server asked for."""
    for header in ("Retry-After", "X-Rate-Limit-Reset"):
        raw = exc.headers.get(header) if exc.headers else None
        if raw and raw.strip().isdigit():
            # Cap it: a server asking for a coffee break is not worth blocking
            # the rest of the report for.
            return min(float(raw.strip()), 30.0)
    return fallback


def _fetch(url: str, headers: dict, data: bytes | None, timeout: int,
           read, retry_statuses: frozenset):
    """Make the request, retrying the failures that are not answers.

    Raises the last error once the attempts run out, so every caller's existing
    error handling still reports the real reason. `retry_statuses` is a
    parameter because 404 means different things to different endpoints: a blip
    from GoatCounter, but the ordinary answer for a day the App Store had no
    sales, where retrying it would sleep through every quiet day in the window.
    """
    delay = RETRY_BACKOFF
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return read(resp)
        except urllib.error.HTTPError as exc:
            if attempt == RETRY_ATTEMPTS or exc.code not in retry_statuses:
                raise
            wait = _retry_after(exc, delay)
        except (urllib.error.URLError, TimeoutError):
            # A refused connection or a timed-out one. URLError is the parent of
            # HTTPError, so this arm only sees the transport failures the arm
            # above did not already claim. A bare TimeoutError is NOT a URLError
            # and has to be named, or an unattended run dies on a slow socket.
            if attempt == RETRY_ATTEMPTS:
                raise
            wait = delay
        time.sleep(wait)
        delay *= 2
    raise AssertionError("unreachable: the loop returns or raises")


def _get_json(url: str, headers: dict, data: bytes | None = None, timeout: int = 30):
    """GET/POST JSON, retrying the failures that are not answers."""
    return _fetch(url, headers, data, timeout, json.load, RETRY_STATUSES)


def _get_bytes(url: str, headers: dict, timeout: int = 60,
               retry_statuses: frozenset = RETRY_STATUSES) -> bytes:
    """GET a binary body, with the same retry policy."""
    return _fetch(url, headers, None, timeout, lambda resp: resp.read(), retry_statuses)


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
    # GoatCounter counts events in `total` alongside real page views, so a store
    # badge tap inflates the pageview figure. `total_events` is the authoritative
    # event count; the per-day split has to be subtracted row by row, because the
    # daily series carries the same mixture.
    event_hits = [h for h in all_hits if h.get("event")]
    events_by_day: dict[str, int] = {}
    for hit in event_hits:
        for day in hit.get("stats", []):
            events_by_day[day["day"]] = events_by_day.get(day["day"], 0) + day.get("daily", 0)

    return {
        "start": start.isoformat(),
        "end": today.isoformat(),
        "views": max(total.get("total", 0) - total.get("total_events", 0), 0),
        "events_total": total.get("total_events", 0),
        "daily": [
            (s["day"], max(s["daily"] - events_by_day.get(s["day"], 0), 0))
            for s in total.get("stats", [])
        ],
        "pages": sorted(
            ((h.get("path", "?"), h.get("count", 0)) for h in all_hits if not h.get("event")),
            key=lambda r: -r[1],
        ),
        "events": {h.get("path"): h.get("count", 0) for h in event_hits},
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


# --- App Store ---------------------------------------------------------------


def _asc_config() -> dict:
    """Where the App Store credentials are, and which vendor account to read.

    The key ids come from fastlane's dotenv so there is one place to change
    them; the optional JSON overrides any of it and is the only home the vendor
    number has.
    """
    conf = {"key_path": ASC_KEY_PATH, "key_id": "", "issuer_id": "", "vendor_number": ""}

    try:
        with open(ASC_ENV_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "ASC_KEY_ID":
                    conf["key_id"] = value.strip()
                elif name.strip() == "ASC_ISSUER_ID":
                    conf["issuer_id"] = value.strip()
    except OSError:
        pass

    if os.path.exists(ASC_CONFIG_PATH):
        try:
            with open(ASC_CONFIG_PATH, encoding="utf-8") as fh:
                conf.update({k: v for k, v in json.load(fh).items() if v})
        except (OSError, ValueError) as exc:
            return {"error": f"{ASC_CONFIG_PATH} could not be read: {exc}"}

    if not conf["key_id"] or not conf["issuer_id"]:
        return {"error": f"No ASC_KEY_ID / ASC_ISSUER_ID in {ASC_ENV_PATH}."}
    if not os.path.exists(conf["key_path"]):
        return {"error": f"No App Store Connect key at {conf['key_path']}."}
    return conf


def _asc_token(conf: dict) -> str:
    from _apple_auth import token
    return token(conf["key_path"], conf["key_id"], conf["issuer_id"])


def _sales_report(day: date, vendor: str, token: str) -> list[dict] | None:
    """One day of sales, or None when Apple has nothing for that date.

    The reports come back as a gzipped tab-separated file, and a date with no
    sales - or one Apple has not compiled yet - is a 404 rather than an empty
    file. The caller decides which of those it is from how recent the day is.
    """
    import gzip
    import io as _io

    query = urllib.parse.urlencode({
        "filter[frequency]": "DAILY",
        "filter[reportDate]": day.isoformat(),
        "filter[reportSubType]": "SUMMARY",
        "filter[reportType]": "SALES",
        "filter[vendorNumber]": vendor,
    })
    try:
        raw = gzip.decompress(_get_bytes(
            f"{ASC_API}/v1/salesReports?{query}",
            {"Authorization": f"Bearer {token}", "Accept": "application/a-gzip"},
            retry_statuses=SALES_RETRY_STATUSES,
        ))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise

    import csv
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(_io.StringIO(text), delimiter="\t"))


def _units(row: dict) -> int:
    try:
        return int(row.get("Units") or 0)
    except ValueError:
        return 0


def _is_update(row: dict) -> bool:
    """Apple's product type identifiers for an update all start with 7.

    Everything else a free app can produce - 1F, 1T, 1E and their universal
    variants - is someone getting the app, whether for the first time or again
    on a new phone. The summary report does not split those two, so the figure
    is named "downloads" rather than "new users".
    """
    return str(row.get("Product Type Identifier") or "").startswith("7")


def app_store(days: int) -> dict:
    """Downloads and updates from the App Store's daily sales reports."""
    conf = _asc_config()
    if "error" in conf:
        return conf
    if not conf["vendor_number"]:
        return {"error": (
            "No vendor number. It is the one figure with no API: App Store "
            "Connect shows it under Payments and Financial Reports. Put it in "
            f'{ASC_CONFIG_PATH} as {{"vendor_number": "..."}}.')}

    try:
        token = _asc_token(conf)
    except Exception as exc:  # noqa: BLE001 - any auth failure reads the same here
        return {"error": f"App Store auth failed: {exc}"}

    # Ask for the lag days on top of the window. The most recent ones get
    # dropped below because Apple has not compiled them, and without the
    # padding the series comes back short: the weekly buckets then silently
    # lose a whole comparison week while the page header still claims to be
    # measuring against it.
    start, today = utc_window(days + ASC_REPORT_LAG_DAYS)
    start = max(start, ASC_FIRST_RELEASE)
    # Everything is kept per day and folded up only after the window is
    # trimmed, so the totals, the countries and the devices all describe the
    # same days the sparkline draws.
    per_day: list[dict] = []
    unpublished: list[str] = []

    day = start
    while day <= today:
        try:
            rows = _sales_report(day, conf["vendor_number"], token)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:200]
            return {"error": f"App Store sales report returned HTTP {exc.code}: {detail}"}
        except (urllib.error.URLError, TimeoutError) as exc:
            # TimeoutError is not a URLError, and an uncaught one here would
            # take the whole report down, panels that already succeeded and all.
            reason = getattr(exc, "reason", exc)
            return {"error": f"App Store unreachable: {reason}"}

        entry = {"day": day.isoformat(), "downloads": 0, "updates": 0,
                 "countries": {}, "devices": {}}
        if rows is None:
            # Either a quiet day or one Apple has not written yet. Record it and
            # let the trim below decide, so a real zero still shows as a zero.
            unpublished.append(entry["day"])
        else:
            for row in rows:
                n = _units(row)
                if n <= 0:
                    continue
                if _is_update(row):
                    entry["updates"] += n
                    continue
                entry["downloads"] += n
                country = row.get("Country Code") or "??"
                entry["countries"][country] = entry["countries"].get(country, 0) + n
                device = row.get("Device") or "Unknown"
                entry["devices"][device] = entry["devices"].get(device, 0) + n
        per_day.append(entry)
        day += timedelta(days=1)

    # Drop the trailing days Apple has plausibly not compiled yet. Older gaps
    # stay in as zeros, because a quiet week must not be able to hide itself by
    # shortening the window.
    horizon = (today - timedelta(days=ASC_REPORT_LAG_DAYS)).isoformat()
    pending = 0
    while per_day and per_day[-1]["day"] in unpublished and per_day[-1]["day"] > horizon:
        per_day.pop()
        pending += 1

    # Now cut back to the window that was actually asked for.
    per_day = per_day[-days:]

    by_country: dict[str, int] = {}
    by_device: dict[str, int] = {}
    for entry in per_day:
        for name, n in entry["countries"].items():
            by_country[name] = by_country.get(name, 0) + n
        for name, n in entry["devices"].items():
            by_device[name] = by_device.get(name, 0) + n

    return {
        "start": per_day[0]["day"] if per_day else start.isoformat(),
        "end": per_day[-1]["day"] if per_day else today.isoformat(),
        "downloads": sum(e["downloads"] for e in per_day),
        "updates": sum(e["updates"] for e in per_day),
        "daily": [(e["day"], e["downloads"]) for e in per_day],
        "countries": sorted(by_country.items(), key=lambda kv: -kv[1]),
        "devices": sorted(by_device.items(), key=lambda kv: -kv[1]),
        "pending_days": pending,
    }


def app_store_reviews(days: int, limit: int = 200) -> dict:
    """Reviews left in the window, newest first.

    Apple has no date filter here, so this walks the newest reviews and stops
    at the first one older than the window. On an app this size that is one
    page; the limit is there so a sudden pile of reviews cannot turn a weekly
    report into an unbounded crawl.
    """
    conf = _asc_config()
    if "error" in conf:
        return conf
    try:
        token = _asc_token(conf)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"App Store auth failed: {exc}"}

    start, _ = utc_window(days)
    headers = {"Authorization": f"Bearer {token}"}
    url = (f"{ASC_API}/v1/apps/{ASC_APP_ID}/customerReviews"
           "?sort=-createdDate&limit=50")

    reviews: list[dict] = []
    total = 0
    try:
        while url and len(reviews) < limit:
            payload = _get_json(url, headers)
            total = payload.get("meta", {}).get("paging", {}).get("total", total)
            stop = False
            for item in payload.get("data", []):
                attrs = item.get("attributes", {})
                created = (attrs.get("createdDate") or "")[:10]
                if created and created < start.isoformat():
                    stop = True
                    break
                reviews.append({
                    "date": created,
                    "rating": attrs.get("rating"),
                    "title": attrs.get("title") or "",
                    "body": attrs.get("body") or "",
                    "reviewer": attrs.get("reviewerNickname") or "",
                    "territory": attrs.get("territory") or "",
                })
            url = None if stop else payload.get("links", {}).get("next")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        return {"error": f"App Store reviews returned HTTP {exc.code}: {detail}"}
    except urllib.error.URLError as exc:
        return {"error": f"App Store reviews unreachable: {exc.reason}"}

    rated = [r["rating"] for r in reviews if isinstance(r.get("rating"), int)]
    return {
        "start": start.isoformat(),
        "new": len(reviews),
        "lifetime": total,
        "average": round(sum(rated) / len(rated), 2) if rated else None,
        "reviews": reviews,
    }


def app_store_listing(country: str = "us") -> dict:
    """The live storefront record: version, release date, stars.

    Star ratings are not in the App Store Connect API at all. The public lookup
    endpoint has them, needs no credential, and is the same data the store page
    shows, so it is the honest source rather than a workaround.
    """
    query = urllib.parse.urlencode({"id": ASC_APP_ID, "country": country})
    try:
        payload = _get_json(f"{ITUNES_LOOKUP}?{query}", {})
    except urllib.error.HTTPError as exc:
        return {"error": f"App Store lookup returned HTTP {exc.code}."}
    except urllib.error.URLError as exc:
        return {"error": f"App Store lookup unreachable: {exc.reason}"}

    results = payload.get("results") or []
    if not results:
        return {"error": "The App Store lookup returned no record for this app."}
    app = results[0]
    return {
        "version": app.get("version"),
        "released": (app.get("currentVersionReleaseDate") or "")[:10],
        "rating": app.get("averageUserRating") or 0,
        "ratings": app.get("userRatingCount") or 0,
        "url": app.get("trackViewUrl", ""),
        "minimum_os": app.get("minimumOsVersion", ""),
    }
