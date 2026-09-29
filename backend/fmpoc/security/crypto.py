"""Portable application-level encryption for sensitive values (BR-035/036/037/085).

* AES-256-GCM authenticated encryption with random nonces for full bank account numbers.
* HMAC-SHA256 keyed fingerprint (separate key) for uniqueness checks - never ciphertext comparison.
* The key file is plain JSON (base64) in APP_DATA_DIR/secrets, protected by filesystem permissions and
  NOT bound to any OS keystore, so the data set can move between Windows and Linux.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_FILENAME = "portable-encryption-key.json"
_AAD = b"fmpoc:bank_account_number:v1"
MASK_LENGTH = 10
ACCOUNT_NUMBER_RE = re.compile(r"^[A-Z0-9]{4,34}$")


class KeyError_(Exception):
    """Raised when the portable key is missing/mismatched (message never contains key material)."""


@dataclass(frozen=True)
class KeyMaterial:
    enc_key: bytes
    fp_key: bytes

    @property
    def check_value(self) -> str:
        return hmac.new(self.enc_key, b"fmpoc-key-check", hashlib.sha256).hexdigest()[:32]


def key_path(secrets_dir: Path) -> Path:
    return secrets_dir / KEY_FILENAME


def load_key(secrets_dir: Path) -> KeyMaterial | None:
    p = key_path(secrets_dir)
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("format") != "fmpoc-portable-key" or data.get("version") != 1:
        raise KeyError_("Unsupported portable key file format")
    return KeyMaterial(base64.b64decode(data["enc_key"]), base64.b64decode(data["fp_key"]))


def create_key(secrets_dir: Path) -> KeyMaterial:
    """Create the key file exclusively (never overwrites an existing key)."""
    secrets_dir.mkdir(parents=True, exist_ok=True)
    km = KeyMaterial(secrets.token_bytes(32), secrets.token_bytes(32))
    payload = json.dumps(
        {
            "format": "fmpoc-portable-key",
            "version": 1,
            "algorithm": "AES-256-GCM + HMAC-SHA256",
            "enc_key": base64.b64encode(km.enc_key).decode(),
            "fp_key": base64.b64encode(km.fp_key).decode(),
            "note": "Back up together with the database and attachments. Required to decrypt account numbers.",
        },
        indent=2,
    )
    p = key_path(secrets_dir)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(payload)
    try:
        os.chmod(p, 0o600)
    except OSError:  # pragma: no cover
        pass
    return km


def load_or_create_key(secrets_dir: Path) -> KeyMaterial:
    return load_key(secrets_dir) or create_key(secrets_dir)


def normalize_account_number(raw: str) -> str:
    value = re.sub(r"[\s-]", "", raw or "").upper()
    if not ACCOUNT_NUMBER_RE.match(value):
        raise ValueError("account number must be 4-34 letters/digits (spaces and hyphens are ignored)")
    return value


def encrypt(km: KeyMaterial, plaintext: str) -> str:
    nonce = secrets.token_bytes(12)
    ct = AESGCM(km.enc_key).encrypt(nonce, plaintext.encode("utf-8"), _AAD)
    return "v1:" + base64.b64encode(nonce + ct).decode()


def decrypt(km: KeyMaterial, token: str) -> str:
    if not token.startswith("v1:"):
        raise KeyError_("Unsupported ciphertext version")
    raw = base64.b64decode(token[3:])
    return AESGCM(km.enc_key).decrypt(raw[:12], raw[12:], _AAD).decode("utf-8")


def fingerprint(km: KeyMaterial, normalized: str) -> str:
    return hmac.new(km.fp_key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def visible_suffix_length(n: int) -> int:
    """At most 4 characters revealed and at least ceil(n/2) characters remain masked (BR-037)."""
    return max(0, min(4, n - math.ceil(n / 2)))


def visible_suffix(normalized: str) -> str:
    k = visible_suffix_length(len(normalized))
    return normalized[-k:] if k else ""


def mask(suffix: str) -> str:
    """Fixed 10-character masked representation."""
    return "*" * (MASK_LENGTH - len(suffix)) + suffix
