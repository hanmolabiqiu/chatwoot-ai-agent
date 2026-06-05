# -*- coding: utf-8 -*-
"""Synchronous facade for the Gateway library.

``fetch`` is the entry point used by ``chatwoot_ws_agent.py``.  It runs
on the main thread but schedules its work onto ``gateway_loop`` and blocks
on the result.  All caching, breaker, and rate-limit logic lives here so
the adapters stay minimal.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from . import amazon, jd, taobao, pdd, tiktok
from .base import UnifiedResult
from .breaker import get_breaker, get_tenant_limiter
from .cache import TTLCache
from .credentials import load_credentials
from .loop import gateway_loop

log = logging.getLogger("chathub.gateway.router")

_cache = TTLCache(ttl_seconds=60, max_size=1000)
_HANDLERS = {
    "amazon": amazon.fetch,
    "jd": jd.fetch,
    "taobao": taobao.fetch,
    "pdd": pdd.fetch,
    "tiktok": tiktok.fetch,
}


def _query_hash(channel: str, tenant_id: int, query: dict) -> str:
    raw = json.dumps({"c": channel, "t": tenant_id, "q": query}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def _call_channel(channel: str, creds: dict, query: dict) -> UnifiedResult:
    handler = _HANDLERS.get(channel)
    if not handler:
        return UnifiedResult(status="error", error=f"unknown channel: {channel}", channel=channel)
    breaker = get_breaker(channel)
    if not breaker.allow():
        return UnifiedResult(status="breaker_open", error="circuit breaker open", channel=channel)
    try:
        result = await handler(creds, query)
        if result.ok:
            breaker.on_success()
        else:
            breaker.on_failure()
        return result
    except Exception as e:
        breaker.on_failure()
        return UnifiedResult(status="error", error=str(e)[:200], channel=channel)


async def _async_fetch(channel: str, tenant_id: int, query: dict, timeout: float) -> UnifiedResult:
    cache_key = f"{channel}:{tenant_id}:{json.dumps(query, sort_keys=True)}"
    cached = _cache.get(cache_key)
    if cached is not None:
        # mark as cache_hit
        hit = UnifiedResult(
            status="cache_hit",
            data=cached.data,
            latency_ms=0,
            channel=channel,
        )
        return hit
    creds = load_credentials(tenant_id, channel)
    if not creds:
        return UnifiedResult(status="no_creds", error="channel not configured", channel=channel)
    limiter = get_tenant_limiter(tenant_id)
    await limiter.acquire(str(tenant_id))
    start = time.time()
    try:
        result = await asyncio.wait_for(_call_channel(channel, creds, query), timeout=timeout)
    except asyncio.TimeoutError:
        result = UnifiedResult(status="timeout", error=f"timed out after {timeout}s", channel=channel)
    result.latency_ms = int((time.time() - start) * 1000)
    if result.ok:
        _cache.set(cache_key, result)
    return result


def fetch(channel: str, tenant_id: int, query: dict, timeout: float = 5.0) -> UnifiedResult:
    """Synchronous entry point.  Returns UnifiedResult.

    Args:
        channel:    "amazon" | "jd" | "taobao" | "pdd" | "tiktok"
        tenant_id:  chathub tenant id
        query:      {"asin"|"sku"|"num_iid"|"goods_id"|"keyword": ...}
        timeout:    seconds before giving up
    """
    if not gateway_loop.loop or not gateway_loop.loop.is_running():
        return UnifiedResult(
            status="error",
            error="gateway loop not started; call gateway_loop.start() at process boot",
            channel=channel,
        )
    try:
        return gateway_loop.run(_async_fetch(channel, tenant_id, query, timeout), timeout=timeout + 2.0)
    except TimeoutError as e:
        return UnifiedResult(status="timeout", error=str(e), channel=channel)
    except RuntimeError as e:
        return UnifiedResult(status="error", error=str(e), channel=channel)
    except Exception as e:
        log.exception("fetch failed channel=%s tenant=%s", channel, tenant_id)
        return UnifiedResult(status="error", error=str(e)[:200], channel=channel)


def fetch_all(
    tenant_id: int,
    query: dict,
    channels: list[str] | None = None,
    timeout: float = 5.0,
) -> dict[str, UnifiedResult]:
    """Fan-out to multiple channels in parallel; returns dict keyed by channel."""
    if channels is None:
        channels = list(_HANDLERS.keys())

    if not gateway_loop.loop or not gateway_loop.loop.is_running():
        err = UnifiedResult(
            status="error",
            error="gateway loop not started; call gateway_loop.start() at process boot",
            channel="*",
        )
        return {c: err for c in channels}

    async def _gather() -> list[UnifiedResult]:
        coros = [_async_fetch(c, tenant_id, query, timeout) for c in channels]
        return await asyncio.gather(*coros, return_exceptions=False)

    try:
        results = gateway_loop.run(_gather(), timeout=timeout + 3.0)
    except Exception as e:
        log.exception("fetch_all failed tenant=%s", tenant_id)
        return {c: UnifiedResult(status="error", error=str(e)[:200], channel=c) for c in channels}
    return {c: r for c, r in zip(channels, results)}
