from __future__ import annotations

"""
高德地图 Places API 餐厅爬虫（P0 数据源）。
文档：https://lbs.amap.com/api/webservice/guide/api/search
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_BASE_URL = "https://restapi.amap.com/v3/place/text"
_AROUND_URL = "https://restapi.amap.com/v3/place/around"
_PAGE_SIZE = 25  # 高德最大每页 25

# 餐厅 POI 类型码（高德）：餐饮服务
_FOOD_TYPE_CODE = "050000"


async def search_restaurants_by_keyword(
    keyword: str,
    city: str = "北京",
    page: int = 1,
    page_size: int = _PAGE_SIZE,
) -> List[Dict[str, Any]]:
    """按关键词搜索餐厅 POI。"""
    if not cfg.gaode_api_key:
        logger.warning("GAODE_API_KEY not configured")
        return []

    params = {
        "key": cfg.gaode_api_key,
        "keywords": keyword,
        "types": _FOOD_TYPE_CODE,
        "city": city,
        "citylimit": "true",
        "children": "1",
        "offset": page_size,
        "page": page,
        "output": "json",
        "extensions": "all",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "1":
            logger.error("Gaode API error: %s", data.get("info"))
            return []
        return data.get("pois", [])
    except Exception as exc:
        logger.error("Gaode keyword search failed: %s", exc)
        return []


async def search_restaurants_around(
    lat: float,
    lng: float,
    radius: int = 3000,
    page: int = 1,
) -> List[Dict[str, Any]]:
    """按坐标周边搜索餐厅 POI。"""
    if not cfg.gaode_api_key:
        logger.warning("GAODE_API_KEY not configured")
        return []

    params = {
        "key": cfg.gaode_api_key,
        "location": f"{lng},{lat}",
        "radius": radius,
        "types": _FOOD_TYPE_CODE,
        "offset": _PAGE_SIZE,
        "page": page,
        "output": "json",
        "extensions": "all",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_AROUND_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "1":
            logger.error("Gaode API error: %s", data.get("info"))
            return []
        return data.get("pois", [])
    except Exception as exc:
        logger.error("Gaode around search failed: %s", exc)
        return []


def normalize_poi(poi: Dict[str, Any]) -> Dict[str, Any]:
    """
    将高德 POI 原始数据规范化为 DietSearch 内部餐厅格式。
    geo 使用高德 GCJ-02 坐标系（如需 WGS-84 需额外转换）。
    """
    location = poi.get("location", "")
    lat, lng = 0.0, 0.0
    if location and "," in location:
        parts = location.split(",")
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            pass

    # 评分（高德评分满分 5）
    rating_raw = poi.get("biz_ext", {}).get("rating", "")
    try:
        rating = float(rating_raw) if rating_raw else None
    except ValueError:
        rating = None

    # 人均消费
    cost_raw = poi.get("biz_ext", {}).get("cost", "")
    price_level: Optional[int] = None
    try:
        cost = float(cost_raw)
        if cost < 50:
            price_level = 1
        elif cost < 100:
            price_level = 2
        elif cost < 200:
            price_level = 3
        else:
            price_level = 4
    except (ValueError, TypeError):
        pass

    photos = [p.get("url", "") for p in poi.get("photos", []) if p.get("url")]

    return {
        "restaurant_id": f"gaode_{poi.get('id', '')}",
        "name": poi.get("name", ""),
        "description": poi.get("tag", ""),
        "cuisine_type": poi.get("type", "").split(";")[-1] if poi.get("type") else "",
        "address": poi.get("address", ""),
        "phone": poi.get("tel", ""),
        "price_level": price_level,
        "rating": rating,
        "rating_count": None,
        "geo": {"lat": lat, "lng": lng},
        "diet_labels": [],       # 由 nlp_labeler 填充
        "allergens": [],
        "allergen_free": [],
        "business_hours": [],
        "images": photos[:5],
        "source": "gaode",
        "menu_items": [],
    }


async def crawl_city(
    city: str,
    keywords: Optional[List[str]] = None,
    max_pages: int = 5,
) -> List[Dict[str, Any]]:
    """爬取城市内餐厅数据，返回规范化后的列表。"""
    keywords = keywords or ["餐厅", "饭店", "素食", "清真", "健康餐", "沙拉"]
    results: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for kw in keywords:
        for page in range(1, max_pages + 1):
            pois = await search_restaurants_by_keyword(kw, city=city, page=page)
            if not pois:
                break
            for poi in pois:
                rid = poi.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    results.append(normalize_poi(poi))
            await asyncio.sleep(0.3)  # 限速

    logger.info("Crawled %d unique restaurants from city=%s", len(results), city)
    return results
