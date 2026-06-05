# -*- coding: utf-8 -*-
"""JD (jingdong.com) union open platform adapter.

Endpoint: https://api.jd.com/routerjson
Auth:     app_key + app_secret + access_token (LWC OAuth 2.0)
Sign:     MD5(app_secret + sorted(k1v1k2v2...) + app_secret) uppercased

Methods:
  jd.union.open.goods.promotiongoodsinfo.query   by SKU ID
  jd.union.open.goods.query                        by keyword

cred shape:
  {"app_key": "...", "app_secret": "...", "access_token": "...", "site_id": "..."}

query shape:
  {"sku": "100012345678"}                -> goods.promotiongoodsinfo.query
  {"keyword": "iPhone 15"}               -> goods.query
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

log = logging.getLogger("chathub.gateway.jd")

API_URL = "https://api.jd.com/routerjson"
SKU_QUERY_METHOD = "jd.union.open.goods.promotiongoodsinfo.query"
KEYWORD_QUERY_METHOD = "jd.union.open.goods.query"


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _sign(app_secret: str, params: dict[str, str]) -> str:
    """JD sign: app_secret + sorted(k1v1k2v2...) + app_secret, MD5, uppercase."""
    pieces = "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
    return hashlib.md5((app_secret + pieces + app_secret).encode("utf-8")).hexdigest().upper()


def _parse_sku_response(payload: dict, sku: str) -> UnifiedResult:
    inner = payload.get("jd_union_open_goods_promotiongoodsinfo_query_response") or {}
    result_str = inner.get("result", "{}")
    try:
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
    except Exception:
        result = {}
    data = result.get("data") or {}
    if not data:
        return UnifiedResult(status="error", error=f"sku {sku} not found", channel="jd")
    price_info = data.get("priceInfo") or {}
    img_info = data.get("imageInfo") or {}
    base = data.get("baseInfo") or {}
    return UnifiedResult(
        status="success",
        data={
            "title": base.get("name") or data.get("skuName") or f"SKU {sku}",
            "price": price_info.get("price") or price_info.get("lowestPrice"),
            "currency": "CNY",
            "url": data.get("url") or f"https://item.jd.com/{sku}.html",
            "image": (img_info.get("imageList") or [None])[0],
            "in_stock": (data.get("stockState") or 1) != 0,
        },
        channel="jd",
    )


def _parse_keyword_response(payload: dict) -> UnifiedResult:
    inner = payload.get("jd_union_open_goods_query_response") or {}
    result_str = inner.get("result", "{}")
    try:
        result = json.loads(result_str) if isinstance(result_str, str) else result_str
    except Exception:
        result = {}
    items = result.get("data") or []
    if not items:
        return UnifiedResult(status="error", error="no items for keyword", channel="jd")
    out = []
    for it in items[:3]:
        price_info = it.get("priceInfo") or {}
        out.append({
            "title": it.get("skuName") or "(无标题)",
            "price": price_info.get("price"),
            "currency": "CNY",
            "url": it.get("url") or "",
        })
    return UnifiedResult(status="success", data=out, channel="jd")


async def fetch(creds: dict, query: dict) -> UnifiedResult:
    sku = query.get("sku")
    keyword = query.get("keyword")

    app_key = creds.get("app_key") or creds.get("app_id")
    app_secret = creds.get("app_secret")
    access_token = creds.get("access_token") or creds.get("refresh_token")

    if not app_key or not app_secret:
        return UnifiedResult(
            status="no_creds",
            error="missing app_key/app_secret (set them via channelAuth)",
            channel="jd",
        )
    if not access_token:
        return UnifiedResult(
            status="no_creds",
            error="missing access_token (use refresh_token via LWC OAuth to obtain)",
            channel="jd",
        )

    if sku:
        method = SKU_QUERY_METHOD
        biz = {"skuIds": [str(sku)]}
    elif keyword:
        method = KEYWORD_QUERY_METHOD
        biz = {"keyword": str(keyword), "pageSize": 3}
    else:
        return UnifiedResult(status="error", error="missing sku or keyword", channel="jd")

    public_params = {
        "method": method,
        "app_key": app_key,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "access_token": access_token,
        "param_json": _json_dumps(biz),
    }
    public_params["sign"] = _sign(app_secret, public_params)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                API_URL,
                data=urlencode(public_params),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPStatusError as e:
        return UnifiedResult(
            status="error",
            error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            channel="jd",
        )
    except Exception as e:
        return UnifiedResult(status="error", error=str(e)[:200], channel="jd")

    jd_code = str(payload.get("code", ""))
    if jd_code not in ("200", "0", ""):
        return UnifiedResult(
            status="error",
            error=f"JD code={jd_code} message={payload.get('message') or payload.get('error_response', '')}",
            channel="jd",
        )

    if sku:
        return _parse_sku_response(payload, sku)
    return _parse_keyword_response(payload)
