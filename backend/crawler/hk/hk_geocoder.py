from __future__ import annotations

"""
Hong Kong address geocoder.

Primary: HK Government Address Lookup Service (ALS)
    https://www.als.gov.hk/lookup?q=<address>&n=1
    Free, no API key, WGS-84, HK-specific.

Fallback: OpenStreetMap Nominatim
    https://nominatim.openstreetmap.org/search?q=<address>+Hong+Kong&format=json&limit=1
    Free, no key, 1 req/s limit.

Usage:
    lat, lng = await geocode_address("1 Harbour Road, Wan Chai")
"""

import asyncio
import logging
import urllib.parse
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ALS_URL = "https://www.als.gov.hk/lookup"
_NOM_URL = "https://nominatim.openstreetmap.org/search"
_TIMEOUT = 10.0
_ALS_DELAY = 0.2      # 5 req/s
_NOM_DELAY = 1.1      # Nominatim 1 req/s policy


async def _try_als(client: httpx.AsyncClient, address: str) -> tuple[float, float] | tuple[None, None]:
    """Query HK Government ALS — returns (lat, lng) or (None, None)."""
    try:
        resp = await client.get(
            _ALS_URL,
            params={"q": address, "n": 1},
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None, None
        data: Any = resp.json()
        suggestions = data.get("SuggestedAddress") or []
        if not suggestions:
            return None, None
        geo = (
            suggestions[0]
            .get("Address", {})
            .get("PremisesAddress", {})
            .get("GeospatialInformation", {})
        )
        lat = geo.get("Latitude")
        lng = geo.get("Longitude")
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    except Exception as exc:
        logger.debug("ALS geocode failed for %r: %s", address[:60], exc)
    return None, None


async def _try_nominatim(client: httpx.AsyncClient, address: str) -> tuple[float, float] | tuple[None, None]:
    """Query Nominatim — returns (lat, lng) or (None, None)."""
    try:
        resp = await client.get(
            _NOM_URL,
            params={"q": f"{address} Hong Kong", "format": "json", "limit": 1},
            timeout=_TIMEOUT,
            headers={"User-Agent": "urban-potato-hk-geocoder/1.0"},
        )
        if resp.status_code != 200:
            return None, None
        results: list = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        logger.debug("Nominatim geocode failed for %r: %s", address[:60], exc)
    return None, None


def _clean_address(address: str) -> str:
    """Strip Chinese characters and simplify for geocoding APIs."""
    import re
    # Remove CJK characters (Chinese/Japanese/Korean)
    english_only = re.sub(r'[一-鿿㐀-䶿豈-﫿]+', ' ', address)
    # Collapse whitespace
    return ' '.join(english_only.split()).strip()


async def geocode_address(address: str) -> tuple[float, float] | tuple[None, None]:
    """
    Geocode a HK address. Returns (lat, lng) in WGS-84, or (None, None) on failure.

    Tries ALS first (full address), then Nominatim with English-only address.
    """
    if not address or not address.strip():
        return None, None

    async with httpx.AsyncClient() as client:
        # ALS handles mixed Chinese/English well
        lat, lng = await _try_als(client, address)
        await asyncio.sleep(_ALS_DELAY)
        if lat is not None:
            logger.debug("ALS geocoded %r → (%.5f, %.5f)", address[:60], lat, lng)
            return lat, lng

        # Nominatim works better with English-only addresses
        lat, lng = await _try_nominatim(client, _clean_address(address))
        await asyncio.sleep(_NOM_DELAY)
        if lat is not None:
            logger.debug("Nominatim geocoded %r → (%.5f, %.5f)", address[:60], lat, lng)
            return lat, lng

    logger.debug("Geocode failed for %r", address[:60])
    return None, None


async def geocode_batch(addresses: list[str]) -> list[tuple[float, float] | tuple[None, None]]:
    """Geocode a list of addresses sequentially (respects rate limits)."""
    results = []
    for addr in addresses:
        result = await geocode_address(addr)
        results.append(result)
    return results
