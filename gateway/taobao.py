# -*- coding: utf-8 -*-
"""Taobao (淘宝/淘宝客) TOP API adapter.

Endpoint: https://eco.taobao.com/router/rest
Auth:     app_key + app_secret + session_key (OAuth 2.0授权)
Sign:     MD5(secret + sorted(k1v1k2v2...) + secret) uppercased
Method:   taobao.item.get         (基础商品详情 by num_iid)
          taobao.tbk.item.search   (淘宝客商品搜索 by keyword + adzone_id)

cred shape:
  {"app_key": "...", "app_secret": "...", "session_key": "...",
   "adzone_id": "12345", "site_id": "67890"}     # adzone_id required for keyword

query shape:
  {"num_iid": "680123456789"}            -> item detail (item.get)
  {"keyword": "iPhone 15"}               -> keyword search (tbk.item.search)
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

log = logging.getLogger("chathub.gateway.taobao")

API_URL = "https://eco.taobao.com/router/rest"
ITEM_GET_METHOD = "taobao.item.get"
TBK_SEARCH_METHOD = "taobao.tbk.item.search"


def _md5_sign(secret: str, params: dict[str, str]) -> str:
    """Taobao sign: secret + sorted(k1v1k2v2...) + secret, MD5, uppercase."""
    pieces = "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
    return hashlib.md5((secret + pieces + secret).encode("utf-8")).hexdigest().upper()


async def fetch(creds: dict, query: dict) -> UnifiedResult:
    num_iid = query.get("num_iid") or query.get("sku")
    keyword = query.get("keyword")

    if not num_iid and not keyword:
        return UnifiedResult(status="error", error="missing num_iid or keyword", channel="taobao")

    app_key = creds.get("app_key") or creds.get("app_id")
    app_secret = creds.get("app_secret")
    session_key = creds.get("session_key") or creds.get("access_token") or creds.get("refresh_token")

    if not app_key or not app_secret:
        return UnifiedResult(
            status="no_creds",
            error="missing app_key/app_secret (set them via channelAuth)",
            channel="taobao",
        )

    if keyword and not num_iid:
        adzone_id = creds.get("adzone_id")
        if not adzone_id:
            return UnifiedResult(
                status="no_creds",
                error="missing adzone_id in creds JSON (taobao.tbk.item.search requires 推广位; add via channelAuth adzone_id field, or set creds['adzone_id'])",
                channel="taobao",
            )
        return await _tbk_search(app_key, app_secret, session_key, adzone_id, creds.get("site_id"), keyword)

    if not session_key:
        return UnifiedResult(
            status="no_creds",
            error="missing session_key (obtain via Taobao OAuth authorization code grant)",
            channel="taobao",
        )
    return await _item_get(app_key, app_secret, session_key, num_iid)


async def _item_get(app_key: str, app_secret: str, session_key: str, num_iid: str) -> UnifiedResult:
    public_params = {
        "method": ITEM_GET_METHOD,
        "app_key": app_key,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "session": session_key,
        "num_iid": str(num_iid),
        "fields": "num_iid,title,price,promotion_price,num,sales,pic_url,detail_url,nick,props_name,stock",
    }
    public_params["sign"] = _md5_sign(app_secret, public_params)
    payload, err = await _post_taobao(public_params)
    if err:
        return err

    inner = payload.get("item_get_response") or {}
    code = inner.get("code")
    if code and int(code) != 0:
        return UnifiedResult(
            status="error",
            error=f"Taobao code={code} msg={inner.get('msg', '')} sub={inner.get('sub_msg', '')}",
            channel="taobao",
        )
    item = inner.get("item") or {}
    if not item:
        return UnifiedResult(status="error", error=f"num_iid {num_iid} not found", channel="taobao")
    return UnifiedResult(
        status="success",
        data={
            "title": item.get("title") or f"item {num_iid}",
            "price": item.get("promotion_price") or item.get("price"),
            "currency": "CNY",
            "url": item.get("detail_url") or f"https://item.taobao.com/item.htm?id={num_iid}",
            "image": item.get("pic_url"),
            "in_stock": (item.get("num") or 0) > 0,
            "sales": item.get("sales"),
        },
        channel="taobao",
    )


async def _tbk_search(app_key: str, app_secret: str, session_key: str | None,
                      adzone_id: str, site_id: str | None, keyword: str) -> UnifiedResult:
    public_params = {
        "method": TBK_SEARCH_METHOD,
        "app_key": app_key,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "q": keyword,
        "adzone_id": str(adzone_id),
        "page_size": "3",
        "sort": "total_sales_des",
    }
    if session_key:
        public_params["session"] = session_key
    if site_id:
        public_params["site_id"] = str(site_id)
    public_params["sign"] = _md5_sign(app_secret, public_params)
    payload, err = await _post_taobao(public_params)
    if err:
        return err

    inner = payload.get("tbk_item_search_response") or {}
    code = inner.get("code")
    if code and int(code) != 0:
        return UnifiedResult(
            status="error",
            error=f"Taobao code={code} msg={inner.get('msg', '')} sub={inner.get('sub_msg', '')}",
            channel="taobao",
        )
    results = (inner.get("results") or {}).get("n_results") or []
    if not results:
        results = inner.get("result_list") or inner.get("results") or []
    if not results:
        return UnifiedResult(status="error", error=f"no items for keyword '{keyword}'", channel="taobao")
    items = []
    for r in results[:3]:
        if isinstance(r, dict) and "item" in r:
            r = r["item"]
        items.append({
            "title": r.get("title") or "(无标题)",
            "price": r.get("zk_final_price") or r.get("price") or r.get("reserve_price"),
            "currency": "CNY",
            "url": r.get("item_url") or r.get("url") or r.get("click_url") or "",
            "image": r.get("pict_url") or r.get("pic_url"),
        })
    return UnifiedResult(status="success", data=items, channel="taobao")


async def _post_taobao(public_params: dict) -> tuple[dict | None, UnifiedResult | None]:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                API_URL,
                data=urlencode(public_params),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            return r.json(), None
    except httpx.HTTPStatusError as e:
        return None, UnifiedResult(
            status="error",
            error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            channel="taobao",
        )
    except Exception as e:
        return None, UnifiedResult(status="error", error=str(e)[:200], channel="taobao")
