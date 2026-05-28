"""
饿了么爬虫（使用登录后的 Cookie）。

Cookie 来源：本地运行 eleme_login.py 后生成的 eleme_cookies.json。

功能：
  - 按关键词 + 坐标搜索餐厅
  - 获取餐厅菜单（含菜品名、价格、图片）
  - 规范化为 DietSearch 内部格式（menu_items 字段填充）
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_COOKIE_FILE = Path(__file__).parent / "eleme_cookies.json"

# 饿了么 H5 API
_BASE            = "https://h5.ele.me/restapi"
_SEARCH_URL      = f"{_BASE}/shopping/v3/restaurants"
_RESTAURANT_URL  = f"{_BASE}/shopping/v2/restaurant/{{rid}}"
_MENU_URL        = f"{_BASE}/shopping/v2/restaurant/{{rid}}/food"

_TIMEOUT = 20.0


# ── Cookie 加载 ───────────────────────────────────────────────────────────────

def _load_session() -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    加载 eleme_cookies.json，返回 (cookies_dict, headers_dict)。
    如果文件不存在，返回空 dict（后续请求会返回空数据）。
    """
    if not _COOKIE_FILE.exists():
        logger.warning(
            "eleme_cookies.json not found. "
            "Run eleme_login.py locally and upload the file to crawler/."
        )
        return {}, {}

    try:
        data = json.loads(_COOKIE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to load eleme_cookies.json: %s", exc)
        return {}, {}

    # Playwright 格式的 cookie 列表 → dict
    cookies = {c["name"]: c["value"] for c in data.get("cookies", [])}
    headers = data.get("headers", {})
    logger.info("Loaded %d ele.me cookies", len(cookies))
    return cookies, headers


_SESSION_COOKIES: Dict[str, str] = {}
_SESSION_HEADERS: Dict[str, str] = {}
_SESSION_LOADED = False


def _get_session() -> Tuple[Dict[str, str], Dict[str, str]]:
    global _SESSION_COOKIES, _SESSION_HEADERS, _SESSION_LOADED
    if not _SESSION_LOADED:
        _SESSION_COOKIES, _SESSION_HEADERS = _load_session()
        _SESSION_LOADED = True
    return _SESSION_COOKIES, _SESSION_HEADERS


def reload_session() -> bool:
    """强制重新加载 Cookie（Cookie 过期后调用）。"""
    global _SESSION_LOADED
    _SESSION_LOADED = False
    cookies, _ = _get_session()
    return bool(cookies)


# ── 底层 HTTP 请求 ────────────────────────────────────────────────────────────

def _make_headers(extra: Optional[Dict] = None) -> Dict[str, str]:
    cookies, session_hdrs = _get_session()
    headers = {
        "User-Agent": session_hdrs.get(
            "User-Agent",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        ),
        "Referer":         session_hdrs.get("Referer", "https://h5.ele.me/"),
        "Accept":          "application/json, */*",
        "Accept-Language": session_hdrs.get("Accept-Language", "zh-CN,zh;q=0.9"),
        "X-Requested-With": "XMLHttpRequest",
    }
    if extra:
        headers.update(extra)
    return headers


async def _get_json(
    url: str,
    params: Optional[Dict] = None,
) -> Any:
    cookies, _ = _get_session()
    if not cookies:
        return None

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            trust_env=False,
            cookies=cookies,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, params=params, headers=_make_headers())
            resp.raise_for_status()

            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                logger.warning("Eleme returned non-JSON: %s", ct)
                return None

            data = resp.json()

            # 检查是否被踢出登录
            if isinstance(data, dict):
                code = data.get("code") or data.get("status")
                if code in ("NEED_LOGIN", "401", 401):
                    logger.warning("Eleme session expired, need re-login")
                    return None

            return data

    except httpx.HTTPStatusError as e:
        logger.warning("Eleme HTTP %d: %s", e.response.status_code, url)
        return None
    except Exception as exc:
        logger.warning("Eleme request failed: %s", exc)
        return None


# ── 搜索餐厅 ─────────────────────────────────────────────────────────────────

def _geohash(lat: float, lng: float, precision: int = 7) -> str:
    """计算 geohash（不依赖第三方库）。"""
    BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_r, lng_r = [-90.0, 90.0], [-180.0, 180.0]
    bits = bit = 0
    chars: List[str] = []
    even = True
    while len(chars) < precision:
        if even:
            mid = (lng_r[0] + lng_r[1]) / 2
            if lng >= mid: bit = (bit << 1) | 1; lng_r[0] = mid
            else:          bit = (bit << 1);     lng_r[1] = mid
        else:
            mid = (lat_r[0] + lat_r[1]) / 2
            if lat >= mid: bit = (bit << 1) | 1; lat_r[0] = mid
            else:          bit = (bit << 1);     lat_r[1] = mid
        even = not even
        bits += 1
        if bits == 5:
            chars.append(BASE32[bit])
            bits = bit = 0
    return "".join(chars)


async def search_restaurants(
    lat: float,
    lng: float,
    keyword: str = "",
    limit: int = 20,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """按坐标 + 关键词搜索饿了么餐厅，返回原始 POI 列表。"""
    gh = _geohash(lat, lng)
    params: Dict[str, Any] = {
        "geohash":  gh,
        "latitude": lat,
        "longitude": lng,
        "limit":    limit,
        "offset":   offset,
    }
    if keyword:
        params["keyword"] = keyword

    data = await _get_json(_SEARCH_URL, params)
    if not data:
        return []

    # 返回格式可能是 list 或 {"items": [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or data.get("restaurants") or data.get("data") or []
    return []


# ── 获取餐厅菜单 ──────────────────────────────────────────────────────────────

async def get_menu(restaurant_id: str) -> List[Dict[str, Any]]:
    """
    获取餐厅菜单，返回菜品列表。
    每个菜品：{name, description, price, image_url, specs, activity}
    """
    url = _MENU_URL.format(rid=restaurant_id)
    data = await _get_json(url)
    if not data:
        return []

    items: List[Dict[str, Any]] = []
    # 饿了么菜单按分类分组 [{name: "凉菜", foods: [{...}]}, ...]
    categories = data if isinstance(data, list) else []
    for cat in categories:
        category_name = cat.get("name", "")
        for food in cat.get("foods", []):
            specs = food.get("specfoods", [{}])
            price = specs[0].get("price") if specs else food.get("current_price")
            items.append({
                "name":        food.get("name", ""),
                "description": food.get("description", ""),
                "category":    category_name,
                "price":       float(price) if price else None,
                "image_url":   food.get("image_path", ""),
                "monthly_sales": food.get("month_sales", 0),
                "rating":      food.get("rating", None),
            })

    logger.debug("Eleme menu rid=%s → %d items", restaurant_id, len(items))
    return items


# ── 规范化 → DietSearch 格式 ──────────────────────────────────────────────────

def normalize_restaurant(raw: Dict[str, Any], menu: List[Dict]) -> Optional[Dict[str, Any]]:
    """
    将饿了么餐厅原始数据 + 菜单规范化为 DietSearch 内部格式。
    会与高德数据去重（restaurant_id 前缀不同，但菜单字段填充进来）。
    """
    name = (raw.get("name") or "").strip()
    if not name:
        return None

    lat  = float(raw.get("latitude",  0) or 0)
    lng  = float(raw.get("longitude", 0) or 0)
    rid  = str(raw.get("id", ""))

    # 评分（满分 5）
    rating_raw = raw.get("rating") or raw.get("wm_poi_score")
    try:    rating: Optional[float] = float(rating_raw)
    except: rating = None

    # 人均消费 → price_level
    cost_raw = raw.get("average_cost") or raw.get("pricetips")
    price_level: Optional[int] = None
    try:
        cost = float(str(cost_raw).replace("¥","").replace("元","").strip())
        price_level = 1 if cost < 50 else 2 if cost < 120 else 3 if cost < 250 else 4
    except: pass

    # 图片
    images = []
    if raw.get("image_path"):    images.append(raw["image_path"])
    if raw.get("wm_poi_picture"): images.append(raw["wm_poi_picture"])

    # 菜品规范化（用于搜索索引 + 过敏原推断）
    menu_items = [
        {
            "name":      item["name"],
            "price":     item["price"],
            "calories":  None,   # 后续由 nlp_labeler 或 food DB 填充
            "diet_labels": [],
            "allergens": [],
        }
        for item in menu
        if item.get("name")
    ]

    return {
        "restaurant_id":  f"eleme_{rid}",
        "name":           name,
        "description":    raw.get("description") or raw.get("promotion_info") or "",
        "cuisine_type":   raw.get("category_name") or raw.get("flavors_label") or "餐厅",
        "address":        raw.get("address") or "",
        "phone":          raw.get("phone") or "",
        "price_level":    price_level,
        "rating":         rating,
        "rating_count":   raw.get("rating_count") or raw.get("recent_order_num"),
        "geo":            {"lat": lat, "lng": lng},
        "diet_labels":    [],       # 由 nlp_labeler 推断
        "allergens":      [],
        "allergen_free":  [],
        "business_hours": [raw.get("opening_hours", "")],
        "images":         images[:5],
        "source":         "eleme",
        "menu_items":     menu_items,
        "website":        "",
    }


# ── 主爬取入口 ────────────────────────────────────────────────────────────────

import asyncio


async def crawl_around(
    lat: float,
    lng: float,
    keyword: str = "",
    radius_m: int = 5000,
    max_restaurants: int = 30,
    fetch_menu: bool = True,
) -> List[Dict[str, Any]]:
    """
    爬取坐标附近的饿了么餐厅（含菜单）。
    返回规范化后的文档列表。
    """
    cookies, _ = _get_session()
    if not cookies:
        logger.warning("No eleme session, skipping eleme crawl")
        return []

    raw_list = await search_restaurants(lat, lng, keyword=keyword, limit=max_restaurants)
    logger.info("Eleme search lat=%.4f lng=%.4f kw=%r → %d restaurants", lat, lng, keyword, len(raw_list))

    results: List[Dict[str, Any]] = []
    for raw in raw_list[:max_restaurants]:
        rid = str(raw.get("id", ""))
        menu: List[Dict] = []
        if fetch_menu and rid:
            menu = await get_menu(rid)
            await asyncio.sleep(0.5)   # 礼貌间隔

        doc = normalize_restaurant(raw, menu)
        if doc:
            results.append(doc)

    logger.info("Eleme crawl done: %d docs (with menu)", len(results))
    return results


async def crawl_by_keyword(
    keyword: str,
    city_lat: float = 39.9042,   # 北京天安门
    city_lng: float = 116.4074,
    pages: int = 3,
    fetch_menu: bool = True,
) -> List[Dict[str, Any]]:
    """
    按关键词批量爬取（定时任务使用）。
    """
    cookies, _ = _get_session()
    if not cookies:
        return []

    results: List[Dict[str, Any]] = []
    seen: set = set()
    page_size = 20

    for page in range(pages):
        raw_list = await search_restaurants(
            city_lat, city_lng,
            keyword=keyword,
            limit=page_size,
            offset=page * page_size,
        )
        if not raw_list:
            break

        for raw in raw_list:
            rid = str(raw.get("id", ""))
            if rid in seen:
                continue
            seen.add(rid)

            menu: List[Dict] = []
            if fetch_menu and rid:
                menu = await get_menu(rid)
                await asyncio.sleep(0.5)

            doc = normalize_restaurant(raw, menu)
            if doc:
                results.append(doc)

        await asyncio.sleep(1.0)

    logger.info("Eleme crawl_by_keyword kw=%r → %d docs", keyword, len(results))
    return results
