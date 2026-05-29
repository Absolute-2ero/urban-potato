"""
Pipeline smoke test — 3 restaurants end-to-end.

Pulls 3 restaurants from Gaode, enriches them with Ele.me, runs the LLM,
then indexes them into ES and saves progress to SQLite. Finishes with a
verification step that checks both stores for the expected data.

Usage (from the backend/ directory):
    python -m crawler.test.pipeline_smoke_test

Flags:
    --no-eleme   Skip Ele.me step (useful if eleme_state.json is missing)
    --no-llm     Skip LLM step (useful if LLM_API_KEY is not set)
    --city 上海   Override city (default: first city in config/cities.yaml)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PASS = "  [PASS]"
FAIL = "  [FAIL]"
SKIP = "  [SKIP]"
INFO = "  [INFO]"

N_RESTAURANTS = 3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def _print_doc(doc: dict, indent: int = 4) -> None:
    pad = " " * indent
    print(f"{pad}name        : {doc.get('name')}")
    print(f"{pad}restaurant_id: {doc.get('restaurant_id')}")
    print(f"{pad}address     : {doc.get('address', '—')}")
    print(f"{pad}rating      : {doc.get('rating', '—')}")
    print(f"{pad}diet_labels : {doc.get('diet_labels', [])}")
    print(f"{pad}allergens   : {doc.get('allergens', [])}")
    items = doc.get("menu_items", [])
    print(f"{pad}menu_items  : {len(items)}")
    for item in items[:3]:
        name_en = item.get("name_en", "")
        cal     = item.get("calories", "?")
        labels  = item.get("diet_labels", [])
        print(f"{pad}  · {item.get('name')} / {name_en}  {cal} kcal  {labels}")
    if len(items) > 3:
        print(f"{pad}  … and {len(items) - 3} more")


# ── Steps ─────────────────────────────────────────────────────────────────────

async def step_gaode(city: str) -> list[dict]:
    _section(f"Step 1 — Gaode crawl  (city={city}, n={N_RESTAURANTS})")
    from crawler.gaode_crawler import normalize_poi, search_restaurants_by_keyword

    pois = await search_restaurants_by_keyword("餐厅", city=city, page=1)
    if not pois:
        print(f"{FAIL} Gaode returned 0 results — check GAODE_API_KEY and city name")
        return []

    docs = [normalize_poi(p) for p in pois[:N_RESTAURANTS]]
    print(f"{PASS} Got {len(docs)} restaurants from Gaode")
    for doc in docs:
        print(f"\n    • {doc['name']}")
        print(f"      address: {doc.get('address', '—')}")
        print(f"      rating : {doc.get('rating', '—')}")
    return docs


async def step_eleme(docs: list[dict], city: str, headless: bool = True) -> list[dict]:
    _section("Step 2 — Ele.me enrichment")
    try:
        from crawler.eleme_crawler import ElemeScraper
    except ImportError:
        print(f"{SKIP} Playwright not installed")
        return docs

    enriched_count = 0
    async with ElemeScraper(city=city, headless=headless) as scraper:
        for doc in docs:
            try:
                await scraper.enrich(doc)
                n = len(doc.get("menu_items", []))
                if n:
                    enriched_count += 1
                    print(f"{PASS} {doc['name']}: {n} menu items, images={len(doc.get('images', []))}")
                else:
                    print(f"{INFO} {doc['name']}: no Ele.me match found")
            except Exception as exc:
                print(f"{FAIL} {doc['name']}: {exc}")
            await asyncio.sleep(1.5)

    print(f"\n{INFO} Enriched {enriched_count}/{len(docs)} restaurants with menu data")
    return docs


async def step_nlp(docs: list[dict]) -> list[dict]:
    _section("Step 3 — NLP labeling")
    from crawler.nlp_labeler import label_restaurant

    for doc in docs:
        label_restaurant(doc)
        print(f"{PASS} {doc['name']}: diet_labels={doc['diet_labels']}")
    return docs


async def step_llm(docs: list[dict]) -> list[dict]:
    _section("Step 4 — LLM analysis")
    from config import cfg

    if not cfg.llm_api_key:
        print(f"{SKIP} LLM_API_KEY not set in .env")
        return docs

    from crawler.llm_labeler import label_menu_items_batch

    for doc in docs:
        items = doc.get("menu_items", [])
        if not items:
            print(f"{INFO} {doc['name']}: no menu items — skipping LLM")
            continue
        try:
            await label_menu_items_batch(doc)
            translated = sum(1 for i in items if i.get("name_en"))
            print(f"{PASS} {doc['name']}: {len(items)} items analyzed, {translated} translated to English")
        except Exception as exc:
            print(f"{FAIL} {doc['name']}: {exc}")
    return docs


async def step_save_progress(docs: list[dict]) -> None:
    _section("Step 5 — Save to SQLite pipeline_progress")
    from crawler.pipeline import _init_progress_table, _mark, _upsert_doc

    await _init_progress_table()
    for doc in docs:
        await _upsert_doc(doc)
        await _mark(doc["restaurant_id"], "eleme_done")
        await _mark(doc["restaurant_id"], "llm_done")
        print(f"{PASS} Saved: {doc['name']}  ({doc['restaurant_id']})")


async def step_index_es(docs: list[dict]) -> None:
    _section("Step 6 — Index to Elasticsearch")
    from services.index_service import bulk_index, ensure_index
    from crawler.pipeline import _mark

    await ensure_index()
    n = await bulk_index(docs)
    if n == len(docs):
        print(f"{PASS} Indexed {n}/{len(docs)} documents")
    else:
        print(f"{FAIL} Only {n}/{len(docs)} indexed — check ES logs")
    for doc in docs:
        await _mark(doc["restaurant_id"], "indexed")


# ── Verification ──────────────────────────────────────────────────────────────

async def verify_sqlite(docs: list[dict]) -> None:
    _section("Verification — SQLite pipeline_progress")
    from database import get_sqlite

    db = get_sqlite()
    all_ok = True
    for doc in docs:
        rid = doc["restaurant_id"]
        async with db.execute(
            "SELECT name, eleme_done, llm_done, indexed, errors FROM pipeline_progress WHERE restaurant_id=?",
            (rid,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            print(f"{FAIL} {doc['name']}: NOT FOUND in pipeline_progress")
            all_ok = False
            continue
        flags = f"eleme={row['eleme_done']} llm={row['llm_done']} indexed={row['indexed']}"
        errors = json.loads(row["errors"] or "[]")
        if row["eleme_done"] and row["llm_done"] and row["indexed"]:
            print(f"{PASS} {row['name']}: {flags}")
        else:
            print(f"{FAIL} {row['name']}: {flags}  errors={errors}")
            all_ok = False
    print(f"\n  SQLite: {'ALL GOOD' if all_ok else 'SOME FAILURES — see above'}")


async def verify_es(docs: list[dict]) -> None:
    _section("Verification — Elasticsearch")
    from database import get_es

    es = get_es()
    all_ok = True
    for doc in docs:
        rid = doc["restaurant_id"]
        try:
            result = await es.get(index="restaurants", id=rid)
            source = result["_source"]
            menu_count = len(source.get("menu_items", []))
            labels = source.get("diet_labels", [])
            print(f"{PASS} {source.get('name')}: menu_items={menu_count} diet_labels={labels}")
        except Exception as exc:
            print(f"{FAIL} {doc['name']} ({rid}): {exc}")
            all_ok = False
    print(f"\n  Elasticsearch: {'ALL GOOD' if all_ok else 'SOME FAILURES — see above'}")


async def print_final_docs(docs: list[dict]) -> None:
    _section("Final document state (what was saved)")
    for i, doc in enumerate(docs, 1):
        print(f"\n  [{i}] ", end="")
        _print_doc(doc)


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(city: str, run_eleme: bool, run_llm: bool, show_browser: bool = False) -> None:
    from database import close_all, init_es, init_sqlite
    from config import load_cities

    if not city:
        cities = load_cities()
        city = cities[0]["label"] if cities else "北京"

    print(f"\nPipeline smoke test — city={city}  eleme={run_eleme}  llm={run_llm}  headless={not show_browser}")

    await init_sqlite()
    await init_es()

    try:
        docs = await step_gaode(city)
        if not docs:
            return

        if run_eleme:
            docs = await step_eleme(docs, city, headless=not show_browser)

        docs = await step_nlp(docs)

        if run_llm:
            docs = await step_llm(docs)

        await step_save_progress(docs)
        await step_index_es(docs)

        await print_final_docs(docs)
        await verify_sqlite(docs)
        await verify_es(docs)

        print(f"\n{'─' * 60}")
        print("  Smoke test complete.")
        print(f"{'─' * 60}\n")
    finally:
        await close_all()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-eleme",      action="store_true", dest="no_eleme",
                   help="Skip Ele.me enrichment")
    p.add_argument("--no-llm",        action="store_true", dest="no_llm",
                   help="Skip LLM analysis")
    p.add_argument("--city",          default="",
                   help="City to crawl (default: first city in cities.yaml)")
    p.add_argument("--show-browser",  action="store_true", dest="show_browser",
                   help="Run Chromium in visible (non-headless) mode for debugging")
    args = p.parse_args()

    asyncio.run(main(
        city=args.city,
        run_eleme=not args.no_eleme,
        run_llm=not args.no_llm,
        show_browser=args.show_browser,
    ))
