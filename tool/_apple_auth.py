"""Mint an App Store Connect API token from the .p8 key, stdlib only.

The same reasoning as _google_auth: this runs unattended on a timer, so a
compiled crypto dependency between a cron tick and a number on a page is a
liability. Apple wants ES256 rather than Google's RS256, which is one extra
step - openssl emits an ECDSA signature as DER, and a JWT wants the raw pair
of 32-byte integers - so the DER is unwrapped here rather than pulled in with
a library.

The key itself is the one fastlane already publishes releases with, so this
adds no new secret to the machine. Its ids live beside it in ios/fastlane/.env.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time

AUDIENCE = "appstoreconnect-v1"
# Apple rejects anything over 20 minutes. Ten is plenty for one report run and
# is one less long-lived credential in flight.
LIFETIME = 600


def _b64(raw: bytes) -> str:
    """base64url without padding, which is what JWT wants."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _der_to_jose(der: bytes) -> bytes:
    """Unwrap openssl's DER ECDSA signature into the raw r||s a JWT carries.

    DER is SEQUENCE { INTEGER r, INTEGER s }, with each integer trimmed of
    leading zeros and possibly carrying one back to keep it positive. JOSE
    wants both fixed at 32 bytes for P-256, so each is stripped and re-padded.
    """
    if not der or der[0] != 0x30:
        raise ValueError("signature is not a DER SEQUENCE")
    i = 2
    if der[1] & 0x80:  # long-form length; skip the length-of-length bytes
        i = 2 + (der[1] & 0x7F)
    out = b""
    for _ in range(2):
        if der[i] != 0x02:
            raise ValueError("expected a DER INTEGER in the signature")
        length = der[i + 1]
        value = der[i + 2:i + 2 + length]
        i += 2 + length
        out += value.lstrip(b"\x00").rjust(32, b"\x00")
    return out


def token(key_path: str, key_id: str, issuer_id: str) -> str:
    """A bearer token for api.appstoreconnect.apple.com."""
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"App Store Connect key not found at {key_path}")

    now = int(time.time())
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    claims = {"iss": issuer_id, "iat": now, "exp": now + LIFETIME, "aud": AUDIENCE}
    signing_input = (
        f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    ).encode()

    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", key_path],
        input=signing_input,
        capture_output=True,
        # This runs unattended. An openssl that blocks with no timeout takes
        # the whole weekly report with it, and nothing is there to notice.
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"openssl signing failed: {proc.stderr.decode().strip()}")

    return f"{signing_input.decode()}.{_b64(_der_to_jose(proc.stdout))}"
