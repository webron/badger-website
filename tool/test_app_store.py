"""Tests for the App Store source.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

The sales-report path is the one part of the weekly report that cannot be
exercised against the live API without a vendor account's numbers, and it is
also the part with real parsing in it: a gzipped tab-separated file whose
product-type codes decide whether a row is a download or an update. These pin
that, and pin the rule that stops a quiet week from hiding itself behind
Apple's publishing lag.
"""

from __future__ import annotations

import gzip
import io
import sys
import unittest
import urllib.error
from datetime import timedelta
from email.message import Message
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _stats_sources as src  # noqa: E402
from _apple_auth import _der_to_jose  # noqa: E402

COLUMNS = [
    "Provider", "Provider Country", "SKU", "Developer", "Title", "Version",
    "Product Type Identifier", "Units", "Developer Proceeds", "Begin Date",
    "End Date", "Customer Currency", "Country Code", "Currency of Proceeds",
    "Apple Identifier", "Customer Price", "Promo Code", "Parent Identifier",
    "Subscription", "Period", "Category", "CMB", "Device",
    "Supported Platforms", "Proceeds Reason", "Preserved Pricing", "Client",
    "Order Type",
]


def report(rows: list[dict]) -> bytes:
    """A gzipped Apple sales report carrying the given rows."""
    lines = ["\t".join(COLUMNS)]
    for row in rows:
        lines.append("\t".join(str(row.get(c, "")) for c in COLUMNS))
    return gzip.compress(("\n".join(lines) + "\n").encode("utf-8"))


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class SalesReportParsing(unittest.TestCase):
    def test_reads_a_gzipped_tab_separated_report(self):
        payload = report([
            {"Product Type Identifier": "1F", "Units": "3", "Country Code": "US",
             "Device": "iPhone"},
        ])
        with mock.patch.object(src.urllib.request, "urlopen",
                               return_value=FakeResponse(payload)):
            rows = src._sales_report(src.date(2026, 9, 9), "12345678", "tok")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Units"], "3")
        self.assertEqual(rows[0]["Country Code"], "US")

    def test_a_404_is_no_report_rather_than_a_failure(self):
        error = urllib.error.HTTPError("http://x", 404, "Not Found", Message(),
                                       io.BytesIO(b""))
        with mock.patch.object(src.urllib.request, "urlopen", side_effect=error):
            self.assertIsNone(src._sales_report(src.date(2026, 9, 9), "1", "tok"))

    def test_updates_are_the_product_types_starting_with_seven(self):
        self.assertTrue(src._is_update({"Product Type Identifier": "7F"}))
        self.assertTrue(src._is_update({"Product Type Identifier": "7T"}))
        for code in ("1F", "1T", "1E", "1EU", "F1"):
            self.assertFalse(src._is_update({"Product Type Identifier": code}), code)

    def test_a_missing_or_broken_unit_count_is_zero_not_a_crash(self):
        self.assertEqual(src._units({}), 0)
        self.assertEqual(src._units({"Units": ""}), 0)
        self.assertEqual(src._units({"Units": "not a number"}), 0)
        self.assertEqual(src._units({"Units": "12"}), 12)


class AppStoreAggregation(unittest.TestCase):
    def setUp(self):
        self.conf = {"key_path": "/x.p8", "key_id": "K", "issuer_id": "I",
                     "vendor_number": "12345678"}
        _, self.today = src.utc_window(1)

    def run_with(self, per_day, days=7):
        # The release-date floor is a real calendar date, so leave it out of
        # the window arithmetic these tests are actually about.
        with mock.patch.object(src, "_asc_config", return_value=self.conf), \
             mock.patch.object(src, "ASC_FIRST_RELEASE", src.date(2020, 1, 1)), \
             mock.patch.object(src, "_asc_token", return_value="tok"), \
             mock.patch.object(src, "_sales_report",
                               side_effect=lambda day, v, t: per_day(day)):
            return src.app_store(days)

    def test_downloads_and_updates_are_counted_apart(self):
        rows = [
            {"Product Type Identifier": "1F", "Units": "2", "Country Code": "US",
             "Device": "iPhone"},
            {"Product Type Identifier": "1T", "Units": "1", "Country Code": "GB",
             "Device": "iPad"},
            {"Product Type Identifier": "7F", "Units": "9", "Country Code": "US",
             "Device": "iPhone"},
        ]
        out = self.run_with(lambda day: rows)
        # Seven days, three downloads each, and the updates stay out of the
        # download figure and out of the country split.
        self.assertEqual(out["downloads"], 21)
        self.assertEqual(out["updates"], 63)
        self.assertEqual(dict(out["countries"]), {"US": 14, "GB": 7})
        self.assertEqual(dict(out["devices"]), {"iPhone": 14, "iPad": 7})

    def test_recent_days_apple_has_not_published_are_left_out(self):
        # Nothing published at all: the two most recent days are pending, the
        # rest are real zeros.
        out = self.run_with(lambda day: None)
        self.assertEqual(out["pending_days"], 2)
        self.assertEqual(out["downloads"], 0)
        self.assertEqual(out["end"],
                         (self.today - timedelta(days=2)).isoformat())

    def test_the_asked_for_window_survives_the_pending_trim(self):
        """The lag is normal, not an edge case, so it must not shorten the run.

        Apple is behind by a day or two on every ordinary run. When those days
        were simply dropped, a 35-day request came back as 33, the weekly
        buckets fell from five to four, and the page went on claiming it was
        measuring against four previous weeks while showing three.
        """
        rows = [{"Product Type Identifier": "1F", "Units": "1",
                 "Country Code": "US", "Device": "iPhone"}]
        published = self.today - timedelta(days=2)

        out = self.run_with(lambda day: None if day > published else rows, days=35)
        self.assertEqual(out["pending_days"], 2)
        self.assertEqual(len(out["daily"]), 35)
        self.assertEqual(out["downloads"], 35)
        self.assertEqual(out["end"], published.isoformat())

        # And with nothing pending, the window is still exactly what was asked
        # for rather than the padded one.
        caught_up = self.run_with(lambda day: rows, days=35)
        self.assertEqual(caught_up["pending_days"], 0)
        self.assertEqual(len(caught_up["daily"]), 35)
        self.assertEqual(caught_up["end"], self.today.isoformat())

    def test_totals_cover_the_same_days_the_sparkline_draws(self):
        """The padded days are fetched, then must not leak into the figures."""
        rows = [{"Product Type Identifier": "1F", "Units": "1",
                 "Country Code": "US", "Device": "iPhone"},
                {"Product Type Identifier": "7F", "Units": "2",
                 "Country Code": "US", "Device": "iPhone"}]
        out = self.run_with(lambda day: rows, days=7)
        self.assertEqual(len(out["daily"]), 7)
        self.assertEqual(out["downloads"], 7)
        self.assertEqual(out["updates"], 14)
        self.assertEqual(dict(out["countries"]), {"US": 7})
        self.assertEqual(dict(out["devices"]), {"iPhone": 7})

    def test_an_older_quiet_day_stays_in_as_a_zero(self):
        quiet = self.today - timedelta(days=4)

        def per_day(day):
            if day == quiet:
                return None
            return [{"Product Type Identifier": "1F", "Units": "1",
                     "Country Code": "US", "Device": "iPhone"}]

        out = self.run_with(per_day)
        self.assertEqual(out["pending_days"], 0)
        self.assertIn((quiet.isoformat(), 0), out["daily"])
        self.assertEqual(out["downloads"], 6)

    def test_days_before_the_app_shipped_are_not_requested(self):
        released = self.today - timedelta(days=3)
        asked = []

        def per_day(day):
            asked.append(day)
            return None

        with mock.patch.object(src, "_asc_config", return_value=self.conf), \
             mock.patch.object(src, "ASC_FIRST_RELEASE", released), \
             mock.patch.object(src, "_asc_token", return_value="tok"), \
             mock.patch.object(src, "_sales_report",
                               side_effect=lambda day, v, t: per_day(day)):
            src.app_store(30)
        self.assertEqual(min(asked), released)

    def test_a_bare_timeout_is_reported_rather_than_thrown(self):
        """TimeoutError is not a URLError.

        An uncaught one here would take down the whole weekly report, losing
        the panels that had already rendered, on an unattended run with nobody
        watching.
        """
        def per_day(day):
            raise TimeoutError("timed out")

        out = self.run_with(per_day)
        self.assertIn("unreachable", out["error"])

    def test_a_missing_vendor_number_says_so_instead_of_calling_apple(self):
        with mock.patch.object(src, "_asc_config",
                               return_value={**self.conf, "vendor_number": ""}), \
             mock.patch.object(src, "_sales_report") as fetch:
            out = src.app_store(7)
        self.assertIn("vendor number", out["error"])
        fetch.assert_not_called()


class AscConfig(unittest.TestCase):
    """The reports key is deliberately separate from the publishing one.

    Apple refuses report downloads to the key fastlane publishes with, and a
    key with a reporting role cannot necessarily read apps and reviews, so one
    credential for both would only move which section comes back empty.
    """

    def write(self, body: str):
        import json as _json
        import tempfile
        path = Path(tempfile.mkdtemp()) / "app-store.json"
        path.write_text(body if isinstance(body, str) else _json.dumps(body))
        env = path.parent / ".env"
        env.write_text("ASC_KEY_ID=PUBLISH\nASC_ISSUER_ID=ISSUER\n"
                       "MATCH_PASSWORD=not a key id\n")
        key = path.parent / "asc_api_key.p8"
        key.write_text("")
        return path, env, key

    def config(self, stored: dict, reports: bool):
        path, env, key = self.write({**stored})
        with mock.patch.object(src, "ASC_CONFIG_PATH", str(path)), \
             mock.patch.object(src, "ASC_ENV_PATH", str(env)), \
             mock.patch.object(src, "ASC_KEY_PATH", str(key)):
            return src._asc_config(reports=reports)

    def test_the_publishing_key_is_the_default_for_both(self):
        stored = {"vendor_number": "94483508"}
        for reports in (False, True):
            conf = self.config(stored, reports)
            self.assertEqual(conf["key_id"], "PUBLISH")
            self.assertEqual(conf["vendor_number"], "94483508")

    def test_a_reports_key_overrides_only_the_reports_side(self):
        stored = {"vendor_number": "1", "reports_key_id": "REPORTS",
                  "reports_issuer_id": "OTHER"}
        self.assertEqual(self.config(stored, reports=False)["key_id"], "PUBLISH")
        conf = self.config(stored, reports=True)
        self.assertEqual(conf["key_id"], "REPORTS")
        self.assertEqual(conf["issuer_id"], "OTHER")

    def test_the_dotenv_password_is_not_mistaken_for_a_key_id(self):
        conf = self.config({"vendor_number": "1"}, reports=False)
        self.assertEqual(conf["key_id"], "PUBLISH")
        self.assertNotIn("not a key id", conf.values())


class AppleJwtSignature(unittest.TestCase):
    def test_der_integers_are_stripped_and_repadded_to_thirty_two_bytes(self):
        # r has a leading zero byte DER adds to keep it positive; s is short.
        r = b"\x00" + b"\xff" * 32
        s = b"\x01\x02"
        der = (b"\x30" + bytes([2 + len(r) + 2 + len(s)])
               + b"\x02" + bytes([len(r)]) + r
               + b"\x02" + bytes([len(s)]) + s)
        raw = _der_to_jose(der)
        self.assertEqual(len(raw), 64)
        self.assertEqual(raw[:32], b"\xff" * 32)
        self.assertEqual(raw[32:], b"\x00" * 30 + b"\x01\x02")

    def test_a_signature_that_is_not_der_is_rejected(self):
        with self.assertRaises(ValueError):
            _der_to_jose(b"\x99\x01\x02")


if __name__ == "__main__":
    unittest.main()
