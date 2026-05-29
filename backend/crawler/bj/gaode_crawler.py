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
    geo 使用高德 GCJ-02 坐标系。
    """
    biz_ext = poi.get("biz_ext") or {}

    # ── 坐标 ──────────────────────────────────────────────────────────────────
    location = poi.get("location", "")
    lat, lng = 0.0, 0.0
    if location and "," in location:
        parts = location.split(",")
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            pass

    # ── 评分 ──────────────────────────────────────────────────────────────────
    try:
        rating: Optional[float] = float(biz_ext.get("rating") or 0) or None
    except (ValueError, TypeError):
        rating = None

    # ── 人均消费 ──────────────────────────────────────────────────────────────
    try:
        avg_cost: Optional[float] = float(biz_ext.get("cost") or 0) or None
    except (ValueError, TypeError):
        avg_cost = None

    price_level: Optional[int] = None
    if avg_cost:
        if avg_cost < 50:    price_level = 1
        elif avg_cost < 100: price_level = 2
        elif avg_cost < 200: price_level = 3
        else:                price_level = 4

    # ── 图片 ──────────────────────────────────────────────────────────────────
    photos = [p.get("url", "") for p in poi.get("photos", []) if p.get("url")]

    # ── 标签 ──────────────────────────────────────────────────────────────────
    tag_str = poi.get("tag") or ""
    tags = [t.strip() for t in tag_str.split(";") if t.strip()]

    # ── 营业时间 ──────────────────────────────────────────────────────────────
    opening_hours = (
        biz_ext.get("opentime_today")
        or biz_ext.get("opentime")
        or poi.get("opentime_today", "")
    )

    return {
        # ── IDs ───────────────────────────────────────────────────────────────
        "restaurant_id":  f"gaode_{poi.get('id', '')}",
        "gaode_poi_id":   poi.get("id", ""),

        # ── 展示信息 ──────────────────────────────────────────────────────────
        "name":           poi.get("name", ""),
        "address":        poi.get("address", ""),
        "district":       poi.get("adname", ""),       # 区名，如 "朝阳区"

        # ── 分类 ──────────────────────────────────────────────────────────────
        "cuisine_type":   poi.get("type", "").split(";")[-1] if poi.get("type") else "",
        "typecode":       poi.get("typecode", ""),
        "tags":           tags,                         # 如 ["素食", "健康餐"]
        "biz_type":       poi.get("biz_type", ""),

        # ── 联系 ──────────────────────────────────────────────────────────────
        "phone":          poi.get("tel", ""),

        # ── 经营数据 ──────────────────────────────────────────────────────────
        "rating":         rating,
        "rating_count":   None,
        "avg_cost":       avg_cost,
        "price_level":    price_level,
        "opening_hours":  opening_hours,

        # ── 位置 ──────────────────────────────────────────────────────────────
        "geo":            {"lat": lat, "lng": lng},

        # ── 饮食标签（由 nlp_labeler + Gemini 填充）──────────────────────────
        "diet_labels":    [],
        "allergens":      [],
        "allergen_free":  [],

        # ── 媒体 ──────────────────────────────────────────────────────────────
        "images":         photos[:5],

        # ── 菜单（由 eleme_crawler 填充）──────────────────────────────────────
        "menu_items":     [],

        # ── 饿了么关联（由 eleme_crawler 填充）──────────────────────────────
        "eleme_id":       None,
        "eleme_name":     None,

        # ── 元数据 ────────────────────────────────────────────────────────────
        "source":         "gaode",
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
