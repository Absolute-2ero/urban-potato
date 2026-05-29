from __future__ import annotations

"""
爬虫 Pipeline — 并行流水线版本

四阶段通过 asyncio.Queue 并发运行：
  Gaode 抓取 →[q1]→ Ele.me 丰富 →[q2]→ NLP+LLM 标注 →[q3]→ ES 写入

Crawl modes (no --gemini = crawl only, saves to SQLite + CSV, no ES):
  # Gaode only:
    python -m crawler.pipeline --max-pages 20

  # Gaode + Ele.me (visible browser for CAPTCHA):
    python -m crawler.pipeline --eleme --show-browser --max-pages 20

  # Resume interrupted crawl:
    python -m crawler.pipeline --eleme --show-browser --max-pages 20 --resume

  # Apply NLP + LLM after crawling, then index to ES:
    python -m crawler.pipeline --retry-llm

  # Full pipeline in one shot:
    python -m crawler.pipeline --eleme --gemini

  # Coverage report:
    python -m crawler.pipeline --audit
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

_DEFAULT_KEYWORDS = ["餐厅", "素食", "清真", "有机", "健康餐", "沙拉", "轻食"]
_DONE = object()   # sentinel: signals a stage to shut down
_ES_FLUSH_SIZE = 20

_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline_export.csv")
_CSV_COLUMNS = [
    "restaurant_id", "name", "address", "city", "rating",
    "diet_labels", "allergens", "menu_items_count",
    "has_eleme", "eleme_id", "eleme_distance_m", "monthly_sales",
    "has_llm", "images", "menu_items_json",
]


# ── CSV backup writer ─────────────────────────────────────────────────────────

class _CsvWriter:
    """Writes one CSV row per restaurant. Thread-safe flush on Ctrl+C."""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        self._rows: list[dict] = []
        self._last: dict | None = None
        self._file = None
        self._writer = None
        self._open()

    def _open(self) -> None:
        exists = os.path.exists(self.path)
        self._file = open(self.path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        if not exists:
            self._writer.writeheader()

    def add(self, doc: dict) -> None:
        row = {
            "restaurant_id":   doc.get("restaurant_id", ""),
            "name":            doc.get("name", ""),
            "address":         doc.get("address", ""),
            "city":            doc.get("city", ""),
            "rating":          doc.get("rating", ""),
            "diet_labels":     "|".join(doc.get("diet_labels", [])),
            "allergens":       "|".join(doc.get("allergens", [])),
            "menu_items_count": len(doc.get("menu_items", [])),
            "has_eleme":       1 if doc.get("eleme_id") else 0,
            "eleme_id":        doc.get("eleme_id", ""),
            "eleme_distance_m": doc.get("eleme_distance_m", ""),
            "monthly_sales":   doc.get("monthly_sales", ""),
            "has_llm":         1 if any(i.get("calories") for i in doc.get("menu_items", [])) else 0,
            "images":          "|".join(doc.get("images", [])),
            "menu_items_json": json.dumps(doc.get("menu_items", []), ensure_ascii=False),
        }
        self._writer.writerow(row)
        self._file.flush()
        self._last = doc
        logger.debug("CSV: wrote row for %r", doc.get("name"))

    def flush_last(self) -> None:
        """Called on Ctrl+C — last good record is already written (we flush after every row)."""
        if self._last:
            logger.info("CSV last record: %r", self._last.get("name"))

    def close(self) -> None:
        if self._file:
            self._file.close()


_csv_writer: _CsvWriter | None = None


# ── SQLite checkpoint ─────────────────────────────────────────────────────────

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
    await db.commit()


async def _is_done(restaurant_id: str) -> bool:
    """True if this restaurant has already been processed (eleme enriched OR fully indexed)."""
    from database import get_sqlite
    db = get_sqlite()
    async with db.execute(
        "SELECT 1 FROM pipeline_progress WHERE restaurant_id=? AND (eleme_done=1 OR indexed=1)",
        (restaurant_id,),
    ) as cur:
        return await cur.fetchone() is not None


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


_MARK_SQL = {
    "eleme_done": "UPDATE pipeline_progress SET eleme_done=1, updated_at=datetime('now') WHERE restaurant_id=?",
    "llm_done":   "UPDATE pipeline_progress SET llm_done=1,   updated_at=datetime('now') WHERE restaurant_id=?",
    "indexed":    "UPDATE pipeline_progress SET indexed=1,     updated_at=datetime('now') WHERE restaurant_id=?",
}
_MARK_SQL_ERR = {
    "eleme_done": "UPDATE pipeline_progress SET eleme_done=1, errors=json_insert(COALESCE(errors,'[]'),'$[#]',?), updated_at=datetime('now') WHERE restaurant_id=?",
    "llm_done":   "UPDATE pipeline_progress SET llm_done=1,   errors=json_insert(COALESCE(errors,'[]'),'$[#]',?), updated_at=datetime('now') WHERE restaurant_id=?",
    "indexed":    "UPDATE pipeline_progress SET indexed=1,     errors=json_insert(COALESCE(errors,'[]'),'$[#]',?), updated_at=datetime('now') WHERE restaurant_id=?",
}


async def _mark(restaurant_id: str, field: str, error: str | None = None) -> None:
    from database import get_sqlite
    db = get_sqlite()
    if error:
        await db.execute(_MARK_SQL_ERR[field], (f"{field}:{error[:150]}", restaurant_id))
    else:
        await db.execute(_MARK_SQL[field], (restaurant_id,))
    await db.commit()


# ── Stage 1: Gaode producer ───────────────────────────────────────────────────

async def _stage_gaode(
    city: str,
    keywords: list[str],
    max_pages: int,
    out_q: asyncio.Queue,
    resume: bool,
) -> None:
    import crawler.gaode_crawler as _gaode

    seen_ids: set = set()
    sent = skipped = 0

    try:
        for kw in keywords:
            for page in range(1, max_pages + 1):
                pois = await _gaode.search_restaurants_by_keyword(kw, city=city, page=page)
                if not pois:
                    break
                new_this_page = 0
                for poi in pois:
                    rid = poi.get("id")
                    if not rid or rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    new_this_page += 1
                    doc = _gaode.normalize_poi(poi)
                    doc["city"] = city
                    if resume and await _is_done(doc["restaurant_id"]):
                        skipped += 1
                        continue
                    await _upsert_doc(doc)
                    await out_q.put(doc)
                    sent += 1
                logger.info(
                    "Gaode page kw=%r page=%d new=%d total_sent=%d",
                    kw, page, new_this_page, sent,
                )
                await asyncio.sleep(0.3)
                if new_this_page == 0:
                    break  # all results for this keyword are duplicates — stop paging

        if sent == 0:
            logger.warning("Gaode: 0 restaurants queued — check GAODE_API_KEY")
        else:
            logger.info("Gaode stage done: sent=%d skipped=%d unique_seen=%d", sent, skipped, len(seen_ids))
    except Exception as exc:
        logger.error("Gaode stage error: %s", exc)
    finally:
        await out_q.put(_DONE)


# ── Stage 2a: Ele.me enricher (queue-based, used in full pipeline) ────────────

async def _stage_eleme_from_sqlite(city: str, show_browser: bool = False) -> int:
    """Read all unenriched restaurants from SQLite and enrich with Ele.me."""
    from database import get_sqlite

    db = get_sqlite()
    async with db.execute(
        "SELECT restaurant_id, doc_json FROM pipeline_progress WHERE eleme_done=0"
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        logger.info("Ele.me: nothing to enrich")
        return 0

    logger.info("Ele.me: enriching %d restaurants from SQLite", len(rows))

    try:
        from crawler.eleme_crawler import ElemeScraper
    except ImportError:
        logger.warning("Playwright not installed — Ele.me enrichment skipped")
        return 0

    enriched = 0
    async with ElemeScraper(city=city, headless=not show_browser) as scraper:
        for row in rows:
            doc = json.loads(row["doc_json"])
            try:
                await scraper.enrich(doc)
                if doc.get("menu_items"):
                    enriched += 1
                await _upsert_doc(doc)
                await _mark(doc["restaurant_id"], "eleme_done")
                if _csv_writer:
                    _csv_writer.add(doc)
                logger.info(
                    "Ele.me enriched: %r (%d items)", doc.get("name"), len(doc.get("menu_items", []))
                )
            except Exception as exc:
                logger.warning("Ele.me failed for %r: %s", doc.get("name"), exc)
                await _mark(doc["restaurant_id"], "eleme_done", error=str(exc))
            await asyncio.sleep(random.uniform(1.2, 3.0))

    logger.info("Ele.me enrichment done: enriched=%d/%d", enriched, len(rows))
    return len(rows)


async def _stage_eleme(
    in_q: asyncio.Queue,
    out_q: asyncio.Queue,
    city: str,
    enabled: bool,
    show_browser: bool = False,
) -> None:
    if not enabled:
        while True:
            item = await in_q.get()
            if item is _DONE:
                break
            await out_q.put(item)
        await out_q.put(_DONE)
        return

    try:
        from crawler.eleme_crawler import ElemeScraper
    except ImportError:
        logger.warning("Playwright not installed — Ele.me enrichment skipped")
        while True:
            item = await in_q.get()
            if item is _DONE:
                break
            await out_q.put(item)
        await out_q.put(_DONE)
        return

    enriched = total = 0
    async with ElemeScraper(city=city, headless=not show_browser) as scraper:
        while True:
            doc = await in_q.get()
            if doc is _DONE:
                break
            total += 1
            try:
                await scraper.enrich(doc)
                if doc.get("menu_items"):
                    enriched += 1
                await _upsert_doc(doc)
                await _mark(doc["restaurant_id"], "eleme_done")
            except Exception as exc:
                logger.warning("Ele.me failed for %r: %s", doc.get("name"), exc)
                await _mark(doc["restaurant_id"], "eleme_done", error=str(exc))

            await out_q.put(doc)
            await asyncio.sleep(random.uniform(1.2, 3.0))

    logger.info("Ele.me stage done: enriched=%d/%d", enriched, total)
    await out_q.put(_DONE)


# ── Stage 3: NLP + LLM labeler ────────────────────────────────────────────────

async def _stage_label(
    in_q: asyncio.Queue,
    out_q: asyncio.Queue,
    run_llm: bool,
) -> None:
    from crawler.nlp_labeler import label_restaurant

    llm_fn = None
    if run_llm:
        try:
            from crawler.llm_labeler import label_menu_items_batch
            llm_fn = label_menu_items_batch
        except ImportError:
            logger.warning("llm_labeler not available — LLM step skipped")

    total = 0
    while True:
        doc = await in_q.get()
        if doc is _DONE:
            break
        total += 1

        try:
            label_restaurant(doc)
        except Exception as exc:
            logger.warning("NLP failed for %r: %s", doc.get("name"), exc)

        if llm_fn and doc.get("menu_items"):
            try:
                await llm_fn(doc)
                await _upsert_doc(doc)
                await _mark(doc["restaurant_id"], "llm_done")
            except Exception as exc:
                logger.warning("LLM failed for %r: %s", doc.get("name"), exc)
                await _mark(doc["restaurant_id"], "llm_done", error=str(exc))
        else:
            await _mark(doc["restaurant_id"], "llm_done")

        await out_q.put(doc)

    logger.info("Label stage done: processed=%d", total)
    await out_q.put(_DONE)


# ── Stage 4: ES indexer + CSV writer ─────────────────────────────────────────

async def _stage_index(in_q: asyncio.Queue, dry_run: bool) -> int:
    from services.index_service import bulk_index

    if dry_run:
        count = 0
        first = None
        while True:
            doc = await in_q.get()
            if doc is _DONE:
                break
            count += 1
            if _csv_writer:
                _csv_writer.add(doc)
            if first is None:
                first = doc
        if first:
            print(json.dumps(first, ensure_ascii=False, indent=2, default=str))
        logger.info("Dry run: %d restaurants would be indexed", count)
        return count

    batch: list[dict] = []
    indexed = 0

    async def _flush() -> None:
        nonlocal indexed, batch
        if not batch:
            return
        n = await bulk_index(batch)
        for doc in batch:
            await _mark(doc["restaurant_id"], "indexed")
            if _csv_writer:
                _csv_writer.add(doc)
        indexed += n
        logger.info("ES flush: +%d (total indexed=%d)", n, indexed)
        batch = []

    while True:
        doc = await in_q.get()
        if doc is _DONE:
            await _flush()
            break
        batch.append(doc)
        if len(batch) >= _ES_FLUSH_SIZE:
            await _flush()

    return indexed


# ── Audit ─────────────────────────────────────────────────────────────────────

async def run_audit() -> None:
    from database import get_sqlite
    db = get_sqlite()
    async with db.execute(
        "SELECT COUNT(*) as t, SUM(eleme_done) as e, SUM(llm_done) as l, SUM(indexed) as i FROM pipeline_progress"
    ) as cur:
        row = await cur.fetchone()
    if not row or not row["t"]:
        print("No pipeline data — run the pipeline first.")
        return

    t = row["t"]
    pct = lambda n: f"{(n or 0) / t * 100:.1f}%"
    print(f"\nPipeline coverage")
    print(f"  Total restaurants : {t}")
    print(f"  Ele.me enriched   : {row['e'] or 0}  ({pct(row['e'])})")
    print(f"  LLM analyzed      : {row['l'] or 0}  ({pct(row['l'])})")
    print(f"  ES indexed        : {row['i'] or 0}  ({pct(row['i'])})")

    async with db.execute(
        "SELECT COUNT(*) as n FROM pipeline_progress WHERE eleme_done=1 AND llm_done=0"
    ) as cur:
        r2 = await cur.fetchone()
    if r2 and r2["n"]:
        print(f"\n  {r2['n']} restaurants enriched but missing LLM — run --retry-llm")

    async with db.execute(
        "SELECT COUNT(*) as n FROM pipeline_progress WHERE indexed=0"
    ) as cur:
        r3 = await cur.fetchone()
    if r3 and r3["n"]:
        print(f"  {r3['n']} restaurants not yet indexed — re-run with --resume")
    print()


# ── Retry LLM ────────────────────────────────────────────────────────────────

async def run_retry_llm() -> int:
    from database import get_sqlite
    from crawler.nlp_labeler import label_restaurant
    from crawler.llm_labeler import label_menu_items_batch
    from services.index_service import index_restaurant

    db = get_sqlite()
    async with db.execute(
        "SELECT restaurant_id, doc_json FROM pipeline_progress WHERE llm_done=0"
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        print("Nothing to retry — all restaurants already have LLM data.")
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
            logger.info("Retry OK: %s", doc.get("name"))
        except Exception as exc:
            logger.warning("Retry failed for %r: %s", doc.get("name"), exc)
            await _mark(doc["restaurant_id"], "llm_done", error=str(exc))

    logger.info("LLM retry complete: %d/%d done", done, len(rows))
    return done


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline(
    city: str = "北京",
    keywords: list[str] | None = None,
    max_pages: int = 5,
    enrich_eleme: bool = False,
    run_gemini: bool = False,
    dry_run: bool = False,
    resume: bool = False,
    show_browser: bool = False,
) -> int:
    keywords = keywords or _DEFAULT_KEYWORDS
    await _init_progress_table()

    gaode_q: asyncio.Queue = asyncio.Queue(maxsize=200)
    eleme_q: asyncio.Queue = asyncio.Queue(maxsize=200)

    # Crawl-only mode: any run without --gemini stops after Gaode (+ optional Ele.me).
    # Each restaurant is written to SQLite + CSV immediately.
    # Use --retry-llm afterwards to apply NLP + LLM and index to Elasticsearch.
    crawl_only = not run_gemini and not dry_run

    logger.info(
        "Pipeline start: city=%s pages=%d eleme=%s llm=%s crawl_only=%s resume=%s show_browser=%s",
        city, max_pages, enrich_eleme, run_gemini, crawl_only, resume, show_browser,
    )

    if crawl_only:
        # Phase 1: collect all Gaode data into SQLite + CSV before touching Ele.me
        async def _drain(q: asyncio.Queue) -> int:
            n = 0
            while True:
                item = await q.get()
                if item is _DONE:
                    return n
                n += 1
                if _csv_writer:
                    _csv_writer.add(item)

        _, gaode_count = await asyncio.gather(
            _stage_gaode(city, keywords, max_pages, gaode_q, resume),
            _drain(gaode_q),
        )
        logger.info("Phase 1 (Gaode) complete: %d restaurants in SQLite + CSV", gaode_count)

        if not enrich_eleme:
            return gaode_count

        # Phase 2: Ele.me enrichment — reads from SQLite, no concurrent Gaode
        eleme_count = await _stage_eleme_from_sqlite(city, show_browser)
        logger.info("Phase 2 (Ele.me) complete: %d restaurants enriched", eleme_count)
        return eleme_count

    label_q: asyncio.Queue = asyncio.Queue(maxsize=200)
    results = await asyncio.gather(
        _stage_gaode(city, keywords, max_pages, gaode_q, resume),
        _stage_eleme(gaode_q, eleme_q, city, enrich_eleme, show_browser),
        _stage_label(eleme_q, label_q, run_gemini),
        _stage_index(label_q, dry_run),
    )
    count: int = results[3]
    logger.info("Pipeline complete: %d restaurants indexed", count)
    return count


async def run_all_cities(
    max_pages: int = 5,
    enrich_eleme: bool = False,
    run_gemini: bool = False,
    dry_run: bool = False,
    resume: bool = False,
    show_browser: bool = False,
) -> int:
    from config import load_cities
    cities = load_cities()
    if not cities:
        logger.warning("No cities found in cities.yaml — nothing to crawl")
        return 0
    total = 0
    for city_cfg in cities:
        label = city_cfg["label"]
        logger.info("=== Starting city: %s ===", label)
        n = await run_pipeline(
            city=label,
            max_pages=max_pages,
            enrich_eleme=enrich_eleme,
            run_gemini=run_gemini,
            dry_run=dry_run,
            resume=resume,
            show_browser=show_browser,
        )
        total += n
        logger.info("=== Done: %s — %d indexed ===", label, n)
    return total


async def run_scheduled_crawl() -> int:
    return await run_all_cities(max_pages=2, resume=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

async def main_async(args: argparse.Namespace) -> None:
    global _csv_writer

    from database import close_all, init_es, init_pg, init_redis, init_sqlite
    from services.index_service import ensure_index

    await init_pg()
    await init_sqlite()
    await init_redis()

    # Open CSV writer unless audit/retry-llm/dry-run
    if not args.audit:
        _csv_writer = _CsvWriter(_CSV_PATH)
        print(f"CSV backup: {_csv_writer.path}")

    try:
        if args.audit:
            await run_audit()
            return

        await init_es()
        await ensure_index()

        if args.retry_llm:
            n = await run_retry_llm()
            print(f"LLM retry: {n} restaurants processed")
            return

        keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
        if args.city:
            count = await run_pipeline(
                city=args.city,
                keywords=keywords,
                max_pages=args.max_pages,
                enrich_eleme=args.eleme,
                run_gemini=args.gemini,
                dry_run=args.dry_run,
                resume=args.resume,
                show_browser=args.show_browser,
            )
        else:
            count = await run_all_cities(
                max_pages=args.max_pages,
                enrich_eleme=args.eleme,
                run_gemini=args.gemini,
                dry_run=args.dry_run,
                resume=args.resume,
                show_browser=args.show_browser,
            )
        if args.dry_run:
            print(f"Would index {count} restaurants (dry run — nothing written to ES)")
        elif not args.gemini:
            mode = "Gaode + Ele.me" if args.eleme else "Gaode only"
            print(f"Crawl-only ({mode}): {count} restaurants saved to SQLite + CSV")
            print("Next step: python -m crawler.pipeline --retry-llm")
        else:
            print(f"Indexed {count} restaurants")
        if _csv_writer:
            print(f"CSV: {_csv_writer.path}")
    finally:
        if _csv_writer:
            _csv_writer.close()
        await close_all()


def main() -> None:
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)  # suppress Playwright pipe noise on Windows
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description="MacroBite crawler pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Recommended workflow:
  # Step 1a — Gaode only (fast, no browser needed):
    python -m crawler.pipeline --max-pages 20

  # Step 1b — add Ele.me enrichment (shows browser for CAPTCHA):
    python -m crawler.pipeline --eleme --show-browser --max-pages 20 --resume

  # Step 2 — NLP + LLM analysis + index to Elasticsearch:
    python -m crawler.pipeline --retry-llm

One-shot (everything in one run):
    python -m crawler.pipeline --eleme --gemini --max-pages 20

Other:
    python -m crawler.pipeline --audit          # coverage report
    python -m crawler.pipeline --retry-llm      # re-run LLM on missing restaurants
""",
    )
    p.add_argument("--city",         default="",      help="Override city (default: all cities in config/cities.yaml)")
    p.add_argument("--keywords",     default="",      help="Comma-separated search keywords")
    p.add_argument("--max-pages",    type=int, default=5, dest="max_pages")
    p.add_argument("--eleme",        action="store_true", help="Enable Ele.me enrichment")
    p.add_argument("--gemini",       action="store_true", help="Enable LLM analysis")
    p.add_argument("--show-browser", action="store_true", dest="show_browser",
                   help="Show Chromium window (lets you solve CAPTCHA manually)")
    p.add_argument("--dry-run",      action="store_true", dest="dry_run", help="Skip ES write, print sample doc")
    p.add_argument("--resume",       action="store_true", help="Skip already-indexed restaurants")
    p.add_argument("--audit",        action="store_true", help="Show coverage report and exit")
    p.add_argument("--retry-llm",    action="store_true", dest="retry_llm",
                   help="Re-run LLM on restaurants missing analysis")
    try:
        asyncio.run(main_async(p.parse_args()))
    except KeyboardInterrupt:
        print("\n\nCtrl+C — all completed restaurants are already saved (SQLite + CSV).")


if __name__ == "__main__":
    main()
