# -*- coding: utf-8 -*-
"""PDD (拼多多) DDK open platform adapter.

Endpoint: https://api.pinduoduo.com/router
Auth:     client_id + client_secret + access_token (多多进宝 OAuth)
Sign:     MD5(secret + sorted(k1v1k2v2...) + secret) uppercased
Method:   pdd.ddk.goods.search (by keyword) / pdd.ddk.goods.detail (by goods_sign)

cred shape:
  {"client_id": "...", "client_secret": "...", "access_token": "..."}

query shape:
  {"keyword": "iPhone 15"}               -> goods.search
  {"goods_sign": "c9r2omogKFFAc7WB..."}  -> goods.detail
  {"goods_id": "12345"}                   -> alias of goods_sign fallback
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from .base import UnifiedResult

log = logging.getLogger("chathub.gateway.pdd")

API_URL = "https://api.pinduoduo.com/router"
SEARCH_METHOD = "pdd.ddk.goods.search"
DETAIL_METHOD = "pdd.ddk.goods.detail"


def _md5_sign(secret: str, params: dict[str, str]) -> str:
    """PDD sign: secret + sorted(k1v1k2v2...) + secret, MD5, uppercase."""
    pieces = "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
    return hashlib.md5((secret + pieces + secret).encode("utf-8")).hexdigest().upper()


async def fetch(creds: dict, query: dict) -> UnifiedResult:
    keyword = query.get("keyword")
    goods_sign = query.get("goods_sign") or query.get("sku")

    client_id = creds.get("client_id") or creds.get("app_id") or creds.get("app_key")
    client_secret = creds.get("client_secret") or creds.get("app_secret")
    access_token = creds.get("access_token") or creds.get("refresh_token")

    if not client_id or not client_secret:
        return UnifiedResult(
            status="no_creds",
            error="missing client_id/client_secret (set them via channelAuth)",
            channel="pdd",
        )
    if not access_token:
        return UnifiedResult(
            status="no_creds",
            error="missing access_token (obtain via 多多进宝 OAuth authorization)",
            channel="pdd",
        )

    if goods_sign:
        method = DETAIL_METHOD
        biz = {"goods_sign": str(goods_sign)}
    elif keyword:
        method = SEARCH_METHOD
        biz = {"keyword": str(keyword), "page": 1, "page_size": 10}
    else:
        return UnifiedResult(status="error", error="missing keyword or goods_sign", channel="pdd")

    public_params = {
        "type": method,
        "client_id": client_id,
        "timestamp": str(int(time.time() * 1000)),
        "data_type": "JSON",
        "version": "V1",
        "access_token": access_token,
    }
    for k, v in biz.items():
        public_params[k] = v
    public_params["sign"] = _md5_sign(client_secret, public_params)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(API_URL, data=urlencode(public_params), headers={"Content-Type": "application/x-www-form-urlencoded"})
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPStatusError as e:
        return UnifiedResult(
            status="error",
            error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            channel="pdd",
        )
    except Exception as e:
        return UnifiedResult(status="error", error=str(e)[:200], channel="pdd")

    if goods_sign:
        return _parse_detail(payload, goods_sign)
    return _parse_search(payload, keyword)


def _parse_detail(payload: dict, goods_sign: str) -> UnifiedResult:
    inner = payload.get("goods_detail_response") or {}
    data = inner.get("goods_details") or []
    if not data:
        return UnifiedResult(status="error", error=f"goods_sign {goods_sign} not found", channel="pdd")
    g = data[0]
    return UnifiedResult(
        status="success",
        data={
            "title": g.get("goods_name") or f"goods {goods_sign[:10]}",
            "price": (g.get("min_group_price") or 0) / 100,
            "currency": "CNY",
            "url": f"https://mobile.yangkeduo.com/goods.html?goods_id={g.get('goods_id', '')}",
            "image": (g.get("goods_image_url") or "").split(",")[0] if g.get("goods_image_url") else None,
            "in_stock": (g.get("goods_stock_num") or 0) > 0,
        },
        channel="pdd",
    )


def _parse_search(payload: dict, keyword: str) -> UnifiedResult:
    inner = payload.get("goods_search_response") or {}
    items = inner.get("goods_list") or []
    if not items:
        return UnifiedResult(status="error", error=f"no items for keyword '{keyword}'", channel="pdd")
    out = []
    for g in items[:3]:
        out.append({
            "title": g.get("goods_name") or "(无标题)",
            "price": (g.get("min_group_price") or 0) / 100,
            "currency": "CNY",
            "url": f"https://mobile.yangkeduo.com/goods.html?goods_id={g.get('goods_id', '')}",
        })
    return UnifiedResult(status="success", data=out, channel="pdd")
