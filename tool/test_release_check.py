"""Tests for the post-release check.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

The failure that matters is silence: a release that never went live, or a
source that could not be read, must never look like a healthy run.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
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
        self.assertEqual(check.check_release(rows, state, date(2026, 11, 21)), [])
        found = check.check_release(rows, state, date(2026, 11, 22))
        self.assertEqual(len(found), 1)
        self.assertIn("after 4 days", found[0])
        self.assertIn("still serves 1.1.46", found[0])
        self.assertEqual(check.check_release(rows, state, date(2026, 11, 23)), [])

    def test_states_that_need_the_developer_alert_at_once_once_each(self):
        for name, words in (("NOT_SENT_FOR_REVIEW", "not been sent for review"),
                            ("APPROVED_NOT_PUBLISHED", "approved but not published"),
                            ("NOT_APPROVED", "did not approve")):
            with self.subTest(name):
                state = fresh()
                found = check.check_release([rel(48, name), rel(46, "PUBLISHED")], state, TODAY)
                self.assertEqual(len(found), 1)
                self.assertIn(words, found[0])
                self.assertEqual(check.check_release([rel(48, name)], state, TODAY), [])
        state = fresh()
        check.check_release([rel(48, "NOT_SENT_FOR_REVIEW")], state, TODAY)
        self.assertEqual(len(check.check_release([rel(48, "APPROVED_NOT_PUBLISHED")], state, TODAY)), 1)

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
        self.assertIn("2 CRASH reports from at least 1 people on one day", found[0])
        self.assertIn("46: 1", found[0])
        self.assertEqual(check.check_crashes(rows, live, state), [])
        rows[0]["reports"] = 1  # the window slid: a smaller count is not news
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


class DailyCounts(unittest.TestCase):
    @staticmethod
    def row(kind, code, n, users="1"):
        return {"dimensions": [{"dimension": "reportType", "stringValue": kind},
                               {"dimension": "versionCode", "int64Value": code}],
                "metrics": [{"metric": "errorReportCount", "decimalValue": {"value": n}},
                            {"metric": "distinctUsers", "decimalValue": {"value": users}}]}

    def test_days_sum_reports_and_users_take_the_busiest_day(self):
        rows = [self.row("CRASH", "48", "2", "2"), self.row("CRASH", "48", "3", "1"),
                self.row("CRASH", "48", "1", "4")]
        self.assertEqual(src._error_count_rows(rows),
                         [{"code": 48, "kind": "CRASH", "reports": 6, "users": 4}])

    def test_both_anr_spellings_count_as_anr(self):
        rows = [self.row("ANR", "48", "1"), self.row("APPLICATION_NOT_RESPONDING", "48", "2")]
        self.assertEqual(src._error_count_rows(rows),
                         [{"code": 48, "kind": "ANR", "reports": 3, "users": 1}])

    def test_an_unknown_report_type_is_an_error_not_silence(self):
        with self.assertRaises(ValueError):
            src._error_count_rows([self.row("SOMETHING_NEW", "48", "1")])
        with mock.patch.object(src.os.path, "exists", return_value=True), \
                mock.patch.dict(sys.modules, {"_google_auth": mock.Mock(
                    access_token=mock.Mock(return_value="t"))}), \
                mock.patch.object(src, "_get_json", side_effect=[
                    FRESH, {"rows": [self.row("SOMETHING_NEW", "48", "1")]}]):
            self.assertIn("SOMETHING_NEW", src.play_error_counts()["error"])

    def test_the_query_is_daily_and_ends_at_the_freshness_day(self):
        seen = []

        def get(url, headers, data=None, timeout=30):
            seen.append(data)
            return FRESH if data is None else {"rows": [self.row("CRASH", "48", "2")]}
        with mock.patch.object(src.os.path, "exists", return_value=True), \
                mock.patch.dict(sys.modules, {"_google_auth": mock.Mock(
                    access_token=mock.Mock(return_value="t"))}), \
                mock.patch.object(src, "_get_json", side_effect=get):
            got = src.play_error_counts(28)
        spec = json.loads(seen[1])["timelineSpec"]
        self.assertEqual(spec["aggregationPeriod"], "DAILY")
        self.assertEqual(spec["endTime"], {"year": 2026, "month": 11, "day": 22})
        self.assertEqual(spec["startTime"], {"year": 2026, "month": 10, "day": 25})
        self.assertEqual((got["start"], got["end"]), ("2026-10-25", "2026-11-21"))
        self.assertEqual(got["counts"][0]["reports"], 2)


FRESH = {"freshnessInfo": {"freshnesses": [
    {"aggregationPeriod": "DAILY", "latestEndTime": {"year": 2026, "month": 11, "day": 22}}]}}


class PlayReleases(unittest.TestCase):
    PAYLOAD = {"releases": [{"releaseName": "1.1.19", "releaseLifecycleState":
                             "RELEASE_LIFECYCLE_STATE_IN_REVIEW",
                             "activeArtifacts": [{"versionCode": "48"}]}]}

    def call(self, effects):
        sleep = mock.Mock()
        with mock.patch.object(src.os.path, "exists", return_value=True), \
                mock.patch.dict(sys.modules, {"_google_auth": mock.Mock(
                    access_token=mock.Mock(return_value="t"))}), \
                mock.patch.object(src, "_get_json", side_effect=effects) as get:
            return src.play_releases(sleep=sleep), sleep, get

    @staticmethod
    def quota():
        return urllib.error.HTTPError("u", 403, "quota", {}, None)

    def test_a_403_is_retried_twice_with_a_pause(self):
        got, sleep, get = self.call([self.quota(), self.quota(), self.PAYLOAD])
        self.assertEqual(got["releases"][0]["state"], "IN_REVIEW")
        self.assertEqual((get.call_count, [c.args for c in sleep.call_args_list]),
                         (3, [(30,), (30,)]))

    def test_a_third_403_is_returned_as_the_error(self):
        got, sleep, get = self.call([self.quota()] * 3)
        self.assertIn("403", got["error"])
        self.assertEqual((get.call_count, sleep.call_count), (3, 2))

    def test_other_errors_are_not_retried(self):
        got, sleep, get = self.call([urllib.error.HTTPError("u", 500, "x", {}, None)])
        self.assertEqual((get.call_count, sleep.call_count), (1, 0))
        self.assertIn("500", got["error"])


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

    def test_play_ratings_count_from_a_day_before_go_live(self):
        state = fresh()
        state["live_since"]["48"] = "2026-11-20"
        row = {"id": "a", "submitted": "", "updated": "2026-11-19", "date": "2026-11-19",
               "rating": 1, "text": "bad"}
        problems, _ = self.run_with(state, play_ratings={"ratings": [row], "note": ""})
        self.assertEqual(len(problems), 1)
        row["updated"] = row["date"] = "2026-11-18"
        self.assertEqual(self.run_with(state, play_ratings={"ratings": [row], "note": ""})[0], [])

    def test_ratings_are_watched_longer_than_crashes(self):
        state = fresh()
        state["live_since"]["48"] = "2026-11-13"  # 10 days live
        low = {"error": "crashes must not be read"}
        reviews = mock.Mock(return_value={"reviews": []}, __name__="app_store_reviews")
        ratings = mock.Mock(return_value={"ratings": [], "note": ""}, __name__="play_ratings")
        mocks = {k: mock.Mock(return_value=v, __name__=k) for k, v in {
            **self.sources, "play_error_counts": low,
            "app_store_listing": {"released": "2026-11-13"}}.items()}
        with mock.patch.multiple(check, **{**mocks, "play_ratings": ratings,
                                           "app_store_reviews": reviews}):
            self.assertEqual(check.run(state, TODAY), ([], []))
        ratings.assert_called_once_with(check.RATING_DAYS + 7)
        reviews.assert_called_once_with(check.RATING_DAYS + 7)

    def test_ios_reviews_with_a_blank_reviewer_do_not_collide(self):
        a, b = [{"date": "2026-11-20", "reviewer": "", "rating": 1, "title": t, "body": "x"}
                for t in ("one", "two")]
        keys = {r["key"] for r in check.ios_rows([a, b])}
        self.assertEqual(len(keys), 2)

    def test_an_old_release_is_not_watched(self):
        state = fresh()
        state["live_since"]["48"] = "2026-10-01"
        low = {"error": "must not be read"}
        self.assertEqual(self.run_with(state, play_error_counts=low, play_ratings=low,
                                       app_store_listing={"released": "2026-10-01"},
                                       app_store_reviews=low), ([], []))


class Main(unittest.TestCase):
    def test_a_failed_send_keeps_dates_but_not_the_alert_marks(self):
        def fake_run(state, today):
            state["waiting_since"]["48"] = "2026-11-20"
            state["alerted"]["48:waiting"] = 1
            return ["bad"], []
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(check, "STATE", Path(tmp) / "s.json"), \
                mock.patch.object(check, "run", side_effect=fake_run), \
                mock.patch.object(check, "send", side_effect=RuntimeError("no mail")), \
                mock.patch.object(sys, "argv", ["x"]), \
                mock.patch("builtins.print") as out:
            self.assertEqual(check.main(), 1)
            saved = json.loads(check.STATE.read_text())
            self.assertEqual((saved["waiting_since"], saved["alerted"]),
                             ({"48": "2026-11-20"}, {}))
            self.assertIn("no mail", str(out.call_args_list))

    def test_a_corrupt_state_file_is_set_aside_and_the_checks_still_run(self):
        bad = ["{not json", "[1]", '{"alerted": []}', '{"alerted": {"a": "x"}}',
               '{"live_since": {"48": "soon"}}']
        for text in bad:
            with self.subTest(text), tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(check, "STATE", Path(tmp) / "s.json"), \
                    mock.patch.object(check, "run", return_value=([], [])) as run, \
                    mock.patch.object(sys, "argv", ["x"]), mock.patch("builtins.print") as out:
                check.STATE.write_text(text)
                self.assertEqual(check.main(), 1)
                run.assert_called_once()
                self.assertEqual((Path(tmp) / "s.bad").read_text(), text)
                self.assertEqual(json.loads(check.STATE.read_text())["alerted"], {})
                self.assertIn("error:", str(out.call_args_list))

    def test_a_corrupt_state_file_is_left_alone_in_a_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(check, "STATE", Path(tmp) / "s.json"), \
                mock.patch.object(check, "run", return_value=([], [])), \
                mock.patch.object(sys, "argv", ["x", "--dry-run"]), mock.patch("builtins.print"):
            check.STATE.write_text("{not json")
            self.assertEqual(check.main(), 1)
            self.assertEqual(check.STATE.read_text(), "{not json")
            self.assertFalse((Path(tmp) / "s.bad").exists())

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

    def test_the_people_column_says_it_is_one_day(self):
        counts = {"start": "a", "end": "b",
                  "counts": [{"code": 48, "kind": "CRASH", "reports": 2, "users": 1}]}
        with mock.patch.object(report, "play_releases", return_value={"releases": []}), \
                mock.patch.object(report, "play_error_counts", return_value=counts):
            self.assertIn("busiest day", report.play_builds_section())


if __name__ == "__main__":
    unittest.main()
