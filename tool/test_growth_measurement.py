"""Tests for the iOS deletions source and the AI-answer probe.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

Neither can be run against the live service in CI (the first needs an Admin
key, the second paid keys), so these pin the parts that decide a number: how
the report's rows fold into installs and deletions, how the walk from request to
file handles an empty or missing request, and what counts as "named".
"""

from __future__ import annotations

import gzip
import importlib.util
import sys
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _ai_probe as probe  # noqa: E402
import _apple_analytics as aa  # noqa: E402

COLS = ["Date", "Event", "Counts", "Territory"]


def tsv(rows: list[tuple]) -> bytes:
    lines = ["\t".join(COLS)] + ["\t".join(str(c) for c in r) for r in rows]
    return gzip.compress(("\n".join(lines) + "\n").encode())


class AnalyticsParsing(unittest.TestCase):
    def test_folds_installs_and_deletions_per_day(self):
        rows = aa.parse_segment(tsv([
            ("2026-11-01", "Install", 4, "US"),
            ("2026-11-01", "Delete", 1, "US"),
            ("2026-11-01", "Delete", 2, "GB"),
            ("2026-11-02", "Install", 3, "US"),
            ("2026-11-02", "Session", 99, "US"),
        ]))
        out = aa.fold(rows)
        self.assertEqual(out["daily"]["2026-11-01"], {"install": 4, "delete": 3})
        self.assertEqual(out["daily"]["2026-11-02"], {"install": 3, "delete": 0})
        self.assertEqual(out["territories"], {"US": 1, "GB": 2})

    def test_event_words_match_on_their_stem(self):
        self.assertEqual(aa._event_kind({"Event": "Installs"}), "install")
        self.assertEqual(aa._event_kind({"Event": "DELETE"}), "delete")
        self.assertIsNone(aa._event_kind({"Event": "Redownload"}))

    def test_reads_an_ungzipped_segment_too(self):
        raw = gzip.decompress(tsv([("2026-11-01", "Delete", 5, "US")]))
        self.assertEqual(aa.parse_segment(raw)[0]["Counts"], "5")

    def test_bad_counts_are_skipped_not_fatal(self):
        out = aa.fold([{"Date": "2026-11-01", "Event": "Delete", "Counts": "x"}])
        self.assertEqual(out["daily"], {})


class AnalyticsFlow(unittest.TestCase):
    conf = {"key_path": "k", "key_id": "i", "issuer_id": "s", "vendor_number": "v"}

    def patched(self, requests, **kw):
        stack = [
            mock.patch.object(aa.src, "_asc_config", return_value=self.conf),
            mock.patch.object(aa.src, "_asc_token", return_value="t"),
            mock.patch.object(aa, "list_requests", return_value=requests),
        ]
        for name, value in kw.items():
            stack.append(mock.patch.object(aa, name, **value))
        return stack

    def run_with(self, stack):
        for p in stack:
            p.start()
        self.addCleanup(mock.patch.stopall)
        return aa.installs_and_deletions(28)

    def test_no_request_says_to_run_setup(self):
        out = self.run_with(self.patched([]))
        self.assertIn("--setup", out["error"])

    def test_request_without_a_report_is_pending_not_an_error(self):
        out = self.run_with(self.patched(
            [{"id": "1", "attributes": {"accessType": "ONGOING"}}],
            _find_reports={"return_value": []}))
        self.assertIn("pending", out)
        self.assertNotIn("error", out)

    def test_end_to_end_with_one_instance(self):
        day = aa.src.utc_window(28)[1].isoformat()
        payload = tsv([(day, "Install", 5, "US"), (day, "Delete", 2, "US")])

        def fake_list(url, token):
            if url.endswith("/instances?filter%5Bgranularity%5D=DAILY&limit=200"):
                return [{"id": "i1", "attributes": {"processingDate": day}}]
            if "/segments" in url:
                return [{"attributes": {"url": "https://example.test/seg"}}]
            raise AssertionError(url)

        stack = self.patched(
            [{"id": "1", "attributes": {"accessType": "ONGOING"}}],
            _find_reports={"return_value": [{"id": "r1"}]},
            _list_all={"side_effect": fake_list})
        stack.append(mock.patch.object(aa.src, "_get_bytes", return_value=payload))
        out = self.run_with(stack)
        self.assertEqual((out["installs"], out["deletes"]), (5, 2))
        self.assertEqual(out["territories"], [("US", 2)])

    def test_sparse_days_are_zero_filled_and_territories_windowed(self):
        today = aa.src.utc_window(28)[1]
        d1, d3 = (today - __import__("datetime").timedelta(days=2)).isoformat(), today.isoformat()
        payload = tsv([(d1, "Delete", 1, "US"), (d3, "Delete", 2, "GB"),
                       ("2020-01-01", "Delete", 50, "FR")])

        def fake_list(url, token):
            if "/instances" in url:
                return [{"id": "i1", "attributes": {"processingDate": d3}}]
            return [{"attributes": {"url": "https://example.test/seg"}}]

        stack = self.patched(
            [{"id": "1", "attributes": {"accessType": "ONGOING"}}],
            _find_reports={"return_value": [{"id": "r1"}]},
            _list_all={"side_effect": fake_list})
        stack.append(mock.patch.object(aa.src, "_get_bytes", return_value=payload))
        out = self.run_with(stack)
        self.assertEqual([n for _, n in out["daily"]], [1, 0, 2])
        self.assertEqual(out["deletes"], 3)
        self.assertEqual(dict(out["territories"]), {"US": 1, "GB": 2})  # no FR

    def test_a_restated_day_is_counted_once(self):
        day = aa.src.utc_window(28)[1].isoformat()
        payload = tsv([(day, "Delete", 4, "US")])

        def fake_list(url, token):
            if "/instances" in url:  # same processing day twice
                return [{"id": "old", "attributes": {"processingDate": day}},
                        {"id": "new", "attributes": {"processingDate": day}}]
            return [{"attributes": {"url": "https://example.test/seg"}}]

        stack = self.patched(
            [{"id": "1", "attributes": {"accessType": "ONGOING"}}],
            _find_reports={"return_value": [{"id": "r1"}]},
            _list_all={"side_effect": fake_list})
        stack.append(mock.patch.object(aa.src, "_get_bytes", return_value=payload))
        self.assertEqual(self.run_with(stack)["deletes"], 4)

    def test_report_name_matches_on_its_stem(self):
        self.assertTrue(aa._is_our_report("App Store Installations and Deletions Standard"))
        self.assertFalse(aa._is_our_report("App Store Downloads"))

    def test_infinite_counts_do_not_crash(self):
        self.assertEqual(aa.fold([{"Date": "2026-11-01", "Event": "Delete",
                                   "Counts": "inf"}])["daily"], {})

    def test_stopped_requests_are_recreated(self):
        stopped = [{"attributes": {"accessType": "ONGOING", "stoppedDueToInactivity": True}}]
        with mock.patch.object(aa, "list_requests", return_value=stopped), \
             mock.patch.object(aa.src, "_get_json", return_value={}):
            self.assertEqual(aa.ensure_requests("t")["created"],
                             ["ONGOING", "ONE_TIME_SNAPSHOT"])

    def test_setup_403_names_the_admin_key(self):
        exc = urllib.error.HTTPError("u", 403, "Forbidden", Message(), None)
        self.assertIn("Admin", aa.setup_error(exc))

    def test_ensure_requests_creates_only_what_is_missing(self):
        calls = []
        with mock.patch.object(aa, "list_requests",
                               return_value=[{"attributes": {"accessType": "ONGOING"}}]), \
             mock.patch.object(aa.src, "_get_json",
                               side_effect=lambda *a, **k: calls.append(a) or {}):
            out = aa.ensure_requests("t")
        self.assertEqual(out, {"created": ["ONE_TIME_SNAPSHOT"], "existing": ["ONGOING"]})
        self.assertEqual(len(calls), 1)


class ProbeDetection(unittest.TestCase):
    def test_names_the_brand_not_the_animal(self):
        self.assertTrue(probe.detect("Try Badger Fit for GZCLP", [])["named"])
        self.assertTrue(probe.detect("Badger.fit is a tracker", [])["named"])
        self.assertFalse(probe.detect("A honey badger is fierce", [])["named"])

    def test_brand_match_needs_a_word_end(self):
        self.assertFalse(probe.detect("Badger Fitness Club", [])["named"])
        self.assertFalse(probe.detect("outfit.badger", [])["named"])

    def test_anthropic_search_hits_are_not_citations_and_pause_turn_errors(self):
        got = probe.parse_anthropic({"content": [
            {"type": "web_search_tool_result", "content": [{"url": "https://badger.fit/"}]},
            {"type": "text", "text": "ok"}]})
        self.assertFalse(probe.detect(got["text"], got["urls"])["cited"])
        with self.assertRaises(ValueError):
            probe.parse_anthropic({"stop_reason": "pause_turn", "content": []})

    def test_same_day_rerun_replaces_instead_of_doubling(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "h.tsv"
            row = {"date": "2026-11-05", "provider": "openai", "model": "m",
                   "prompt": "a", "named": "1", "cited": "0", "error": ""}
            probe.append_history([row, row], path)
            self.assertEqual(probe.latest_summary(path)["providers"]["openai"]["asked"], 1)

    def test_corrupt_history_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "h.tsv"
            path.write_bytes(b"\xff\xfe\x00bad")
            self.assertEqual(probe.latest_summary(path), {"empty": True})

    def test_cited_needs_the_domain_as_a_host(self):
        self.assertTrue(probe.detect("", ["https://badger.fit/help/x"])["cited"])
        self.assertTrue(probe.detect("", ["https://www.badger.fit/"])["cited"])
        self.assertFalse(probe.detect("", ["https://notbadger.fit.example/"])["cited"])

    def test_provider_parsers(self):
        self.assertEqual(probe.parse_perplexity(
            {"choices": [{"message": {"content": "hi"}}], "citations": ["https://a"]}),
            {"text": "hi", "urls": ["https://a"]})
        got = probe.parse_openai({"output": [
            {"type": "web_search_call"},
            {"type": "message", "content": [{"text": "yo", "annotations": [
                {"type": "url_citation", "url": "https://badger.fit/"}]}]}]})
        self.assertEqual(got, {"text": "yo", "urls": ["https://badger.fit/"]})
        got = probe.parse_gemini({"candidates": [{"content": {"parts": [{"text": "x"}]},
            "groundingMetadata": {"groundingChunks": [{"web": {"uri": "u", "title": "badger.fit"}}]}}]})
        self.assertTrue(probe.detect(got["text"], got["urls"])["cited"])
        got = probe.parse_anthropic({"content": [
            {"type": "text", "text": "ok",
             "citations": [{"url": "https://badger.fit/"}]}]})
        self.assertTrue(probe.detect(got["text"], got["urls"])["cited"])


class ProbeRun(unittest.TestCase):
    def test_skips_providers_without_a_key_and_records_errors_apart(self):
        def fake(provider, prompt, key, model):
            if "GZCLP" in prompt:
                raise RuntimeError("boom")
            return {"text": "Use Badger Fit", "urls": []}

        out = probe.run(["GZCLP?", "5/3/1?"], fake,
                        ({"openai": "k"}, dict(probe.DEFAULT_MODELS)))
        self.assertEqual(out["skipped"], ["perplexity", "gemini", "anthropic"])
        failed, ok = out["rows"]
        self.assertEqual((failed["error"], failed["named"]), ("RuntimeError", ""))
        self.assertEqual((ok["error"], ok["named"]), ("", "1"))

    def test_history_round_trip_ignores_errors_in_the_rate(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "h.tsv"
            self.assertEqual(probe.latest_summary(path), {"empty": True})
            rows = [
                {"date": "2026-11-05", "provider": "openai", "model": "m", "prompt": "a",
                 "named": "1", "cited": "0", "error": ""},
                {"date": "2026-11-05", "provider": "openai", "model": "m", "prompt": "b",
                 "named": "", "cited": "", "error": "X"},
                {"date": "2026-10-29", "provider": "openai", "model": "m", "prompt": "a",
                 "named": "0", "cited": "0", "error": ""},
            ]
            probe.append_history(rows, path)
            got = probe.latest_summary(path)
            self.assertEqual(got["date"], "2026-11-05")
            self.assertEqual(got["providers"]["openai"],
                             {"asked": 1, "named": 1, "cited": 0, "errors": 1})

    def test_config_file_supplies_keys_and_env_wins(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "c.json"
            cfg.write_text('{"PERPLEXITY_API_KEY": "file", "openai_model": "gpt-x"}')
            with mock.patch.object(probe, "CONFIG_PATH", str(cfg)), \
                 mock.patch.dict(probe.os.environ, {"PERPLEXITY_API_KEY": "env"}, clear=True):
                keys, models = probe.load_keys()
        self.assertEqual(keys, {"perplexity": "env"})
        self.assertEqual(models["openai"], "gpt-x")


class ReportWiring(unittest.TestCase):
    def test_weekly_report_builds_both_new_panels_without_keys_or_requests(self):
        spec = importlib.util.spec_from_file_location("weekly_report", HERE / "weekly-report.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with mock.patch.object(mod, "installs_and_deletions",
                               return_value={"error": "none yet"}):
            self.assertIn("none yet", mod.ios_deletions_section(28))
        with mock.patch.object(mod, "latest_summary", return_value={"empty": True}):
            self.assertIn("has not run", mod.build_ai_answers())
        summary = {"date": "2026-11-05", "providers": {"openai": {
            "asked": 12, "named": 3, "cited": 1, "errors": 0}}}
        with mock.patch.object(mod, "latest_summary", return_value=summary):
            html = mod.build_ai_answers()
        self.assertIn("3 of 12", html)
        self.assertIn("perplexity", html)  # listed as having no key


if __name__ == "__main__":
    unittest.main()
