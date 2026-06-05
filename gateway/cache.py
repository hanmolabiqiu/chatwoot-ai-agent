# -*- coding: utf-8 -*-
"""In-process TTL+LRU cache for gateway queries.

Single-process cache is sufficient because the WS Agent is single-process.
Cache key: ``f"{channel}:{tenant_id}:{query_json}"``.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    """Tiny TTL+LRU cache.  Thread-safe."""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 1000) -> None:
        self.ttl = ttl_seconds
        self.max = max_size
        self._data: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            ts, val = entry
            if now - ts > self.ttl:
                self._data.pop(key, None)
                return None
            # LRU touch
            self._data.move_to_end(key)
            return val

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
