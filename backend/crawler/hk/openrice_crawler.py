from __future__ import annotations

"""
OpenRice Hong Kong crawler.

Scrolls the takeaway restaurant list, then visits each restaurant's detail page
to extract name, address, cuisine, menu items, rating, and images.

Usage (from backend/):
    py -3.12 -m crawler.hk.hk_pipeline --openrice --max-scroll 200
    py -3.12 -m crawler.hk.hk_pipeline --openrice --max-scroll 200 --resume
"""

import asyncio
import logging
import random
import re
from typing import Any

logger = logging.getLogger(__name__)

_LIST_URL = "https://www.openrice.com/en/hongkong/restaurants/menu/takeaway"
_BASE_URL = "https://www.openrice.com"


def _slug_from_url(url: str) -> str:
    """Extract a stable slug from an OpenRice restaurant URL.

    /en/hongkong/r/restaurant-name-r123456  →  r123456
    """
    m = re.search(r"-r(\d+)(?:/|$)", url)
    if m:
        return m.group(1)
    m = re.search(r"/r/([^/?#]+)", url)
    return m.group(1) if m else re.sub(r"[^a-z0-9]", "_", url.lower())[-40:]


def _parse_price_level(text: str) -> int:
    """Count $ signs: $ → 1, $$ → 2, $$$ → 3, $$$$ → 4."""
    return min(text.count("$"), 4) or 0


def _parse_price_hkd(text: str) -> float | None:
    """Extract first number from strings like 'HK$38' or '$38.5'."""
    m = re.search(r"[\$＄HK]*\s*([0-9]+(?:\.[0-9]+)?)", text.replace(",", ""))
    return float(m.group(1)) if m else None



async def _dismiss_modals(page: Any) -> None:
    """Dismiss any pickup-time or cookie modal. Escape is the most reliable fallback."""
    # Try clicking known dismiss buttons first
    for sel in [
        "button:has-text('Confirm')",
        "button:has-text('OK')",
        "button:has-text('Continue')",
        "button:has-text('Close')",
        "[class*='modal'] [class*='close']",
        "[class*='popup'] [class*='close']",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=800):
                await btn.click()
                await asyncio.sleep(0.4)
                logger.debug("Dismissed modal via %s", sel)
                return
        except Exception:
            continue
    # Escape closes most modals regardless of button text
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
    except Exception:
        pass


async def scrape_restaurant_detail(page: Any, url: str) -> dict:
    """Navigate to a takeaway menu page and extract restaurant + menu data."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(random.uniform(1.5, 2.5))
        await _dismiss_modals(page)
    except Exception as exc:
        logger.warning("Failed to load %s: %s", url, exc)
        return {}

    doc: dict[str, Any] = {}

    # Wait for the restaurant name to confirm the page rendered
    try:
        await page.wait_for_selector(".poi-menu-poi-info-cell-poi-name", timeout=10_000)
    except Exception:
        logger.warning("Page did not render within 10s, skipping: %s", url)
        return {}

    # Pass 1: menu page — name, district, cuisine, menu items, and profile link
    data: dict = await page.evaluate("""() => {
        const txt = el => (el ? el.innerText.trim() : "");
        const name     = txt(document.querySelector(".poi-menu-poi-info-cell-poi-name"));
        const district = txt(document.querySelector(".poi-menu-poi-info-cell-district"));
        const cuisine  = txt(document.querySelector(".poi-menu-poi-info-cell-cuisine"));
        const ogImg    = document.querySelector('meta[property="og:image"]');
        const image    = ogImg ? ogImg.getAttribute("content") : "";

        // Profile page link e.g. /en/hongkong/r-vision-8-tsuen-wan-italian-r190869/
        const profileA = document.querySelector('a[href*="/hongkong/r-"]');
        const profilePath = profileA ? profileA.getAttribute("href") : "";

        const items = [];
        let category = "";
        const els = document.querySelectorAll(
            ".poi-menu-category, .text-trim.poi-menu-item-info-name"
        );
        for (const el of els) {
            if (el.classList.contains("poi-menu-category")) {
                category = txt(el);
            } else {
                const parent = el.parentElement;
                items.push({
                    name:        txt(el),
                    category:    category,
                    price_str:   parent ? txt(parent.querySelector(".poi-menu-item-info-price")) : "",
                    description: parent ? txt(parent.querySelector(".poi-menu-item-info-desc"))  : "",
                });
            }
        }
        return { name, district, cuisine, image, profilePath, items };
    }""")

    menu_items = [
        {
            "name": i["name"],
            "category": i["category"],
            "price": _parse_price_hkd(i["price_str"]),
            "description": i["description"],
        }
        for i in data.get("items", []) if i.get("name")
    ]

    doc["name"]          = data.get("name", "")
    doc["district"]      = data.get("district", "")
    doc["cuisine_type"]  = data.get("cuisine", "")
    doc["images"]        = [data["image"]] if data.get("image") else []
    doc["menu_items"]    = menu_items
    doc["address"]       = ""
    doc["price_level"]   = 0
    doc["rating"]        = None
    doc["rating_count"]  = None
    doc["phone"]         = ""
    doc["opening_hours"] = ""

    # Pass 2: profile page — address, rating, phone, opening hours
    profile_path = data.get("profilePath", "")
    if profile_path:
        profile_url = _BASE_URL + profile_path if not profile_path.startswith("http") else profile_path
        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(random.uniform(1.0, 1.8))
            await _dismiss_modals(page)
            profile: dict = await page.evaluate("""() => {
                const txt = el => (el ? el.innerText.trim() : "");

                const address = txt(document.querySelector(".pdid-location-section-address"));
                const phone   = txt(document.querySelector(".phone-text"));

                // Opening hours: each row is a .opening-hours-date followed by a sibling with the time
                let openingHours = "";
                document.querySelectorAll(".opening-hours-date").forEach(dateEl => {
                    const timeEl = dateEl.nextElementSibling;
                    if (timeEl) openingHours += txt(dateEl) + ": " + txt(timeEl) + "\\n";
                });
                openingHours = openingHours.trim().slice(0, 300);

                // Price range tag e.g. "$201-400"
                let priceRange = "";
                document.querySelectorAll("a.pdhs-filter-tags-section-item").forEach(el => {
                    if (el.innerText.includes("$")) priceRange = txt(el);
                });

                // Review count from tab label "Review (1608)"
                let reviewCount = null;
                document.querySelectorAll("div").forEach(el => {
                    const m = el.innerText.match(/^Review \\((\\d+)\\)$/);
                    if (m) reviewCount = parseInt(m[1]);
                });

                // Smile counts — happy/ok/sad (OpenRice's rating system)
                const smileEl = document.querySelector(".pdfbd-left-smile span");
                const okEl    = document.querySelector(".pdfbd-left-ok span");
                const cryEl   = document.querySelector(".pdfbd-left-cry span");
                const happy = parseInt((smileEl ? smileEl.innerText : "0").replace(/[^0-9]/g, "")) || 0;
                const ok    = parseInt((okEl    ? okEl.innerText    : "0").replace(/[^0-9]/g, "")) || 0;
                const sad   = parseInt((cryEl   ? cryEl.innerText   : "0").replace(/[^0-9]/g, "")) || 0;
                const total = happy + ok + sad;
                // Weighted score: happy=5, ok=3, sad=1 → scale 1-5
                const smileScore = total > 0 ? Math.round((happy*5 + ok*3 + sad*1) / total * 10) / 10 : null;
                const smileCounts = [happy, ok, sad];

                // Gallery images
                const imgs = [...document.querySelectorAll(".photo-cell img, .poi-cover-photo img")]
                    .map(i => i.src).filter(Boolean).slice(0, 5);

                return { address, phone, openingHours, priceRange, reviewCount, smileCounts, smileScore, imgs };
            }""")
            if profile.get("address"):
                doc["address"] = profile["address"]
            if profile.get("phone"):
                doc["phone"] = profile["phone"]
            if profile.get("openingHours"):
                doc["opening_hours"] = profile["openingHours"]
            if profile.get("priceRange"):
                doc["price_range"] = profile["priceRange"]
                import re as _re
                nums = [int(n) for n in _re.findall(r'\d+', profile["priceRange"])]
                if nums:
                    avg = sum(nums) / len(nums)
                    doc["price_level"] = 1 if avg < 100 else 2 if avg < 200 else 3 if avg < 400 else 4
            if profile.get("reviewCount") is not None:
                doc["rating_count"] = profile["reviewCount"]
            if profile.get("smileCounts"):
                doc["smile_counts"] = profile["smileCounts"]  # [happy, ok, sad]
            if profile.get("smileScore") is not None:
                doc["rating"] = profile["smileScore"]  # 1-5 weighted score
            if profile.get("imgs"):
                doc["images"] = list(dict.fromkeys(doc["images"] + profile["imgs"]))
        except Exception as exc:
            logger.debug("Profile page fetch failed for %s: %s", profile_url, exc)

    return doc


class OpenRiceScraper:
    """
    Scrapes the OpenRice HK takeaway restaurant list + individual restaurant pages.

    Usage:
        async with OpenRiceScraper(headless=False) as scraper:
            async for doc in scraper.crawl(max_scrolls=200, resume_ids=set()):
                save(doc)
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def __aenter__(self) -> "OpenRiceScraper":
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-HK",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._page = await self._context.new_page()
        return self

    async def __aexit__(self, *_: Any) -> None:
        for obj, method in [(self._browser, "close"), (self._playwright, "stop")]:
            if obj:
                try:
                    await asyncio.wait_for(getattr(obj, method)(), timeout=5.0)
                except Exception:
                    pass

    async def _collect_restaurant_links(self, max_scrolls: int) -> list[dict]:
        """
        Scroll the list page and collect restaurant URLs directly from card <a> hrefs.
        Cards link to /en/hongkong/menu/NUMBER/takeaway — extract the numeric ID from there.
        Returns a list of {openrice_id, name_hint, url} dicts.
        """
        seen_ids: set[str] = set()
        collected: list[dict] = []

        async def _harvest() -> None:
            """Grab all restaurant card links currently in the DOM."""
            hrefs: list[str] = await self._page.eval_on_selector_all(
                "a[href*='/hongkong/menu/']",
                "els => els.map(e => e.href)",
            )
            for href in hrefs:
                m = re.search(r"/menu/(\d+)/", href)
                if not m:
                    continue
                rid = m.group(1)
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                # Normalise to English takeaway menu page
                url = re.sub(r"openrice\.com/[a-z]{2}/", "openrice.com/en/", href.split("?")[0])
                url = f"{url}?source=takeaway"
                collected.append({"openrice_id": rid, "name_hint": "", "url": url})

        logger.info("OpenRice: loading list page %s", _LIST_URL)
        await self._page.goto(_LIST_URL, wait_until="domcontentloaded", timeout=30_000)
        # Wait for actual restaurant cards to render (not just skeleton loaders)
        try:
            await self._page.wait_for_selector("a[href*='/hongkong/menu/']", timeout=20_000)
        except Exception:
            logger.warning("OpenRice: timed out waiting for restaurant cards to appear")
        await _harvest()

        prev = 0
        no_new_streak = 0
        for scroll_n in range(max_scrolls):
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(2.5, 4.0))

            # Random mouse movement ~30% of scrolls
            if random.random() < 0.3:
                await self._page.mouse.move(
                    random.randint(200, 1000), random.randint(200, 700)
                )
                await asyncio.sleep(random.uniform(0.3, 0.8))

            # Occasional longer pause every ~20 scrolls
            if scroll_n > 0 and scroll_n % random.randint(18, 25) == 0:
                pause = random.uniform(5.0, 12.0)
                logger.debug("OpenRice: human pause %.1fs at scroll %d", pause, scroll_n)
                await asyncio.sleep(pause)

            await _harvest()
            logger.debug("OpenRice scroll %d: %d restaurant links collected", scroll_n, len(collected))

            if len(collected) == prev:
                no_new_streak += 1
                if no_new_streak >= 5:
                    logger.info("OpenRice: no new cards for 5 scrolls — stopping at scroll %d", scroll_n)
                    break
            else:
                no_new_streak = 0
            prev = len(collected)

        logger.info("OpenRice: collected %d restaurant links from page", len(collected))
        return collected

    async def crawl(
        self,
        max_scrolls: int = 200,
        resume_ids: set[str] | None = None,
    ):
        """Async generator yielding one normalized doc per restaurant."""
        resume_ids = resume_ids or set()
        stubs = await self._collect_restaurant_links(max_scrolls)

        if not stubs:
            logger.warning("OpenRice: found 0 restaurant links — check that the list page loaded correctly.")
            return

        # Use a separate page for detail scraping so the list page stays intact
        detail_page = await self._context.new_page()
        try:
            for stub in stubs:
                openrice_id = stub["openrice_id"]
                restaurant_id = f"openrice_{openrice_id}"
                if restaurant_id in resume_ids:
                    logger.debug("OpenRice: skip (already done) %s", restaurant_id)
                    continue

                url = stub["url"]
                detail = await scrape_restaurant_detail(detail_page, url)

                # If detail scrape failed but we have API data, use the stub name as fallback
                name = detail.get("name") or stub.get("name_hint", "")
                if not name:
                    logger.debug("OpenRice: no name for %s — skipping", url)
                    continue

                doc: dict[str, Any] = {
                    "restaurant_id": restaurant_id,
                    "openrice_id": openrice_id,
                    "openrice_url": url,
                    "source": "openrice",
                    "city": "香港",
                    "name": name,
                    "address": detail.get("address", ""),
                    "district": detail.get("district", ""),
                    "cuisine_type": detail.get("cuisine_type", ""),
                    "price_level": detail.get("price_level", 0),
                    "rating": detail.get("rating"),
                    "rating_count": detail.get("rating_count"),
                    "phone": detail.get("phone", ""),
                    "opening_hours": detail.get("opening_hours", ""),
                    "images": detail.get("images", []),
                    "menu_items": detail.get("menu_items", []),
                    "diet_labels": [],
                    "allergens": [],
                    "allergen_free": [],
                    "geo": {"lat": None, "lng": None},
                    "tags": [],
                }

                logger.info(
                    "OpenRice: scraped %r  district=%s  menu=%d items",
                    doc["name"], doc["district"], len(doc["menu_items"]),
                )
                yield doc
                # Randomise inter-restaurant delay; occasionally take a longer break
                if random.random() < 0.1:
                    await asyncio.sleep(random.uniform(8.0, 15.0))
                else:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
        finally:
            await detail_page.close()
