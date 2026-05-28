from __future__ import annotations

"""
高德地图官方 Web Service API 餐厅爬虫。
文档：https://lbs.amap.com/api/webservice/guide/api/search

API 特性：
- 免费配额 30,000 次/天
- POI 搜索：关键词搜索 + 周边搜索
- extensions=all 可返回评分、人均消费、营业时间、图片
- 每页最多 25 条，最多 100 页（实际受总数限制）
- 支持 HMAC-MD5 数字签名（设置安全密钥后启用）
"""

import asyncio
import hashlib
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_TEXT_URL   = "https://restapi.amap.com/v3/place/text"
_AROUND_URL = "https://restapi.amap.com/v3/place/around"
_PAGE_SIZE  = 25   # 高德单页最大 25
_MAX_PAGES  = 40   # 每个关键词最多爬 40 页 = 1000 条

# 餐饮 POI 大类（囊括所有餐厅子类型）
_FOOD_TYPES = "050000"

# 高德城市名称（用于 city 参数）
CITY_NAMES = {
    "beijing":   "北京",
    "shanghai":  "上海",
    "guangzhou": "广州",
    "shenzhen":  "深圳",
    "chengdu":   "成都",
    "hangzhou":  "杭州",
}

# 各城市搜索关键词（覆盖饮食类型 + 热门菜系）
_DIET_KEYWORDS = [
    "素食", "纯素", "清真", "有机", "无麸质",
    "健康餐", "沙拉", "轻食", "减脂餐", "低卡",
    "火锅", "日料", "韩餐", "泰餐", "越南菜",
    "寿司", "印度菜", "中餐", "西餐", "自助餐",
]


# ── 数字签名（安全密钥模式）────────────────────────────────────────────────────

def _sign_params(params: Dict[str, str], secret: str) -> str:
    """
    高德 Web Service 数字签名算法：
    1. 将所有参数按 key 字典序排列
    2. 拼接成 key1=val1&key2=val2 形式
    3. 末尾追加安全密钥（不含 &）
    4. 对整串做 MD5
    """
    sorted_str = "&".join(f"{k}={params[k]}" for k in sorted(params))
    raw = sorted_str + secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _build_params(extra: Dict[str, Any]) -> Dict[str, str]:
    """构建含签名的请求参数。"""
    params: Dict[str, str] = {
        "key":    cfg.gaode_api_key,
        "output": "json",
    }
    for k, v in extra.items():
        params[str(k)] = str(v)

    if cfg.gaode_security_key:
        params["sig"] = _sign_params(params, cfg.gaode_security_key)

    return params


# ── 单次 API 请求 ─────────────────────────────────────────────────────────────

async def _get_pois(url: str, params: Dict[str, str]) -> tuple[List[Dict], int]:
    """
    执行一次高德 API 请求，返回 (pois, total_count)。
    total_count 用于判断是否还有下一页。
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            info = data.get("info", "unknown error")
            infocode = data.get("infocode", "")
            logger.warning("Gaode API error [%s]: %s", infocode, info)
            return [], 0

        pois  = data.get("pois", []) or []
        count = int(data.get("count", 0) or 0)
        return pois, count

    except httpx.HTTPStatusError as e:
        logger.warning("Gaode HTTP %d: %s", e.response.status_code, url)
        return [], 0
    except Exception as exc:
        logger.warning("Gaode request failed: %s", exc)
        return [], 0


# ── 规范化 POI → 内部格式 ────────────────────────────────────────────────────

# 高德 POI 类型末段 → cuisine_type 中文映射
_TYPE_CUISINE: Dict[str, str] = {
    "中餐厅":    "中餐",
    "日本料理":  "日料",
    "韩国料理":  "韩餐",
    "东南亚料理":"泰/越南菜",
    "西餐厅":    "西餐",
    "素食":      "素食",
    "清真餐厅":  "清真",
    "火锅店":    "火锅",
    "烧烤店":    "烧烤",
    "咖啡厅":    "咖啡",
    "快餐厅":    "快餐",
    "小吃快餐":  "小吃",
    "蛋糕甜点":  "甜点",
    "面包":      "面包/烘焙",
    "饺子":      "饺子/点心",
}


def normalize_poi(poi: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """将高德 POI 原始数据转为 DietSearch 内部餐厅格式。"""
    name = (poi.get("name") or "").strip()
    if not name:
        return None

    # 坐标（高德 GCJ-02，location = "lng,lat"）
    location = poi.get("location", "")
    lat, lng = 0.0, 0.0
    if location and "," in location:
        try:
            lng_s, lat_s = location.split(",", 1)
            lng, lat = float(lng_s), float(lat_s)
        except ValueError:
            pass

    # 菜系：取 type 最后一段
    type_str   = poi.get("type", "") or ""
    type_last  = type_str.split(";")[-1].strip() if type_str else ""
    cuisine_zh = _TYPE_CUISINE.get(type_last, type_last or "餐厅")

    # 评分（0-5，缺失为 None）
    biz = poi.get("biz_ext") or {}
    rating_raw = biz.get("rating") or poi.get("rating") or ""
    try:
        rating: Optional[float] = float(rating_raw) if rating_raw else None
    except ValueError:
        rating = None

    # 人均消费 → price_level 1-4
    cost_raw = biz.get("cost") or poi.get("cost") or ""
    price_level: Optional[int] = None
    try:
        cost = float(cost_raw)
        price_level = 1 if cost < 50 else 2 if cost < 120 else 3 if cost < 250 else 4
    except (ValueError, TypeError):
        pass

    # 图片
    photos = [p["url"] for p in (poi.get("photos") or []) if p.get("url")]

    # 营业时间
    opentime = biz.get("opentime") or biz.get("open_time") or ""
    hours = [opentime] if opentime else []

    # 评论数
    rating_count_raw = biz.get("rating_count") or poi.get("comment_num") or ""
    try:
        rating_count: Optional[int] = int(rating_count_raw) if rating_count_raw else None
    except (ValueError, TypeError):
        rating_count = None

    return {
        "restaurant_id": f"gaode_{poi.get('id', '')}",
        "name":          name,
        "description":   (poi.get("tag") or poi.get("business_name") or ""),
        "cuisine_type":  cuisine_zh,
        "address":       poi.get("address") or "",
        "phone":         poi.get("tel") or "",
        "price_level":   price_level,
        "rating":        rating,
        "rating_count":  rating_count,
        "geo":           {"lat": lat, "lng": lng},
        "diet_labels":   [],      # 由 nlp_labeler 填充
        "allergens":     [],
        "allergen_free": [],
        "business_hours": hours,
        "images":        photos[:8],
        "source":        "gaode",
        "menu_items":    [],
        "website":       "",
    }


# ── 关键词搜索（含分页）──────────────────────────────────────────────────────

async def search_by_keyword(
    keyword: str,
    city:    str = "北京",
    max_pages: int = _MAX_PAGES,
) -> List[Dict[str, Any]]:
    """
    按关键词搜索一个城市内的餐厅，自动翻页直到无更多结果。
    返回规范化后的文档列表。
    """
    if not cfg.gaode_api_key:
        logger.warning("GAODE_API_KEY not set, skipping gaode crawl")
        return []

    results: List[Dict[str, Any]] = []
    seen: set = set()

    for page in range(1, max_pages + 1):
        params = _build_params({
            "keywords":  keyword,
            "types":     _FOOD_TYPES,
            "city":      city,
            "citylimit": "true",
            "children":  "1",
            "offset":    _PAGE_SIZE,
            "page":      page,
            "extensions": "all",
        })
        pois, total = await _get_pois(_TEXT_URL, params)

        for poi in pois:
            pid = poi.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                doc = normalize_poi(poi)
                if doc:
                    results.append(doc)

        logger.debug(
            "Gaode keyword=%r city=%s page=%d/%d got=%d total=%d",
            keyword, city, page, max_pages, len(pois), total,
        )

        # 没有更多结果时提前退出
        if not pois or len(results) >= total:
            break

        await asyncio.sleep(0.4)   # ~2.5 req/s，安全避开 QPS 限额

    logger.info(
        "Gaode search: keyword=%r city=%s → %d restaurants",
        keyword, city, len(results),
    )
    return results


# ── 周边搜索 ─────────────────────────────────────────────────────────────────

async def search_around(
    lat:      float,
    lng:      float,
    keyword:  Optional[str] = None,
    radius_m: int = 5000,
    max_pages: int = 4,
) -> List[Dict[str, Any]]:
    """
    按坐标 + 半径搜索附近餐厅（实时搜索触发时使用）。
    """
    if not cfg.gaode_api_key:
        return []

    results: List[Dict[str, Any]] = []
    seen: set = set()

    for page in range(1, max_pages + 1):
        extra: Dict[str, Any] = {
            "location":   f"{lng},{lat}",
            "radius":     radius_m,
            "types":      _FOOD_TYPES,
            "offset":     _PAGE_SIZE,
            "page":       page,
            "extensions": "all",
        }
        if keyword:
            extra["keywords"] = keyword

        params = _build_params(extra)
        pois, total = await _get_pois(_AROUND_URL, params)

        for poi in pois:
            pid = poi.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                doc = normalize_poi(poi)
                if doc:
                    results.append(doc)

        if not pois or len(results) >= total:
            break

        await asyncio.sleep(0.4)

    logger.info(
        "Gaode around: lat=%.4f lng=%.4f r=%dm keyword=%r → %d",
        lat, lng, radius_m, keyword, len(results),
    )
    return results


# ── 城市批量爬取 ──────────────────────────────────────────────────────────────

async def crawl_city(
    city:     str,
    keywords: Optional[List[str]] = None,
    max_pages_per_kw: int = 10,
) -> List[Dict[str, Any]]:
    """
    爬取一个城市内的餐厅数据（定时批量任务使用）。
    city: 英文城市名（beijing / shanghai / ...）或中文（北京 / ...）。
    返回去重、规范化后的文档列表。
    """
    city_zh = CITY_NAMES.get(city.lower(), city)   # 英文 → 中文
    keywords = keywords or _DIET_KEYWORDS

    all_docs: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for kw in keywords:
        docs = await search_by_keyword(kw, city=city_zh, max_pages=max_pages_per_kw)
        for doc in docs:
            rid = doc.get("restaurant_id")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                all_docs.append(doc)
        await asyncio.sleep(1.0)   # 关键词之间额外等待

    logger.info(
        "Gaode crawl_city: city=%s keywords=%d → %d unique restaurants",
        city_zh, len(keywords), len(all_docs),
    )
    return all_docs
