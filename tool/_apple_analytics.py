"""iOS installs and deletions, from Apple's Analytics Reports API.

Play shows uninstalls; App Store Connect's sales reports show downloads and
nothing about people removing the app. The Analytics Reports API has it, as the
report "App Store Installations and Deletions". It works differently from the
sales reports:

1. A one-time *request* per app asks Apple to start producing reports. ONGOING
   gives a new daily report each day from then on; ONE_TIME_SNAPSHOT gives the
   history Apple still holds. Nothing exists until a request does, and the first
   files take a day or two to appear.
2. A request owns *reports* (one per report type). Pick ours by name.
3. A report owns *instances* (one per day), an instance owns *segments*, and a
   segment carries a signed URL to a gzipped tab-separated file. The URL needs
   no Authorization header.

Creating a request is the only write this module can make, and it only happens
through `ensure_requests()`, which the weekly report never calls: it is the
one-time step `python3 tool/_apple_analytics.py --setup`. Creating a request
needs an Admin key. Reading needs only the reporting key the sales report uses.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import urllib.error
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _stats_sources as src  # noqa: E402

REPORT_NAME = "App Store Installations and Deletions"
# Apple does not publish the day's file for a day or two, and the instance list
# only names days that have one. No lag trimming is needed: a day without an
# instance is simply not in the series.
ACCESS_TYPES = ("ONGOING", "ONE_TIME_SNAPSHOT")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _list_all(url: str, token: str) -> list[dict]:
    """Every record of a paged JSON:API list."""
    out: list[dict] = []
    while url:
        payload = src._get_json(url, _headers(token))
        out.extend(payload.get("data", []))
        url = payload.get("links", {}).get("next")
    return out


def list_requests(token: str) -> list[dict]:
    return _list_all(
        f"{src.ASC_API}/v1/apps/{src.ASC_APP_ID}/analyticsReportRequests?limit=200", token)


def ensure_requests(token: str) -> dict:
    """Create the ONGOING and snapshot requests that do not exist yet.

    The only write in this module. Returns {"created": [...], "existing": [...]}.
    A 403 here means the key is not Admin, which `setup_error` words for Ron.
    """
    # A request Apple stopped for inactivity produces nothing, so it does not
    # count as existing: setup makes a fresh one.
    have = {r["attributes"].get("accessType") for r in list_requests(token)
            if not r["attributes"].get("stoppedDueToInactivity")}
    created, existing = [], []
    for access in ACCESS_TYPES:
        if access in have:
            existing.append(access)
            continue
        body = {"data": {
            "type": "analyticsReportRequests",
            "attributes": {"accessType": access},
            "relationships": {"app": {"data": {"type": "apps", "id": src.ASC_APP_ID}}},
        }}
        src._get_json(f"{src.ASC_API}/v1/analyticsReportRequests", _headers(token),
                      data=json.dumps(body).encode())
        created.append(access)
    return {"created": created, "existing": existing}


def setup_error(exc: urllib.error.HTTPError) -> str:
    if exc.code == 403:
        return ("Apple refused: creating an analytics report request needs an "
                "Admin API key. Ron's one step: in App Store Connect, Users and "
                "Access, Integrations, create a key with the Admin role, then add "
                '"reports_key_path", "reports_key_id" and "reports_issuer_id" for '
                f"it to {src.ASC_CONFIG_PATH}. The key can go back to a reporting "
                "role afterwards: reading needs no Admin.")
    return f"Apple answered HTTP {exc.code}: {exc.read().decode(errors='replace')[:200]}"


def _is_our_report(name: str) -> bool:
    """Apple's name may gain a Standard/Detailed suffix; match on the stem."""
    return (name or "").strip().lower().startswith("app store installation")


def _find_reports(token: str, requests: list[dict]) -> list[dict]:
    """Every installs-and-deletions report, snapshot first, ongoing last.

    Both are read and merged by day, ongoing winning: right after setup the
    ongoing report exists with no days while the snapshot already holds history.
    """
    ordered = sorted(requests, key=lambda r: r["attributes"].get("accessType") == "ONGOING")
    found: list[dict] = []
    for request in ordered:
        reports = _list_all(
            f"{src.ASC_API}/v1/analyticsReportRequests/{request['id']}/reports?limit=200", token)
        found += [r for r in reports if _is_our_report(r["attributes"].get("name"))]
    return found


def _event_kind(row: dict) -> str | None:
    """'install', 'delete' or None for a row of the report.

    Apple's column is "Event" and its values are words ("Install", "Delete");
    matching on a stem keeps this working if the casing or plural changes.
    """
    event = (row.get("Event") or "").strip().lower()
    if event.startswith("install"):
        return "install"
    if event.startswith("delet"):
        return "delete"
    return None


def parse_segment(raw: bytes) -> list[dict]:
    """A segment file: gzipped when Apple says so, tab-separated either way."""
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass  # not gzipped
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def fold(rows: list[dict], start: str = "", end: str = "9999-12-31") -> dict:
    """Counts per kind, and per day, from the report's rows inside [start, end]."""
    daily: dict[str, dict[str, int]] = {}
    territories: dict[str, int] = {}
    for row in rows:
        kind = _event_kind(row)
        if not kind:
            continue
        try:
            n = int(float(row.get("Counts") or 0))
        except (ValueError, OverflowError):
            continue
        day = (row.get("Date") or "")[:10]
        if not day or not start <= day <= end:
            continue
        slot = daily.setdefault(day, {"install": 0, "delete": 0})
        slot[kind] += n
        if kind == "delete":
            territory = row.get("Territory") or "??"
            territories[territory] = territories.get(territory, 0) + n
    return {"daily": daily, "territories": territories}


def installs_and_deletions(days: int) -> dict:
    """Installs and deletions over the window, or {"error": ...} / {"pending": ...}.

    `pending` is not a failure: the request exists but Apple has not written a
    file yet, which is the normal state for the first day or two.
    """
    conf = src._asc_config(reports=True)
    if "error" in conf:
        return conf
    try:
        token = src._asc_token(conf)
        requests = list_requests(token)
        if not requests:
            return {"error": (
                "No analytics report request exists yet, so Apple is producing "
                "nothing. Run `python3 tool/_apple_analytics.py --setup` once "
                "with an Admin API key.")}
        reports = _find_reports(token, requests)
        if not reports:
            return {"pending": "Apple has not produced the installs and deletions "
                               "report yet. A new request takes a day or two."}

        start, today = src.utc_window(days)
        query = urllib.parse.urlencode({"filter[granularity]": "DAILY", "limit": 200})
        # One set of rows per processing day. A day Apple restates, or one both
        # the snapshot and the ongoing report carry, is counted once: the later
        # report in the list wins.
        by_day: dict[str, list[dict]] = {}
        for report in reports:
            instances = _list_all(
                f"{src.ASC_API}/v1/analyticsReports/{report['id']}/instances?{query}", token)
            newest: dict[str, dict] = {}
            for instance in instances:
                day = instance["attributes"].get("processingDate") or ""
                if day and day < start.isoformat():
                    continue
                newest[day] = instance  # list order is oldest first, so last wins
            for day, instance in newest.items():
                rows: list[dict] = []
                segments = _list_all(
                    f"{src.ASC_API}/v1/analyticsReportInstances/{instance['id']}/segments",
                    token)
                for segment in segments:
                    url = segment["attributes"].get("url")
                    if url:
                        rows.extend(parse_segment(src._get_bytes(url, {})))
                by_day[day] = rows

        all_rows = [row for rows in by_day.values() for row in rows]
        if not all_rows:
            return {"pending": "The report exists but holds no days in this window yet."}
        folded = fold(all_rows, start.isoformat(), today.isoformat())
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return {"error": "This App Store Connect key cannot read analytics reports."}
        return {"error": f"App Store analytics returned HTTP {exc.code}."}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"error": f"App Store unreachable: {getattr(exc, 'reason', exc)}"}
    except Exception as exc:  # noqa: BLE001 - one panel must not sink the report
        return {"error": f"App Store analytics failed ({type(exc).__name__})."}

    window = folded["daily"]
    if not window:
        return {"pending": "The report exists but holds no days in this window yet."}
    first = date.fromisoformat(min(window))
    last = date.fromisoformat(max(window))
    # Apple writes a file only for days with data, and the weekly buckets assume
    # consecutive days, so the quiet ones are filled in as zeros.
    series = []
    day = first
    while day <= last:
        series.append((day.isoformat(), window.get(day.isoformat(), {}).get("delete", 0)))
        day += timedelta(days=1)
    return {
        "start": first.isoformat(),
        "end": last.isoformat(),
        "installs": sum(v["install"] for v in window.values()),
        "deletes": sum(v["delete"] for v in window.values()),
        "daily": series,
        "territories": sorted(folded["territories"].items(), key=lambda kv: -kv[1]),
    }


def main() -> None:
    if "--setup" not in sys.argv:
        print(__doc__)
        return
    conf = src._asc_config(reports=True)
    if "error" in conf:
        sys.exit(conf["error"])
    token = src._asc_token(conf)
    try:
        result = ensure_requests(token)
    except urllib.error.HTTPError as exc:
        sys.exit(setup_error(exc))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
