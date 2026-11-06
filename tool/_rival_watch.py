"""Rival watcher: what the apps Badger is compared with changed this week.

Read-only. It makes GET requests to public pages and Apple's public lookup
endpoint, a handful per week, and posts nothing anywhere. It keeps two things
outside the repo, in `~/Development/badger-artifacts/site-stats/rivals/`:

  latest.json        the snapshot from the last fetch
  last-changes.json  what differed between the last two fetches, and the
                     ratings figures, which is all the weekly report reads
  history.md         one section per fetch, newest last, so past weeks stay
                     readable after weekly.html is overwritten

weekly-report.py calls `panel()`. That refreshes the snapshot when it is more
than six days old, so a normal weekly run fetches once and a manual re-run the
same day only re-reads `last-changes.json`. It never raises: a source that
cannot answer is named in the panel, the previous data for it is kept, and the
rest still render.

Run it alone to see the result as text:

    python3 tool/_rival_watch.py            # refresh if stale, print changes
    python3 tool/_rival_watch.py --force    # fetch now

Watched, per rival: the App Store record (version, release notes, price,
description, rating), the Google Play listing (title, description, rating), and
one or two public pages (home or pricing, a support page). Add a rival or a page
by editing RIVALS. A package name or app id that stops resolving shows up in the
panel as an error instead of silently going quiet.
"""

from __future__ import annotations

import difflib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

STATE_DIR = Path.home() / "Development/badger-artifacts/site-stats/rivals"
STALE_AFTER_DAYS = 6
USER_AGENT = "badger-fit-rival-watch/1 (weekly, read-only; https://badger.fit)"
TIMEOUT = 25

# Ids and packages checked 2026-11-05. Apple's lookup is the US storefront.
RIVALS: dict[str, dict] = {
    "StrongLifts": {
        "ios": "488580022",
        "play": "com.stronglifts.app",
        "pages": [
            "https://stronglifts.com/app/",
            "https://support.stronglifts.com/article/148-power-pack",
        ],
    },
    "Strong": {
        "ios": "464254577",
        "play": "io.strongapp.strong",
        "pages": ["https://www.strong.app/"],
    },
    "Hevy": {
        "ios": "1458862350",
        "play": "com.hevy",
        "pages": ["https://hevy.com/pricing", "https://www.hevyapp.com/"],
    },
    "Boostcamp": {
        "ios": "1529354455",
        "play": "com.bpmhealth.boostcamp",
        "pages": ["https://www.boostcamp.app/"],
    },
    "FitNotes": {
        "ios": "1059245195",
        "play": "com.github.jamesgay.fitnotes",
        "pages": ["https://www.fitnotesapp.com/"],
    },
}

# Fields from the App Store record that count as a change when they differ.
IOS_WATCHED = ("version", "price", "releaseNotes", "description", "trackName")
PLAY_WATCHED = ("title", "description")
# A page where more than this share of lines moved was redesigned, not edited;
# listing hundreds of lines would bury the one that matters.
REWRITE_SHARE = 0.4
MAX_LINES = 5
LINE_WIDTH = 150


# --- fetching ---------------------------------------------------------------

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


class _Text(HTMLParser):
    """Visible text only: no scripts, styles, or page chrome that churns."""

    SKIP = {"script", "style", "noscript", "svg", "head", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.lines: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            text = " ".join(data.split())
            if len(text) > 2:
                self.lines.append(text)


def page_lines(markup: str) -> list[str]:
    parser = _Text()
    parser.feed(markup)
    seen: set[str] = set()
    out = []
    for line in parser.lines:
        if line not in seen:  # repeated nav and card text is noise
            seen.add(line)
            out.append(line)
    return out


def parse_ios(payload: dict) -> dict:
    """The few fields of Apple's record worth diffing, or {} if it has none."""
    results = payload.get("results") or []
    if not results:
        return {}
    r = results[0]
    return {
        "trackName": r.get("trackName", ""),
        "version": r.get("version", ""),
        "price": r.get("formattedPrice") or str(r.get("price", "")),
        "releaseNotes": (r.get("releaseNotes") or "").strip(),
        "description": (r.get("description") or "").strip(),
        "released": r.get("currentVersionReleaseDate", ""),
        "rating": r.get("averageUserRating"),
        "ratingCount": r.get("userRatingCount"),
    }


def parse_play(markup: str) -> dict:
    """Title, description and rating from a Play listing, or {} if none found.

    Play has no API for this and its markup is not stable, so every field is
    best-effort: a field that goes missing is simply absent from the snapshot,
    and the diff ignores fields absent on either side.
    """
    out: dict = {}
    m = re.search(r'property="og:title" content="([^"]*)"', markup)
    if m:
        out["title"] = html.unescape(m.group(1)).replace(" - Apps on Google Play", "").strip()
    m = re.search(r'data-g-id="description"[^>]*>(.*?)</div>', markup, re.S)
    if m:
        text = re.sub(r"<br\s*/?>", "\n", m.group(1))
        out["description"] = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    m = re.search(r'"ratingValue":\s*"?([\d.]+)', markup)
    if m:
        out["rating"] = round(float(m.group(1)), 2)
    m = re.search(r'"ratingCount":\s*"?(\d+)', markup)
    if m:
        out["ratingCount"] = int(m.group(1))
    return out


def fetch_snapshot(prev: dict | None = None, get=_get) -> dict:
    """Fetch every source. A failed source keeps its previous data and is named
    in `errors`, so one outage reads as an error rather than a mass deletion."""
    prev = prev or {}
    snap: dict = {"date": date.today().isoformat(), "rivals": {}, "errors": []}
    for name, cfg in RIVALS.items():
        old = (prev.get("rivals") or {}).get(name, {})
        cur: dict = {"pages": {}}

        try:
            data = parse_ios(json.loads(get(
                "https://itunes.apple.com/lookup?id=%s&country=us" % cfg["ios"])))
            if not data:
                raise ValueError("no record for app id %s" % cfg["ios"])
            cur["ios"] = data
        except Exception as e:  # noqa: BLE001 - any failure degrades, never raises
            snap["errors"].append("%s App Store: %s" % (name, _short(e)))
            if old.get("ios"):
                cur["ios"] = old["ios"]

        try:
            data = parse_play(get(
                "https://play.google.com/store/apps/details?id=%s&hl=en_US&gl=US"
                % urllib.parse.quote(cfg["play"])))
            if not data.get("title"):
                raise ValueError("no listing for package %s" % cfg["play"])
            cur["play"] = data
        except Exception as e:  # noqa: BLE001
            snap["errors"].append("%s Google Play: %s" % (name, _short(e)))
            if old.get("play"):
                cur["play"] = old["play"]

        for url in cfg["pages"]:
            try:
                lines = page_lines(get(url))
                if not lines:
                    raise ValueError("page has no text")
                cur["pages"][url] = lines
            except Exception as e:  # noqa: BLE001
                snap["errors"].append("%s %s: %s" % (name, url, _short(e)))
                if url in (old.get("pages") or {}):
                    cur["pages"][url] = old["pages"][url]

        snap["rivals"][name] = cur
    return snap


def _short(e: Exception) -> str:
    return (str(e) or e.__class__.__name__)[:120]


# --- diffing ----------------------------------------------------------------

def _clip(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= LINE_WIDTH else text[: LINE_WIDTH - 1] + "…"


def _line_changes(old: str, new: str) -> tuple[list[str], list[str]]:
    a, b = old.splitlines(), new.splitlines()
    return _list_changes(a, b)


def _list_changes(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    added, removed = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += a[i1:i2]
        if tag in ("replace", "insert"):
            added += b[j1:j2]
    return added, removed


def diff_snapshots(old: dict, new: dict) -> list[dict]:
    """Changes between two snapshots, each {rival, source, summary, added, removed}.

    Rating counts are not changes; they move every day and live in `ratings`.
    Fields absent on either side are skipped, since a missing field means the
    parser lost it, not that the rival deleted it.
    """
    out: list[dict] = []
    for name, cur in (new.get("rivals") or {}).items():
        prev = (old.get("rivals") or {}).get(name)
        if not prev:
            continue
        for src, fields, label in (("ios", IOS_WATCHED, "App Store"),
                                   ("play", PLAY_WATCHED, "Google Play")):
            a, b = prev.get(src) or {}, cur.get(src) or {}
            for f in fields:
                if f not in a or f not in b or a[f] == b[f]:
                    continue
                if f in ("version", "price", "trackName"):
                    out.append({"rival": name, "source": label,
                                "summary": "%s: %s → %s" % (f, a[f] or "none", b[f] or "none"),
                                "added": [], "removed": []})
                else:
                    added, removed = _line_changes(a[f], b[f])
                    out.append({"rival": name, "source": label,
                                "summary": "%s changed" % ("release notes" if f == "releaseNotes" else f),
                                "added": [_clip(x) for x in added[:MAX_LINES]],
                                "removed": [_clip(x) for x in removed[:MAX_LINES]]})
        for url, lines in (cur.get("pages") or {}).items():
            before = (prev.get("pages") or {}).get(url)
            if before is None or before == lines:
                continue
            added, removed = _list_changes(before, lines)
            if not added and not removed:
                continue
            moved = (len(added) + len(removed)) / max(len(before) + len(lines), 1)
            host = urllib.parse.urlparse(url)
            where = host.netloc.replace("www.", "") + host.path
            if moved > REWRITE_SHARE:
                out.append({"rival": name, "source": where,
                            "summary": "page rewritten (%d lines in, %d out)" % (len(added), len(removed)),
                            "added": [], "removed": []})
            else:
                out.append({"rival": name, "source": where, "summary": "page text changed",
                            "added": [_clip(x) for x in added[:MAX_LINES]],
                            "removed": [_clip(x) for x in removed[:MAX_LINES]]})
    return out


def ratings_table(old: dict | None, new: dict) -> list[dict]:
    """Per rival: average and count on each store, and the count's change."""
    rows = []
    for name, cur in (new.get("rivals") or {}).items():
        prev = ((old or {}).get("rivals") or {}).get(name, {})
        row = {"rival": name}
        for src in ("ios", "play"):
            c, p = cur.get(src) or {}, prev.get(src) or {}
            count = c.get("ratingCount")
            before = p.get("ratingCount")
            row[src] = {
                "rating": c.get("rating"),
                "count": count,
                "delta": (count - before) if count is not None and before is not None else None,
            }
        rows.append(row)
    return rows


# --- state ------------------------------------------------------------------

def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def refresh(state_dir: Path = STATE_DIR, force: bool = False, get=_get,
            today: date | None = None) -> dict:
    """Fetch if the snapshot is stale, write both files, return last-changes.

    The first ever run records a baseline and reports no changes.
    """
    today = today or date.today()
    latest = _load(state_dir / "latest.json")
    if latest and not force:
        age = (today - date.fromisoformat(latest["date"])).days
        cached = _load(state_dir / "last-changes.json")
        if age < STALE_AFTER_DAYS and cached:
            return cached

    snap = fetch_snapshot(latest, get=get)
    snap["date"] = today.isoformat()
    result = {
        "date": snap["date"],
        "previous": latest["date"] if latest else None,
        "baseline": latest is None,
        "changes": diff_snapshots(latest, snap) if latest else [],
        "ratings": ratings_table(latest, snap),
        "errors": snap["errors"],
    }
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "latest.json").write_text(json.dumps(snap), encoding="utf-8")
        (state_dir / "last-changes.json").write_text(json.dumps(result), encoding="utf-8")
        (state_dir / "snapshots").mkdir(exist_ok=True)
        (state_dir / "snapshots" / ("%s.json" % snap["date"])).write_text(
            json.dumps(snap), encoding="utf-8")
    except OSError as e:
        result["errors"].append("could not save snapshot: %s" % _short(e))
    # Last and on its own: a bad history file must not cost the snapshot or the panel.
    try:
        append_history(state_dir / "history.md", result)
    except Exception as e:  # noqa: BLE001
        result["errors"].append("could not write history: %s" % _short(e))
    return result


def history_entry(result: dict) -> str:
    """One readable section of history.md for a fetch."""
    if result.get("baseline"):
        return "## %s\n\nBaseline recorded.\n" % result["date"]
    lines = ["## %s (since %s)" % (result["date"], result.get("previous")), ""]
    if not result["changes"]:
        lines.append("No changes.")
    for c in result["changes"]:
        lines.append("- **%s**, %s: %s" % (c["rival"], c["source"], c["summary"]))
        lines += ["  - added: " + x for x in c["added"]]
        lines += ["  - removed: " + x for x in c["removed"]]
    lines += ["- error: " + e for e in result["errors"]]
    return "\n".join(lines) + "\n"


def append_history(path: Path, result: dict) -> None:
    """Add this fetch to history.md, once per date (a same-day re-run is skipped)."""
    entry = history_entry(result)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Rival watch history\n"
    if ("\n## %s" % result["date"]) in existing:
        return
    path.write_text(existing.rstrip("\n") + "\n\n" + entry, encoding="utf-8")


# --- rendering --------------------------------------------------------------

def _esc(v: object) -> str:
    return html.escape(str(v), quote=True)


def _stars(cell: dict) -> str:
    if not cell.get("count"):
        return "–"
    rating = "%.2f" % cell["rating"] if cell.get("rating") else "?"
    delta = "" if cell.get("delta") in (None, 0) else " (%+d)" % cell["delta"]
    return "%s from %s%s" % (rating, format(cell["count"], ","), delta)


def render(result: dict) -> str:
    """The report panel, in the markup weekly-report.py's panels use."""
    parts = []
    when = result.get("date", "")
    prev = result.get("previous")
    if result.get("baseline"):
        parts.append('<p class="empty">Baseline recorded. Changes show from next week.</p>')
    elif not result.get("changes"):
        parts.append('<p class="empty">Nothing changed since %s in the listings, release '
                     'notes, prices or watched pages.</p>' % _esc(prev or "the last check"))
    else:
        rows = []
        for c in result["changes"]:
            detail = ""
            if c.get("added") or c.get("removed"):
                detail = "".join('<div>+ %s</div>' % _esc(x) for x in c["added"]) + \
                         "".join('<div>− %s</div>' % _esc(x) for x in c["removed"])
            rows.append("<tr><td>%s</td><td>%s · %s%s</td></tr>" % (
                _esc(c["rival"]), _esc(c["source"]), _esc(c["summary"]), detail))
        parts.append("<table><thead><tr><th>Rival</th><th>What changed</th></tr></thead>"
                     "<tbody>%s</tbody></table>" % "".join(rows))

    parts.append("<h3>Ratings</h3>")
    rows = ["<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        _esc(r["rival"]), _esc(_stars(r["ios"])), _esc(_stars(r["play"])))
        for r in result.get("ratings", [])]
    parts.append("<table><thead><tr><th>Rival</th><th>App Store (US)</th><th>Google Play</th>"
                 "</tr></thead><tbody>%s</tbody></table>" % "".join(rows)
                 if rows else '<p class="empty">No ratings.</p>')
    for e in result.get("errors", []):
        parts.append('<p class="error">%s</p>' % _esc(e))
    return ('<section><h2>Rivals</h2><p class="sub">Checked %s. Public listings and pages '
            'only, read once a week.</p>%s</section>' % (_esc(when), "".join(parts)))


def panel() -> str:
    """For weekly-report.py. Never raises."""
    try:
        return render(refresh())
    except Exception as e:  # noqa: BLE001
        return ('<section><h2>Rivals</h2><p class="error">Rival watcher failed: %s</p></section>'
                % _esc(_short(e)))


def text_summary(result: dict) -> str:
    lines = ["Rivals, checked %s" % result["date"]]
    if result.get("baseline"):
        lines.append("Baseline recorded.")
    elif not result["changes"]:
        lines.append("No changes since %s." % result.get("previous"))
    for c in result["changes"]:
        lines.append("- %s [%s] %s" % (c["rival"], c["source"], c["summary"]))
        lines += ["    + " + x for x in c["added"]] + ["    - " + x for x in c["removed"]]
    lines += ["ERROR " + e for e in result["errors"]]
    return "\n".join(lines)


if __name__ == "__main__":
    print(text_summary(refresh(force="--force" in sys.argv[1:])))
