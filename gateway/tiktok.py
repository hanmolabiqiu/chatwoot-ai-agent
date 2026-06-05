# -*- coding: utf-8 -*-
"""TikTok/Douyin (抖音) open platform adapter.

Endpoint: https://open.douyin.com/ (multiple paths)
Auth:     client_key + client_secret + access_token (OAuth 2.0)
Sign:     HMAC-SHA256 (different from MD5 platforms)
Method:   /goods/detail  (by goods_id)  -- requires video/goods scope

cred shape:
  {"client_key": "...", "client_secret": "...", "access_token": "..."}

query shape:
  {"goods_id": "12345"}   -> /goods/detail
  {"sku": "12345"}        -> alias
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode, quote

import httpx

from .base import UnifiedResult

log = logging.getLogger("chathub.gateway.tiktok")

OAUTH_TOKEN_URL = "https://open.douyin.com/oauth/access_token/"
GOODS_DETAIL_URL = "https://open.douyin.com/goods/detail"


def _hmac_sign(secret: str, message: str) -> str:
    """Douyin HMAC-SHA256 hex (lowercase)."""
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


async def fetch(creds: dict, query: dict) -> UnifiedResult:
    goods_id = query.get("goods_id") or query.get("sku")

    client_key = creds.get("client_key") or creds.get("app_id") or creds.get("app_key")
    client_secret = creds.get("client_secret") or creds.get("app_secret")
    access_token = creds.get("access_token") or creds.get("refresh_token")

    if not client_key or not client_secret:
        return UnifiedResult(
            status="no_creds",
            error="missing client_key/client_secret (set them via channelAuth)",
            channel="tiktok",
        )
    if not access_token:
        return UnifiedResult(
            status="no_creds",
            error="missing access_token (obtain via 抖音 OAuth authorization; 2hr TTL, refresh via refresh_token)",
            channel="tiktok",
        )
    if not goods_id:
        return UnifiedResult(status="error", error="missing goods_id", channel="tiktok")

    params = {
        "access_token": access_token,
        "goods_id": str(goods_id),
        "app_id": client_key,
    }
    param_json = json.dumps({"goods_id": str(goods_id)}, ensure_ascii=False, separators=(",", ":"))
    base_string = f"app_id={client_key}&goods_id={goods_id}&access_token={access_token}"
    signature = _hmac_sign(client_secret, base_string)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                GOODS_DETAIL_URL,
                params={"access_token": access_token, "app_id": client_key, "goods_id": str(goods_id), "sign": signature},
            )
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPStatusError as e:
        return UnifiedResult(
            status="error",
            error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            channel="tiktok",
        )
    except Exception as e:
        return UnifiedResult(status="error", error=str(e)[:200], channel="tiktok")

    err_code = str(payload.get("err_no", payload.get("code", "")))
    if err_code not in ("", "0"):
        return UnifiedResult(
            status="error",
            error=f"Douyin err_no={err_code} msg={payload.get('message', payload.get('errmsg', ''))}",
            channel="tiktok",
        )

    data = payload.get("data") or payload.get("goods_detail") or {}
    if not data:
        return UnifiedResult(status="error", error=f"goods_id {goods_id} not found", channel="tiktok")

    price = data.get("price") or data.get("min_price")
    if price and isinstance(price, str):
        try:
            price = float(price) / 100
        except (ValueError, TypeError):
            pass

    return UnifiedResult(
        status="success",
        data={
            "title": data.get("title") or data.get("goods_name") or f"goods {goods_id}",
            "price": price,
            "currency": "CNY",
            "url": data.get("share_url") or data.get("detail_url") or f"https://haohuo.jinritemai.com/GoodsDetail?goods_id={goods_id}",
            "image": (data.get("cover") or {}).get("url") if isinstance(data.get("cover"), dict) else data.get("cover"),
            "in_stock": (data.get("stock") or 0) > 0,
            "sales": data.get("sales"),
        },
        channel="tiktok",
    )
