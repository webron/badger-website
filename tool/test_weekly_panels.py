"""Tests for the weekly report's panel isolation, the AI failure reasons and
the Play country column.

Run: python3 -m unittest discover -s tool -p 'test_*.py'
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _ai_probe as probe  # noqa: E402
import _stats_sources as src  # noqa: E402

_spec = importlib.util.spec_from_file_location("weekly_report", HERE / "weekly-report.py")
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)


def boom(*args, **kwargs):
    raise RuntimeError("unexpected")


class PanelIsolation(unittest.TestCase):
    def test_a_crashing_app_store_downloads_call_leaves_the_rest_of_the_panel(self):
        ratings = {"error": "no ratings today"}
        with mock.patch.object(report, "app_store", side_effect=boom), \
             mock.patch.object(report, "app_store_listing", return_value={"error": "x"}), \
             mock.patch.object(report, "app_store_ratings", return_value=ratings), \
             mock.patch.object(report, "app_store_reviews", return_value={"error": "y"}), \
             mock.patch.object(report, "installs_and_deletions", return_value={"error": "z"}):
            html = report.build_app_store(35)
        self.assertIn("App Store downloads failed (RuntimeError).", html)
        self.assertIn("no ratings today", html)
        self.assertIn("Written reviews", html)

    def test_every_source_in_the_other_panels_is_guarded(self):
        for name, build, args in [
            ("goatcounter", report.build_goatcounter, (35,)),
            ("search_console", report.build_search_console, (35,)),
            ("play", report.build_play, (35,)),
        ]:
            with self.subTest(name=name), mock.patch.object(report, name, side_effect=boom):
                self.assertIn("RuntimeError", build(*args))

    def test_play_quality_crash_keeps_the_play_panel(self):
        play = {"installs": 1, "active": 1, "uninstalls": 0, "daily": [], "start": "a",
                "end": "b", "missing": [], "listing_conversion": None,
                "listing_visitors": 0, "listing_acquisitions": 0, "sources": []}
        with mock.patch.object(report, "play", return_value=play), \
             mock.patch.object(report, "play_ratings", return_value={"error": "r"}), \
             mock.patch.object(report, "play_quality", side_effect=boom):
            html = report.build_play(35)
        self.assertIn("Play quality stats failed (RuntimeError).", html)
        self.assertIn("Ratings and reviews", html)

    def test_a_crashing_rival_watch_is_an_error_panel(self):
        with mock.patch.object(report, "build_rivals", side_effect=boom):
            self.assertIn("Rival watch failed (RuntimeError).", report.build_rivals_safe())


HEADER = "date\tprovider\tmodel\tprompt\tnamed\tcited\terror\n"


def history(rows: list[str]) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "h.tsv"
    tmp.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return tmp


class AiFailureReasons(unittest.TestCase):
    def test_summary_lists_the_most_common_error_codes_first(self):
        path = history(
            [f"2026-11-09\tgemini\tg\tp{i}\t\t\t429" for i in range(3)]
            + ["2026-11-09\tgemini\tg\tp9\t\t\t404",
               "2026-11-09\topenai\to\tp1\t1\t1\t"])
        s = probe.latest_summary(path)["providers"]
        self.assertEqual(s["gemini"]["errors"], 4)
        self.assertEqual(s["gemini"]["error_codes"], ["429", "404"])
        self.assertEqual(s["openai"]["error_codes"], [])

    def panel(self, rows):
        summary = probe.latest_summary(history(rows))
        with mock.patch.object(report, "latest_summary", return_value=summary):
            return report.build_ai_answers()

    def test_panel_shows_the_code_and_the_429_note(self):
        html = self.panel([f"2026-11-09\tgemini\tg\tp{i}\t\t\t429" for i in range(12)])
        self.assertIn("12 (HTTP 429)", html)
        self.assertIn("429 means the provider refused for quota or rate limits", html)

    def test_a_timeout_shows_by_name_and_no_429_note(self):
        html = self.panel(["2026-11-09\tgemini\tg\tp1\t\t\tTimeoutError"])
        self.assertIn("1 (TimeoutError)", html)
        self.assertNotIn("429 means", html)

    def test_429_note_shows_even_when_429_is_not_a_top_code(self):
        rows = ([f"2026-11-09\tgemini\tg\tp{i}\t\t\tTimeoutError" for i in range(3)]
                + [f"2026-11-09\tgemini\tg\tq{i}\t\t\t404" for i in range(2)]
                + [f"2026-11-09\tgemini\tg\tr{i}\t\t\t429" for i in range(2)])
        summary = probe.latest_summary(history(rows))
        self.assertEqual(summary["providers"]["gemini"]["error_codes"], ["TimeoutError", "404"])
        with mock.patch.object(report, "latest_summary", return_value=summary):
            html = report.build_ai_answers()
        self.assertIn("7 (TimeoutError, HTTP 404)", html)
        self.assertIn("429 means the provider refused", html)

    def test_a_csv_error_reads_as_no_history(self):
        with mock.patch.object(probe.csv, "DictReader", side_effect=probe.csv.Error("bad")):
            self.assertEqual(probe.latest_summary(history(["x"])), {"empty": True})

    def test_a_crashing_ai_panel_is_an_error_panel(self):
        with mock.patch.object(report, "build_ai_answers", side_effect=boom):
            self.assertIn("AI answers failed (RuntimeError).", report.build_ai_answers_safe())

    def test_no_failures_shows_a_bare_zero(self):
        html = self.panel(["2026-11-09\topenai\to\tp1\t1\t1\t"])
        self.assertIn("<td>0</td>", html)


COUNTRY_ROWS = [
    {"Date": "2026-10-27", "Country": "IT", "Daily Average Rating": "5.0", "Total Average Rating": "5.0"},
    {"Date": "2026-10-28", "Country": "IT", "Daily Average Rating": "0.0", "Total Average Rating": "5.0"},
    {"Date": "2026-10-27", "Country": "US", "Daily Average Rating": "4.0", "Total Average Rating": "4.5"},
    {"Date": "2026-10-28", "Country": "US", "Daily Average Rating": "0.0", "Total Average Rating": "4.5"},
    {"Date": "2026-10-28", "Country": "FR", "Daily Average Rating": "0.0", "Total Average Rating": "0.0"},
]


class PlayCountries(unittest.TestCase):
    def test_countries_with_any_nonzero_total_and_their_latest_value(self):
        totals, _ = src._rating_countries(COUNTRY_ROWS)
        self.assertEqual(totals, [("IT", 5.0), ("US", 4.5)])

    def test_days_list_only_countries_with_a_nonzero_daily_value(self):
        _, by_day = src._rating_countries(COUNTRY_ROWS)
        self.assertEqual(by_day, {"2026-10-27": ["IT", "US"]})

    def test_play_files_days_in_pacific_time(self):
        # 05:22 UTC on the 28th is the evening of the 27th in Pacific time.
        row = {"submitted": "2026-10-28T05:22:04Z"}
        _, by_day = src._rating_countries(COUNTRY_ROWS)
        self.assertEqual(src._play_countries_for(row, by_day), ["IT", "US"])

    def test_no_match_and_unfiled_reviews_are_unknown(self):
        _, by_day = src._rating_countries(COUNTRY_ROWS)
        self.assertEqual(src._play_countries_for({"submitted": "2026-11-02T10:00:00Z"}, by_day), [])
        self.assertEqual(src._play_countries_for({"submitted": ""}, by_day), [])

    def ratings(self, country_files_fail=False):
        review = {"Star Rating": "5", "Review Submit Date and Time": "2026-10-28T05:22:04Z",
                  "Review Last Update Date and Time": "2026-10-28T05:22:04Z",
                  "Review Link": "x?reviewId=abc&c=1", "Reviewer Language": "en",
                  "App Version Name": "1.0"}
        country = [dict(r) for r in COUNTRY_ROWS if r["Country"] != "US"]

        def csv_for(raw, *a):
            return raw

        def obj(bucket, name, token):
            return name

        def parse(name):
            if "_country" in name:
                if country_files_fail:
                    raise ValueError("bad file")
                return country
            return [review] if name.startswith("reviews/") else []

        def lister(bucket, prefix, token):
            return {"reviews/": ["reviews/reviews_fit.badger.app_202610.csv"],
                    "stats/ratings/": ["stats/ratings/ratings_fit.badger.app_202610_country.csv"]}[prefix]

        with mock.patch("os.path.exists", return_value=True), \
             mock.patch("_google_auth.access_token", return_value="tok"), \
             mock.patch.object(src, "_gcs_list", side_effect=lister), \
             mock.patch.object(src, "_gcs_object", side_effect=obj), \
             mock.patch.object(src, "_play_csv", side_effect=parse), \
             mock.patch.object(src, "_play_api_reviews", return_value=[]), \
             mock.patch.object(src, "utc_window", return_value=(
                 src.date(2026, 10, 1), src.date(2026, 11, 1))):
            return src.play_ratings(35)

    def test_play_ratings_attaches_countries_and_the_summary(self):
        out = self.ratings()
        self.assertEqual(out["by_country"], [("IT", 5.0)])
        self.assertEqual(out["ratings"][0]["countries"], ["IT"])

    def test_country_file_failure_keeps_the_ratings(self):
        out = self.ratings(country_files_fail=True)
        self.assertIn("country files could not be read (ValueError)", out["country_note"])
        self.assertEqual(len(out["ratings"]), 1)

    def section(self, **extra):
        r = {"average": 5.0, "lifetime": 1, "unfiled": 0, "this_week": 0, "note": "",
             "by_country": [("US", 5.0), ("GB", 5.0)], "country_note": "",
             "ratings": [{"rating": 5, "date": "2026-10-28", "updated": "2026-10-28",
                          "version": "1.0", "text": "", "fresh": False, "language": "en",
                          "countries": ["IT", "US"]}]}
        r.update(extra)
        with mock.patch.object(report, "play_ratings", return_value=r):
            return report.play_ratings_section(35)

    def test_section_shows_summary_country_column_and_language(self):
        html = self.section()
        self.assertIn("Ratings by country: US 5.0, GB 5.0", html)
        self.assertIn("<th>Country</th>", html)
        self.assertIn("IT or US", html)
        self.assertIn('<span class="empty">en</span>', html)

    def test_section_says_not_known_when_no_country_matches(self):
        html = self.section(ratings=[{"rating": 5, "date": "d", "updated": "d", "version": "",
                                      "text": "", "fresh": True, "language": "",
                                      "countries": []}])
        self.assertIn("not known", html)

    def test_section_still_renders_with_a_country_note(self):
        html = self.section(by_country=[], country_note="Play's country files could not be read (X), so countries are missing.")
        self.assertIn("countries are missing", html)
        self.assertIn("not known", html)
        self.assertIn("Stars only", html)


if __name__ == "__main__":
    unittest.main()
