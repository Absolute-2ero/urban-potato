from __future__ import annotations

"""
OpenStreetMap Overpass API 爬虫（免费、无需 API key、完全合法）。
文档：https://overpass-api.de/

用于补充高德 API 数据，或在无高德 Key 时作为主要数据源。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# 多个镜像，按优先级依次尝试
_OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
_TIMEOUT = 30.0

# OSM amenity 类型 → cuisine_type 映射
_CUISINE_MAP: Dict[str, str] = {
    "chinese":      "中餐",
    "japanese":     "日料",
    "korean":       "韩餐",
    "thai":         "泰餐",
    "vietnamese":   "越南菜",
    "indian":       "印度菜",
    "italian":      "意餐",
    "pizza":        "比萨",
    "burger":       "汉堡",
    "sushi":        "寿司",
    "noodles":      "面食",
    "dumpling":     "饺子/点心",
    "hot_pot":      "火锅",
    "barbecue":     "烧烤",
    "vegan":        "纯素",
    "vegetarian":   "素食",
    "halal":        "清真",
    "regional":     "地方菜",
    "international":"国际料理",
}

# cuisine → diet_labels 推断
_CUISINE_DIET_LABELS: Dict[str, List[str]] = {
    "vegan":      ["vegan", "vegetarian"],
    "vegetarian": ["vegetarian"],
    "halal":      ["halal"],
}


def _build_overpass_query(
    lat: float,
    lng: float,
    radius_m: int = 5000,
    keyword: Optional[str] = None,
) -> str:
    """
    构建 Overpass QL 查询：搜索给定坐标 radius_m 米内的餐厅 POI。
    如果提供 keyword 则附加 name 过滤（正则）。
    """
    name_filter = f'[name~"{keyword}",i]' if keyword else ""
    return f"""
[out:json][timeout:25];
(
  node[amenity=restaurant]{name_filter}(around:{radius_m},{lat},{lng});
  way[amenity=restaurant]{name_filter}(around:{radius_m},{lat},{lng});
  node[amenity=cafe]{name_filter}(around:{radius_m},{lat},{lng});
  node[amenity=fast_food]{name_filter}(around:{radius_m},{lat},{lng});
);
out body center;
"""


def _build_overpass_query_by_city(city_bbox: tuple, keyword: Optional[str] = None) -> str:
    """
    按城市 bbox 查询 (south, west, north, east)。
    keyword 用于 name 正则过滤。
    """
    s, w, n, e = city_bbox
    name_filter = f'[name~"{keyword}",i]' if keyword else ""
    return f"""
[out:json][timeout:25];
(
  node[amenity=restaurant]{name_filter}({s},{w},{n},{e});
  way[amenity=restaurant]{name_filter}({s},{w},{n},{e});
  node[amenity=cafe]{name_filter}({s},{w},{n},{e});
);
out body center;
"""


async def _query_overpass(ql: str) -> List[Dict[str, Any]]:
    """逐个尝试 Overpass 镜像，第一个成功即返回。"""
    _HEADERS = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "DietSearch/1.0 (IR research project; contact: research@example.com)",
    }
    encoded_data = f"data={ql}"

    for endpoint in _OVERPASS_ENDPOINTS:
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT, trust_env=False) as client:
                    resp = await client.post(
                        endpoint,
                        content=encoded_data.encode(),
                        headers=_HEADERS,
                    )
                    resp.raise_for_status()
                    data = resp.json().get("elements", [])
                    logger.debug("Overpass %s → %d elements", endpoint, len(data))
                    return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 503):
                    wait = 5 * (attempt + 1)
                    logger.warning("Overpass rate limit at %s, wait %ds", endpoint, wait)
                    await asyncio.sleep(wait)
                else:
                    logger.warning("Overpass %s HTTP %d, trying next mirror", endpoint, e.response.status_code)
                    break
            except Exception as exc:
                logger.warning("Overpass %s failed: %s, trying next mirror", endpoint, exc)
                break

    logger.error("All Overpass mirrors failed")
    return []


def _normalize_osm_element(elem: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将 OSM element 转为 DietSearch 内部餐厅格式。"""
    tags = elem.get("tags", {})
    name = tags.get("name") or tags.get("name:zh") or tags.get("name:en")
    if not name:
        return None

    # 坐标
    if "center" in elem:
        lat = elem["center"].get("lat", 0)
        lng = elem["center"].get("lon", 0)
    else:
        lat = elem.get("lat", 0)
        lng = elem.get("lon", 0)

    # 菜系
    cuisine_raw = tags.get("cuisine", "")
    cuisine_zh = _CUISINE_MAP.get(cuisine_raw.split(";")[0].strip(), cuisine_raw or "餐厅")

    # 饮食标签推断
    diet_labels: List[str] = []
    for cuisine_key, labels in _CUISINE_DIET_LABELS.items():
        if cuisine_key in cuisine_raw:
            diet_labels.extend(labels)
    # diet:vegan / diet:vegetarian OSM 标签
    if tags.get("diet:vegan") in ("yes", "only"):
        diet_labels.append("vegan")
    if tags.get("diet:vegetarian") in ("yes", "only"):
        if "vegetarian" not in diet_labels:
            diet_labels.append("vegetarian")
    if tags.get("diet:halal") in ("yes", "only"):
        if "halal" not in diet_labels:
            diet_labels.append("halal")
    if tags.get("diet:gluten_free") in ("yes", "only"):
        diet_labels.append("gluten-free")
    if tags.get("diet:organic") in ("yes", "only"):
        diet_labels.append("organic")
    diet_labels = list(dict.fromkeys(diet_labels))  # 去重保序

    # 价格
    price_raw = tags.get("price_level") or tags.get("level_of_price")
    try:
        price_level: Optional[int] = int(price_raw) if price_raw else None
    except (ValueError, TypeError):
        price_level = None

    # 联系方式
    phone = tags.get("phone") or tags.get("contact:phone", "")
    website = tags.get("website") or tags.get("contact:website", "")
    address_parts = [
        tags.get("addr:street", ""),
        tags.get("addr:housenumber", ""),
        tags.get("addr:city", ""),
    ]
    address = " ".join(p for p in address_parts if p)

    osm_id = elem.get("id", "")
    elem_type = elem.get("type", "node")

    return {
        "restaurant_id": f"osm_{elem_type}_{osm_id}",
        "name": name,
        "description": tags.get("description", ""),
        "cuisine_type": cuisine_zh,
        "address": address,
        "phone": phone,
        "price_level": price_level,
        "rating": None,        # OSM 无评分
        "rating_count": None,
        "geo": {"lat": lat, "lng": lng},
        "diet_labels": diet_labels,
        "allergens": [],
        "allergen_free": [],
        "business_hours": [tags.get("opening_hours", "")],
        "images": [],
        "source": "osm",
        "menu_items": [],
        "website": website,
    }


async def crawl_around(
    lat: float,
    lng: float,
    radius_m: int = 5000,
    keyword: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    按坐标+半径实时抓取 OSM 餐厅。
    适合搜索触发时的按需补充。
    """
    ql = _build_overpass_query(lat, lng, radius_m=radius_m, keyword=keyword)
    elements = await _query_overpass(ql)

    results: List[Dict[str, Any]] = []
    for elem in elements:
        doc = _normalize_osm_element(elem)
        if doc:
            results.append(doc)

    logger.info(
        "OSM crawl_around lat=%.4f lng=%.4f r=%dm keyword=%r → %d restaurants",
        lat, lng, radius_m, keyword, len(results),
    )
    return results


# 主要城市 bbox (south, west, north, east)
CITY_BBOX: Dict[str, tuple] = {
    "beijing":   (39.75, 116.10, 40.20, 116.70),
    "shanghai":  (31.00, 121.20, 31.50, 121.70),
    "guangzhou": (22.90, 113.10, 23.40, 113.65),
    "shenzhen":  (22.45, 113.75, 22.80, 114.45),
    "chengdu":   (30.45, 103.90, 30.85, 104.40),
    "hangzhou":  (29.95, 119.95, 30.50, 120.50),
}


async def crawl_city_osm(
    city: str,
    keyword: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """按城市名称批量抓取。"""
    bbox = CITY_BBOX.get(city.lower())
    if bbox is None:
        logger.warning("Unknown city: %s, falling back to Beijing bbox", city)
        bbox = CITY_BBOX["beijing"]

    ql = _build_overpass_query_by_city(bbox, keyword=keyword)
    elements = await _query_overpass(ql)

    results: List[Dict[str, Any]] = []
    seen: set = set()
    for elem in elements:
        doc = _normalize_osm_element(elem)
        if doc and doc["restaurant_id"] not in seen:
            seen.add(doc["restaurant_id"])
            results.append(doc)

    logger.info("OSM city=%s keyword=%r → %d restaurants", city, keyword, len(results))
    return results
