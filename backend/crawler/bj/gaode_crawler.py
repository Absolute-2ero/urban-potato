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
import math
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_TEXT_URL   = "https://restapi.amap.com/v3/place/text"
_AROUND_URL = "https://restapi.amap.com/v3/place/around"
_PAGE_SIZE  = 25   # 高德单页最大 25
_MAX_PAGES  = 40   # 每个关键词最多爬 40 页 = 1000 条

# 各城市核心城区边界框（GCJ-02），格式：(lat_min, lat_max, lng_min, lng_max)
# 只覆盖建成区；郊区/农村餐厅密度极低，意义不大
CITY_BOUNDS: Dict[str, Tuple[float, float, float, float]] = {
    "北京":  (39.68, 40.20, 116.00, 116.78),
    "上海":  (30.98, 31.52, 121.10, 121.75),
    "广州":  (22.94, 23.40, 113.05, 113.68),
    "深圳":  (22.44, 22.76, 113.75, 114.37),
    "成都":  (30.52, 30.80, 103.88, 104.28),
    "杭州":  (30.12, 30.42, 119.95, 120.35),
}

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


# ── 单次 API 请求（含限流重试）──────────────────────────────────────────────

_RATE_LIMIT_CODES = {"10021", "10020", "10044"}  # CUQPS / QPS / 并发超限

async def _get_pois(
    url: str,
    params: Dict[str, str],
    _retries: int = 4,
) -> tuple[List[Dict], int]:
    """
    执行一次高德 API 请求，返回 (pois, total_count)。
    遇到限流错误码（10021 等）自动指数退避重试，最多 _retries 次。
    """
    delay = 2.0
    for attempt in range(_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1":
                infocode = str(data.get("infocode", ""))
                info     = data.get("info", "unknown error")
                if infocode in _RATE_LIMIT_CODES and attempt < _retries:
                    logger.debug("Rate limited [%s], retry %d/%d in %.1fs",
                                 infocode, attempt + 1, _retries, delay)
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
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

    # 标签：POI type 层级各段 + tag 字段（供 nlp_labeler 使用）
    tags: List[str] = [s.strip() for s in type_str.split(";") if s.strip()]
    raw_tag = poi.get("tag") or biz.get("tag") or ""
    tags += [t.strip() for t in re.split(r"[,，;；]", raw_tag) if t.strip()]

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
        "tags":          tags,
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


# ── 网格扫描（全量覆盖）──────────────────────────────────────────────────────

def _grid_points(
    lat_min: float, lat_max: float,
    lng_min: float, lng_max: float,
    radius_m: int = 1500,
) -> Iterator[Tuple[float, float]]:
    """
    生成覆盖边界框的网格坐标序列。
    步长 = radius * √2，相邻圆圈恰好相切于对角线上，保证无盲区。
    """
    # 1° 纬度 ≈ 111 km；1° 经度 ≈ 111 * cos(lat) km
    mid_lat = (lat_min + lat_max) / 2
    step_lat = (radius_m * math.sqrt(2)) / 111_000
    step_lng = (radius_m * math.sqrt(2)) / (111_000 * math.cos(math.radians(mid_lat)))

    lat = lat_min
    while lat <= lat_max + step_lat:
        lng = lng_min
        while lng <= lng_max + step_lng:
            yield round(lat, 6), round(lng, 6)
            lng += step_lng
        lat += step_lat


async def _search_grid_cell(
    lat: float, lng: float,
    radius_m: int,
    sem: asyncio.Semaphore,
    seen_ids: set,
) -> List[Dict[str, Any]]:
    """搜索单个网格格心，返回该格内的新 POI（已全局去重）。"""
    async with sem:
        results: List[Dict[str, Any]] = []
        for page in range(1, 5):   # 每格最多 4 页 = 100 条
            params = _build_params({
                "location":   f"{lng},{lat}",
                "radius":     radius_m,
                "types":      _FOOD_TYPES,
                "offset":     _PAGE_SIZE,
                "page":       page,
                "extensions": "all",
                "sortrule":   "distance",
            })
            pois, total = await _get_pois(_AROUND_URL, params)
            for poi in pois:
                pid = poi.get("id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    doc = normalize_poi(poi)
                    if doc:
                        results.append(doc)

            if not pois or len(pois) < _PAGE_SIZE:
                break   # 不足一页，无需继续翻页

            await asyncio.sleep(0.5)

        return results


async def crawl_city_grid(
    city: str,
    radius_m: int = 1500,
    concurrency: int = 2,
    batch_size: int = 1000,
    batch_cb=None,
    progress_cb=None,
) -> List[Dict[str, Any]]:
    """
    网格扫描爬取整座城市，覆盖率远高于关键词搜索。

    参数
    ----
    city        : 城市中文名（须在 CITY_BOUNDS 中）或英文名
    radius_m    : 单格搜索半径（米），默认 1500
    concurrency : 同时发起的请求数，默认 2（高德免费 CUQPS=2）
    batch_size  : 积累到此数量后调用 batch_cb，默认 1000
    batch_cb    : async callable(docs)，每批新文档就调用一次（用于边爬边写）
    progress_cb : 可选回调 (done, total, found)，用于进度显示
    """
    if not cfg.gaode_api_key:
        logger.warning("GAODE_API_KEY not set, skipping grid crawl")
        return []

    city_zh = CITY_NAMES.get(city.lower(), city)
    bounds  = CITY_BOUNDS.get(city_zh)
    if bounds is None:
        logger.error("No bounds defined for city=%s, add it to CITY_BOUNDS", city_zh)
        return []

    points   = list(_grid_points(*bounds, radius_m=radius_m))
    total    = len(points)
    seen_ids: set = set()
    all_docs: List[Dict[str, Any]] = []
    pending:  List[Dict[str, Any]] = []   # 待 flush 的批次
    sem      = asyncio.Semaphore(concurrency)

    logger.info(
        "Grid crawl city=%s radius=%dm → %d cells (concurrency=%d)",
        city_zh, radius_m, total, concurrency,
    )

    tasks = [
        _search_grid_cell(lat, lng, radius_m, sem, seen_ids)
        for lat, lng in points
    ]

    done = 0
    for coro in asyncio.as_completed(tasks):
        docs = await coro
        all_docs.extend(docs)
        pending.extend(docs)
        done += 1

        # 积累够一批就 flush
        if batch_cb and len(pending) >= batch_size:
            await batch_cb(pending)
            pending.clear()

        if done % 50 == 0 or done == total:
            logger.info(
                "Grid crawl %s: %d/%d cells, %d restaurants so far",
                city_zh, done, total, len(all_docs),
            )
        if progress_cb:
            progress_cb(done, total, len(all_docs))

    # flush 剩余
    if batch_cb and pending:
        await batch_cb(pending)

    logger.info(
        "Grid crawl done: city=%s → %d unique restaurants",
        city_zh, len(all_docs),
    )
    return all_docs
