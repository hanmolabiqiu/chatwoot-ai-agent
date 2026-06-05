# -*- coding: utf-8 -*-
"""Credential loading: read encrypted blobs from MySQL and decrypt in-memory.

Cache: per-process, 5-minute TTL.  FastAdmin writes via the PHP controller;
the WS Agent reads here.  Direct MySQL access avoids an HTTP hop.

Requires env: ``CHATHUB_DB_HOST`` / ``CHATHUB_DB_USER`` / ``CHATHUB_DB_PASS`` /
``CHATHUB_DB_NAME``.  The same credentials the provision server uses are
fine; they are not secrets.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

from . import crypto

log = logging.getLogger("chathub.gateway.credentials")

_TTL = 300  # 5 minutes

_lock = threading.Lock()
_cache: dict[tuple[int, str], tuple[float, dict]] = {}


def _db_config() -> dict[str, str]:
    return {
        "host": os.environ.get("CHATHUB_DB_HOST", "mysql"),
        "port": int(os.environ.get("CHATHUB_DB_PORT", "3306")),
        "user": os.environ.get("CHATHUB_DB_USER", "root"),
        "password": os.environ.get("CHATHUB_DB_PASS", "mysql_Py5N2W"),
        "database": os.environ.get("CHATHUB_DB_NAME", "chathub"),
    }


def _query_mysql(sql: str, params: tuple) -> list[dict]:
    """Tiny helper.  No ORM, no SQLAlchemy — keep it small."""
    try:
        import pymysql  # type: ignore
    except ImportError:
        # Fall back to mysql-connector if available
        try:
            import mysql.connector as pymysql  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Neither pymysql nor mysql.connector is installed; "
                "credentials cannot be loaded"
            ) from e

    cfg = _db_config()
    conn = pymysql.connect(**cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def load_credentials(tenant_id: int, channel: str) -> dict[str, Any] | None:
    """Return decrypted credentials for a tenant+channel, or None.

    Returns a dict with at least ``access_token``; some channels may include
    ``refresh_token``, ``expires_at``, ``shop_id``, etc.
    """
    if not crypto.is_configured():
        return None
    now = time.time()
    key = (tenant_id, channel)
    with _lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < _TTL:
            return cached[1]
    try:
        rows = _query_mysql(
            "SELECT credentials_encrypted, expires_at, status "
            "FROM fa_chathub_channel_account "
            "WHERE tenant_id=%s AND channel=%s AND status='active' "
            "ORDER BY id DESC LIMIT 1",
            (tenant_id, channel),
        )
        if not rows:
            return None
        blob = rows[0]["credentials_encrypted"]
        if isinstance(blob, (bytes, bytearray)):
            try:
                text = bytes(blob).decode("utf-8")
            except UnicodeDecodeError:
                if not crypto.is_configured():
                    log.warning("AES key not set; cannot decrypt binary blob tenant=%s channel=%s", tenant_id, channel)
                    return None
                creds = crypto.decrypt(bytes(blob))
                with _lock:
                    _cache[key] = (now, creds)
                return creds
            blob = text
        if isinstance(blob, str):
            if crypto.is_configured() and blob.startswith("enc:"):
                creds = crypto.decrypt(blob[4:].encode("utf-8"))
            else:
                try:
                    creds = json.loads(blob)
                    if not crypto.is_configured():
                        log.info("loaded plaintext credentials tenant=%s channel=%s (set GATEWAY_AES_KEY for encryption)", tenant_id, channel)
                except Exception as e:
                    log.warning("credentials blob not JSON for tenant=%s channel=%s: %s", tenant_id, channel, e)
                    return None
        else:
            log.warning("credentials_encrypted for tenant=%s channel=%s is unsupported type %s", tenant_id, channel, type(blob).__name__)
            return None
        with _lock:
            _cache[key] = (now, creds)
        return creds
    except Exception as e:
        log.error("load_credentials failed tenant=%s channel=%s: %s", tenant_id, channel, e)
        return None


def invalidate(tenant_id: int, channel: str) -> None:
    with _lock:
        _cache.pop((tenant_id, channel), None)
