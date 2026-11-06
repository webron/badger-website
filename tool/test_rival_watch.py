"""Tests for the rival watcher (tool/_rival_watch.py).

Run: python3 -m unittest discover -s tool -p 'test_*.py'

No test touches the network. What matters here: a source that fails must keep its
old data instead of reading as a deletion; a field the parser lost must not read
as a change; and a redesigned page must collapse to one line, not hundreds.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _rival_watch as rw  # noqa: E402

PLAY = (
    '<meta property="og:title" content="Hevy - Gym Log - Apps on Google Play">'
    '<div class="x" data-g-id="description" inert><b>Get strong</b><br>Log sets &amp; reps</div>'
    '"ratingValue":4.879,"ratingCount":"287192"'
)


def ios(version="1.0", notes="Fixed bugs", price="Free", count=100):
    return json.dumps({"results": [{
        "trackName": "App", "version": version, "formattedPrice": price,
        "releaseNotes": notes, "description": "Track workouts",
        "averageUserRating": 4.5, "userRatingCount": count,
        "currentVersionReleaseDate": "2026-11-01T00:00:00Z"}]})


def page(*lines):
    return "<html><head><title>t</title><script>var x=1;</script></head><body>" + \
        "".join("<p>%s</p>" % x for x in lines) + "</body></html>"


def fake_get(version="1.0", notes="Fixed bugs", price="Free", lines=("Alpha", "Beta"),
             count=100, fail=()):
    def get(url):
        if any(f in url for f in fail):
            raise OSError("down")
        if "itunes.apple.com" in url:
            return ios(version, notes, price, count)
        if "play.google.com" in url:
            return PLAY
        return page(*lines)
    return get


class Parsing(unittest.TestCase):
    def test_play_fields(self):
        d = rw.parse_play(PLAY)
        self.assertEqual(d["title"], "Hevy - Gym Log")
        self.assertEqual(d["description"], "Get strong\nLog sets & reps")
        self.assertEqual(d["ratingCount"], 287192)
        self.assertEqual(d["rating"], 4.88)

    def test_play_missing_listing_is_empty(self):
        self.assertEqual(rw.parse_play("<html>Not Found</html>"), {})

    def test_ios_empty_results(self):
        self.assertEqual(rw.parse_ios({"results": []}), {})

    def test_page_text_skips_scripts_and_repeats(self):
        self.assertEqual(rw.page_lines(page("Alpha", "Alpha", "Beta")), ["Alpha", "Beta"])


class Diffing(unittest.TestCase):
    def snap(self, **kw):
        return rw.fetch_snapshot(None, get=fake_get(**kw))

    def test_no_change_is_empty(self):
        self.assertEqual(rw.diff_snapshots(self.snap(), self.snap()), [])

    def test_version_price_and_notes(self):
        changes = rw.diff_snapshots(self.snap(), self.snap(version="1.1", price="$4.99",
                                                           notes="Fixed bugs\nNew widget"))
        summaries = {c["summary"] for c in changes if c["rival"] == "Hevy"}
        self.assertIn("version: 1.0 → 1.1", summaries)
        self.assertIn("price: Free → $4.99", summaries)
        notes = [c for c in changes
                 if c["rival"] == "Hevy" and c["summary"] == "release notes changed"][0]
        self.assertEqual(notes["added"], ["New widget"])

    def test_rating_count_alone_is_not_a_change(self):
        self.assertEqual(rw.diff_snapshots(self.snap(count=1), self.snap(count=900)), [])

    def test_small_page_edit_lists_lines(self):
        old = self.snap(lines=("a1 text", "b2 text", "c3 text", "d4 text", "e5 text", "f6 text"))
        new = self.snap(lines=("a1 text", "b2 text", "c3 text", "d4 text", "e5 text",
                               "Now $9 a month"))
        c = [x for x in rw.diff_snapshots(old, new) if x["summary"] == "page text changed"][0]
        self.assertEqual(c["added"], ["Now $9 a month"])
        self.assertEqual(c["removed"], ["f6 text"])

    def test_redesign_collapses_to_one_line_per_page(self):
        old = self.snap(lines=tuple("old line %d" % i for i in range(30)))
        new = self.snap(lines=tuple("new line %d" % i for i in range(30)))
        c = [x for x in rw.diff_snapshots(old, new) if "rewritten" in x["summary"]]
        self.assertTrue(c)
        self.assertEqual(c[0]["added"], [])

    def test_lost_field_is_not_a_change(self):
        old, new = self.snap(), self.snap()
        del new["rivals"]["Hevy"]["play"]["description"]
        self.assertEqual(rw.diff_snapshots(old, new), [])

    def test_ratings_delta(self):
        rows = rw.ratings_table(self.snap(count=100), self.snap(count=130))
        self.assertEqual(rows[0]["ios"]["delta"], 30)
        self.assertIn("(+30)", rw._stars(rows[0]["ios"]))


class Failures(unittest.TestCase):
    def test_failed_source_keeps_old_data_and_is_reported(self):
        old = rw.fetch_snapshot(None, get=fake_get())
        new = rw.fetch_snapshot(old, get=fake_get(fail=("itunes.apple.com",)))
        self.assertTrue(any("App Store" in e for e in new["errors"]))
        self.assertEqual(new["rivals"]["Hevy"]["ios"], old["rivals"]["Hevy"]["ios"])
        self.assertEqual(rw.diff_snapshots(old, new), [])

    def test_unknown_app_id_is_an_error_not_silence(self):
        def get(url):
            return json.dumps({"results": []}) if "itunes" in url else fake_get()(url)
        snap = rw.fetch_snapshot(None, get=get)
        self.assertTrue(any("no record" in e for e in snap["errors"]))


class Refresh(unittest.TestCase):
    def test_baseline_then_weekly_change_then_cached(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            first = rw.refresh(d, get=fake_get(), today=date(2026, 11, 5))
            self.assertTrue(first["baseline"])
            self.assertEqual(first["changes"], [])

            def boom(url):
                raise AssertionError("fetched")

            # Same week: no fetch, same answer.
            again = rw.refresh(d, get=boom, today=date(2026, 11, 8))
            self.assertEqual(again["date"], "2026-11-05")
            # A week later: fetch and diff.
            wk = rw.refresh(d, get=fake_get(version="2.0"), today=date(2026, 11, 12))
            self.assertFalse(wk["baseline"])
            self.assertEqual(wk["previous"], "2026-11-05")
            self.assertTrue(any(c["summary"].startswith("version") for c in wk["changes"]))
            self.assertTrue((d / "snapshots" / "2026-11-12.json").exists())
            history = (d / "history.md").read_text()
            self.assertIn("## 2026-11-05\n\nBaseline recorded.", history)
            self.assertIn("## 2026-11-12 (since 2026-11-05)", history)
            self.assertIn("version: 1.0 \u2192 2.0", history)
            # A same-day forced re-run does not write the section twice.
            rw.refresh(d, force=True, get=fake_get(version="2.0"), today=date(2026, 11, 12))
            self.assertEqual((d / "history.md").read_text().count("## 2026-11-12"), 1)

    def test_unwritable_history_keeps_snapshot_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "history.md").mkdir()  # a directory where the file should be
            r = rw.refresh(d, get=fake_get(), today=date(2026, 11, 5))
            self.assertTrue((d / "snapshots" / "2026-11-05.json").exists())
            self.assertTrue(any("history" in e for e in r["errors"]))
            (d / "history.md").rmdir()
            (d / "history.md").write_bytes(b"\xff\xfe bad")
            r = rw.refresh(d, force=True, get=fake_get(), today=date(2026, 11, 12))
            self.assertTrue(any("history" in e for e in r["errors"]))

    def test_render_escapes(self):
        result = {"date": "2026-11-12", "previous": "2026-11-05", "baseline": False,
                  "changes": [{"rival": "X", "source": "s", "summary": "page text changed",
                               "added": ["<script>alert(1)</script>"], "removed": []}],
                  "ratings": [], "errors": ["boom <b>"]}
        out = rw.render(result)
        self.assertNotIn("<script>", out)
        self.assertNotIn("<b>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_quiet_week_says_so(self):
        out = rw.render({"date": "d", "previous": "p", "baseline": False,
                         "changes": [], "ratings": [], "errors": []})
        self.assertIn("Nothing changed since p", out)


if __name__ == "__main__":
    unittest.main()
