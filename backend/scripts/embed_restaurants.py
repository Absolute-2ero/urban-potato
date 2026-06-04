"""
批量给 ES 里的餐厅生成 embedding 并写回。
用法：cd backend && python -m scripts.embed_restaurants [--batch 20] [--skip-existing]

- 并发调用 ZhipuAI embedding-2
- 每批 20 条（API 限制），用 ES bulk update 写回
- 支持断点续跑：--skip-existing 跳过已有 embedding 的文档
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_INDEX = "restaurants"


async def run(batch_size: int, skip_existing: bool) -> None:
    from database import init_sqlite, init_postgres, init_redis, init_es
    from services.embedding_service import EmbeddingService, restaurant_to_text

    await init_sqlite()
    await init_postgres()
    await init_redis()
    await init_es()

    from database import get_es
    es = get_es()

    svc = EmbeddingService()
    if not svc.enabled:
        logger.error("ZhipuAI key not set, aborting")
        return

    # Scroll through all documents
    query: Dict[str, Any] = {"match_all": {}}
    if skip_existing:
        query = {"bool": {"must_not": {"exists": {"field": "embedding"}}}}

    resp = await es.search(
        index=_INDEX,
        body={
            "size": batch_size,
            "query": query,
            "_source": ["name", "cuisine_type", "diet_labels",
                        "description", "signature_dishes", "tags"],
        },
        scroll="5m",
    )
    scroll_id = resp["_scroll_id"]
    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]["value"]
    logger.info("Total documents to embed: %d", total)

    processed = 0
    t0 = time.time()

    while hits:
        texts   = [restaurant_to_text(h["_source"]) for h in hits]
        ids     = [h["_id"] for h in hits]
        vectors = await svc.embed_batch(texts)

        # Bulk update
        ops: List[Any] = []
        for doc_id, vec in zip(ids, vectors):
            if vec is None:
                continue
            ops.append({"update": {"_index": _INDEX, "_id": doc_id}})
            ops.append({"doc": {"embedding": vec}})

        if ops:
            await es.bulk(operations=ops, refresh=False)

        processed += len(hits)
        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed else 0
        eta  = (total - processed) / rate if rate else 0
        logger.info(
            "Progress: %d/%d (%.1f/s) — ETA %.0fs",
            processed, total, rate, eta,
        )

        resp = await es.scroll(scroll_id=scroll_id, scroll="5m")
        scroll_id = resp["_scroll_id"]
        hits = resp["hits"]["hits"]

    await es.clear_scroll(scroll_id=scroll_id)
    await es.indices.refresh(index=_INDEX)
    logger.info("Done. Embedded %d documents in %.1fs", processed, time.time() - t0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--skip-existing", action="store_true", default=True)
    args = parser.parse_args()
    asyncio.run(run(args.batch, args.skip_existing))


if __name__ == "__main__":
    main()
