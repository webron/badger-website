"""Tests for the GoatCounter vs Search Console tracking check (no network).

Run: python3 -m unittest discover -s tool -p 'test_*.py'
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _tracking_check as tc  # noqa: E402


class CompareTests(unittest.TestCase):
    def test_goatcounter_silent_while_google_sends_clicks_is_flagged(self):
        r = tc.compare(14, 0, "2026-11-01", "2026-11-14")
        self.assertTrue(r["flag"])
        self.assertIn("stopped counting", r["line"])

    def test_partial_loss_below_a_third_is_flagged(self):
        self.assertTrue(tc.compare(12, 3, "a", "b")["flag"])

    def test_exactly_a_third_is_not_flagged(self):
        self.assertFalse(tc.compare(12, 4, "a", "b")["flag"])

    def test_normal_week_is_ok(self):
        r = tc.compare(10, 19, "a", "b")
        self.assertFalse(r["flag"])
        self.assertTrue(r["line"].startswith("Tracking check: OK."))

    def test_too_few_clicks_is_never_flagged(self):
        r = tc.compare(3, 0, "a", "b")
        self.assertFalse(r["flag"])
        self.assertIn("too few", r["line"])

    def test_threshold_boundary_at_min_clicks(self):
        self.assertTrue(tc.compare(tc.MIN_CLICKS, 0, "a", "b")["flag"])


class GoogleVisitsTests(unittest.TestCase):
    def test_sums_every_google_row_and_ignores_others(self):
        rows = [{"name": "Google", "count": 9},
                {"name": "android-app://com.google.android.googlequicksearchbox", "count": 2},
                {"name": "chatgpt.com", "count": 31},
                {"name": "", "count": 40},
                {"name": None, "count": 5}]
        self.assertEqual(tc.google_visits(rows), 11)

    def test_empty(self):
        self.assertEqual(tc.google_visits([]), 0)


class WindowTests(unittest.TestCase):
    def test_window_ends_at_search_console_lag_and_spans_fourteen_days(self):
        start, end = tc._window(date(2026, 11, 16))
        self.assertEqual(end, date(2026, 11, 14))
        self.assertEqual(start, date(2026, 11, 1))
        self.assertEqual((end - start).days + 1, tc.WINDOW_DAYS)


if __name__ == "__main__":
    unittest.main()
