"""Tests for the retry in _stats_sources._get_json.

Run: python3 -m unittest discover -s tool -p 'test_*.py'

The weekly report runs unattended once a week, so a transient failure that is
not retried costs a whole section for seven days. These pin which failures are
worth another go and which are answers to be reported as-is.
"""

from __future__ import annotations

import io
import sys
import unittest
import warnings
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _stats_sources as src  # noqa: E402


def http_error(code: int, headers: dict | None = None) -> urllib.error.HTTPError:
    msg = Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return urllib.error.HTTPError("http://x/y", code, "Boom", msg, io.BytesIO(b"body"))


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def ok(payload: bytes = b'{"total": 1}') -> FakeResponse:
    return FakeResponse(payload)


class GetJsonRetry(unittest.TestCase):
    def setUp(self):
        # Hand-built HTTPErrors are never closed, and CPython warns about that
        # on collection. It is an artifact of the fixtures, not of the code
        # under test.
        warnings.simplefilter("ignore", ResourceWarning)

    def call(self, side_effect):
        """Run _get_json against a scripted urlopen, with sleep stubbed out."""
        with mock.patch.object(src.urllib.request, "urlopen") as urlopen, \
             mock.patch.object(src.time, "sleep") as sleep:
            urlopen.side_effect = side_effect
            try:
                result = src._get_json("http://x/y", {})
                error = None
            except Exception as exc:  # noqa: BLE001
                result, error = None, exc
        return result, error, urlopen.call_count, [c.args[0] for c in sleep.call_args_list]

    def test_succeeds_first_time_without_sleeping(self):
        result, error, calls, waits = self.call([ok()])
        self.assertIsNone(error)
        self.assertEqual(result, {"total": 1})
        self.assertEqual(calls, 1)
        self.assertEqual(waits, [])

    def test_retries_the_observed_404_and_recovers(self):
        # The 2026-09-07 blip: a 404 from an endpoint that answered normally
        # minutes later. One retry should have saved the whole Website section.
        result, error, calls, _ = self.call([http_error(404), ok()])
        self.assertIsNone(error)
        self.assertEqual(result, {"total": 1})
        self.assertEqual(calls, 2)

    def test_retries_rate_limit_and_server_errors(self):
        for code in (429, 500, 502, 503, 504):
            with self.subTest(code=code):
                result, error, calls, _ = self.call([http_error(code), ok()])
                self.assertIsNone(error, f"{code} should have been retried")
                self.assertEqual(calls, 2)

    def test_does_not_retry_a_configuration_answer(self):
        # 400/401/403 mean the request or the credential is wrong. Retrying only
        # delays the message the reader needs.
        for code in (400, 401, 403):
            with self.subTest(code=code):
                _, error, calls, _ = self.call([http_error(code), ok()])
                self.assertIsInstance(error, urllib.error.HTTPError)
                self.assertEqual(error.code, code)
                self.assertEqual(calls, 1)

    def test_gives_up_after_three_attempts_and_raises_the_last_error(self):
        _, error, calls, waits = self.call([http_error(503)] * 3)
        self.assertIsInstance(error, urllib.error.HTTPError)
        self.assertEqual(error.code, 503)
        self.assertEqual(calls, src.RETRY_ATTEMPTS)
        self.assertEqual(len(waits), src.RETRY_ATTEMPTS - 1)

    def test_backoff_doubles(self):
        _, _, _, waits = self.call([http_error(503)] * 3)
        self.assertEqual(waits, [src.RETRY_BACKOFF, src.RETRY_BACKOFF * 2])

    def test_honors_the_rate_limit_reset_header(self):
        # GoatCounter allows 4 requests a second and says when the window
        # resets. Waiting what it asked for beats guessing.
        _, _, _, waits = self.call([http_error(429, {"X-Rate-Limit-Reset": "3"}), ok()])
        self.assertEqual(waits, [3.0])

    def test_honors_retry_after_but_caps_a_long_one(self):
        _, _, _, waits = self.call([http_error(503, {"Retry-After": "600"}), ok()])
        self.assertEqual(waits, [30.0])

    def test_ignores_a_non_numeric_retry_after(self):
        # Retry-After may be an HTTP date. Fall back rather than crash.
        _, _, _, waits = self.call([
            http_error(503, {"Retry-After": "Wed, 09 Sep 2026 09:00:00 GMT"}), ok()])
        self.assertEqual(waits, [src.RETRY_BACKOFF])

    def test_retries_a_transport_failure(self):
        result, error, calls, _ = self.call([urllib.error.URLError("connection reset"), ok()])
        self.assertIsNone(error)
        self.assertEqual(calls, 2)

    def test_retries_a_timeout(self):
        result, error, calls, _ = self.call([TimeoutError("timed out"), ok()])
        self.assertIsNone(error)
        self.assertEqual(calls, 2)

    def test_error_body_survives_the_retry_path(self):
        # play_quality() calls exc.read() on the raised error. Reading headers
        # during the retry decision must not consume the body.
        _, error, _, _ = self.call([http_error(400)])
        self.assertEqual(error.read(), b"body")


if __name__ == "__main__":
    unittest.main()
