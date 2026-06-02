from __future__ import annotations

"""
高德地图 Web 端点爬虫（无需官方 API key）。

高德 Web 端使用的是公开 js_key（通过浏览器 Network tab 可观察到）。
本模块通过解析高德地图 H5 页面的公开 JSON 接口抓取 POI 数据。
仅供学习/IR 研究使用，请勿大规模商业爬取。

备用方案：若高德 Web 被封，自动切换到 OSM。
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from crawler.osm_crawler import crawl_around as osm_around

logger = logging.getLogger(__name__)

# 高德地图 Web H5 搜索（无需官方 key，使用 web 内嵌 key）
_AMAP_WEB_SEARCH = "https://m.amap.com/api/search/v3/tip"
_AMAP_WEB_AROUND = "https://m.amap.com/search/v3/poi/around"
_AMAP_H5_KEY = "28b00e988dd27e3e93fe4af5d43da378"  # 高德 H5 公开 key

# 请求头模拟 H5 浏览器
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://m.amap.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_FOOD_TYPE_CODE = "050000"   # 餐饮服务
_PAGE_SIZE = 20


def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_price_level(cost_str: Any) -> Optional[int]:
    cost = _safe_float(cost_str)
    if cost is None:
        return None
    if cost < 50:
        return 1
    if cost < 100:
        return 2
    if cost < 200:
        return 3
    return 4


def _normalize_amap_web_poi(poi: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = poi.get("name") or ""
    if not name:
        return None

    location = poi.get("location", "")
    lat, lng = 0.0, 0.0
    if location and "," in str(location):
        parts = str(location).split(",")
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            pass

    biz_ext = poi.get("biz_ext") or {}
    rating = _safe_float(biz_ext.get("rating"))
    price_level = _parse_price_level(biz_ext.get("cost"))

    type_str = poi.get("type", "")
    cuisine_type = type_str.split(";")[-1] if type_str else "餐厅"

    photos = poi.get("photos") or []
    images = [p.get("url", "") for p in photos if isinstance(p, dict) and p.get("url")]

    return {
        "restaurant_id": f"amap_{poi.get('id', '')}",
        "name": name,
        "description": poi.get("tag", ""),
        "cuisine_type": cuisine_type,
        "address": poi.get("address", ""),
        "phone": poi.get("tel", ""),
        "price_level": price_level,
        "rating": rating,
        "rating_count": None,
        "geo": {"lat": lat, "lng": lng},
        "diet_labels": [],
        "allergens": [],
        "allergen_free": [],
        "business_hours": [],
        "images": images[:4],
        "source": "amap_web",
        "menu_items": [],
    }


async def _amap_web_around(
    lat: float,
    lng: float,
    keyword: str = "",
    radius: int = 3000,
    page: int = 1,
) -> List[Dict[str, Any]]:
    params = {
        "key": _AMAP_H5_KEY,
        "location": f"{lng},{lat}",
        "keywords": keyword or "餐厅",
        "types": _FOOD_TYPE_CODE,
        "radius": radius,
        "offset": _PAGE_SIZE,
        "page": page,
        "extensions": "all",
        "output": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=_HEADERS, trust_env=False) as client:
            resp = await client.get(_AMAP_WEB_AROUND, params=params)
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "1":
            logger.debug("Amap web API status!=1: %s", data.get("info"))
            return []
        return data.get("pois", [])
    except Exception as exc:
        logger.warning("Amap web request failed: %s", exc)
        return []


async def crawl_web_around(
    lat: float,
    lng: float,
    keyword: str = "",
    radius_m: int = 3000,
    max_pages: int = 2,
) -> List[Dict[str, Any]]:
    """
    高德 Web → 规范化。失败自动回退到 OSM。
    """
    results: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for page in range(1, max_pages + 1):
        pois = await _amap_web_around(lat, lng, keyword=keyword, radius=radius_m, page=page)
        if not pois:
            break
        for poi in pois:
            rid = poi.get("id")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                doc = _normalize_amap_web_poi(poi)
                if doc:
                    results.append(doc)
        await asyncio.sleep(0.5)  # 礼貌等待

    if not results:
        logger.info("Amap web returned 0 results, falling back to OSM")
        results = await osm_around(lat, lng, radius_m=radius_m, keyword=keyword or None)

    logger.info(
        "web_crawler.crawl_web_around lat=%.4f lng=%.4f kw=%r → %d",
        lat, lng, keyword, len(results),
    )
    return results
