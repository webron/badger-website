"""Tests for the Search health flagging logic (canned JSON, no network).

Run: python3 -m unittest discover -s tool -p 'test_*.py'
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import unittest.mock
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _search_health as sh  # noqa: E402

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def ms(dt: datetime) -> str:
    return f"/Date({int(dt.timestamp() * 1000)}-0700)/"


class SitemapTests(unittest.TestCase):
    def test_stale_sitemap_flagged(self):
        r = sh.analyze_sitemaps([{"path": "https://badger.fit/sitemap-index.xml",
                                  "lastDownloaded": "2026-09-03T10:00:00Z"}], NOW)
        self.assertTrue(any("65 days ago" in f for f in r["flags"]))

    def test_fresh_sitemap_ok(self):
        r = sh.analyze_sitemaps([{"path": "p", "lastDownloaded": "2026-11-05T10:00:00Z",
                                  "errors": "0", "warnings": "0"}], NOW)
        self.assertEqual(r["flags"], [])

    def test_errors_flagged(self):
        r = sh.analyze_sitemaps([{"path": "p", "lastDownloaded": "2026-11-05T10:00:00Z",
                                  "errors": "2"}], NOW)
        self.assertTrue(any("2 error" in f for f in r["flags"]))

    def test_pending_first_read_is_a_note_not_a_flag(self):
        r = sh.analyze_sitemaps([{"path": "p", "isPending": True,
                                  "lastSubmitted": "2026-11-08T20:00:00Z"}], NOW)
        self.assertEqual(r["flags"], [])
        self.assertEqual(len(r["notes"]), 1)

    def test_never_downloaded_and_none_submitted(self):
        self.assertTrue(sh.analyze_sitemaps([{"path": "p"}], NOW)["flags"])
        self.assertTrue(sh.analyze_sitemaps([], NOW)["flags"])


def inspect(verdict: str, state: str) -> dict:
    return {"inspectionResult": {"indexStatusResult": {"verdict": verdict, "coverageState": state}}}


class InspectionTests(unittest.TestCase):
    def test_not_indexed_listed_and_counted(self):
        r = sh.summarize_inspections({
            "https://badger.fit/": inspect("PASS", "Submitted and indexed"),
            "https://badger.fit/a": inspect("NEUTRAL", "Discovered - currently not indexed"),
            "https://badger.fit/b": {"error": "HTTP 500"},
        })
        self.assertEqual(r["not_indexed"],
                         [("https://badger.fit/a", "Discovered - currently not indexed")])
        self.assertEqual(r["states"]["Submitted and indexed"], 1)
        self.assertEqual(len(r["failed"]), 1)
        self.assertEqual(len(r["flags"]), 2)

    def test_all_indexed_no_flags(self):
        r = sh.summarize_inspections({"u": inspect("PASS", "Submitted and indexed")})
        self.assertEqual(r["flags"], [])


class BingTests(unittest.TestCase):
    def test_stale_feed_and_crawl_summary(self):
        feeds = [{"Url": "https://badger.fit/sitemap-index.xml", "Status": "Success",
                  "LastCrawled": ms(datetime(2026, 6, 10, tzinfo=timezone.utc))}]
        crawl = [{"Date": ms(datetime(2026, 11, 1, tzinfo=timezone.utc)), "CrawledPages": 3,
                  "CrawlErrors": 0, "InIndex": 40},
                 {"Date": ms(datetime(2026, 11, 6, tzinfo=timezone.utc)), "CrawledPages": 9,
                  "CrawlErrors": 1, "InIndex": 44}]
        r = sh.analyze_bing(feeds, crawl, NOW)
        self.assertTrue(any("151 days ago" in f for f in r["flags"]))
        self.assertEqual(r["crawl"], {"date": "2026-11-06", "crawled": 9, "errors": 1, "in_index": 44})

    def test_healthy(self):
        feeds = [{"Url": "u", "Status": "Success",
                  "LastCrawled": ms(datetime(2026, 11, 6, tzinfo=timezone.utc))}]
        self.assertEqual(sh.analyze_bing(feeds, [], NOW)["flags"], [])

    def test_missing_key_is_one_line_not_a_crash(self):
        r = sh.bing_health(NOW, key_path="/nonexistent/bing.key")
        self.assertEqual(r, {"no_key": sh.BING_NO_KEY})

    def test_empty_key_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".key") as fh:
            fh.write("\n"); fh.flush()
            self.assertIn("no_key", sh.bing_health(NOW, key_path=fh.name))

    def test_api_error_is_one_line_without_key(self):
        def boom(url, headers):
            raise RuntimeError("down")
        with tempfile.NamedTemporaryFile("w", suffix=".key") as fh:
            fh.write("SECRETKEY\n"); fh.flush()
            r = sh.bing_health(NOW, key_path=fh.name, get_json=boom)
        self.assertIn("error", r)
        self.assertNotIn("SECRETKEY", r["error"])

    def test_key_scrubbed_when_exception_carries_url(self):
        def boom(url, headers):
            raise RuntimeError(url)
        with tempfile.NamedTemporaryFile("w", suffix=".key") as fh:
            fh.write("SECRET/KEY+1\n"); fh.flush()
            r = sh.bing_health(NOW, key_path=fh.name, get_json=boom)
        self.assertIn("error", r)
        self.assertNotIn("SECRET", r["error"])
        self.assertNotIn("SECRET%2FKEY", r["error"])
        self.assertIn("apikey=***", r["error"])


def placeholder_feed(submitted: datetime, **kw) -> dict:
    f = {"Url": "https://badger.fit/sitemap-index.xml",
         "Status": "The page is not accessible", "FileSize": 0, "Type": "NA",
         "Submitted": ms(submitted), "LastCrawled": ms(submitted)}
    f.update(kw)
    return f


class BingPlaceholderTests(unittest.TestCase):
    def test_fresh_placeholder_is_a_note(self):
        r = sh.analyze_bing([placeholder_feed(datetime(2026, 11, 7, tzinfo=timezone.utc))], [], NOW)
        self.assertEqual(r["flags"], [])
        self.assertEqual(r["notes"], ["Bing sitemap https://badger.fit/sitemap-index.xml: "
                                      "pending first fetch (submitted 2026-11-07)"])

    def test_old_placeholder_is_flagged(self):
        r = sh.analyze_bing([placeholder_feed(datetime(2026, 10, 1, tzinfo=timezone.utc))], [], NOW)
        self.assertEqual(len(r["flags"]), 1)
        self.assertIn("38 days ago", r["flags"][0])
        self.assertEqual(r["notes"], [])

    def test_real_failure_still_flagged(self):
        sub = datetime(2026, 11, 1, tzinfo=timezone.utc)
        f = placeholder_feed(sub, FileSize=123, Type="Sitemap")
        r = sh.analyze_bing([f], [], NOW)
        self.assertTrue(any("status" in x for x in r["flags"]))


class ParseMsDateTests(unittest.TestCase):
    def test_plain_and_offset(self):
        self.assertEqual(sh.parse_ms_date("/Date(1315781995040)/"),
                         datetime(2011, 9, 11, 22, 59, 55, 40000, tzinfo=timezone.utc))
        self.assertEqual(sh.parse_ms_date("/Date(1315781995040-0700)/"),
                         sh.parse_ms_date("/Date(1315781995040)/"))

    def test_never_is_none(self):
        self.assertIsNone(sh.parse_ms_date("/Date(-62135596800000)/"))

    def test_bad_input_is_none(self):
        for raw in (None, "", "garbage", "/Date(abc)/"):
            self.assertIsNone(sh.parse_ms_date(raw))


class GoogleHealthTests(unittest.TestCase):
    def test_all_inspections_failed(self):
        def boom(*a, **k):
            raise RuntimeError("quota")
        with tempfile.NamedTemporaryFile("w") as fh:
            old = sh.SC_KEY_PATH
            sh.SC_KEY_PATH = fh.name
            try:
                with unittest.mock.patch.object(sh, "_fetch", boom):
                    r = sh.google_health(NOW, get_json=lambda u, h: {"sitemap": []},
                                         token_fn=lambda *a: "t",
                                         urls_fn=lambda: ["https://badger.fit/", "https://badger.fit/a"],
                                         sleep=lambda s: None)
            finally:
                sh.SC_KEY_PATH = old
        self.assertIn("failed for every URL", r["inspection"]["error"])
        self.assertIn("quota", r["inspection"]["error"])


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "weekly_report", Path(__file__).resolve().parent / "weekly-report.py")
        cls.wr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.wr)

    def test_flags_come_before_ok_lines(self):
        google = {"sitemaps": {"flags": ["stale"], "sitemaps": []},
                  "inspection": {"flags": [], "total": 3, "states": {}, "not_indexed": [], "failed": []}}
        flags, oks = self.wr.search_health_lines(google, {"no_key": sh.BING_NO_KEY})
        self.assertEqual(flags, ["stale"])
        self.assertIn(sh.BING_NO_KEY, oks)

    def test_not_indexed_flags_capped_at_ten(self):
        ni = [(f"https://badger.fit/{i}", "x") for i in range(13)]
        google = {"sitemaps": {"flags": [], "sitemaps": []},
                  "inspection": {"flags": ["13 URL(s) not indexed by Google."], "total": 20,
                                 "states": {"x": 13}, "not_indexed": ni, "failed": []}}
        flags, _ = self.wr.search_health_lines(google, {"no_key": "x"})
        self.assertEqual(len([f for f in flags if f.startswith("Not indexed:")]), 10)
        self.assertIn("...and 3 more not indexed.", flags)
        self.assertIn("13 URL(s) not indexed by Google.", flags)

    def test_build_search_health_exception_path(self):
        def boom():
            raise ValueError("x")
        with unittest.mock.patch.object(self.wr, "google_health", boom):
            out = self.wr.build_search_health()
        self.assertIn("Search health failed (ValueError)", out)

    def test_google_error_is_a_single_flag(self):
        flags, _ = self.wr.search_health_lines({"error": "auth failed"}, {"no_key": "x"})
        self.assertEqual(flags, ["auth failed"])


if __name__ == "__main__":
    unittest.main()
