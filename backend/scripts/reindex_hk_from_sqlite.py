"""
Re-index HK restaurant data from SQLite pipeline_progress into ES.

Usage (from backend/ directory):
    python -m scripts.reindex_hk_from_sqlite
    python -m scripts.reindex_hk_from_sqlite --all        # include not-yet-llm-done rows too
    python -m scripts.reindex_hk_from_sqlite --dry-run    # print first 3 docs, don't index
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_INDEX = "restaurants"
_CHUNK_SIZE = 200
_DEFAULT_SQLITE = Path(__file__).parent.parent / "data" / "food_db.sqlite"


def _load_from_sqlite(path: Path, llm_only: bool = True) -> List[Dict[str, Any]]:
    import sqlite3
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    query = "SELECT doc_json FROM pipeline_progress"
    if llm_only:
        query += " WHERE llm_done=1"
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    docs = []
    for row in rows:
        raw = row["doc_json"]
        if not raw:
            continue
        try:
            doc = json.loads(raw)
            doc["city"] = "hongkong"
            # Normalise geo: ensure {lat, lon} not {lat, lng}
            if "geo" in doc and isinstance(doc["geo"], dict):
                g = doc["geo"]
                doc["geo"] = {
                    "lat": g.get("lat") or 0,
                    "lon": g.get("lon") or g.get("lng") or 0,
                }
            docs.append(doc)
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("Failed to parse doc_json: %s", exc)

    logger.info("Loaded %d HK documents from SQLite (%s)", len(docs), "llm_done only" if llm_only else "all")
    return docs


async def _wait_for_es(es: Any, timeout: int = 60) -> None:
    for attempt in range(timeout):
        try:
            await es.info()
            logger.info("Elasticsearch is ready")
            return
        except Exception:
            if attempt % 5 == 0:
                logger.info("Waiting for Elasticsearch… (%ds)", attempt)
            await asyncio.sleep(1)
    raise RuntimeError(f"Elasticsearch not ready after {timeout}s")


async def _bulk_index(docs: List[Dict[str, Any]], es_url: str) -> None:
    from elasticsearch import AsyncElasticsearch
    es = AsyncElasticsearch(es_url)
    try:
        await _wait_for_es(es)
        total = len(docs)
        indexed = 0
        for i in range(0, total, _CHUNK_SIZE):
            chunk = docs[i: i + _CHUNK_SIZE]
            actions: List[Dict] = []
            for doc in chunk:
                rid = doc.get("restaurant_id")
                if not rid:
                    continue
                actions.append({"index": {"_index": _INDEX, "_id": rid}})
                actions.append(doc)
            if not actions:
                continue
            resp = await es.bulk(operations=actions, refresh="wait_for")
            errors = [item for item in resp["items"] if "error" in item.get("index", {})]
            if errors:
                logger.warning("Chunk %d had %d errors: %s", i // _CHUNK_SIZE + 1, len(errors), errors[:2])
            indexed += len(chunk) - len(errors)
            logger.info("Progress: %d/%d indexed", indexed, total)
        logger.info("Import complete: %d/%d HK documents indexed into '%s'", indexed, total, _INDEX)
    finally:
        await es.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Re-index HK restaurants from SQLite into ES")
    parser.add_argument("--sqlite", type=Path, default=_DEFAULT_SQLITE)
    parser.add_argument("--es-url", default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"))
    parser.add_argument("--all", action="store_true", dest="include_all", help="Include rows where llm_done=0 too")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.sqlite.exists():
        logger.error("SQLite not found: %s", args.sqlite)
        sys.exit(1)

    docs = _load_from_sqlite(args.sqlite, llm_only=not args.include_all)

    if args.dry_run:
        for doc in docs[:3]:
            print(json.dumps({k: v for k, v in doc.items() if k != "menu_items"}, ensure_ascii=False, indent=2))
        return

    await _bulk_index(docs, args.es_url)


if __name__ == "__main__":
    asyncio.run(main())
