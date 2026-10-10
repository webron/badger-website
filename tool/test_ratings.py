"""Tests for the store ratings in the weekly report.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

Two things here are easy to get quietly wrong: a star-only Play rating has no
link and so no id, and must still count; and App Store ratings have no date, so
"new this week" is a difference between runs that a mid-week manual run must
not reset.
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

_spec = importlib.util.spec_from_file_location("weekly_report", HERE / "weekly-report.py")
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)

LINK = ("http://play.google.com/console/developers/1/app/2/user-feedback/"
        "review-details?reviewId=abc-123&corpus=PUBLIC_REVIEWS")


class PlayRows(unittest.TestCase):
    def test_review_id_comes_out_of_the_link(self):
        self.assertEqual(src._review_id(LINK), "abc-123")
        self.assertEqual(src._review_id(""), "")

    def test_a_star_only_rating_still_counts(self):
        rows = src._play_review_rows([
            {"Star Rating": "5", "Review Link": "", "Review Text": "",
             "Review Submit Date and Time": "2026-10-04T15:11:42Z",
             "Review Last Update Date and Time": "2026-10-04T15:11:42Z"},
            {"Star Rating": "3", "Review Link": LINK, "Review Text": " ok ",
             "Review Submit Date and Time": "2026-10-01T07:56:30Z",
             "Review Last Update Date and Time": "2026-10-06T07:56:30Z"},
        ])
        self.assertEqual(len(rows), 2)
        # Newest by last update first, so an edited review rises to the top.
        self.assertEqual([r["rating"] for r in rows], [3, 5])
        self.assertEqual(rows[0]["text"], "ok")
        self.assertEqual(rows[1]["id"], "")

    def test_a_row_without_stars_is_skipped(self):
        self.assertEqual(src._play_review_rows([{"Star Rating": ""}]), [])


class AppStoreSweep(unittest.TestCase):
    def test_sums_every_storefront_and_weights_the_average(self):
        def fake(url, headers, data=None, timeout=30):
            if "country=fr" in url:
                return {"results": [{"userRatingCount": 1, "averageUserRating": 4}]}
            if "country=de" in url:
                return {"results": [{"userRatingCount": 3, "averageUserRating": 5}]}
            return {"results": [{"userRatingCount": 0, "averageUserRating": 0}]}

        with mock.patch.object(src, "_get_json", side_effect=fake):
            out = src.app_store_ratings()
        self.assertEqual(out["total"], 4)
        self.assertEqual(out["average"], 4.75)
        self.assertEqual(out["countries"][0], ("DE", 3, 5.0))
        self.assertEqual(out["failed"], [])

    def test_unreachable_everywhere_is_an_error_not_zero(self):
        with mock.patch.object(src, "_get_json",
                               side_effect=src.urllib.error.URLError("down")):
            self.assertIn("error", src.app_store_ratings())


class RatingsChange(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "history.json"

    def test_first_run_has_no_baseline(self):
        self.assertIsNone(report.ratings_change(1, self.path, date(2026, 10, 12)))

    def test_change_is_against_a_count_at_least_six_days_old(self):
        report.ratings_change(1, self.path, date(2026, 10, 5))
        report.ratings_change(3, self.path, date(2026, 10, 9))  # a manual mid-week run
        self.assertEqual(report.ratings_change(4, self.path, date(2026, 10, 12)),
                         (3, "2026-10-05"))

    def test_with_nothing_old_enough_it_uses_the_oldest(self):
        report.ratings_change(1, self.path, date(2026, 10, 9))
        self.assertEqual(report.ratings_change(2, self.path, date(2026, 10, 12)),
                         (1, "2026-10-09"))

    def test_rerunning_the_same_day_does_not_compare_to_itself(self):
        report.ratings_change(1, self.path, date(2026, 10, 5))
        report.ratings_change(2, self.path, date(2026, 10, 12))
        self.assertEqual(report.ratings_change(2, self.path, date(2026, 10, 12)),
                         (1, "2026-10-05"))

    def test_an_incomplete_count_is_not_kept_as_a_baseline(self):
        report.ratings_change(13, self.path, date(2026, 10, 5))
        self.assertEqual(report.ratings_change(3, self.path, date(2026, 10, 12), record=False),
                         (-10, "2026-10-05"))
        self.assertEqual(report.ratings_change(14, self.path, date(2026, 10, 19)),
                         (1, "2026-10-05"))

    def test_a_corrupt_history_file_costs_the_delta_not_the_report(self):
        for junk in ("[]", '{"2026-10-05": "x"}', "not json"):
            self.path.write_text(junk)
            self.assertIsNone(report.ratings_change(1, self.path, date(2026, 10, 12)))


class Timeouts(unittest.TestCase):
    def test_a_storefront_timeout_does_not_escape(self):
        import socket

        def fake(url, headers, data=None, timeout=30):
            if "country=fr" in url:
                raise socket.timeout("slow")
            return {"results": [{"userRatingCount": 1, "averageUserRating": 5}]}

        with mock.patch.object(src, "_get_json", side_effect=fake):
            out = src.app_store_ratings()
        self.assertEqual(out["failed"], ["fr"])

    def test_a_play_file_timeout_is_an_error_not_a_crash(self):
        import socket
        with mock.patch("os.path.exists", return_value=True), \
             mock.patch("_google_auth.access_token", return_value="tok"), \
             mock.patch.object(src, "_gcs_list", side_effect=socket.timeout("slow")):
            self.assertIn("error", src.play_ratings(35))


if __name__ == "__main__":
    unittest.main()
