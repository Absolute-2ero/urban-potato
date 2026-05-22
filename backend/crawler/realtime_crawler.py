from __future__ import annotations

"""
实时爬虫触发器。

工作流程：
1. search_service 搜索 ES，若命中 < TRIGGER_THRESHOLD，调用 maybe_trigger()
2. maybe_trigger() 检查 Redis 去重锁（避免重复触发）
3. 无锁则 asyncio.create_task() 后台执行 _crawl_and_index()
4. 爬取完成 → NLP 标注 → 批量写入 ES
5. 下次搜索即可命中新数据

定时批量爬虫（由 main.py scheduler 调用）：
    await batch_crawl_city(city, keywords)
"""

import asyncio
import logging
from typing import List, Optional, Tuple

from crawler.nlp_labeler import label_batch
from crawler.web_crawler import crawl_web_around
from crawler.osm_crawler import crawl_city_osm
from database import get_redis
from services.index_service import bulk_index

logger = logging.getLogger(__name__)

# ES 命中数低于此阈值才触发爬虫
TRIGGER_THRESHOLD = 5

# Redis 去重锁前缀 + TTL（秒）——锁住后不再重复触发
_LOCK_PREFIX = "crawl:lock:"
_LOCK_TTL = 300   # 5 分钟内不重复触发同一 key

# 每次实时触发最多爬几条（控制延迟）
_REALTIME_MAX_RESULTS = 30


def _crawl_lock_key(query: str, lat: Optional[float], lng: Optional[float]) -> str:
    geo = f"{lat:.3f},{lng:.3f}" if lat is not None and lng is not None else "nogeo"
    safe_query = query.strip()[:40].replace(" ", "_")
    return f"{_LOCK_PREFIX}{safe_query}:{geo}"


async def _is_locked(key: str) -> bool:
    try:
        redis = get_redis()
        return bool(await redis.exists(key))
    except Exception:
        return False   # Redis 不可用时不阻止触发


async def _set_lock(key: str) -> None:
    try:
        redis = get_redis()
        await redis.set(key, "1", ex=_LOCK_TTL)
    except Exception:
        pass


async def _crawl_and_index(
    query: str,
    lat: Optional[float],
    lng: Optional[float],
) -> int:
    """后台任务：爬取 → NLP 标注 → 写 ES。返回索引的文档数。"""
    try:
        if lat is not None and lng is not None:
            raw_docs = await crawl_web_around(
                lat, lng,
                keyword=query,
                radius_m=5000,
                max_pages=2,
            )
        else:
            # 无位置信息：按 OSM 关键词搜索（北京为默认城市）
            from crawler.osm_crawler import crawl_city_osm
            raw_docs = await crawl_city_osm("beijing", keyword=query if query else None)

        # 截断（避免首次太慢）
        raw_docs = raw_docs[:_REALTIME_MAX_RESULTS]

        labeled = label_batch(raw_docs)
        count = await bulk_index(labeled)
        logger.info(
            "Realtime crawl done: query=%r geo=(%s,%s) → %d indexed",
            query, lat, lng, count,
        )
        return count
    except Exception as exc:
        logger.error("Realtime crawl failed: %s", exc, exc_info=True)
        return 0


async def maybe_trigger(
    query: str,
    es_hit_count: int,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> bool:
    """
    由 search_service 调用。
    若命中数 < 阈值且无锁，则后台触发爬虫，返回 True。
    """
    if es_hit_count >= TRIGGER_THRESHOLD:
        return False

    lock_key = _crawl_lock_key(query, lat, lng)
    if await _is_locked(lock_key):
        logger.debug("Crawl locked for key=%s", lock_key)
        return False

    await _set_lock(lock_key)
    logger.info(
        "Triggering realtime crawl: query=%r hits=%d geo=(%s,%s)",
        query, es_hit_count, lat, lng,
    )
    # 不等待结果，fire-and-forget
    asyncio.create_task(_crawl_and_index(query, lat, lng))
    return True


# ── 定时批量爬虫入口 ──────────────────────────────────────────────────────────

_BATCH_KEYWORDS = [
    "素食", "纯素", "清真", "有机", "无麸质",
    "健康餐", "沙拉", "轻食", "火锅", "日料",
    "韩餐", "泰餐", "越南菜", "寿司",
    "vegan", "halal", "gluten free",
]

_BATCH_CITIES = ["beijing", "shanghai", "guangzhou", "shenzhen", "chengdu"]


async def batch_crawl_city(
    city: str = "beijing",
    keywords: Optional[List[str]] = None,
) -> int:
    """
    定时批量爬：按城市 + 关键词列表抓取并写入 ES。
    由 scheduler 调用，不阻塞主服务。
    """
    keywords = keywords or _BATCH_KEYWORDS
    total = 0

    for kw in keywords:
        lock_key = _crawl_lock_key(kw, None, None)
        if await _is_locked(lock_key):
            continue

        raw_docs = await crawl_city_osm(city, keyword=kw)
        if raw_docs:
            labeled = label_batch(raw_docs)
            count = await bulk_index(labeled)
            total += count
            logger.info("Batch crawl city=%s kw=%r → %d", city, kw, count)

        await _set_lock(lock_key)
        await asyncio.sleep(2.0)   # Overpass API 礼貌等待

    logger.info("Batch crawl finished: city=%s total=%d", city, total)
    return total


async def run_scheduled_crawl() -> None:
    """
    定时任务入口（由 main.py 的 asyncio 定时循环调用）。
    轮询所有主要城市。
    """
    for city in _BATCH_CITIES:
        try:
            await batch_crawl_city(city)
        except Exception as exc:
            logger.error("Scheduled crawl error for city=%s: %s", city, exc)
        await asyncio.sleep(5.0)
