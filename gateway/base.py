# -*- coding: utf-8 -*-
"""Unified result object returned by all channel adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UnifiedResult:
    """A platform-agnostic representation of a fetch outcome.

    ``status`` semantics:
        success       - data fetched, ``data`` is populated
        cache_hit     - served from local LRU cache
        rate_limited  - tenant or platform quota exhausted
        breaker_open  - circuit breaker tripped
        error         - platform errored, ``error`` populated
        timeout       - exceeded per-call timeout
        no_creds      - tenant has not authorised this channel
    """

    status: str
    data: dict | list | None = None
    error: str | None = None
    latency_ms: int = 0
    channel: str = ""
    raw: dict | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.status in ("success", "cache_hit")

    def to_prompt_block(self) -> str:
        """Render ``self`` as a markdown block for the LLM prompt.

        Returns a short failure hint on platform errors so the LLM does not
        hallucinate prices/stock. Returns empty on ``no_creds`` (silent skip).
        """
        if self.status == "no_creds":
            return ""
        if not self.ok or not self.data:
            if self.status == "rate_limited":
                return "📦 实时商品数据: 触发限流，请稍后重试"
            if self.status == "breaker_open":
                return "📦 实时商品数据: 平台服务暂时不可用（熔断）"
            if self.status == "timeout":
                return "📦 实时商品数据: 请求超时，已跳过"
            return "📦 实时商品数据: 平台 API 暂不可用，请基于现有知识谨慎回答（不要编造价格/库存）"
        lines = ["📦 实时商品信息:"]
        # data shape (per channel): {"title": ..., "price": ..., "currency": ..., "url": ..., "in_stock": ...}
        d = self.data
        if isinstance(d, dict):
            if d.get("title"):
                lines.append(f"  - 商品: {d['title']}")
            if d.get("price") is not None:
                cur = d.get("currency", "")
                lines.append(f"  - 价格: {cur} {d['price']}".strip())
            if d.get("in_stock") is not None:
                lines.append(f"  - 库存: {'有' if d['in_stock'] else '无'}")
            if d.get("url"):
                lines.append(f"  - 链接: {d['url']}")
        elif isinstance(d, list):
            for i, item in enumerate(d[:3], 1):
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "(无标题)")
                price = item.get("price")
                cur = item.get("currency", "")
                lines.append(f"  {i}. {title} — {cur} {price}".strip())
        return "\n".join(lines)
