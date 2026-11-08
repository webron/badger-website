"""Tests for the iOS deletions source and the AI-answer probe.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

Neither can be run against the live service in CI (the first needs an Admin
key, the second paid keys), so these pin the parts that decide a number: how
the report's rows fold into installs and deletions, how the walk from request to
file handles an empty or missing request, and what counts as "named".
"""

from __future__ import annotations

import csv
import gzip
import json
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


class ProbeSources(unittest.TestCase):
    def test_strips_tracking_and_www_and_dedupes_in_order(self):
        got = probe.extract_sources([
            "https://www.Example.com/best-apps?utm_source=openai&id=3#top",
            "https://example.com/other",
            "https://www.example.com/best-apps?id=3&utm_source=x",
        ])
        self.assertEqual(got, [
            {"url": "https://www.example.com/best-apps?id=3", "domain": "example.com"},
            {"url": "https://example.com/other", "domain": "example.com"}])

    def test_gemini_redirects_are_dropped_and_titles_give_the_domain(self):
        got = probe.extract_sources([
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "reddit.com",
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/def", "alternativeto.net"])
        self.assertEqual(got, [{"url": "", "domain": "reddit.com"},
                               {"url": "", "domain": "alternativeto.net"}])

    def test_a_bare_domain_is_redundant_next_to_a_url_from_it(self):
        got = probe.extract_sources(["reddit.com", "https://www.reddit.com/r/x/comments/1"])
        self.assertEqual([i["domain"] for i in got], ["reddit.com"])
        self.assertTrue(got[0]["url"])

    def test_junk_is_ignored(self):
        self.assertEqual(probe.extract_sources(["", None, "not a url", "ftp://x.org/a"]), [])

    def test_each_provider_parser_feeds_sources(self):
        oa = probe.parse_openai({"output": [{"type": "message", "content": [
            {"text": "t", "annotations": [
                {"type": "url_citation", "url": "https://a.com/x?utm_source=openai"},
                {"type": "file_citation", "url": "https://skip.com"}]}]}]})
        self.assertEqual(probe.extract_sources(oa["urls"]),
                         [{"url": "https://a.com/x", "domain": "a.com"}])
        pp = probe.parse_perplexity({"choices": [{"message": {"content": "t"}}],
                                     "citations": ["https://b.org/p"]})
        self.assertEqual(probe.extract_sources(pp["urls"])[0]["domain"], "b.org")
        an = probe.parse_anthropic({"content": [{"type": "text", "text": "t",
                                                 "citations": [{"url": "https://c.net/q"}]}]})
        self.assertEqual(probe.extract_sources(an["urls"])[0]["domain"], "c.net")

    def test_run_collects_sources_per_answer_and_skips_failures(self):
        def fake(provider, prompt, key, model):
            if "bad" in prompt:
                raise RuntimeError("boom")
            return {"text": "x", "urls": ["https://a.com/1", "https://a.com/1"]}

        out = probe.run(["ok", "bad"], fake, ({"openai": "k"}, dict(probe.DEFAULT_MODELS)))
        self.assertEqual(len(out["sources"]), 1)
        self.assertEqual((out["sources"][0]["provider"], out["sources"][0]["prompt"],
                          out["sources"][0]["domain"]), ("openai", "ok", "a.com"))

    def test_sources_file_replaces_same_day_and_never_touches_history(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.tsv"
            row = lambda day, dom: {"date": day, "provider": "openai", "prompt": "p",
                                    "url": f"https://{dom}/", "domain": dom}
            probe.append_sources([row("2026-11-05", "a.com")], path)
            probe.append_sources([row("2026-11-08", "b.com")], path)
            probe.append_sources([row("2026-11-08", "c.com")], path)
            with open(path, encoding="utf-8", newline="") as fh:
                got = list(csv.DictReader(fh, delimiter="\t"))
            self.assertEqual([(r["date"], r["domain"]) for r in got],
                             [("2026-11-05", "a.com"), ("2026-11-08", "c.com")])
            self.assertEqual(probe.SOURCE_FIELDS, ["date", "provider", "prompt", "url", "domain"])
            self.assertEqual(probe.FIELDS[:7],
                             ["date", "provider", "model", "prompt", "named", "cited", "error"])
            self.assertNotEqual(probe.SOURCES_PATH, probe.HISTORY_PATH)

    def test_a_malformed_url_is_skipped_and_the_rest_survive(self):
        got = probe.extract_sources(["https://[bad/x", "https://ok.com/a"])
        self.assertEqual(got, [{"url": "https://ok.com/a", "domain": "ok.com"}])

    def test_a_malformed_url_leaves_the_history_row_error_free(self):
        def fake(provider, prompt, key, model):
            return {"text": "Try Badger Fit", "urls": ["https://[bad/x", "https://ok.com/a"]}

        out = probe.run(["p"], fake, ({"openai": "k"}, dict(probe.DEFAULT_MODELS)))
        self.assertEqual((out["rows"][0]["error"], out["rows"][0]["named"]), ("", "1"))
        self.assertEqual([s["domain"] for s in out["sources"]], ["ok.com"])

    def test_a_source_extraction_fault_cannot_set_the_row_error(self):
        def fake(provider, prompt, key, model):
            return {"text": "x", "urls": ["https://a.com"]}

        with mock.patch.object(probe, "extract_sources", side_effect=RuntimeError("x")):
            out = probe.run(["p"], fake, ({"openai": "k"}, dict(probe.DEFAULT_MODELS)))
        self.assertEqual((out["rows"][0]["error"], out["rows"][0]["named"]), ("", "0"))
        self.assertEqual(out["sources"], [])

    def test_numeric_and_version_strings_are_not_domains(self):
        self.assertEqual(probe.extract_sources(["1.2", "v1.0", "3.14.15", "a.b"]), [])
        self.assertEqual(probe.extract_sources(["bbc.co.uk"])[0]["domain"], "bbc.co.uk")

    def test_pages_differing_only_by_www_or_trailing_slash_dedupe(self):
        got = probe.extract_sources(["https://example.com/a/", "https://www.example.com/a",
                                     "https://example.com/a?x=1"])
        self.assertEqual([i["url"] for i in got],
                         ["https://example.com/a/", "https://example.com/a?x=1"])

    def test_a_gemini_payload_goes_through_the_parser_into_sources(self):
        got = probe.parse_gemini({"candidates": [{
            "content": {"parts": [{"text": "t"}]},
            "groundingMetadata": {"groundingChunks": [
                {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/a",
                         "title": "reddit.com"}},
                {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/b",
                         "title": "reddit.com"}},
                {"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/c",
                         "title": "badger.fit"}}]}}]})
        self.assertEqual(probe.extract_sources(got["urls"]),
                         [{"url": "", "domain": "reddit.com"}, {"url": "", "domain": "badger.fit"}])

    def test_an_undecodable_sources_file_is_left_intact_and_append_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.tsv"
            path.write_bytes(b"date\tprovider\n\xff\xfe\x80\n")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                probe.append_sources([{"date": "2026-11-08", "provider": "openai",
                                       "prompt": "p", "url": "", "domain": "a.com"}], path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in Path(d).iterdir()], ["s.tsv"])

    def test_a_partial_rerun_keeps_the_rows_of_a_prompt_that_failed_this_time(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.tsv"
            row = lambda provider, prompt, dom: {
                "date": "2026-11-08", "provider": provider, "prompt": prompt,
                "url": f"https://{dom}/", "domain": dom}
            probe.append_sources([row("openai", "p1", "a.com"), row("openai", "p2", "b.com")], path)
            probe.append_sources([row("openai", "p1", "c.com")], path)  # p2 failed this time
            probe.append_sources([row("gemini", "p1", "g.com")], path)  # same day, other provider
            with open(path, encoding="utf-8", newline="") as fh:
                got = list(csv.DictReader(fh, delimiter="\t"))
            self.assertEqual(sorted((r["provider"], r["prompt"], r["domain"]) for r in got),
                             [("gemini", "p1", "g.com"), ("openai", "p1", "c.com"),
                              ("openai", "p2", "b.com")])

    def test_main_prints_results_then_exits_nonzero_when_sources_cannot_be_saved(self):
        result = {"rows": [{"provider": "openai", "error": "", "named": "1", "prompt": "p"}],
                  "sources": [], "skipped": []}
        with mock.patch.object(probe, "run", return_value=result), \
                mock.patch.object(probe, "append_history") as hist, \
                mock.patch.object(probe, "append_sources", side_effect=ValueError("bad")), \
                mock.patch("builtins.print") as shown:
            with self.assertRaises(SystemExit) as cm:
                probe.main()
        hist.assert_called_once()
        shown.assert_called_once()
        self.assertIn("NOT saved", str(cm.exception.code))


class ProbeXai(unittest.TestCase):
    def test_inline_annotations_are_the_citations(self):
        got = probe.parse_xai({
            "citations": ["https://x.com/i/status/1", "https://uncited.example/"],
            "output": [{"type": "message", "content": [{"type": "output_text",
                "text": "Try Badger Fit [[1]](https://badger.fit/)",
                "annotations": [{"type": "url_citation", "url": "https://badger.fit/",
                                 "start_index": 14, "end_index": 40, "title": "1"}]}]}]})
        self.assertEqual(got["urls"], ["https://badger.fit/"])
        self.assertEqual(got["text"], "Try Badger Fit [[1]](https://badger.fit/)")
        self.assertTrue(probe.detect(got["text"], got["urls"]) == {"named": True, "cited": True})

    def test_the_flat_list_alone_is_not_a_citation(self):
        got = probe.parse_xai({"citations": ["https://badger.fit/x"],
                               "output": [{"type": "message", "content": [
                                   {"type": "output_text", "text": "t"}]}]})
        self.assertEqual(got["urls"], [])
        self.assertFalse(probe.detect(got["text"], got["urls"])["cited"])

    def test_empty_payload_is_an_empty_answer(self):
        self.assertEqual(probe.parse_xai({}), {"text": "", "urls": []})

    def test_xai_is_a_known_provider_with_a_key_name_and_model(self):
        self.assertIn("xai", probe.PROVIDERS)
        self.assertEqual(probe.ENV_KEYS["xai"], "XAI_API_KEY")
        self.assertTrue(probe.DEFAULT_MODELS["xai"].startswith("grok"))

    def test_request_uses_the_responses_endpoint_with_both_search_tools(self):
        seen = {}

        def fake_get_json(url, headers, body, timeout):
            seen.update(url=url, headers=headers, body=json.loads(body))
            return {"output": []}

        with mock.patch.object(probe.src, "_get_json", fake_get_json):
            probe.ask("xai", "q?", "k", "grok-4.7")
        self.assertEqual(seen["url"], "https://api.x.ai/v1/responses")
        self.assertEqual(seen["headers"]["Authorization"], "Bearer k")
        self.assertEqual([t["type"] for t in seen["body"]["tools"]], ["web_search", "x_search"])
        self.assertEqual(seen["body"]["input"], [{"role": "user", "content": "q?"}])

    def test_xai_key_is_read_from_config(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "c.json"
            cfg.write_text('{"XAI_API_KEY": "kk", "xai_model": "grok-4.5"}')
            with mock.patch.object(probe, "CONFIG_PATH", str(cfg)), \
                 mock.patch.dict(probe.os.environ, {}, clear=True):
                keys, models = probe.load_keys()
        self.assertEqual(keys, {"xai": "kk"})
        self.assertEqual(models["xai"], "grok-4.5")


class ProbeRun(unittest.TestCase):
    def test_skips_providers_without_a_key_and_records_errors_apart(self):
        def fake(provider, prompt, key, model):
            if "GZCLP" in prompt:
                raise RuntimeError("boom")
            return {"text": "Use Badger Fit", "urls": []}

        out = probe.run(["GZCLP?", "5/3/1?"], fake,
                        ({"openai": "k"}, dict(probe.DEFAULT_MODELS)))
        self.assertEqual(out["skipped"], ["perplexity", "gemini", "anthropic", "xai"])
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
