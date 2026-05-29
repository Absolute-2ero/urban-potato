"""
export_data.py — Export all crawled data to a portable zip file.

Run from the project root:
    py -3.12 scripts/export_data.py

Produces: macrobite_data_YYYY-MM-DD.zip
"""

import asyncio
import json
import os
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
BACKEND = ROOT / "backend"
SQLITE_PATH = BACKEND / "data" / "food_db.sqlite"
EXPORT_DIR = ROOT / "_export_tmp"
OUTPUT_ZIP = ROOT / f"macrobite_data_{date.today()}.zip"

ES_URL = os.environ.get("ES_URL", "http://localhost:9200")
ES_INDEX = "restaurants"


def _check_deps():
    try:
        import elasticsearch  # noqa
    except ImportError:
        print("ERROR: Run from the backend venv or install elasticsearch-py first.")
        sys.exit(1)


async def export_elasticsearch():
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

    out_path = EXPORT_DIR / "restaurants.ndjson"
    count = 0

    print(f"Exporting ES index '{ES_INDEX}'...")
    with open(out_path, "w", encoding="utf-8") as f:
        resp = await es.search(
            index=ES_INDEX,
            body={"query": {"match_all": {}}, "size": 500},
            scroll="2m",
        )
        scroll_id = resp["_scroll_id"]
        hits = resp["hits"]["hits"]

        while hits:
            for hit in hits:
                doc = hit["_source"]
                doc["_id"] = hit["_id"]
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                count += 1

            resp = await es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp["_scroll_id"]
            hits = resp["hits"]["hits"]

        try:
            await es.clear_scroll(scroll_id=scroll_id)
        except Exception:
            pass

    await es.close()
    print(f"  Exported {count} documents → {out_path.name}")
    return count


def export_sqlite():
    if not SQLITE_PATH.exists():
        print(f"WARNING: SQLite not found at {SQLITE_PATH} — skipping")
        return
    dest = EXPORT_DIR / "food_db.sqlite"
    shutil.copy2(SQLITE_PATH, dest)
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"Exported SQLite ({size_mb:.2f} MB) → {dest.name}")


def create_zip():
    print(f"Creating zip: {OUTPUT_ZIP.name} ...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in EXPORT_DIR.iterdir():
            zf.write(f, f.name)
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  + {f.name} ({size_mb:.2f} MB)")
    zip_mb = OUTPUT_ZIP.stat().st_size / 1024 / 1024
    print(f"\nDone! {OUTPUT_ZIP.name} ({zip_mb:.2f} MB)")
    print("Copy this file to the target machine and run:  py scripts/import_data.py <zipfile>")


async def main():
    _check_deps()
    sys.path.insert(0, str(BACKEND))

    EXPORT_DIR.mkdir(exist_ok=True)
    try:
        export_sqlite()
        await export_elasticsearch()
        create_zip()
    finally:
        shutil.rmtree(EXPORT_DIR, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
