"""
End-to-end pipeline test: crawl 1 restaurant from OpenRice + 1 from Foodpanda,
then run geocode → NLP → LLM (bilingual) and print the final result.

Run from backend/:
    py -3.12 -m crawler.hk.test_pipeline

Set LLM_API_KEY in .env (or environment) before running — otherwise LLM step is skipped.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Step 1: Crawl 1 restaurant from OpenRice ──────────────────────────────────

async def crawl_openrice_one() -> dict | None:
    from crawler.hk.openrice_crawler import OpenRiceScraper
    logger.info("=== STEP 1a: OpenRice — crawling 1 restaurant ===")
    async with OpenRiceScraper(headless=False) as scraper:
        stubs = await scraper._collect_restaurant_links(max_scrolls=1)
        if not stubs:
            logger.error("OpenRice: no links found")
            return None
        stub = stubs[0]
        logger.info("OpenRice: using %s", stub["url"])
        detail_page = await scraper._context.new_page()
        try:
            from crawler.hk.openrice_crawler import scrape_restaurant_detail
            doc = await scrape_restaurant_detail(detail_page, stub["url"])
        finally:
            await detail_page.close()

    if not doc.get("name"):
        logger.error("OpenRice: scrape returned no name")
        return None

    doc.update({
        "restaurant_id": f"openrice_{stub['openrice_id']}",
        "openrice_id":   stub["openrice_id"],
        "openrice_url":  stub["url"],
        "source":        "openrice",
        "city":          "香港",
        "geo":           {"lat": None, "lng": None},
        "diet_labels":   [],
        "allergens":     [],
        "allergen_free": [],
        "tags":          [],
    })
    logger.info("OpenRice scraped: %r  district=%s  menu=%d items",
                doc["name"], doc.get("district"), len(doc.get("menu_items", [])))
    return doc


# ── Step 2: Crawl 1 restaurant from Foodpanda ─────────────────────────────────

async def crawl_foodpanda_one() -> dict | None:
    from crawler.hk.foodpanda_crawler import FoodpandaScraper
    logger.info("=== STEP 1b: Foodpanda — crawling 1 restaurant ===")
    async with FoodpandaScraper(headless=False) as scraper:
        links = await scraper._collect_vendor_links(max_items=1)
        if not links:
            logger.error("Foodpanda: no links found")
            return None
        url = links[0]
        logger.info("Foodpanda: using %s", url)

        import re
        m = re.search(r"/restaurant/([^/?]+)", url)
        code = m.group(1) if m else "unknown"
        stub = {
            "restaurant_id": f"foodpanda_{code}",
            "foodpanda_id":  code,
            "foodpanda_url": url,
            "source":        "foodpanda",
            "city":          "香港",
            "name": "", "address": "", "district": "", "cuisine_type": "",
            "price_level": 0, "rating": None, "rating_count": None,
            "phone": "", "opening_hours": "",
            "images": [], "menu_items": [],
            "diet_labels": [], "allergens": [], "allergen_free": [],
            "geo": {"lat": None, "lng": None}, "tags": [],
        }
        menu_items = await scraper._fetch_menu(stub)
        stub["menu_items"] = menu_items
        if not stub.get("name"):
            # Skip the vendor code (first path segment) in the slug
            slug_parts = url.split("/restaurant/")[-1].split("?")[0].split("/")
            slug = slug_parts[1] if len(slug_parts) > 1 else slug_parts[0]
            stub["name"] = slug.replace("-", " ").title()

    logger.info("Foodpanda scraped: %r  menu=%d items",
                stub["name"], len(stub.get("menu_items", [])))
    return stub


# ── Step 3: Geocode (OpenRice only — Foodpanda gets lat/lng from API) ─────────

async def geocode_one(doc: dict) -> dict:
    logger.info("=== STEP 2: Geocode ===")
    if doc.get("geo", {}).get("lat") is not None:
        logger.info("Already has lat/lng — skipping")
        return doc
    address = doc.get("address") or doc.get("district") or ""
    if not address:
        logger.warning("No address to geocode")
        return doc
    from crawler.hk.hk_geocoder import geocode_address
    lat, lng = await geocode_address(address)
    doc["geo"] = {"lat": lat, "lng": lng}
    logger.info("Geocoded %r → (%s, %s)", doc.get("name"), lat, lng)
    return doc


# ── Step 4: Dedup check ───────────────────────────────────────────────────────

def dedup_check(or_doc: dict | None, fp_doc: dict | None) -> None:
    logger.info("=== STEP 3: Dedup check ===")
    if not or_doc or not fp_doc:
        logger.info("Only one source — nothing to dedup")
        return
    or_name = (or_doc.get("name") or "").lower().strip()
    fp_name = (fp_doc.get("name") or "").lower().strip()
    # Simple name overlap check
    or_words = set(or_name.split())
    fp_words = set(fp_name.split())
    overlap = or_words & fp_words
    if overlap and len(overlap) / max(len(or_words), len(fp_words), 1) > 0.5:
        logger.info("Possible duplicate: %r ≈ %r (overlap: %s)", or_name, fp_name, overlap)
    else:
        logger.info("No duplicate detected: %r vs %r", or_name, fp_name)


# ── Step 5: NLP labeling ──────────────────────────────────────────────────────

def nlp_label(doc: dict) -> dict:
    logger.info("=== STEP 4: NLP labeling ===")
    from crawler.hk.nlp_labeler import label_restaurant
    label_restaurant(doc)
    logger.info("NLP diet_labels: %s", doc.get("diet_labels"))
    logger.info("NLP allergens:   %s", doc.get("allergens"))
    return doc


# ── Step 6: LLM labeling with bilingual translation ───────────────────────────

async def llm_label(doc: dict) -> dict:
    logger.info("=== STEP 5: LLM labeling (bilingual) ===")
    from crawler.beijing.llm_labeler import label_menu_items_batch
    from config import cfg
    if not cfg.llm_api_key:
        logger.warning("LLM_API_KEY not set — skipping (set in .env to enable)")
        return doc

    # Translate restaurant name
    await _translate_restaurant_name(doc)

    # Label + translate menu items (first 5 only for speed)
    items = doc.get("menu_items", [])
    doc["menu_items"] = items[:5]
    await label_menu_items_batch(doc)
    doc["menu_items"] = items  # restore full list (only first 5 have nutrition)
    logger.info("LLM done — sample item: %s",
                json.dumps(doc["menu_items"][0] if doc["menu_items"] else {}, ensure_ascii=False))
    return doc


async def _translate_restaurant_name(doc: dict) -> None:
    """Add name_en / name_zh to the restaurant doc."""
    from config import cfg
    if not cfg.llm_api_key:
        return
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return

    name = doc.get("name", "")
    if not name:
        return

    doc.setdefault("name_en", "")
    doc.setdefault("name_zh", "")
    client = AsyncOpenAI(base_url=cfg.llm_base_url, api_key=cfg.llm_api_key, timeout=30.0)
    prompt = (
        f'Restaurant name: "{name}"\n'
        'Return ONLY a JSON object with two keys:\n'
        '  "name_en": English name (translate if Chinese, keep if English)\n'
        '  "name_zh": Traditional Chinese name (translate if English, keep if Chinese)\n'
        'Raw JSON only, no explanation.'
    )
    try:
        resp = await client.chat.completions.create(
            model=cfg.llm_model,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content or ""
        raw = raw.strip().strip("```json").strip("```").strip()
        data = json.loads(raw)
        doc["name_en"] = data.get("name_en", "")
        doc["name_zh"] = data.get("name_zh", "")
        logger.info("Restaurant name: EN=%r  ZH=%r", doc["name_en"], doc["name_zh"])
    except Exception as exc:
        logger.warning("Restaurant name translation failed: %s", exc)


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    results = {}

    # OpenRice
    or_doc = await crawl_openrice_one()
    if or_doc:
        or_doc = await geocode_one(or_doc)
        or_doc = nlp_label(or_doc)
        or_doc = await llm_label(or_doc)
        results["openrice"] = or_doc

    # Foodpanda
    fp_doc = await crawl_foodpanda_one()
    if fp_doc:
        fp_doc = nlp_label(fp_doc)
        fp_doc = await llm_label(fp_doc)
        results["foodpanda"] = fp_doc

    # Dedup check
    dedup_check(or_doc, fp_doc)

    # Print final output
    print("\n" + "="*60)
    print("FINAL PIPELINE OUTPUT")
    print("="*60)
    for source, doc in results.items():
        print(f"\n--- {source.upper()} ---")
        summary = {
            "name":          doc.get("name"),
            "name_en":       doc.get("name_en"),
            "name_zh":       doc.get("name_zh"),
            "district":      doc.get("district"),
            "address":       doc.get("address"),
            "phone":         doc.get("phone"),
            "opening_hours": doc.get("opening_hours"),
            "cuisine_type":  doc.get("cuisine_type"),
            "rating":        doc.get("rating"),
            "geo":           doc.get("geo"),
            "diet_labels":   doc.get("diet_labels"),
            "allergens":     doc.get("allergens"),
            "menu_items_count": len(doc.get("menu_items", [])),
            "sample_items":  [
                {k: v for k, v in item.items() if k in
                 ("name", "name_en", "name_zh", "price", "calories", "protein", "fat", "carbs", "diet_labels")}
                for item in doc.get("menu_items", [])[:3]
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    # Save full output to file
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_pipeline_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nFull output saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
