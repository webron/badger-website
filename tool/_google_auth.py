"""Mint a Google API access token from a service-account key, stdlib only.

The obvious way to do this is google-auth, which pulls in five packages and a
compiled crypto dependency. This runs unattended on a timer, so the fewer
moving parts between a cron tick and a number on a page, the better: RS256 is
one openssl invocation, and everything else here is urllib and json.

Used by the Search Console side of the weekly stats; the GoatCounter side needs
no OAuth at all and just sends a bearer token.
"""

from __future__ import annotations

import base64
import json
import subprocess
import time
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"


def _b64(raw: bytes) -> str:
    """base64url without padding, which is what JWT wants."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def sign_with_key(message: bytes, key_path: str) -> bytes:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", key_path],
        input=message,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"openssl signing failed: {proc.stderr.decode().strip()}")
    return proc.stdout


def access_token(key_file: str, scope: str) -> str:
    """Exchange a service-account key for an OAuth access token.

    key_file is the JSON Google hands you when you create the key. The private
    key inside it is written to a private temp file only for as long as openssl
    needs to read it, then removed.
    """
    import os
    import tempfile

    with open(key_file, encoding="utf-8") as fh:
        key = json.load(fh)

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": key["client_email"],
        "scope": scope,
        "aud": TOKEN_URL,
        "iat": now,
        # Google allows up to an hour. Ask for ten minutes: this process is a
        # one-shot report, and a short-lived token is one less thing to leak.
        "exp": now + 600,
    }
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}".encode()

    fd, pem_path = tempfile.mkstemp(suffix=".pem")
    try:
        os.write(fd, key["private_key"].encode())
        os.close(fd)
        os.chmod(pem_path, 0o600)
        signature = sign_with_key(signing_input, pem_path)
    finally:
        os.unlink(pem_path)

    assertion = f"{signing_input.decode()}.{_b64(signature)}"
    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["access_token"]
