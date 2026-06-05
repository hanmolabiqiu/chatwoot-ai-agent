# -*- coding: utf-8 -*-
"""Platform Gateway — multi-tenant platform API aggregator.

This package is a *library*, not a service. It is imported in-process by
chatwoot_ws_agent.py and exposes a synchronous facade (``router.fetch``)
that schedules work onto a background asyncio event loop.

The library must never start its own event loop.  Callers must call
``gateway.loop.start()`` once at process start.
"""

from .loop import gateway_loop, BackgroundLoop  # noqa: F401
from .router import fetch, fetch_all  # noqa: F401
from .base import UnifiedResult  # noqa: F401

__all__ = ["gateway_loop", "BackgroundLoop", "fetch", "fetch_all", "UnifiedResult"]
