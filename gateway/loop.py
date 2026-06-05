# -*- coding: utf-8 -*-
"""Background asyncio event loop running in a daemon thread.

Sync code (chatwoot_ws_agent) submits coroutines via ``gateway_loop.run(coro)``
and blocks on the result.  All blocking I/O for the 3rd-party platforms happens
on this loop, so the WS Agent's main thread never stalls.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import TimeoutError as FutTimeout
from typing import Any, Coroutine

log = logging.getLogger("chathub.gateway.loop")


class BackgroundLoop:
    """One asyncio loop in a daemon thread, exposed as a sync facade.

    Lifecycle:
        loop = BackgroundLoop()
        loop.start()         # call once at process start
        loop.run(coro, 5)    # block on a coroutine
        loop.stop()          # at shutdown
    """

    def __init__(self, name: str = "gateway-loop") -> None:
        self.name = name
        self.loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._closed = False

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._runner, daemon=True, name=self.name
        )
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError(f"{self.name} failed to start in 5s")
        log.info("Background loop %s started", self.name)

    def _runner(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            self.loop.close()

    def run(self, coro: Coroutine, timeout: float = 30.0) -> Any:
        """Submit a coroutine from sync code, block on result.

        Raises:
            RuntimeError: loop not started
            TimeoutError: coroutine exceeded ``timeout`` seconds
            Exception: whatever the coroutine raised
        """
        if self._closed:
            raise RuntimeError("loop is closed")
        if not self.loop or not self.loop.is_running():
            raise RuntimeError("loop not started; call .start() first")
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            return future.result(timeout=timeout)
        except FutTimeout:
            future.cancel()
            raise TimeoutError(f"coroutine timed out after {timeout}s") from None

    def stop(self) -> None:
        if self._closed or not self.loop:
            return
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)
        self._closed = True
        log.info("Background loop %s stopped", self.name)


# Singleton used by router.py and the WS Agent hook.
gateway_loop = BackgroundLoop()
