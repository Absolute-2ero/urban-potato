from __future__ import annotations

"""
实时爬虫触发器 + 定时批量爬入口。

数据源优先级：
  1. 高德官方 API（有 Key → 数据最丰富）
  2. OSM Overpass（无 Key 时 fallback，或补充数据）

工作流程（实时）：
  search_service 检测 ES 命中 < TRIGGER_THRESHOLD
  → maybe_trigger() 检 Redis 锁
  → asyncio.create_task(_crawl_and_index())   # 非阻塞
  → 爬取 → NLP 标注 → bulk_index ES
  → 前端 10s 后自动刷新即可命中新数据

工作流程（定时）：
  main.py scheduler 每 3600s 调用 run_scheduled_crawl()
  → 遍历城市 × 关键词批量写入 ES
"""

import asyncio
import logging
from typing import List, Optional

from config import cfg
from crawler.nlp_labeler import label_batch
from crawler.osm_crawler import crawl_around as osm_crawl_around, crawl_city_osm
from database import get_redis
from services.index_service import bulk_index

logger = logging.getLogger(__name__)

TRIGGER_THRESHOLD  = 5       # ES 命中数低于此才触发
_LOCK_PREFIX       = "crawl:lock:"
_LOCK_TTL          = 300     # 5 分钟内不重复触发同一查询
_REALTIME_MAX      = 50      # 实时单次最多索引条数


# ── Redis 锁 ─────────────────────────────────────────────────────────────────

def _lock_key(query: str, lat: Optional[float], lng: Optional[float]) -> str:
    geo = f"{lat:.3f},{lng:.3f}" if lat is not None and lng is not None else "nogeo"
    safe = query.strip()[:40].replace(" ", "_")
    return f"{_LOCK_PREFIX}{safe}:{geo}"


async def _is_locked(key: str) -> bool:
    try:
        return bool(await get_redis().exists(key))
    except Exception:
        return False


async def _set_lock(key: str) -> None:
    try:
        await get_redis().set(key, "1", ex=_LOCK_TTL)
    except Exception:
        pass


# ── 核心爬取逻辑 ──────────────────────────────────────────────────────────────

async def _fetch_docs(
    query: str,
    lat: Optional[float],
    lng: Optional[float],
) -> List[dict]:
    """
    按优先级获取原始文档：
      有坐标 → 高德周边 / OSM 周边
      无坐标 → 高德关键词（北京） / OSM 城市
    """
    docs: List[dict] = []

    if lat is not None and lng is not None:
        # ── 周边搜索 ──────────────────────────────────────────────────────
        if cfg.gaode_api_key:
            from crawler.gaode_crawler import search_around as gaode_around
            docs = await gaode_around(lat, lng, keyword=query, radius_m=5000, max_pages=3)
            logger.info("Gaode around → %d docs", len(docs))

        if len(docs) < 5:       # 高德不足时用 OSM 补充
            osm = await osm_crawl_around(lat, lng, radius_m=5000, keyword=query or None)
            existing_ids = {d["restaurant_id"] for d in docs}
            docs += [d for d in osm if d["restaurant_id"] not in existing_ids]
            logger.info("OSM around supplement → total %d docs", len(docs))

    else:
        # ── 关键词搜索（默认北京）────────────────────────────────────────
        if cfg.gaode_api_key:
            from crawler.gaode_crawler import search_by_keyword
            docs = await search_by_keyword(query, city="北京", max_pages=3)
            logger.info("Gaode keyword=%r → %d docs", query, len(docs))

        if len(docs) < 5:
            osm = await crawl_city_osm("beijing", keyword=query or None)
            existing_ids = {d["restaurant_id"] for d in docs}
            docs += [d for d in osm if d["restaurant_id"] not in existing_ids]
            logger.info("OSM city supplement → total %d docs", len(docs))

    return docs[:_REALTIME_MAX]


async def _crawl_and_index(
    query: str,
    lat: Optional[float],
    lng: Optional[float],
) -> int:
    """后台任务：爬取 → NLP 标注 → 写 ES，返回成功索引数。"""
    try:
        raw = await _fetch_docs(query, lat, lng)
        if not raw:
            logger.info("Realtime crawl: no docs fetched for query=%r", query)
            return 0
        labeled = label_batch(raw)
        count = await bulk_index(labeled)
        logger.info(
            "Realtime crawl done: query=%r geo=(%s,%s) → %d indexed",
            query, lat, lng, count,
        )
        return count
    except Exception as exc:
        logger.error("Realtime crawl failed: %s", exc, exc_info=True)
        return 0


# ── 公开接口：由 search_service 调用 ─────────────────────────────────────────

async def maybe_trigger(
    query: str,
    es_hit_count: int,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> bool:
    """
    若 ES 命中不足且无锁，则后台触发爬虫，返回 True。
    fire-and-forget，不阻塞搜索响应。
    """
    if es_hit_count >= TRIGGER_THRESHOLD:
        return False

    key = _lock_key(query, lat, lng)
    if await _is_locked(key):
        logger.debug("Crawl locked: %s", key)
        return False

    await _set_lock(key)
    logger.info(
        "Triggering realtime crawl: query=%r hits=%d geo=(%s,%s)",
        query, es_hit_count, lat, lng,
    )
    asyncio.create_task(_crawl_and_index(query, lat, lng))
    return True


# ── 定时批量爬虫 ──────────────────────────────────────────────────────────────

_BATCH_KEYWORDS = [
    "素食", "纯素", "清真", "有机", "无麸质",
    "健康餐", "沙拉", "轻食", "减脂餐", "低卡",
    "火锅", "日料", "韩餐", "泰餐", "越南菜",
    "寿司", "印度菜", "西餐", "自助餐",
]

_BATCH_CITIES = ["beijing", "shanghai", "guangzhou", "shenzhen", "chengdu", "hangzhou"]


async def batch_crawl_city(city: str, keywords: Optional[List[str]] = None) -> int:
    """
    定时批量爬一个城市。
    优先使用高德 API（数据更丰富），fallback 到 OSM。
    """
    keywords = keywords or _BATCH_KEYWORDS
    total = 0

    if cfg.gaode_api_key:
        # ── 高德批量 ──────────────────────────────────────────────────────
        from crawler.gaode_crawler import crawl_city
        docs = await crawl_city(city, keywords=keywords, max_pages_per_kw=5)
        if docs:
            labeled = label_batch(docs)
            total = await bulk_index(labeled)
            logger.info("Gaode batch city=%s → %d indexed", city, total)
    else:
        # ── OSM 批量（逐关键词，有 Redis 锁保护）─────────────────────────
        for kw in keywords:
            key = _lock_key(kw, None, None)
            if await _is_locked(key):
                continue
            raw = await crawl_city_osm(city, keyword=kw)
            if raw:
                labeled = label_batch(raw)
                n = await bulk_index(labeled)
                total += n
                logger.info("OSM batch city=%s kw=%r → %d", city, kw, n)
            await _set_lock(key)
            await asyncio.sleep(2.0)

    logger.info("Batch crawl done: city=%s total=%d", city, total)
    return total


async def run_scheduled_crawl() -> None:
    """由 main.py scheduler 每小时调用，轮询所有城市。"""
    for city in _BATCH_CITIES:
        try:
            await batch_crawl_city(city)
        except Exception as exc:
            logger.error("Scheduled crawl error city=%s: %s", city, exc)
        await asyncio.sleep(3.0)
