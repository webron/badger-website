"""Tests for the Near wins and declines and Overlap panels of the weekly report.

Run: python3 -m unittest discover -s tool -p 'test_*.py'
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_spec = importlib.util.spec_from_file_location("weekly_report", HERE / "weekly-report.py")
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)

END = date(2026, 11, 20)


def row(query, page, clicks=0, impressions=50, position=8.0):
    return {"query": query, "page": page, "clicks": clicks, "impressions": impressions, "position": position}


def daily(page, weekly_clicks):
    """Page by date rows: weekly_clicks oldest first, all clicks on the week's last day."""
    rows = []
    n = len(weekly_clicks)
    for i, c in enumerate(weekly_clicks):
        age_weeks = n - 1 - i
        rows.append({"page": page, "date": (END - timedelta(days=7 * age_weeks)).isoformat(), "clicks": c})
        # a zero-click day earlier in the same week, so every week has more than one date
        rows.append({"page": page, "date": (END - timedelta(days=7 * age_weeks + 6)).isoformat(), "clicks": 0})
    return rows


class SearchTotals(unittest.TestCase):
    def test_headline_uses_the_total_not_the_visible_queries(self):
        src = sys.modules["_stats_sources"]
        auth = sys.modules.get("_google_auth") or __import__("_google_auth")

        def fake(url, headers, body):
            dims = json.loads(body)["dimensions"]
            if not dims:
                return {"rows": [{"clicks": 17, "impressions": 593, "position": 9.0}]}
            if dims == ["query"]:
                return {"rows": [{"keys": ["badger app"], "clicks": 0, "impressions": 116,
                                  "position": 16.0}]}
            return {"rows": []}

        with mock.patch.object(src, "_get_json", side_effect=fake), \
             mock.patch.object(src.os.path, "exists", return_value=True), \
             mock.patch.object(auth, "access_token", return_value="t"):
            sc = src.search_console(35)
        self.assertEqual((sc["clicks"], sc["impressions"]), (17, 593))
        self.assertEqual(sc["queries"][0]["key"], "badger app")

    def test_no_rows_at_all_is_zero(self):
        src = sys.modules["_stats_sources"]
        auth = sys.modules.get("_google_auth") or __import__("_google_auth")
        with mock.patch.object(src, "_get_json", return_value={}), \
             mock.patch.object(src.os.path, "exists", return_value=True), \
             mock.patch.object(auth, "access_token", return_value="t"):
            sc = src.search_console(35)
        self.assertEqual((sc["clicks"], sc["impressions"]), (0, 0))


class Archive(unittest.TestCase):
    def test_keeps_a_dated_copy_and_a_rerun_replaces_it(self):
        with tempfile.TemporaryDirectory() as d:
            hist = Path(d) / "history"
            report.archive("bad", date(2026, 11, 23), hist)
            report.archive("good", date(2026, 11, 23), hist)
            report.archive("next", date(2026, 11, 30), hist)
            self.assertEqual((hist / "weekly-2026-11-23.html").read_text(), "good")
            self.assertEqual(len(list(hist.iterdir())), 2)

    def test_an_unwritable_folder_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = Path(d) / "file"
            blocker.write_text("x")
            report.archive("page", date(2026, 11, 23), blocker / "history")


class ArchiveWiring(unittest.TestCase):
    def test_only_the_default_page_is_archived(self):
        builders = [n for n in dir(report) if n.startswith("build_")]
        with tempfile.TemporaryDirectory() as d:
            default = Path(d) / "weekly.html"
            with mock.patch.multiple(report, DEFAULT_OUT=default,
                                     **{n: mock.Mock(return_value="") for n in builders}):
                for argv in (["x", "--no-open", "--out", str(Path(d) / "other.html")],
                             ["x", "--no-open"]):
                    with mock.patch.object(sys, "argv", argv), mock.patch("builtins.print"):
                        report.main()
                    copies = list((Path(d) / "history").glob("*"))
                    self.assertEqual(len(copies), 0 if "--out" in argv else 1)


class CanonicalPage(unittest.TestCase):
    def test_spellings_fold(self):
        a = report.canonical_page("https://www.badger.fit/guides/x/?utm_source=ig#top")
        b = report.canonical_page("http://badger.fit/guides/x")
        self.assertEqual(a, b)

    def test_different_paths_stay_apart(self):
        self.assertNotEqual(report.canonical_page("https://badger.fit/guides/x"),
                            report.canonical_page("https://badger.fit/guides/y"))


class NearWins(unittest.TestCase):
    def test_window_and_minimum(self):
        rows = report.merge_query_pages([
            row("a", "https://badger.fit/a", position=3.9),
            row("b", "https://badger.fit/b", position=4.0),
            row("c", "https://badger.fit/c", position=20.0),
            row("d", "https://badger.fit/d", position=20.1),
            row("e", "https://badger.fit/e", position=10.0, impressions=report.NEAR_MIN_IMPRESSIONS - 1),
        ])
        self.assertEqual(sorted(r["query"] for r in report.near_wins(rows)), ["b", "c"])

    def test_empty(self):
        self.assertEqual(report.near_wins([]), [])


class Declines(unittest.TestCase):
    def test_four_drops_in_a_row(self):
        rows = daily("https://badger.fit/a", [35, 28, 21, 14, 7])
        out = report.declining_pages(rows, [], END)
        self.assertEqual([r["page"] for r in out], [report.canonical_page("https://badger.fit/a")])
        self.assertEqual(out[0]["weekly"], [35, 28, 21, 14, 7])

    def test_one_rise_breaks_it(self):
        rows = daily("https://badger.fit/a", [35, 28, 30, 14, 7])
        self.assertEqual(report.declining_pages(rows, [], END), [])

    def test_too_few_weeks(self):
        rows = daily("https://badger.fit/a", [28, 21, 14, 7])
        self.assertEqual(report.declining_pages(rows, [], END), [])

    def test_older_data_ignored(self):
        rows = daily("https://badger.fit/a", [99, 35, 28, 21, 14, 7])
        out = report.declining_pages(rows, [], END)
        self.assertEqual(out[0]["weekly"], [35, 28, 21, 14, 7])


class Overlap(unittest.TestCase):
    def test_two_pages_one_query(self):
        rows = report.merge_query_pages([
            row("5/3/1 app", "https://badger.fit/guides/531-app", clicks=3, position=6.0),
            row("5/3/1 app", "https://badger.fit/tools/531-calculator", clicks=1, position=9.0),
            row("other", "https://badger.fit/x"),
        ])
        out = report.overlaps(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["query"], "5/3/1 app")

    def test_same_page_spellings_are_not_overlap(self):
        rows = report.merge_query_pages([
            row("q", "https://badger.fit/guides/x"),
            row("q", "https://badger.fit/guides/x/?utm_source=ig"),
        ])
        self.assertEqual(report.overlaps(rows), [])


if __name__ == "__main__":
    unittest.main()
