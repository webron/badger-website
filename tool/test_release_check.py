"""Tests for the post-release check.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

The failure that matters is silence: a release that never went live, or a
source that could not be read, must never look like a healthy run.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _stats_sources as src  # noqa: E402


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load("release_check", "release-check.py")
report = _load("weekly_report", "weekly-report.py")

TODAY = date(2026, 11, 23)


def fresh():
    return {"waiting_since": {}, "live_since": {}, "alerted": {}}


def rel(code, state, name=None):
    return {"name": name or f"1.1.{code}", "code": code, "state": state}


class Releases(unittest.TestCase):
    def test_a_release_stuck_in_review_is_reported_once(self):
        state = fresh()
        rows = [rel(48, "IN_REVIEW"), rel(46, "PUBLISHED")]
        self.assertEqual(check.check_release(rows, state, date(2026, 11, 18)), [])
        self.assertEqual(check.check_release(rows, state, date(2026, 11, 20)), [])
        found = check.check_release(rows, state, date(2026, 11, 21))
        self.assertEqual(len(found), 1)
        self.assertIn("after 3 days", found[0])
        self.assertIn("still serves 1.1.46", found[0])
        self.assertEqual(check.check_release(rows, state, date(2026, 11, 22)), [])

    def test_a_refusal_is_reported_the_same_day_even_after_a_wait_alert(self):
        state = fresh()
        state["alerted"]["48:waiting"] = 1
        found = check.check_release([rel(48, "NOT_APPROVED")], state, TODAY)
        self.assertIn("did not approve", found[0])

    def test_published_and_draft_are_quiet(self):
        self.assertEqual(check.check_release([rel(48, "PUBLISHED")], fresh(), TODAY), [])
        self.assertEqual(
            check.check_release([rel(50, "DRAFT"), rel(48, "PUBLISHED")], fresh(), TODAY), [])

    def test_an_unknown_state_counts_as_not_live(self):
        state = fresh()
        state["waiting_since"]["48"] = "2026-11-18"
        self.assertEqual(len(check.check_release([rel(48, "SOMETHING_NEW")], state, TODAY)), 1)

    def test_live_release_is_the_published_one_not_the_newest(self):
        live = check.live_release([rel(48, "IN_REVIEW"), rel(46, "PUBLISHED")], fresh(), TODAY)
        self.assertEqual((live["code"], live["since"]), (46, "2026-11-23"))


class Crashes(unittest.TestCase):
    def test_reported_on_the_live_build_only_and_again_only_if_it_grows(self):
        state = fresh()
        live = {**rel(48, "PUBLISHED"), "since": "2026-11-20"}
        rows = [{"code": 48, "kind": "CRASH", "reports": 2, "users": 1},
                {"code": 46, "kind": "CRASH", "reports": 1, "users": 1},
                {"code": 49, "kind": "ANR", "reports": 5, "users": 1}]
        found = check.check_crashes(rows, live, state)
        self.assertEqual(len(found), 1)
        self.assertIn("2 CRASH reports from 1 people", found[0])
        self.assertIn("46: 1", found[0])
        self.assertEqual(check.check_crashes(rows, live, state), [])
        rows[0]["reports"] = 3
        self.assertEqual(len(check.check_crashes(rows, live, state)), 1)

    def test_rows_parse_and_non_fatal_is_dropped(self):
        def row(kind, code, n):
            return {"dimensions": [{"dimension": "reportType", "stringValue": kind},
                                   {"dimension": "versionCode", "int64Value": code}],
                    "metrics": [{"metric": "errorReportCount", "decimalValue": {"value": n}},
                                {"metric": "distinctUsers", "decimalValue": {"value": "1"}}]}
        rows = src._error_count_rows([row("CRASH", "46", "1"), row("NON_FATAL", "48", "9"),
                                      row("ANR", "48", "2")])
        self.assertEqual(rows, [{"code": 48, "kind": "ANR", "reports": 2, "users": 1},
                                {"code": 46, "kind": "CRASH", "reports": 1, "users": 1}])


class Ratings(unittest.TestCase):
    def row(self, **kw):
        return {"key": "a", "day": "2026-11-22", "rating": 1, "text": "lost all my data", **kw}

    def test_low_since_release_once(self):
        state = fresh()
        rows = [self.row(), self.row(key="b", rating=4), self.row(key="c", day="2026-11-01")]
        found = check.check_ratings("Google Play", rows, "2026-11-20", state)
        self.assertEqual(len(found), 1)
        self.assertIn("lost all my data", found[0])
        self.assertEqual(check.check_ratings("Google Play", rows, "2026-11-20", state), [])

    def test_an_edit_to_fewer_stars_alerts_again(self):
        state = fresh()
        check.check_ratings("Google Play", [self.row(rating=3)], "2026-11-20", state)
        self.assertEqual(
            len(check.check_ratings("Google Play", [self.row(rating=1)], "2026-11-20", state)), 1)


class Run(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "play_releases": {"releases": [rel(48, "PUBLISHED")]},
            "play_error_counts": {"counts": []},
            "play_ratings": {"ratings": [], "note": ""},
            "app_store_listing": {"released": "2026-11-19"},
            "app_store_reviews": {"reviews": []},
        }

    def run_with(self, state=None, **over):
        with mock.patch.multiple(check, **{
                k: mock.Mock(return_value=v, __name__=k) for k, v in {**self.sources, **over}.items()}):
            return check.run(state or fresh(), TODAY)

    def test_all_healthy_is_quiet(self):
        self.assertEqual(self.run_with(), ([], []))

    def test_each_failed_source_is_an_error_not_silence(self):
        for name in self.sources:
            with self.subTest(name):
                self.assertEqual(self.run_with(**{name: {"error": "down"}})[1], ["down"])

    def test_one_dead_source_does_not_stop_the_others(self):
        boom = {"date": "2026-11-20", "reviewer": "x", "rating": 1, "title": "t", "body": "b"}
        problems, errors = self.run_with(play_releases={"error": "down"},
                                         app_store_reviews={"reviews": [boom]})
        self.assertEqual((len(problems), errors), (1, ["down"]))

    def test_a_partial_play_ratings_read_is_an_error(self):
        self.assertEqual(self.run_with(play_ratings={"ratings": [], "note": "partial"})[1],
                         ["partial"])

    def test_an_old_release_is_not_watched(self):
        state = fresh()
        state["live_since"]["48"] = "2026-10-01"
        low = {"error": "must not be read"}
        self.assertEqual(self.run_with(state, play_error_counts=low, play_ratings=low,
                                       app_store_listing={"released": "2026-10-01"},
                                       app_store_reviews=low), ([], []))


class Main(unittest.TestCase):
    def test_a_failed_send_keeps_the_alert_for_the_next_run(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(check, "STATE", Path(tmp) / "s.json"), \
                mock.patch.object(check, "run", return_value=(["bad"], [])), \
                mock.patch.object(check, "send", side_effect=RuntimeError("no mail")), \
                mock.patch.object(sys, "argv", ["x"]):
            with self.assertRaises(RuntimeError):
                check.main()
            self.assertFalse(check.STATE.exists())

    def test_dry_run_sends_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(check, "STATE", Path(tmp) / "s.json"), \
                mock.patch.object(check, "run", return_value=(["bad"], [])), \
                mock.patch.object(check, "send") as send, \
                mock.patch.object(sys, "argv", ["x", "--dry-run"]), \
                mock.patch("builtins.print"):
            self.assertEqual(check.main(), 0)
            send.assert_not_called()
            self.assertFalse(check.STATE.exists())


class Panel(unittest.TestCase):
    def test_shows_state_and_never_claims_zero_crashes(self):
        with mock.patch.object(report, "play_releases",
                               return_value={"releases": [rel(48, "IN_REVIEW", "1.1.19")]}), \
                mock.patch.object(report, "play_error_counts",
                                  return_value={"start": "a", "end": "b", "counts": []}):
            html = report.play_builds_section()
        self.assertIn("in review", html)
        self.assertIn("can still miss one", html)


if __name__ == "__main__":
    unittest.main()
