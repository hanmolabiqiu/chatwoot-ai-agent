# -*- coding: utf-8 -*-
"""AES-256-GCM credential encryption.

The 32-byte key is loaded from ``GATEWAY_AES_KEY`` (base64, 32 bytes raw).

Format on disk (VARBINARY column):
    nonce (12 bytes) || ciphertext_with_tag

Plaintext is the JSON of ``{access_token, refresh_token, ...}`` per channel.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger("chathub.gateway.crypto")


def _key() -> bytes:
    raw = os.environ.get("GATEWAY_AES_KEY", "")
    if not raw:
        raise RuntimeError(
            "GATEWAY_AES_KEY not set — refusing to encrypt/decrypt credentials"
        )
    try:
        decoded = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise RuntimeError(f"GATEWAY_AES_KEY not valid base64: {e}") from None
    if len(decoded) != 32:
        raise RuntimeError(
            f"GATEWAY_AES_KEY must decode to 32 bytes, got {len(decoded)}"
        )
    return decoded


def encrypt(plaintext_obj: dict | str) -> bytes:
    """Encrypt a dict (or string) under AES-256-GCM.  Returns nonce||ct."""
    plaintext = (
        plaintext_obj
        if isinstance(plaintext_obj, str)
        else json.dumps(plaintext_obj, ensure_ascii=False, sort_keys=True)
    )
    nonce = os.urandom(12)
    return nonce + AESGCM(_key()).encrypt(nonce, plaintext.encode("utf-8"), None)


def decrypt(blob: bytes) -> dict:
    """Decrypt a nonce||ct blob back to a dict."""
    if len(blob) < 12 + 16:  # nonce + min GCM tag
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:12], blob[12:]
    raw = AESGCM(_key()).decrypt(nonce, ct, None)
    return json.loads(raw.decode("utf-8"))


def is_configured() -> bool:
    """Check whether a usable key is present.  Used by callers to short-circuit."""
    try:
        _key()
        return True
    except RuntimeError:
        return False
