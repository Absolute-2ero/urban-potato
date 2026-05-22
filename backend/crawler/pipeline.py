from __future__ import annotations

"""
爬虫 Pipeline：抓取 → NLP 标注 → 批量写入 ES。
可作为 CLI 脚本运行：python -m crawler.pipeline --city 北京 --keywords 素食,清真
"""

import argparse
import asyncio
import logging
import sys
import os

# 添加 backend 到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.gaode_crawler import crawl_city
from crawler.nlp_labeler import label_batch
from database import close_all, init_es, init_pg, init_redis, init_sqlite
from services.index_service import bulk_index, ensure_index

logger = logging.getLogger(__name__)


async def run_pipeline(
    city: str = "北京",
    keywords: list = None,
    max_pages: int = 5,
) -> int:
    """
    完整 Pipeline：
    1. 从高德 API 抓取餐厅
    2. NLP 标注饮食标签
    3. 写入 Elasticsearch
    返回成功索引的文档数。
    """
    keywords = keywords or ["餐厅", "素食", "清真", "有机", "健康餐"]

    logger.info("Pipeline start: city=%s, keywords=%s", city, keywords)

    # 1. 爬取
    raw_docs = await crawl_city(city, keywords=keywords, max_pages=max_pages)
    logger.info("Crawled %d restaurants", len(raw_docs))

    if not raw_docs:
        logger.warning("No data crawled, pipeline aborted")
        return 0

    # 2. NLP 标注
    labeled_docs = label_batch(raw_docs)
    logger.info("NLP labeling done")

    # 3. 批量索引
    count = await bulk_index(labeled_docs)
    logger.info("Pipeline complete: %d documents indexed", count)
    return count


async def main_async(args: argparse.Namespace) -> None:
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    # 初始化基础设施
    await init_pg()
    await init_sqlite()
    await init_redis()
    await init_es()
    await ensure_index()

    try:
        count = await run_pipeline(
            city=args.city,
            keywords=keywords,
            max_pages=args.max_pages,
        )
        print(f"✓ Indexed {count} restaurants")
    finally:
        await close_all()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="DietSearch crawler pipeline")
    parser.add_argument("--city", default="北京", help="目标城市")
    parser.add_argument("--keywords", default="", help="搜索关键词（逗号分隔）")
    parser.add_argument("--max-pages", type=int, default=5, dest="max_pages")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
