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

    def test_near_total_loss_is_flagged(self):
        self.assertTrue(tc.compare(14, 1, "a", "b")["flag"])

    def test_normal_noise_at_one_click_a_day_is_not_flagged(self):
        # 14 clicks, healthy GoatCounter at a low share: 2-3 Google visits.
        self.assertFalse(tc.compare(14, 2, "a", "b")["flag"])
        self.assertFalse(tc.compare(14, 3, "a", "b")["flag"])

    def test_normal_week_is_ok(self):
        r = tc.compare(18, 20, "a", "b")
        self.assertFalse(r["flag"])
        self.assertTrue(r["line"].startswith("Tracking check: OK."))

    def test_too_few_clicks_is_never_flagged(self):
        for clicks in range(0, 10):
            r = tc.compare(clicks, 0, "a", "b")
            self.assertFalse(r["flag"], clicks)
            self.assertIn("too few", r["line"])

    def test_ten_clicks_and_zero_visits_is_the_first_alarm(self):
        self.assertTrue(tc.compare(10, 0, "a", "b")["flag"])

    def test_false_alarm_rate_on_healthy_counter_is_below_one_percent(self):
        # Healthy counter at the assumed share: the chance of a flag, summed
        # over every count that would be flagged, stays under ALARM_P.
        for clicks in range(10, 40):
            lam = clicks * tc.EXPECTED_SHARE
            flagged = [k for k in range(clicks + 1)
                       if tc.compare(clicks, k, "a", "b")["flag"]]
            p = tc.poisson_cdf(max(flagged), lam) if flagged else 0.0
            self.assertLess(p, tc.ALARM_P, clicks)


class PoissonTests(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(tc.poisson_cdf(0, 2.0), 0.1353352832, places=8)
        self.assertAlmostEqual(tc.poisson_cdf(2, 3.0), 0.4231900811, places=8)


class GoogleVisitsTests(unittest.TestCase):
    def test_sums_google_search_rows_only(self):
        rows = [{"name": "Google", "count": 9},
                {"name": "android-app://com.google.android.googlequicksearchbox", "count": 2},
                {"name": "www.google.de", "count": 1},
                {"name": "mail.google.com", "count": 4},
                {"name": "docs.google.com", "count": 3},
                {"name": "chatgpt.com", "count": 31},
                {"name": "", "count": 40},
                {"name": None, "count": 5}]
        self.assertEqual(tc.google_visits(rows), 12)

    def test_empty(self):
        self.assertEqual(tc.google_visits([]), 0)


class ZeroRunTests(unittest.TestCase):
    def test_two_empty_complete_days_are_flagged(self):
        daily = [("11-10", 13), ("11-11", 0), ("11-12", 0), ("11-13", 0)]
        self.assertEqual(tc.zero_run(daily), ["11-11", "11-12"])

    def test_today_in_progress_is_ignored(self):
        daily = [("11-11", 5), ("11-12", 0), ("11-13", 0)]
        self.assertEqual(tc.zero_run(daily), [])

    def test_one_empty_day_is_normal(self):
        self.assertEqual(tc.zero_run([("a", 3), ("b", 0), ("c", 4), ("d", 0)]), [])

    def test_old_run_followed_by_traffic_is_not_flagged(self):
        daily = [("a", 0), ("b", 0), ("c", 0), ("d", 6), ("e", 2)]
        self.assertEqual(tc.zero_run(daily), [])

    def test_line_names_the_range(self):
        line = tc.zero_run_line(["2026-11-13", "2026-11-14"])
        self.assertIn("2026-11-13 to 2026-11-14", line)


class DailyViewsTests(unittest.TestCase):
    def test_drops_days_after_today_and_subtracts_events(self):
        from _stats_sources import daily_views
        stats = [{"day": "2026-11-15", "daily": 5}, {"day": "2026-11-16", "daily": 2},
                 {"day": "2026-11-17", "daily": 0}]
        self.assertEqual(daily_views(stats, {"2026-11-15": 1}, "2026-11-16"),
                         [("2026-11-15", 4), ("2026-11-16", 2)])


class WindowTests(unittest.TestCase):
    def test_window_ends_at_search_console_lag_and_spans_the_window(self):
        start, end = tc._window(date(2026, 11, 16))
        self.assertEqual(end, date(2026, 11, 14))
        self.assertEqual(start, date(2026, 10, 18))
        self.assertEqual((end - start).days + 1, tc.WINDOW_DAYS)


if __name__ == "__main__":
    unittest.main()
