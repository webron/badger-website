"""Tests for the Play source's store-performance reading.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

Google renamed `total_store_performance_*` to `store_performance_*` after
2026-08 and the new file carries listing visitors. Two things went wrong
silently: the report kept asking for the old name and showed nothing new, and
only the window's first and last months were read, so a long window skipped
the months between. These pin the filename fallback and the month walk.
"""

from __future__ import annotations

import sys
import types
import unittest
import urllib.error
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _stats_sources as src  # noqa: E402

PKG = src.PLAY_PACKAGE
NEW = "stats/store_performance/store_performance_%s_%s_traffic_source.csv"
OLD = "stats/store_performance/total_store_performance_%s_%s_traffic_source.csv"
INSTALLS = "stats/installs/installs_%s_%s_overview.csv"


def new_row(day: str, source: str, acq: int, visitors: int) -> dict:
    return {"Date": day, "Traffic source": source,
            "Store listing acquisitions": acq, "Store listing visitors": visitors}


def old_row(day: str, source: str, acq: int) -> dict:
    return {"Date": day, "Traffic source": source, "Total store acquisitions": acq}


def install_row(day: str, n: int = 1) -> dict:
    return {"Date": day, "Daily Device Installs": n, "Daily Device Uninstalls": 0,
            "Active Device Installs": 10}


def not_found(name: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(name, 404, "Not Found", {}, None)


class PlayHarness:
    """Runs play() against a dict of object name -> rows, recording each fetch."""

    def __init__(self, files: dict[str, list[dict]], today: date, days: int):
        self.files, self.today, self.days = files, today, days
        self.fetched: list[str] = []

    def fetch(self, bucket, name, token):
        self.fetched.append(name)
        if name not in self.files:
            raise not_found(name)
        return name  # _play_csv is patched to look the rows up by this

    def run(self) -> dict:
        from datetime import timedelta
        window = (self.today - timedelta(days=self.days - 1), self.today)
        auth = types.ModuleType("_google_auth")
        auth.access_token = lambda *a, **k: "token"
        with mock.patch.dict(sys.modules, {"_google_auth": auth}), \
                mock.patch.object(src.os.path, "exists", return_value=True), \
                mock.patch.object(src, "utc_window", return_value=window), \
                mock.patch.object(src, "_gcs_object", side_effect=self.fetch), \
                mock.patch.object(src, "_play_csv", side_effect=lambda n: self.files[n]):
            return src.play(self.days)


class MonthsBetween(unittest.TestCase):
    def test_includes_every_month_between_the_endpoints(self):
        self.assertEqual(
            src._months_between(date(2026, 8, 20), date(2026, 10, 11)),
            ["202608", "202609", "202610"])

    def test_crosses_a_year_boundary(self):
        self.assertEqual(
            src._months_between(date(2025, 11, 30), date(2026, 2, 1)),
            ["202511", "202512", "202601", "202602"])

    def test_one_month(self):
        self.assertEqual(src._months_between(date(2026, 10, 1), date(2026, 10, 11)), ["202610"])


class TrafficSourceFiles(unittest.TestCase):
    def test_reads_the_new_name_and_reports_visitors(self):
        h = PlayHarness({
            NEW % (PKG, "202610"): [new_row("2026-10-01", "Other", 5, 9),
                                    new_row("2026-10-02", "Search", 1, 4)],
            INSTALLS % (PKG, "202610"): [install_row("2026-10-02")],
        }, today=date(2026, 10, 11), days=11)  # Oct 1 .. Oct 11
        p = h.run()
        self.assertEqual(p["listing_visitors"], 13)
        self.assertEqual(p["listing_acquisitions"], 6)
        self.assertAlmostEqual(p["listing_conversion"], 6 / 13)
        self.assertEqual(dict(p["sources"]), {"Other": 5, "Search": 1})
        self.assertEqual(p["missing"], [])
        self.assertNotIn(OLD % (PKG, "202610"), h.fetched)

    def test_falls_back_to_the_old_name_for_older_months(self):
        h = PlayHarness({
            OLD % (PKG, "202607"): [old_row("2026-07-30", "Other", 2)],
            INSTALLS % (PKG, "202607"): [install_row("2026-07-30")],
        }, today=date(2026, 7, 31), days=5)
        p = h.run()
        self.assertEqual(dict(p["sources"]), {"Other": 2})
        self.assertEqual(p["listing_acquisitions"], 2)
        # The old files never had visitors; that is 0 and an unknown rate, not 0%.
        self.assertEqual(p["listing_visitors"], 0)
        self.assertIsNone(p["listing_conversion"])
        self.assertEqual(p["missing"], [])

    def test_new_name_wins_when_a_month_has_both(self):
        h = PlayHarness({
            NEW % (PKG, "202608"): [new_row("2026-08-01", "Other", 2, 3)],
            OLD % (PKG, "202608"): [old_row("2026-08-01", "Other", 2)],
            INSTALLS % (PKG, "202608"): [install_row("2026-08-01")],
        }, today=date(2026, 8, 5), days=10)
        p = h.run()
        self.assertEqual(p["listing_acquisitions"], 2)  # not 4: no double count
        self.assertEqual(p["listing_visitors"], 3)

    def test_a_month_with_neither_file_is_listed_as_missing_once(self):
        h = PlayHarness({INSTALLS % (PKG, "202610"): [install_row("2026-10-02")]},
                        today=date(2026, 10, 11), days=10)
        p = h.run()
        self.assertEqual(p["missing"], [f"store_performance_{PKG}_202610_traffic_source.csv"])

    def test_old_name_not_reported_missing_while_new_name_exists(self):
        h = PlayHarness({NEW % (PKG, "202610"): [new_row("2026-10-01", "Other", 1, 2)]},
                        today=date(2026, 10, 11), days=10)
        self.assertEqual(h.run()["missing"], [f"installs_{PKG}_202610_overview.csv"])


class MonthIteration(unittest.TestCase):
    def test_a_long_window_reads_the_months_between_its_ends(self):
        h = PlayHarness({
            OLD % (PKG, "202608"): [old_row("2026-08-31", "Other", 1)],
            NEW % (PKG, "202609"): [new_row("2026-09-15", "Search", 7, 20)],
            NEW % (PKG, "202610"): [new_row("2026-10-02", "Other", 3, 8)],
            INSTALLS % (PKG, "202608"): [install_row("2026-08-31")],
            INSTALLS % (PKG, "202609"): [install_row("2026-09-15")],
            INSTALLS % (PKG, "202610"): [install_row("2026-10-02")],
        }, today=date(2026, 10, 11), days=45)  # Aug 28 .. Oct 11
        p = h.run()
        self.assertEqual(p["listing_visitors"], 28)  # September is not skipped
        self.assertEqual(p["listing_acquisitions"], 11)
        self.assertEqual(p["installs"], 3)
        self.assertTrue(any("202609" in n for n in h.fetched))


if __name__ == "__main__":
    unittest.main()
