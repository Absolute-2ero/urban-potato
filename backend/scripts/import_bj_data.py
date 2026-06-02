"""
Import Beijing restaurant data from teammate's NDJSON export into the shared ES index.

Usage (from backend/ directory):
    python -m scripts.import_bj_data
    python -m scripts.import_bj_data --path ../backend-bj/restaurants-es-export/restaurants_data.ndjson
    python -m scripts.import_bj_data --dry-run   # print first 3 docs, don't index
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

_DEFAULT_NDJSON = Path(__file__).parent.parent.parent / "backend-bj" / "restaurants-es-export" / "restaurants_data.ndjson"
_INDEX = "restaurants"
_CHUNK_SIZE = 200


def _transform(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a backend-bj doc for import into the unified index."""
    doc = dict(doc)
    doc["city"] = "beijing"

    # Normalise geo: backend-bj may use {lat, lon} — keep as-is, ES expects lat/lon
    if "geo" in doc and isinstance(doc["geo"], dict):
        g = doc["geo"]
        # Unify to {lat, lon} (drop lng alias if present)
        doc["geo"] = {
            "lat": g.get("lat") or 0,
            "lon": g.get("lon") or g.get("lng") or 0,
        }

    # Rename business_hours → opening_hours for schema consistency
    if "business_hours" in doc and "opening_hours" not in doc:
        doc["opening_hours"] = doc.pop("business_hours")

    return doc


def _load_ndjson(path: Path) -> List[Dict[str, Any]]:
    docs = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                # ES export format wraps data in _source; unwrap it
                if "_source" in raw:
                    doc = dict(raw["_source"])
                    # Use _id from wrapper if document has no restaurant_id
                    if not doc.get("restaurant_id") and raw.get("_id"):
                        doc["restaurant_id"] = raw["_id"]
                else:
                    doc = raw
                docs.append(doc)
            except json.JSONDecodeError as exc:
                logger.warning("Line %d: JSON parse error — %s", lineno, exc)
    return docs


async def _wait_for_es(es: Any, timeout: int = 60) -> None:
    """Wait until ES responds to a ping (up to `timeout` seconds)."""
    import asyncio
    for attempt in range(timeout):
        try:
            await es.info()
            logger.info("Elasticsearch is ready")
            return
        except Exception:
            if attempt % 5 == 0:
                logger.info("Waiting for Elasticsearch… (%ds)", attempt)
            await asyncio.sleep(1)
    raise RuntimeError(f"Elasticsearch not ready after {timeout}s — is Docker running?")


async def _bulk_import(docs: List[Dict[str, Any]], es_url: str) -> None:
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
                rid = doc.get("restaurant_id") or doc.get("_id")
                if not rid:
                    logger.warning("Skipping doc with no restaurant_id: %s", str(doc)[:80])
                    continue
                actions.append({"index": {"_index": _INDEX, "_id": rid}})
                actions.append(doc)

            if not actions:
                continue

            resp = await es.bulk(operations=actions, refresh="wait_for")
            errors = [item for item in resp["items"] if "error" in item.get("index", {})]
            if errors:
                logger.warning("Chunk %d/%d had %d errors: %s", i // _CHUNK_SIZE + 1, (total + _CHUNK_SIZE - 1) // _CHUNK_SIZE, len(errors), errors[:2])
            indexed += len(chunk) - len(errors)
            logger.info("Progress: %d/%d indexed", indexed, total)

        logger.info("Import complete: %d/%d documents successfully indexed into '%s'", indexed, total, _INDEX)
    finally:
        await es.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import BJ restaurant data into ES")
    parser.add_argument("--path", type=Path, default=_DEFAULT_NDJSON, help="Path to NDJSON file")
    parser.add_argument("--es-url", default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"), help="ES URL")
    parser.add_argument("--dry-run", action="store_true", help="Print first 3 transformed docs and exit")
    args = parser.parse_args()

    if not args.path.exists():
        logger.error("NDJSON file not found: %s", args.path)
        sys.exit(1)

    logger.info("Loading %s …", args.path)
    docs = [_transform(d) for d in _load_ndjson(args.path)]
    logger.info("Loaded %d documents", len(docs))

    if args.dry_run:
        for doc in docs[:3]:
            print(json.dumps(doc, ensure_ascii=False, indent=2))
        return

    await _bulk_import(docs, args.es_url)


if __name__ == "__main__":
    asyncio.run(main())
