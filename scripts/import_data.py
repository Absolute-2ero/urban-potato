"""
import_data.py — Import crawled data from a zip file exported by export_data.py.

Run from the project root:
    py -3.12 scripts/import_data.py macrobite_data_2026-05-30.zip

What it does:
  1. Restores food_db.sqlite  → backend/data/food_db.sqlite
  2. Re-indexes all restaurants into Elasticsearch
"""

import asyncio
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
BACKEND = ROOT / "backend"
SQLITE_DEST = BACKEND / "data" / "food_db.sqlite"
IMPORT_DIR = ROOT / "_import_tmp"

ES_URL = os.environ.get("ES_URL", "http://localhost:9200")
ES_INDEX = "restaurants"
BULK_SIZE = 200


def _check_deps():
    try:
        import elasticsearch  # noqa
    except ImportError:
        print("ERROR: Run from the backend venv or install elasticsearch-py first.")
        sys.exit(1)


def unzip(zip_path: Path):
    print(f"Unzipping {zip_path.name} ...")
    IMPORT_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(IMPORT_DIR)
        for name in zf.namelist():
            size_mb = (IMPORT_DIR / name).stat().st_size / 1024 / 1024
            print(f"  {name} ({size_mb:.2f} MB)")


def restore_sqlite():
    src = IMPORT_DIR / "food_db.sqlite"
    if not src.exists():
        print("WARNING: food_db.sqlite not found in zip — skipping")
        return
    SQLITE_DEST.parent.mkdir(parents=True, exist_ok=True)
    if SQLITE_DEST.exists():
        backup = SQLITE_DEST.with_suffix(".sqlite.bak")
        shutil.copy2(SQLITE_DEST, backup)
        print(f"  Backed up existing DB → {backup.name}")
    shutil.copy2(src, SQLITE_DEST)
    size_mb = SQLITE_DEST.stat().st_size / 1024 / 1024
    print(f"Restored SQLite ({size_mb:.2f} MB) → {SQLITE_DEST}")


async def restore_elasticsearch():
    ndjson = IMPORT_DIR / "restaurants.ndjson"
    if not ndjson.exists():
        print("WARNING: restaurants.ndjson not found in zip — skipping ES import")
        return

    from elasticsearch import AsyncElasticsearch

    es = AsyncElasticsearch(ES_URL)
    try:
        info = await es.info()
        print(f"ES connected: {info['version']['number']}")
    except Exception as e:
        print(f"ERROR: Cannot connect to Elasticsearch at {ES_URL}: {e}")
        print("Make sure Docker is running: docker-compose up -d elasticsearch")
        await es.close()
        sys.exit(1)

    # Ensure index exists (uses the app's mapping)
    sys.path.insert(0, str(BACKEND))
    try:
        from database import init_es, close_all
        from services.index_service import ensure_index
        await init_es()
        await ensure_index()
    except Exception as e:
        print(f"WARNING: Could not auto-create index ({e}) — will let ES create it dynamically")

    # Bulk index
    print(f"Importing documents into '{ES_INDEX}' ...")
    docs = []
    with open(ndjson, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))

    total = len(docs)
    indexed = 0
    errors = 0

    for start in range(0, total, BULK_SIZE):
        batch = docs[start: start + BULK_SIZE]
        actions = []
        for doc in batch:
            doc_id = doc.pop("_id", doc.get("restaurant_id"))
            actions.append({"index": {"_index": ES_INDEX, "_id": doc_id}})
            actions.append(doc)

        resp = await es.bulk(operations=actions, refresh=False)
        batch_errors = [item for item in resp["items"] if "error" in item.get("index", {})]
        errors += len(batch_errors)
        indexed += len(batch) - len(batch_errors)

        pct = (start + len(batch)) / total * 100
        print(f"  {start + len(batch)}/{total} ({pct:.0f}%) — {errors} errors so far", end="\r")

    await es.indices.refresh(index=ES_INDEX)
    await es.close()
    print(f"\nImported {indexed}/{total} documents  ({errors} errors)")


async def main():
    if len(sys.argv) < 2:
        print("Usage: py scripts/import_data.py <path/to/macrobite_data_YYYY-MM-DD.zip>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    if not zip_path.exists():
        print(f"ERROR: File not found: {zip_path}")
        sys.exit(1)

    _check_deps()

    try:
        unzip(zip_path)
        restore_sqlite()
        await restore_elasticsearch()
        print("\nAll done! Start the backend and the data should be available.")
    finally:
        shutil.rmtree(IMPORT_DIR, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
