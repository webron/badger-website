"""Search health: is Google and Bing actually reading and indexing badger.fit?

Exists because three problems in one week were visible only inside the consoles:
Google's sitemap sat at "Couldn't fetch" for two months, Bing had not crawled
its sitemap since June, and Bing rejected IndexNow pings. The panel built from
this stays quiet (one OK line per engine) and puts anything wrong first.

Pure analysis functions take already-fetched JSON so tests need no network.
Fetchers never raise: they return {"error": "..."} so one dead API costs one
line, not the report.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone

from _stats_sources import (
    SC_KEY_PATH, SC_PROPERTY, SC_SCOPE, RETRY_STATUSES, _fetch, _get_json,
)

STALE_DAYS = 14
SITEMAP_INDEX = "https://badger.fit/sitemap-index.xml"
BING_KEY_PATH = os.path.expanduser("~/.config/badger-stats/bing-webmaster.key")
BING_API = "https://ssl.bing.com/webmaster/api.svc/json/"
BING_NO_KEY = ("Bing: no API key at ~/.config/badger-stats/bing-webmaster.key "
               "(generate one in Bing Webmaster Tools > Settings > API access)")
INSPECT_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
# Not 404: unlike the stats endpoints, a missing page here is an answer.
INSPECT_RETRY = frozenset({429, 500, 502, 503, 504})


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_google_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_ms_date(raw: str | None) -> datetime | None:
    """Bing's WCF dates: /Date(1315781995040-0700)/ (ms since epoch, offset)."""
    m = re.match(r"/Date\((-?\d+)", raw or "")
    if not m:
        return None
    dt = datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc)
    # .NET's default(DateTime) (year 1) means "never", not a real date.
    return dt if dt.year >= 2000 else None


def _age(dt: datetime | None, now: datetime) -> int | None:
    return None if dt is None else (now - dt).days


# ---- Google: sitemaps ----------------------------------------------------

def analyze_sitemaps(sitemaps: list[dict], now: datetime) -> dict:
    flags, rows, notes = [], [], []
    for s in sitemaps:
        path = s.get("path", "?")
        errors = int(s.get("errors") or 0)
        warnings = int(s.get("warnings") or 0)
        downloaded = parse_google_time(s.get("lastDownloaded"))
        age = _age(downloaded, now)
        contents = ", ".join(f'{c.get("type", "?")} {c.get("submitted", "?")}'
                             for c in s.get("contents", []) or [])
        rows.append({"path": path, "lastSubmitted": s.get("lastSubmitted"),
                     "lastDownloaded": s.get("lastDownloaded"),
                     "isPending": bool(s.get("isPending")), "errors": errors,
                     "warnings": warnings, "contents": contents})
        if downloaded is None and s.get("isPending"):
            # Just (re)submitted: Google has not had its turn yet. Not a fault,
            # but next week's report flags it if it is still unread.
            notes.append(f"Google sitemap {path} is pending its first read "
                         f"(submitted {s.get('lastSubmitted')}).")
        elif downloaded is None:
            flags.append(f"Google sitemap {path} has never been downloaded.")
        elif age > STALE_DAYS:
            flags.append(f"Google sitemap {path} was last downloaded {age} days ago.")
        if errors > 0:
            flags.append(f"Google sitemap {path} reports {errors} error(s).")
    if not sitemaps:
        flags.append("Google has no sitemap submitted for this property.")
    return {"sitemaps": rows, "flags": flags, "notes": notes}


# ---- Google: URL inspection ----------------------------------------------

def summarize_inspections(results: dict[str, dict]) -> dict:
    """results maps URL -> inspect response (or {"error": ...})."""
    states: Counter = Counter()
    not_indexed, failed = [], []
    for url, res in results.items():
        if "error" in res:
            failed.append((url, res["error"]))
            continue
        idx = (res.get("inspectionResult") or {}).get("indexStatusResult") or {}
        verdict = idx.get("verdict", "UNKNOWN")
        state = idx.get("coverageState") or verdict
        states[state] += 1
        if verdict != "PASS":
            not_indexed.append((url, state))
    flags = []
    if not_indexed:
        flags.append(f"{len(not_indexed)} URL(s) not indexed by Google.")
    if failed:
        flags.append(f"{len(failed)} URL(s) could not be inspected.")
    return {"total": len(results), "states": dict(states),
            "not_indexed": not_indexed, "failed": failed, "flags": flags}


# ---- Bing ------------------------------------------------------------------

def analyze_bing(feeds: list[dict], crawl: list[dict], now: datetime) -> dict:
    flags, notes = [], []
    feed_rows = []
    for f in feeds:
        crawled = parse_ms_date(f.get("LastCrawled"))
        submitted = parse_ms_date(f.get("Submitted"))
        age = _age(crawled, now)
        url = f.get("Url", "?")
        # Right after a resubmit Bing returns a placeholder: not accessible,
        # size 0, type NA, LastCrawled == Submitted. Not a fault yet.
        placeholder = (crawled is not None and submitted is not None
                       and abs((crawled - submitted).total_seconds()) <= 60
                       and not f.get("FileSize") and f.get("Type") == "NA")
        if placeholder:
            feed_rows.append({"url": url, "status": f.get("Status", "?"),
                              "age": None, "urls": f.get("UrlCount")})
            sub_age = _age(submitted, now)
            if sub_age > STALE_DAYS:
                flags.append(f"Bing sitemap {url} has not been fetched since it "
                             f"was submitted {sub_age} days ago.")
            else:
                notes.append(f"Bing sitemap {url}: pending first fetch "
                             f"(submitted {submitted.date().isoformat()})")
            continue
        feed_rows.append({"url": f.get("Url", "?"), "status": f.get("Status", "?"),
                          "age": age, "urls": f.get("UrlCount")})
        if crawled is None:
            flags.append(f'Bing sitemap {f.get("Url", "?")} has no crawl date.')
        elif age > STALE_DAYS:
            flags.append(f'Bing sitemap {f.get("Url", "?")} was last crawled {age} days ago.')
        status = f.get("Status")
        if status and status != "Success":
            flags.append(f'Bing sitemap {f.get("Url", "?")} status: {status}.')
    if not feeds:
        flags.append("Bing has no sitemap/feed for this site.")
    latest = None
    dated = [(parse_ms_date(c.get("Date")), c) for c in crawl]
    dated = [(d, c) for d, c in dated if d]
    if dated:
        d, c = max(dated, key=lambda t: t[0])
        latest = {"date": d.date().isoformat(), "crawled": c.get("CrawledPages", 0),
                  "errors": c.get("CrawlErrors", 0), "in_index": c.get("InIndex")}
    return {"feeds": feed_rows, "crawl": latest, "flags": flags, "notes": notes}


# ---- fetchers ---------------------------------------------------------------

def _sitemap_urls(index_url: str = SITEMAP_INDEX) -> list[str]:
    def read(url: str) -> ET.Element:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return ET.fromstring(resp.read())

    def locs(root: ET.Element) -> list[str]:
        return [e.text.strip() for e in root.iter() if e.tag.endswith("}loc") and e.text]

    root = read(index_url)
    if root.tag.endswith("sitemapindex"):
        urls: list[str] = []
        for child in locs(root):
            urls += locs(read(child))
        return urls
    return locs(root)


def google_health(now: datetime | None = None, get_json=_get_json,
                  token_fn=None, urls_fn=_sitemap_urls, sleep=time.sleep) -> dict:
    now = now or now_utc()
    if not os.path.exists(SC_KEY_PATH):
        return {"error": f"No Search Console key at {SC_KEY_PATH}."}
    try:
        if token_fn is None:
            from _google_auth import access_token
            token_fn = access_token
        token = token_fn(SC_KEY_PATH, SC_SCOPE)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Google auth failed: {exc}"}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    site = urllib.parse.quote(SC_PROPERTY, safe="")
    out: dict = {}
    try:
        listed = get_json(f"https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps",
                          headers).get("sitemap", [])
        out["sitemaps"] = analyze_sitemaps(listed, now)
    except Exception as exc:  # noqa: BLE001
        out["sitemaps"] = {"error": f"Google sitemaps failed: {_why(exc)}"}
    try:
        urls = urls_fn()
    except Exception as exc:  # noqa: BLE001
        out["inspection"] = {"error": f"Could not read the live sitemap: {_why(exc)}"}
        return out
    results = {}
    for u in urls:
        body = json.dumps({"inspectionUrl": u, "siteUrl": SC_PROPERTY}).encode()
        try:
            results[u] = _fetch(INSPECT_URL, headers, body, 30, json.load, INSPECT_RETRY)
        except Exception as exc:  # noqa: BLE001
            results[u] = {"error": _why(exc)}
        sleep(0.3)
    if results and all("error" in r for r in results.values()):
        first = next(iter(results.values()))["error"]
        out["inspection"] = {"error": f"URL inspection failed for every URL: {first}"}
    else:
        out["inspection"] = summarize_inspections(results)
    return out


def _scrub(text: str, key: str | None = None) -> str:
    if key:
        for k in (key, urllib.parse.quote(key)):
            text = text.replace(k, "***")
    return re.sub(r"apikey=[^&\s]+", "apikey=***", text, flags=re.I)


def _why(exc: Exception, key: str | None = None) -> str:
    return _scrub(_why_raw(exc), key)


def _why_raw(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = exc.read().decode(errors="replace")[:150]
        except Exception:  # noqa: BLE001
            detail = ""
        return f"HTTP {exc.code} {detail}".strip()
    return f"{type(exc).__name__}: {exc}"[:200]


def bing_health(now: datetime | None = None, key_path: str = BING_KEY_PATH,
                get_json=_get_json) -> dict:
    now = now or now_utc()
    try:
        with open(key_path, encoding="utf-8") as fh:
            key = fh.readline().strip()
    except OSError:
        return {"no_key": BING_NO_KEY}
    if not key:
        return {"no_key": BING_NO_KEY}
    site = urllib.parse.quote(SC_PROPERTY, safe="")

    def call(method: str) -> list[dict]:
        url = f"{BING_API}{method}?siteUrl={site}&apikey={urllib.parse.quote(key)}"
        data = get_json(url, {"Content-Type": "application/json; charset=utf-8"})
        return data.get("d", []) or []

    try:
        feeds = call("GetFeeds")
        crawl = call("GetCrawlStats")
    except Exception as exc:  # noqa: BLE001
        # The key is in the URL; _why scrubs it.
        return {"error": f"Bing API failed: {_why(exc, key)}"}
    return analyze_bing(feeds, crawl, now)
