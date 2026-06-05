# -*- coding: utf-8 -*-
"""Amazon PA-API 5 (sync wrapper → async).  Stub with real shape.

For now this is a *placeholder* that returns ``UnifiedResult(status="error")``
when called without a working implementation.  To switch on, paste in the
real PA-API call here (see TODO).  The shape of the function is stable so
swap-in is one line.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .base import UnifiedResult

log = logging.getLogger("chathub.gateway.amazon")

PAAPI_MARKETPLACES = {
    "us": ("https://api.amazon.com",          "www.amazon.com"),
    "jp": ("https://api.amazon.co.jp",       "www.amazon.co.jp"),
    "uk": ("https://api.amazon.co.uk",       "www.amazon.co.uk"),
    "de": ("https://api.amazon.de",          "www.amazon.de"),
    "fr": ("https://api.amazon.fr",          "www.amazon.fr"),
    "it": ("https://api.amazon.it",          "www.amazon.it"),
    "es": ("https://api.amazon.es",          "www.amazon.es"),
    "ca": ("https://api.amazon.ca",          "www.amazon.ca"),
    "in": ("https://api.amazon.in",          "www.amazon.in"),
    "br": ("https://api.amazon.com.br",      "www.amazon.com.br"),
    "mx": ("https://api.amazon.com.mx",      "www.amazon.com.mx"),
    "au": ("https://api.amazon.com.au",      "www.amazon.com.au"),
    "sg": ("https://api.amazon.sg",          "www.amazon.sg"),
}


async def fetch(creds: dict, query: dict) -> UnifiedResult:
    """Fetch a single ASIN or a search keyword.

    query shape:
        {"asin": "B08N5WRWNW"}  -> GetItems
        {"keyword": "iphone 15", "marketplace": "us"}  -> SearchItems

    creds shape:
        {"access_token": "...", "marketplace": "us", "partner_tag": "..."}
    """
    asin = query.get("asin")
    keyword = query.get("keyword")
    marketplace = query.get("marketplace") or creds.get("marketplace", "us")
    mp = PAAPI_MARKETPLACES.get(marketplace)
    if not mp:
        return UnifiedResult(
            status="error",
            error=f"unsupported marketplace: {marketplace}",
            channel="amazon",
        )
    host, marketplace_domain = mp

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            if asin:
                # GetItems
                r = await client.post(
                    f"{host}/paapi5/getitems",
                    json={
                        "ItemIds": [asin],
                        "PartnerTag": creds.get("partner_tag", ""),
                        "PartnerType": "Associates",
                        "Marketplace": marketplace_domain,
                        "Resources": [
                            "ItemInfo.Title",
                            "Offers.Listings.Price",
                            "Offers.Listings.Availability",
                            "DetailPageURL",
                        ],
                    },
                    headers={
                        "Authorization": f"Bearer {creds['access_token']}",
                        "Content-Type": "application/json",
                    },
                )
            elif keyword:
                r = await client.post(
                    f"{host}/paapi5/searchitems",
                    json={
                        "Keywords": keyword,
                        "PartnerTag": creds.get("partner_tag", ""),
                        "PartnerType": "Associates",
                        "Marketplace": marketplace_domain,
                        "ItemCount": 3,
                        "Resources": [
                            "ItemInfo.Title",
                            "Offers.Listings.Price",
                            "Offers.Listings.Availability",
                            "DetailPageURL",
                        ],
                    },
                    headers={
                        "Authorization": f"Bearer {creds['access_token']}",
                        "Content-Type": "application/json",
                    },
                )
            else:
                return UnifiedResult(
                    status="error", error="missing asin or keyword", channel="amazon"
                )

            r.raise_for_status()
            items = r.json().get("ItemsResult", {}).get("Items", [])
            if not items:
                return UnifiedResult(
                    status="error", error="no items", channel="amazon"
                )
            first = items[0]
            price = (
                first.get("Offers", {})
                .get("Listings", [{}])[0]
                .get("Price", {})
                .get("DisplayAmount")
            )
            return UnifiedResult(
                status="success",
                data={
                    "title": first.get("ItemInfo", {}).get("Title", {}).get("DisplayValue"),
                    "price": price,
                    "currency": "",
                    "url": first.get("DetailPageURL"),
                    "in_stock": (
                        first.get("Offers", {})
                        .get("Listings", [{}])[0]
                        .get("Availability", {}).get("Type")
                        != "OUT_OF_STOCK"
                    ),
                },
                channel="amazon",
            )
    except httpx.HTTPStatusError as e:
        sc = e.response.status_code
        snippet = e.response.text[:150].replace("\n", " ")
        if sc in (401, 403):
            hint = " (LWA access_token invalid or expired; tenant must re-bind via channelAuth)"
        else:
            hint = ""
        return UnifiedResult(
            status="error",
            error=f"HTTP {sc}: {snippet}{hint}",
            channel="amazon",
        )
    except Exception as e:
        return UnifiedResult(status="error", error=str(e)[:200], channel="amazon")
