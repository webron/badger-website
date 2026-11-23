#!/usr/bin/env python3
"""Watch a Badger release after it ships, and email only when something is wrong.

Run daily by launchd (fit.badger.release-check). It replaces the Android crash
and store review steps of the day+1, +3, +7 soak in badger-fit/docs/RELEASE.md:

  - the newest Play production release needs action, was refused, or is stuck in review
  - Play reports a crash or ANR on the live build
  - a rating of 3 stars or less on either store since the release went live

Crashes are watched for WATCH_DAYS after go-live, ratings for RATING_DAYS (the
stores file them late). A problem is emailed once, and again only if it grows. A source that cannot be read prints
an error line and exits 1, which the morning digest reports.

    python3 tool/release-check.py            # check, email on trouble
    python3 tool/release-check.py --dry-run  # print the email, send and save nothing
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stats_sources import (  # noqa: E402
    app_store_listing, app_store_reviews, play_error_counts, play_ratings, play_releases,
)

STATE = Path.home() / "Development/badger-artifacts/site-stats/release-check.json"
SEND_MAIL = Path.home() / "Development/fastmail-tools/send_mail.py"
TO = "claude@webron.me"

WATCH_DAYS = 8       # the day+7 read, plus one for Play's lag
RATING_DAYS = 14     # ratings reach the stores days after the review is written
REVIEW_DAYS = 4      # a normal Play review is done inside this (one took 3 days)
LOW_STARS = 3


def guarded(source, *args) -> dict:
    """A source must not be able to take the other checks down with it."""
    try:
        return source(*args)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{getattr(source, '__name__', 'source')} failed ({type(exc).__name__})."}


def days_since(day: str, today: date) -> int:
    return (today - date.fromisoformat(day)).days


# Play states that need a person, not time: alerted at once, with what to do.
ACT_NOW = {
    "NOT_APPROVED": "Google did not approve {rel}.{serving} The reason is in Play Console, "
                    "Publishing overview.",
    "NOT_SENT_FOR_REVIEW": "{rel} has not been sent for review: Play is waiting for you.{serving} "
                           "Send it from Play Console, Publishing overview.",
    "APPROVED_NOT_PUBLISHED": "{rel} is approved but not published: Play is waiting for you to "
                              "publish it.{serving} Publish it from Play Console, Publishing overview.",
}


def check_release(releases: list[dict], state: dict, today: date) -> list[str]:
    """Is the newest release actually out? Records when each was first seen.

    PUBLISHED also covers a staged or halted release, so a halt cannot be seen
    here. IN_REVIEW and states this code does not know alert after REVIEW_DAYS.
    """
    newest = next((r for r in releases if r["state"] != "DRAFT"), None)
    if newest is None or newest["state"] == "PUBLISHED":
        return []
    code = str(newest["code"])
    waiting = state["waiting_since"].setdefault(code, today.isoformat())
    age = days_since(waiting, today)
    kind = newest["state"] if newest["state"] in ACT_NOW else "waiting"
    if kind == "waiting" and age < REVIEW_DAYS:
        return []
    key = f"{code}:{kind}"
    if key in state["alerted"]:
        return []
    state["alerted"][key] = 1
    live = next((r for r in releases if r["state"] == "PUBLISHED"), None)
    serving = f" Play still serves {live['name']} ({live['code']})." if live else ""
    rel = f"{newest['name']} ({code})"
    if kind in ACT_NOW:
        return [ACT_NOW[kind].format(rel=rel, serving=serving)]
    return [f"{rel} is not live on Play after {age} days: "
            f"{newest['state'].replace('_', ' ').lower()}.{serving} "
            "Check Play Console, Publishing overview."]


def live_release(releases: list[dict], state: dict, today: date) -> dict | None:
    """The build Play serves now, with the day this check first saw it live."""
    live = next((r for r in releases if r["state"] == "PUBLISHED"), None)
    if live is None:
        return None
    since = state["live_since"].setdefault(str(live["code"]), today.isoformat())
    return {**live, "since": since}


def check_crashes(counts: list[dict], live: dict, state: dict) -> list[str]:
    out = []
    for kind in ("CRASH", "ANR"):
        mine = [c for c in counts if c["code"] == live["code"] and c["kind"] == kind]
        reports = sum(c["reports"] for c in mine)  # the window slides, so this can shrink
        key = f"{live['code']}:{kind}"
        if reports <= state["alerted"].get(key, 0):
            continue
        state["alerted"][key] = reports
        others = [f"{c['code']}: {c['reports']}" for c in counts
                  if c["kind"] == kind and c["code"] != live["code"]]
        compare = f" Other builds: {', '.join(others)}." if others else " None on other builds."
        out.append(f"{live['name']} ({live['code']}): {reports} {kind} reports from "
                   f"at least {max((c['users'] for c in mine), default=0)} people on one day.{compare}")
    return out


def check_ratings(store: str, rows: list[dict], since: str, state: dict) -> list[str]:
    """Low ratings on or after `since`. Rows: key, day, rating, text."""
    out = []
    for row in rows:
        if row["day"] < since or not row["rating"] or row["rating"] > LOW_STARS:
            continue
        key = f"{store}:{row['key']}:{row['rating']}"
        if key in state["alerted"]:
            continue
        state["alerted"][key] = 1
        text = " ".join(row["text"].split())
        out.append(f"{store}, {row['rating']} stars on {row['day']}: "
                   + (f'"{text}"' if text else "no text."))
    return out


def play_rows(ratings: list[dict]) -> list[dict]:
    return [{"key": r["id"] or r["submitted"], "day": r["updated"] or r["date"],
             "rating": r["rating"], "text": r["text"]} for r in ratings]


def ios_rows(reviews: list[dict]) -> list[dict]:
    return [{"key": f"{r['date']}:{r['reviewer']}:" + hashlib.sha1(
                 f"{r['title']}\n{r['body']}".encode()).hexdigest()[:8], "day": r["date"], "rating": r["rating"],
             "text": f"{r['title']} {r['body']}"} for r in reviews]


def run(state: dict, today: date) -> tuple[list[str], list[str]]:
    """Every check. Returns (problems for Ron, sources that could not be read)."""
    problems: list[str] = []
    errors: list[str] = []

    def read(source, *args) -> dict | None:
        result = guarded(source, *args)
        if "error" in result:
            errors.append(result["error"])
            return None
        return result

    rel = read(play_releases)
    live = None
    if rel:
        problems += check_release(rel["releases"], state, today)
        live = live_release(rel["releases"], state, today)
    age = days_since(live["since"], today) if live else None
    if live and age <= WATCH_DAYS:
        counts = read(play_error_counts)
        if counts:
            problems += check_crashes(counts["counts"], live, state)
    if live and age <= RATING_DAYS:
        ratings = read(play_ratings, RATING_DAYS + 7)
        if ratings:
            if ratings.get("note"):
                errors.append(ratings["note"])
            # Go-live is the day this check first saw it, which can be a day late.
            since = (date.fromisoformat(live["since"]) - timedelta(days=1)).isoformat()
            problems += check_ratings("Google Play", play_rows(ratings["ratings"]), since, state)

    listing = read(app_store_listing)
    if listing and listing["released"] and days_since(listing["released"], today) <= RATING_DAYS:
        reviews = read(app_store_reviews, RATING_DAYS + 7)
        if reviews:
            problems += check_ratings("App Store", ios_rows(reviews["reviews"]),
                                      listing["released"], state)
    return problems, errors


def empty_state() -> dict:
    return {"waiting_since": {}, "live_since": {}, "alerted": {}}


def _is_day(value) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def load_state() -> dict:
    """The saved state, or ValueError when the file is not one this code wrote."""
    if not STATE.exists():
        return empty_state()
    state = json.loads(STATE.read_text())
    if not isinstance(state, dict):
        raise ValueError("not a JSON object")
    for key in ("waiting_since", "live_since", "alerted"):
        if not isinstance(state.setdefault(key, {}), dict):
            raise ValueError(f"{key} is not an object")
    for key in ("waiting_since", "live_since"):
        if not all(_is_day(v) for v in state[key].values()):
            raise ValueError(f"{key} holds a value that is not a date")
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in state["alerted"].values()):
        raise ValueError("alerted holds a value that is not a count")
    return state


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True))
    os.replace(tmp, STATE)


def send(body: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-I", str(SEND_MAIL), "--to", TO,
         "--subject", "Badger release check: needs a look", "--text-file", "-"],
        input=body, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError("send_mail failed: " + (proc.stderr or proc.stdout).strip()[:300])


def main() -> int:
    dry = "--dry-run" in sys.argv[1:]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    errors: list[str] = []
    try:
        state = load_state()
    except (ValueError, OSError) as exc:
        # Keep the file for a look, and do not let it block the checks.
        state = empty_state()
        moved = ""
        if not dry:
            try:
                os.replace(STATE, STATE.with_suffix(".bad"))
                moved = f", moved to {STATE.with_suffix('.bad').name}"
            except OSError:
                pass
        errors.append(f"state file {STATE.name} is unreadable ({exc}){moved}; started empty.")
    before = dict(state["alerted"])
    problems, unread = run(state, date.today())
    errors += unread

    if problems:
        body = "\n\n".join(problems) + "\n"
        if dry:
            print(body)
        else:
            try:
                send(body)
            except Exception as exc:  # noqa: BLE001
                # First-seen dates stay; the alerts are not marked, so tomorrow retries them.
                state["alerted"] = before
                errors.append(f"alert email not sent: {exc}")
    if not dry:
        save_state(state)
    for line in errors:
        print(f"[{stamp}] error: {line}")
    print(f"[{stamp}] problems={len(problems)} unread_sources={len(unread)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
