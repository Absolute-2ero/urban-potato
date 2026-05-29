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

from crawler.gaode_crawler import crawl_city, crawl_city_grid
from crawler.nlp_labeler import label_batch
from database import close_all, init_es, init_pg, init_redis, init_sqlite
from services.index_service import bulk_index, ensure_index

logger = logging.getLogger(__name__)


async def run_pipeline(
    city: str = "北京",
    keywords: list = None,
    max_pages: int = 5,
    use_grid: bool = False,
    grid_radius: int = 1500,
    grid_concurrency: int = 5,
) -> int:
    """
    完整 Pipeline：
    1. 从高德 API 抓取餐厅（关键词模式 or 网格扫描模式）
    2. NLP 标注饮食标签（type 精确映射 + 正则兜底）
    3. 写入 Elasticsearch
    返回成功索引的文档数。
    """
    logger.info("Pipeline start: city=%s mode=%s", city, "grid" if use_grid else "keyword")

    total_indexed = 0

    # 1. 爬取
    if use_grid:
        async def _flush_batch(docs):
            nonlocal total_indexed
            labeled = label_batch(docs)
            n = await bulk_index(labeled)
            total_indexed += n
            logger.info("Flushed batch: %d indexed (total %d)", n, total_indexed)

        await crawl_city_grid(
            city,
            radius_m=grid_radius,
            concurrency=grid_concurrency,
            batch_cb=_flush_batch,
            progress_cb=lambda done, total, found: logger.info(
                "Grid %d/%d cells, %d restaurants", done, total, found
            ),
        )
    else:
        keywords = keywords or ["餐厅", "素食", "清真", "有机", "健康餐"]
        raw_docs = await crawl_city(city, keywords=keywords, max_pages=max_pages)
        if not raw_docs:
            logger.warning("No data crawled, pipeline aborted")
            return 0
        labeled_docs = label_batch(raw_docs)
        total_indexed = await bulk_index(labeled_docs)

    logger.info("Pipeline complete: %d documents indexed", total_indexed)
    return total_indexed


async def main_async(args: argparse.Namespace) -> None:
    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

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
            use_grid=args.grid,
            grid_radius=args.grid_radius,
            grid_concurrency=args.grid_concurrency,
        )
        print(f"✓ Indexed {count} restaurants")
    finally:
        await close_all()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="DietSearch crawler pipeline")
    parser.add_argument("--city", default="北京")
    parser.add_argument("--keywords", default="", help="关键词（逗号分隔，--grid 时忽略）")
    parser.add_argument("--max-pages", type=int, default=5, dest="max_pages")
    parser.add_argument("--grid", action="store_true", help="使用网格扫描模式（全量覆盖）")
    parser.add_argument("--grid-radius", type=int, default=1500, dest="grid_radius", help="网格半径（米）")
    parser.add_argument("--grid-concurrency", type=int, default=2, dest="grid_concurrency",
                        help="并发格子数（免费账号建议 2，付费可调到 5）")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
