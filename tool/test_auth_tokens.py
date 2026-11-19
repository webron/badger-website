"""Tests for the Apple and Google token builders (_apple_auth.token, _google_auth).

Run: python3 -m unittest discover -s tool -p 'test_*.py'

These sign with a throwaway key through the real openssl binary, so they check the
JWT shape a server would see, not just that a mock was called. Skipped when
openssl is not installed.
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _apple_auth as apple  # noqa: E402
import _google_auth as google  # noqa: E402

HAVE_OPENSSL = shutil.which("openssl") is not None


def _unb64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _openssl(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["openssl", *args], input=data, capture_output=True, check=True, timeout=30).stdout


@unittest.skipUnless(HAVE_OPENSSL, "openssl not installed")
class AppleToken(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.key = str(Path(cls.tmp.name) / "AuthKey.pem")
        _openssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", cls.key)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_three_unpadded_base64url_parts_with_header_and_claims(self):
        with mock.patch.object(apple.time, "time", return_value=1_700_000_000):
            tok = apple.token(self.key, "KEY123", "ISSUER-1")
        parts = tok.split(".")
        self.assertEqual(len(parts), 3)
        self.assertNotIn("=", tok)
        self.assertNotRegex(tok, r"[+/]")
        self.assertEqual(json.loads(_unb64(parts[0])), {"alg": "ES256", "kid": "KEY123", "typ": "JWT"})
        claims = json.loads(_unb64(parts[1]))
        self.assertEqual(claims, {"iss": "ISSUER-1", "iat": 1_700_000_000,
                                  "exp": 1_700_000_000 + apple.LIFETIME, "aud": "appstoreconnect-v1"})

    def test_lifetime_stays_under_apples_twenty_minute_cap(self):
        self.assertLessEqual(apple.LIFETIME, 20 * 60)

    def test_signature_is_a_raw_64_byte_r_s_pair(self):
        # Run enough times that DER integers of different lengths (31, 32, 33 bytes) occur.
        for _ in range(12):
            sig = _unb64(apple.token(self.key, "K", "I").split(".")[2])
            self.assertEqual(len(sig), 64)

    def test_signature_verifies_against_the_public_key(self):
        pub = str(Path(self.tmp.name) / "pub.pem")
        _openssl("ec", "-in", self.key, "-pubout", "-out", pub)
        tok = apple.token(self.key, "K", "I")
        head, body, sig = tok.split(".")
        raw = _unb64(sig)
        # Re-wrap r||s as DER so openssl can verify it.
        def der_int(b: bytes) -> bytes:
            b = b.lstrip(b"\x00") or b"\x00"
            if b[0] & 0x80:
                b = b"\x00" + b
            return b"\x02" + bytes([len(b)]) + b
        body_der = der_int(raw[:32]) + der_int(raw[32:])
        der = b"\x30" + bytes([len(body_der)]) + body_der
        sigfile = Path(self.tmp.name) / "sig.der"
        sigfile.write_bytes(der)
        out = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", pub, "-signature", str(sigfile)],
            input=f"{head}.{body}".encode(), capture_output=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_missing_key_file_is_a_clear_error_before_any_signing(self):
        with mock.patch.object(apple.subprocess, "run") as run:
            with self.assertRaisesRegex(FileNotFoundError, "not found"):
                apple.token("/nonexistent/AuthKey.pem", "K", "I")
        run.assert_not_called()

    def test_openssl_failure_raises_instead_of_returning_a_bad_token(self):
        bad = Path(self.tmp.name) / "garbage.pem"
        bad.write_text("not a key")
        with self.assertRaisesRegex(RuntimeError, "openssl signing failed"):
            apple.token(str(bad), "K", "I")

    def test_signing_call_has_a_timeout(self):
        done = subprocess.CompletedProcess([], 0, stdout=bytes([0x30, 6, 2, 1, 1, 2, 1, 1]), stderr=b"")
        with mock.patch.object(apple.subprocess, "run", return_value=done) as run:
            apple.token(self.key, "K", "I")
        self.assertIsNotNone(run.call_args.kwargs.get("timeout"))


@unittest.skipUnless(HAVE_OPENSSL, "openssl not installed")
class GoogleToken(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pem = Path(cls.tmp.name) / "rsa.pem"
        _openssl("genrsa", "-out", str(cls.pem), "2048")
        cls.pub = Path(cls.tmp.name) / "rsa.pub"
        _openssl("rsa", "-in", str(cls.pem), "-pubout", "-out", str(cls.pub))
        cls.keyfile = Path(cls.tmp.name) / "sa.json"
        cls.keyfile.write_text(json.dumps({
            "client_email": "bot@proj.iam.gserviceaccount.com",
            "private_key": cls.pem.read_text(),
        }))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _exchange(self, now=1_700_000_000):
        sent = {}

        def fake_urlopen(req, timeout=None):
            sent["req"], sent["timeout"] = req, timeout
            return io.BytesIO(b'{"access_token": "ya29.abc"}')

        with mock.patch.object(google.time, "time", return_value=now), \
             mock.patch.object(google.urllib.request, "urlopen", fake_urlopen):
            token = google.access_token(str(self.keyfile), "https://www.googleapis.com/auth/analytics.readonly")
        return token, sent

    def test_returns_the_access_token_from_the_response(self):
        token, _ = self._exchange()
        self.assertEqual(token, "ya29.abc")

    def test_posts_a_jwt_bearer_grant_to_the_token_url_with_a_timeout(self):
        _, sent = self._exchange()
        req = sent["req"]
        self.assertEqual(req.full_url, "https://oauth2.googleapis.com/token")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Content-type"), "application/x-www-form-urlencoded")
        self.assertIsNotNone(sent["timeout"])
        from urllib.parse import parse_qs
        form = parse_qs(req.data.decode())
        self.assertEqual(form["grant_type"], ["urn:ietf:params:oauth:grant-type:jwt-bearer"])
        self.assertEqual(len(form["assertion"][0].split(".")), 3)

    def test_assertion_claims_name_the_account_scope_and_a_ten_minute_expiry(self):
        _, sent = self._exchange(now=1_700_000_000)
        from urllib.parse import parse_qs
        head, body, _sig = parse_qs(sent["req"].data.decode())["assertion"][0].split(".")
        self.assertEqual(json.loads(_unb64(head)), {"alg": "RS256", "typ": "JWT"})
        self.assertEqual(json.loads(_unb64(body)), {
            "iss": "bot@proj.iam.gserviceaccount.com",
            "scope": "https://www.googleapis.com/auth/analytics.readonly",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": 1_700_000_000, "exp": 1_700_000_600,
        })

    def test_assertion_signature_verifies_against_the_public_key(self):
        _, sent = self._exchange()
        from urllib.parse import parse_qs
        head, body, sig = parse_qs(sent["req"].data.decode())["assertion"][0].split(".")
        sigfile = Path(self.tmp.name) / "sig.bin"
        sigfile.write_bytes(_unb64(sig))
        out = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(self.pub), "-signature", str(sigfile)],
            input=f"{head}.{body}".encode(), capture_output=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_the_private_key_temp_file_is_removed_even_when_signing_fails(self):
        seen = []
        import os
        def boom(message, path):
            seen.append(path)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            raise RuntimeError("openssl signing failed: x")
        with mock.patch.object(google, "sign_with_key", boom):
            with self.assertRaises(RuntimeError):
                google.access_token(str(self.keyfile), "scope")
        self.assertEqual(len(seen), 1)
        self.assertFalse(os.path.exists(seen[0]))

    def test_sign_with_key_raises_with_openssl_stderr_on_a_bad_key(self):
        bad = Path(self.tmp.name) / "bad.pem"
        bad.write_text("nope")
        with self.assertRaisesRegex(RuntimeError, "openssl signing failed"):
            google.sign_with_key(b"msg", str(bad))


if __name__ == "__main__":
    unittest.main()
