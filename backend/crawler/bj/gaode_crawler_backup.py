from __future__ import annotations

"""
高德地图 Web 备用爬虫（无需官方 API Key）。

当官方 gaode_crawler.py 的 API Key 超出配额时，pipeline 自动切换到此模块。
使用高德地图 H5 页面内嵌的公开 Web Key，通过按坐标周边搜索方式获取 POI 数据。

接口与 gaode_crawler.py 完全相同：
    crawl_city(city, keywords, max_pages) → List[Dict]

局限：
  - 按坐标周边搜索，不支持全城按关键词翻页
  - H5 Key 无官方 SLA，可能被高德限速
  - 返回字段比官方 API 略少（无 biz_type、opentime 等）
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 高德 H5 内嵌公开 Web Key（通过浏览器 Network tab 可观察到）
_AMAP_H5_KEY    = "28b00e988dd27e3e93fe4af5d43da378"
_AMAP_WEB_AROUND = "https://m.amap.com/search/v3/poi/around"
_FOOD_TYPE_CODE  = "050000"   # 餐饮服务
_PAGE_SIZE       = 20

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer":         "https://m.amap.com/",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 城市中心坐标（GCJ-02）
_CITY_CENTER: Dict[str, tuple] = {
    "北京":  (39.9042, 116.4074),
    "上海":  (31.2304, 121.4737),
    "广州":  (23.1291, 113.2644),
    "深圳":  (22.5431, 114.0579),
    "成都":  (30.5728, 104.0668),
    "杭州":  (30.2741, 120.1551),
    "武汉":  (30.5928, 114.3055),
    "西安":  (34.3416, 108.9398),
}


def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val) or None
    except (TypeError, ValueError):
        return None


def normalize_poi(poi: Dict[str, Any]) -> Dict[str, Any]:
    """将高德 H5 Web POI 规范化为与 gaode_crawler.normalize_poi 相同的格式。"""
    biz_ext = poi.get("biz_ext") or {}

    location = poi.get("location", "")
    lat, lng = 0.0, 0.0
    if location and "," in str(location):
        parts = str(location).split(",")
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            pass

    rating   = _safe_float(biz_ext.get("rating"))
    avg_cost = _safe_float(biz_ext.get("cost"))

    price_level: Optional[int] = None
    if avg_cost:
        if avg_cost < 50:    price_level = 1
        elif avg_cost < 100: price_level = 2
        elif avg_cost < 200: price_level = 3
        else:                price_level = 4

    photos = [
        p.get("url", "") for p in (poi.get("photos") or [])
        if isinstance(p, dict) and p.get("url")
    ]
    tag_str = poi.get("tag") or ""
    tags = [t.strip() for t in tag_str.split(";") if t.strip()]

    return {
        "restaurant_id":  f"gaode_{poi.get('id', '')}",
        "gaode_poi_id":   poi.get("id", ""),
        "name":           poi.get("name", ""),
        "address":        poi.get("address", ""),
        "district":       poi.get("adname", ""),
        "cuisine_type":   poi.get("type", "").split(";")[-1] if poi.get("type") else "",
        "typecode":       poi.get("typecode", ""),
        "tags":           tags,
        "biz_type":       "",          # H5 API 不返回此字段
        "phone":          poi.get("tel", ""),
        "rating":         rating,
        "rating_count":   None,
        "avg_cost":       avg_cost,
        "price_level":    price_level,
        "opening_hours":  "",          # H5 API 不返回营业时间
        "geo":            {"lat": lat, "lng": lng},
        "diet_labels":    [],
        "allergens":      [],
        "allergen_free":  [],
        "images":         photos[:5],
        "menu_items":     [],
        "eleme_id":       None,
        "eleme_name":     None,
        "source":         "gaode_web", # 区分来源
    }


async def _search_around(
    lat: float,
    lng: float,
    keyword: str = "餐厅",
    radius: int = 5000,
    page: int = 1,
) -> List[Dict[str, Any]]:
    params = {
        "key":      _AMAP_H5_KEY,
        "location": f"{lng},{lat}",
        "keywords": keyword,
        "types":    _FOOD_TYPE_CODE,
        "radius":   radius,
        "offset":   _PAGE_SIZE,
        "page":     page,
        "extensions": "all",
        "output":   "json",
    }
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=_HEADERS, trust_env=False) as client:
            resp = await client.get(_AMAP_WEB_AROUND, params=params)
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "1":
            logger.debug("Gaode H5 API status!=1: %s", data.get("info"))
            return []
        return data.get("pois", [])
    except Exception as exc:
        logger.warning("Gaode H5 request failed: %s", exc)
        return []


async def crawl_city(
    city: str,
    keywords: Optional[List[str]] = None,
    max_pages: int = 3,
) -> List[Dict[str, Any]]:
    """
    备用城市爬取 — 接口与 gaode_crawler.crawl_city 相同。
    使用城市中心坐标 + 10km 半径周边搜索代替官方 API。
    """
    center = _CITY_CENTER.get(city)
    if not center:
        logger.warning("Backup crawler: unknown city %r, defaulting to Beijing", city)
        center = _CITY_CENTER["北京"]
    lat, lng = center

    keywords = keywords or ["餐厅", "素食", "清真", "有机", "健康餐"]
    results: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for kw in keywords:
        for page in range(1, max_pages + 1):
            pois = await _search_around(lat, lng, keyword=kw, radius=10000, page=page)
            if not pois:
                break
            for poi in pois:
                rid = poi.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    results.append(normalize_poi(poi))
            await asyncio.sleep(0.5)

    logger.info(
        "Backup crawl city=%s → %d unique restaurants", city, len(results)
    )
    return results
