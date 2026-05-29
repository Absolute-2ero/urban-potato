from __future__ import annotations

"""
Hong Kong Crawler Pipeline

Two-source crawl (OpenRice + Foodpanda), followed by geocoding, dedup, NLP/LLM labeling,
and Elasticsearch indexing.

Usage (from backend/):
  # Crawl OpenRice (takes 30-90 min for a full run):
    py -3.12 -m crawler.hk.hk_pipeline --openrice --max-scroll 200

  # Crawl Foodpanda (show browser to handle any CAPTCHA):
    py -3.12 -m crawler.hk.hk_pipeline --foodpanda --show-browser --max-scroll 200

  # Resume an interrupted crawl:
    py -3.12 -m crawler.hk.hk_pipeline --openrice --resume

  # Geocode all restaurants (fills lat/lng from ALS + Nominatim):
    py -3.12 -m crawler.hk.hk_pipeline --geocode

  # Dedup: merge same-restaurant records from both sources:
    py -3.12 -m crawler.hk.hk_pipeline --dedup

  # NLP + LLM + ES index:
    py -3.12 -m crawler.hk.hk_pipeline --retry-llm

  # Coverage report:
    py -3.12 -m crawler.hk.hk_pipeline --audit
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hk_pipeline_export.csv")
_CSV_COLUMNS = [
    "restaurant_id", "source", "name", "address", "district", "city",
    "cuisine_type", "price_level", "rating", "rating_count",
    "phone", "opening_hours", "diet_labels", "allergens",
    "menu_items_count", "has_llm", "images", "menu_items_json",
    "lat", "lng",
]

_ES_FLUSH_SIZE = 20

_DONE = object()


# ── CSV writer ─────────────────────────────────────────────────────────────────

class _CsvWriter:
    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        exists = os.path.exists(self.path)
        self._file = open(self.path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        if not exists:
            self._writer.writeheader()

    def add(self, doc: dict) -> None:
        geo = doc.get("geo") or {}
        row = {
            "restaurant_id":    doc.get("restaurant_id", ""),
            "source":           doc.get("source", ""),
            "name":             doc.get("name", ""),
            "address":          doc.get("address", ""),
            "district":         doc.get("district", ""),
            "city":             doc.get("city", ""),
            "cuisine_type":     doc.get("cuisine_type", ""),
            "price_level":      doc.get("price_level", ""),
            "rating":           doc.get("rating", ""),
            "rating_count":     doc.get("rating_count", ""),
            "phone":            doc.get("phone", ""),
            "opening_hours":    doc.get("opening_hours", ""),
            "diet_labels":      "|".join(doc.get("diet_labels", [])),
            "allergens":        "|".join(doc.get("allergens", [])),
            "menu_items_count": len(doc.get("menu_items", [])),
            "has_llm":          1 if any(i.get("calories") for i in doc.get("menu_items", [])) else 0,
            "images":           "|".join(doc.get("images", [])),
            "menu_items_json":  json.dumps(doc.get("menu_items", []), ensure_ascii=False),
            "lat":              geo.get("lat", ""),
            "lng":              geo.get("lng", ""),
        }
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()


_csv_writer: _CsvWriter | None = None


# ── SQLite helpers (mirrors beijing/pipeline.py) ───────────────────────────────

async def _init_progress_table() -> None:
    from database import get_sqlite
    db = get_sqlite()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_progress (
            restaurant_id TEXT PRIMARY KEY,
            name          TEXT,
            doc_json      TEXT NOT NULL,
            eleme_done    INTEGER DEFAULT 0,
            llm_done      INTEGER DEFAULT 0,
            indexed       INTEGER DEFAULT 0,
            errors        TEXT DEFAULT '[]',
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        )
    """)
    # Extra columns for HK — ignore errors if they already exist
    for col_sql in [
        "ALTER TABLE pipeline_progress ADD COLUMN geocoded INTEGER DEFAULT 0",
        "ALTER TABLE pipeline_progress ADD COLUMN foodpanda_done INTEGER DEFAULT 0",
    ]:
        try:
            await db.execute(col_sql)
        except Exception:
            pass
    await db.commit()


async def _upsert_doc(doc: dict) -> None:
    from database import get_sqlite
    db = get_sqlite()
    await db.execute(
        """INSERT INTO pipeline_progress (restaurant_id, name, doc_json)
           VALUES (?, ?, ?)
           ON CONFLICT(restaurant_id) DO UPDATE SET
               name=excluded.name,
               doc_json=excluded.doc_json,
               updated_at=datetime('now')""",
        (doc["restaurant_id"], doc.get("name", ""),
         json.dumps(doc, ensure_ascii=False, default=str)),
    )
    await db.commit()


async def _mark(restaurant_id: str, field: str, error: str | None = None) -> None:
    from database import get_sqlite
    db = get_sqlite()
    if error:
        sql = (
            f"UPDATE pipeline_progress SET {field}=1, "
            "errors=json_insert(COALESCE(errors,'[]'),'$[#]',?), "
            "updated_at=datetime('now') WHERE restaurant_id=?"
        )
        await db.execute(sql, (f"{field}:{error[:150]}", restaurant_id))
    else:
        await db.execute(
            f"UPDATE pipeline_progress SET {field}=1, updated_at=datetime('now') WHERE restaurant_id=?",
            (restaurant_id,),
        )
    await db.commit()


async def _is_done(restaurant_id: str) -> bool:
    from database import get_sqlite
    db = get_sqlite()
    async with db.execute(
        "SELECT 1 FROM pipeline_progress WHERE restaurant_id=? AND (indexed=1 OR eleme_done=1 OR foodpanda_done=1)",
        (restaurant_id,),
    ) as cur:
        return await cur.fetchone() is not None


# ── Phase 1a: OpenRice crawl ───────────────────────────────────────────────────

async def run_openrice(max_scrolls: int, resume: bool, show_browser: bool) -> int:
    from crawler.hk.openrice_crawler import OpenRiceScraper

    resume_ids: set[str] = set()
    if resume:
        from database import get_sqlite
        db = get_sqlite()
        async with db.execute(
            "SELECT restaurant_id FROM pipeline_progress WHERE restaurant_id LIKE 'openrice_%'"
        ) as cur:
            rows = await cur.fetchall()
        resume_ids = {r["restaurant_id"] for r in rows}
        logger.info("OpenRice resume: skipping %d already-saved restaurants", len(resume_ids))

    count = 0
    async with OpenRiceScraper(headless=not show_browser) as scraper:
        async for doc in scraper.crawl(max_scrolls=max_scrolls, resume_ids=resume_ids):
            await _upsert_doc(doc)
            await _mark(doc["restaurant_id"], "eleme_done")   # reuse flag: "site crawl done"
            if _csv_writer:
                _csv_writer.add(doc)
            count += 1
            logger.info("OpenRice saved: %r (%d total)", doc.get("name"), count)

    logger.info("OpenRice crawl complete: %d restaurants", count)
    return count


# ── Phase 1b: Foodpanda crawl ──────────────────────────────────────────────────

async def run_foodpanda(max_items: int, resume: bool, show_browser: bool) -> int:
    from crawler.hk.foodpanda_crawler import FoodpandaScraper

    resume_ids: set[str] = set()
    if resume:
        from database import get_sqlite
        db = get_sqlite()
        async with db.execute(
            "SELECT restaurant_id FROM pipeline_progress WHERE restaurant_id LIKE 'foodpanda_%'"
        ) as cur:
            rows = await cur.fetchall()
        resume_ids = {r["restaurant_id"] for r in rows}
        logger.info("Foodpanda resume: skipping %d already-saved restaurants", len(resume_ids))

    count = 0
    async with FoodpandaScraper(headless=not show_browser) as scraper:
        async for doc in scraper.crawl(max_items=max_items, resume_ids=resume_ids):
            await _upsert_doc(doc)
            await _mark(doc["restaurant_id"], "foodpanda_done")
            if _csv_writer:
                _csv_writer.add(doc)
            count += 1
            logger.info("Foodpanda saved: %r (%d total)", doc.get("name"), count)

    logger.info("Foodpanda crawl complete: %d restaurants", count)
    return count


# ── Phase 2: Geocoding ─────────────────────────────────────────────────────────

async def run_geocode() -> int:
    from database import get_sqlite
    from crawler.hk.hk_geocoder import geocode_address

    db = get_sqlite()
    # Load all HK restaurants missing geo data
    async with db.execute(
        """SELECT restaurant_id, doc_json FROM pipeline_progress
           WHERE (restaurant_id LIKE 'openrice_%' OR restaurant_id LIKE 'foodpanda_%')
             AND (geocoded=0 OR geocoded IS NULL)"""
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        logger.info("Geocode: nothing to do (all HK restaurants already geocoded)")
        return 0

    logger.info("Geocode: %d restaurants to geocode", len(rows))
    done = 0
    for row in rows:
        doc = json.loads(row["doc_json"])
        geo = doc.get("geo") or {}
        if geo.get("lat") is not None:
            await _mark(doc["restaurant_id"], "geocoded")
            done += 1
            continue

        address = doc.get("address") or doc.get("district") or ""
        if not address:
            await _mark(doc["restaurant_id"], "geocoded")
            continue

        lat, lng = await geocode_address(address)
        if lat is not None:
            doc["geo"] = {"lat": lat, "lng": lng}
            await _upsert_doc(doc)
        await _mark(doc["restaurant_id"], "geocoded")
        done += 1
        logger.info("Geocoded %r → (%s, %s)", doc.get("name"), lat, lng)

    logger.info("Geocode complete: %d/%d geocoded", done, len(rows))
    return done


# ── Phase 3: Dedup ─────────────────────────────────────────────────────────────

async def run_dedup() -> tuple[int, int]:
    from crawler.hk.hk_dedup import run_dedup as _dedup
    merged, remaining = await _dedup()
    print(f"Dedup: merged {merged} pairs, {remaining} restaurants remaining")
    return merged, remaining


# ── Phase 4: NLP + LLM + ES index ─────────────────────────────────────────────

async def run_retry_llm() -> int:
    from database import get_sqlite
    from crawler.hk.nlp_labeler import label_restaurant
    from crawler.bj.llm_labeler import label_menu_items_batch
    from services.index_service import index_restaurant

    db = get_sqlite()
    async with db.execute(
        """SELECT restaurant_id, doc_json FROM pipeline_progress
           WHERE (restaurant_id LIKE 'openrice_%' OR restaurant_id LIKE 'foodpanda_%')
             AND llm_done=0"""
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        print("Nothing to retry — all HK restaurants already have LLM data.")
        return 0

    logger.info("LLM retry: %d restaurants to process", len(rows))
    done = 0
    for row in rows:
        doc = json.loads(row["doc_json"])
        try:
            label_restaurant(doc)
            if doc.get("menu_items"):
                await label_menu_items_batch(doc)
            await _upsert_doc(doc)
            await _mark(doc["restaurant_id"], "llm_done")
            await index_restaurant(doc)
            await _mark(doc["restaurant_id"], "indexed")
            if _csv_writer:
                _csv_writer.add(doc)
            done += 1
            logger.info("LLM OK: %s", doc.get("name"))
        except Exception as exc:
            logger.warning("LLM failed for %r: %s", doc.get("name"), exc)
            await _mark(doc["restaurant_id"], "llm_done", error=str(exc))

    logger.info("LLM retry complete: %d/%d done", done, len(rows))
    return done


# ── Audit ──────────────────────────────────────────────────────────────────────

async def run_audit() -> None:
    from database import get_sqlite
    db = get_sqlite()
    async with db.execute(
        """SELECT COUNT(*) as t,
                  SUM(CASE WHEN restaurant_id LIKE 'openrice_%' THEN 1 ELSE 0 END) as or_n,
                  SUM(CASE WHEN restaurant_id LIKE 'foodpanda_%' THEN 1 ELSE 0 END) as fp_n,
                  SUM(geocoded) as g, SUM(llm_done) as l, SUM(indexed) as i
           FROM pipeline_progress
           WHERE restaurant_id LIKE 'openrice_%' OR restaurant_id LIKE 'foodpanda_%'"""
    ) as cur:
        row = await cur.fetchone()

    if not row or not row["t"]:
        print("No HK data — run --openrice or --foodpanda first.")
        return

    t = row["t"]
    pct = lambda n: f"{(n or 0) / t * 100:.1f}%"
    print(f"\nHK Pipeline coverage ({t} restaurants total)")
    print(f"  OpenRice      : {row['or_n'] or 0}")
    print(f"  Foodpanda     : {row['fp_n'] or 0}")
    print(f"  Geocoded      : {row['g'] or 0}  ({pct(row['g'])})")
    print(f"  LLM analyzed  : {row['l'] or 0}  ({pct(row['l'])})")
    print(f"  ES indexed    : {row['i'] or 0}  ({pct(row['i'])})")
    print()


# ── CLI ────────────────────────────────────────────────────────────────────────

async def main_async(args: argparse.Namespace) -> None:
    global _csv_writer

    from database import init_sqlite, close_sqlite

    # SQLite is always needed
    await init_sqlite()
    await _init_progress_table()

    if not args.audit:
        _csv_writer = _CsvWriter(_CSV_PATH)
        print(f"CSV backup: {_csv_writer.path}")

    try:
        if args.audit:
            await run_audit()
            return

        if args.geocode:
            n = await run_geocode()
            print(f"Geocoded: {n} restaurants")
            return

        if args.dedup:
            await run_dedup()
            return

        if args.retry_llm:
            # Only retry-llm needs ES + LLM API
            from database import init_es, init_pg, init_redis, close_all
            from services.index_service import ensure_index
            try:
                await init_pg()
            except Exception as exc:
                logger.warning("PostgreSQL not available (skipping): %s", exc)
            try:
                await init_redis()
            except Exception as exc:
                logger.warning("Redis not available (skipping): %s", exc)
            await init_es()
            await ensure_index()
            n = await run_retry_llm()
            print(f"LLM retry: {n} restaurants processed")
            return

        max_scroll = args.max_scroll

        if args.openrice:
            n = await run_openrice(
                max_scrolls=max_scroll,
                resume=args.resume,
                show_browser=args.show_browser,
            )
            print(f"OpenRice crawl done: {n} restaurants saved to SQLite + CSV")
            print("Next: py -3.12 -m crawler.hk.hk_pipeline --foodpanda --show-browser")

        if args.foodpanda:
            n = await run_foodpanda(
                max_items=max_scroll * 20,
                resume=args.resume,
                show_browser=args.show_browser,
            )
            print(f"Foodpanda crawl done: {n} restaurants saved to SQLite + CSV")
            print("Next: py -3.12 -m crawler.hk.hk_pipeline --geocode")

    finally:
        if _csv_writer:
            _csv_writer.close()
        await close_sqlite()


def main() -> None:
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    p = argparse.ArgumentParser(
        description="MacroBite HK crawler pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Recommended workflow:
  # Step 1 — crawl both sites (run separately):
    py -3.12 -m crawler.hk.hk_pipeline --openrice --max-scroll 200
    py -3.12 -m crawler.hk.hk_pipeline --foodpanda --show-browser --max-scroll 200

  # Step 2 — geocode addresses:
    py -3.12 -m crawler.hk.hk_pipeline --geocode

  # Step 3 — merge duplicates across sources:
    py -3.12 -m crawler.hk.hk_pipeline --dedup

  # Step 4 — NLP + LLM labeling + ES index:
    py -3.12 -m crawler.hk.hk_pipeline --retry-llm

  # Check coverage:
    py -3.12 -m crawler.hk.hk_pipeline --audit
""",
    )
    p.add_argument("--openrice",     action="store_true", help="Crawl OpenRice HK")
    p.add_argument("--foodpanda",    action="store_true", help="Crawl Foodpanda HK")
    p.add_argument("--geocode",      action="store_true", help="Geocode restaurants via ALS + Nominatim")
    p.add_argument("--dedup",        action="store_true", help="Merge duplicate records across sources")
    p.add_argument("--retry-llm",    action="store_true", dest="retry_llm",
                   help="Run NLP + LLM labeling + ES index")
    p.add_argument("--audit",        action="store_true", help="Show coverage report and exit")
    p.add_argument("--max-scroll",   type=int, default=200, dest="max_scroll",
                   help="Max scrolls / target item count (default 200)")
    p.add_argument("--show-browser", action="store_true", dest="show_browser",
                   help="Show Chromium window (solve CAPTCHA manually)")
    p.add_argument("--resume",       action="store_true", help="Skip already-saved restaurants")

    try:
        asyncio.run(main_async(p.parse_args()))
    except KeyboardInterrupt:
        print("\n\nCtrl+C — all completed restaurants are already saved (SQLite + CSV).")


if __name__ == "__main__":
    main()
