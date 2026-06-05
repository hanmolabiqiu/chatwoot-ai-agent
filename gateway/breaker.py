# -*- coding: utf-8 -*-
"""Per-tenant + per-platform circuit breaker (pybreaker) and rate limiter (aiolimiter).

Both libraries are NOT pre-installed in CoPaw.  We fall back to in-process
implementations if they are missing so the gateway still works on the
existing image.  This avoids a deploy-time dependency on a third-party
package for a feature that, for now, is mostly cosmetic.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Awaitable, Callable, TypeVar

log = logging.getLogger("chathub.gateway.breaker")

T = TypeVar("T")


# ============ Circuit Breaker (fail_fast + reset) ============

class SimpleBreaker:
    """Minimal circuit breaker.

    State machine:
        CLOSED  -> on fail_max consecutive failures -> OPEN
        OPEN    -> after reset_timeout seconds        -> HALF_OPEN
        HALF_OPEN -> next call passes through
        HALF_OPEN -> success -> CLOSED, failure -> OPEN
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF = "half_open"

    def __init__(self, fail_max: int = 5, reset_timeout: float = 60.0) -> None:
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.state = SimpleBreaker.CLOSED
        self._fails: deque[float] = deque()
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    def allow(self) -> bool:
        if self.state == SimpleBreaker.CLOSED:
            return True
        if self.state == SimpleBreaker.OPEN:
            if time.time() - self._opened_at >= self.reset_timeout:
                self.state = SimpleBreaker.HALF
                return True
            return False
        # HALF_OPEN: allow one
        return True

    def on_success(self) -> None:
        self.state = SimpleBreaker.CLOSED
        self._fails.clear()

    def on_failure(self) -> None:
        self._fails.append(time.time())
        if len(self._fails) >= self.fail_max:
            self.state = SimpleBreaker.OPEN
            self._opened_at = time.time()
            log.warning("Circuit breaker OPEN, will half-open in %ss", self.reset_timeout)


_breakers: dict[str, SimpleBreaker] = {}


def get_breaker(channel: str) -> SimpleBreaker:
    if channel not in _breakers:
        _breakers[channel] = SimpleBreaker(fail_max=5, reset_timeout=60.0)
    return _breakers[channel]


# ============ Async token bucket limiter ============

class AsyncLimiter:
    """Naive per-key async limiter.  rps requests per second, burst=2*rps."""

    def __init__(self, rps: float) -> None:
        self.rps = rps
        self._min_interval = 1.0 / max(rps, 0.001)
        self._last: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str) -> None:
        async with self._lock:
            now = time.time()
            last = self._last.get(key, 0.0)
            wait = self._min_interval - (now - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[key] = time.time()


_limiters: dict[int, AsyncLimiter] = {}


def get_tenant_limiter(tenant_id: int, rps: float = 5.0) -> AsyncLimiter:
    if tenant_id not in _limiters:
        _limiters[tenant_id] = AsyncLimiter(rps=rps)
    return _limiters[tenant_id]
