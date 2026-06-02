from __future__ import annotations

"""
Foodpanda Hong Kong crawler.

Uses Playwright network interception (same technique as eleme_crawler.py) to capture
the JSON API responses that Foodpanda fires when loading restaurant lists and menus.

Usage (from backend/):
    py -3.12 -m crawler.hk.hk_pipeline --foodpanda --show-browser --max-scroll 200

If menus return empty, save a session first:
    py -3.12 -m crawler.hk.foodpanda_login_saver
"""

import asyncio
import json
import logging
import os
import random
import re
from typing import Any

logger = logging.getLogger(__name__)

_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "foodpanda_state.json")

_VENDOR_MENU_API = "hk.fd-api.com"  # all menu/vendor detail calls go through this domain

# One list URL per HK district (lat/lng centres) — gives broad coverage
_DISTRICT_URLS = [
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.2855&lng=114.1577",  # Central/Sheung Wan
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.2783&lng=114.1747",  # Wan Chai/Causeway Bay
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.3193&lng=114.1694",  # Mong Kok/Yau Ma Tei
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.3082&lng=114.2235",  # Kowloon Bay/Kwun Tong
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.3714&lng=114.1135",  # Tsuen Wan
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.3832&lng=114.1906",  # Sha Tin
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.4435&lng=114.0240",  # Tuen Mun
    "https://www.foodpanda.hk/?expedition=pickup&vertical=restaurants&lat=22.4897&lng=114.1283",  # Yuen Long
]


def _parse_menu_items(menu_data: Any) -> list[dict]:
    """Extract dishes from Foodpanda's menu API response."""
    items: list[dict] = []
    seen: set[str] = set()

    def _walk(obj: Any, depth: int = 0) -> None:
        if depth > 12:
            return
        if isinstance(obj, dict):
            item_id = str(obj.get("id") or obj.get("item_id") or "")
            name = obj.get("name") or obj.get("title") or ""
            price_raw = obj.get("price") or obj.get("product_price") or obj.get("selling_price")
            if item_id and item_id not in seen and name and price_raw is not None:
                try:
                    price = float(price_raw) / 100  # Foodpanda stores cents
                except (TypeError, ValueError):
                    price = None
                seen.add(item_id)
                # Image: Foodpanda uses a logo_path field
                img = obj.get("logo_path") or obj.get("image_path") or obj.get("image_url") or ""
                if img and not img.startswith("http"):
                    img = f"https://images.deliveryhero.io/image/fd-hk/{img}"
                items.append({
                    "food_id": item_id,
                    "item_id": item_id,
                    "name": name,
                    "price": price,
                    "description": (obj.get("description") or "").strip(),
                    "image_url": img or None,
                })
            for v in obj.values():
                _walk(v, depth + 1)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v, depth + 1)

    _walk(menu_data)
    return items


def _parse_vendor(vendor: dict) -> dict | None:
    """Normalize one vendor entry from the Foodpanda list API."""
    name = vendor.get("name") or vendor.get("name_with_branch", "")
    if not name:
        return None
    vendor_id = str(vendor.get("id") or vendor.get("code") or "")
    address_obj = vendor.get("address") or {}
    address = (
        address_obj.get("street_address") or
        address_obj.get("street") or
        vendor.get("address_line1") or ""
    )
    lat = address_obj.get("latitude") or vendor.get("latitude")
    lng = address_obj.get("longitude") or vendor.get("longitude")
    rating = vendor.get("rating") or vendor.get("customer_rating")
    rating_count = vendor.get("review_number") or vendor.get("rating_count")
    image = vendor.get("logo_path") or vendor.get("hero_image") or ""
    if image and not image.startswith("http"):
        image = f"https://images.deliveryhero.io/image/fd-hk/{image}"

    cuisines = vendor.get("cuisines") or vendor.get("food_characteristics") or []
    cuisine_type = ", ".join(
        (c.get("name") or c) for c in cuisines[:3] if isinstance(c, (dict, str))
    )

    # Minimum delivery fee / budget indicator → price_level 1-4
    avg_cost = vendor.get("minimum_delivery_fee") or vendor.get("budget") or 0
    try:
        price_level = max(1, min(4, int(float(avg_cost) // 80) + 1))
    except (TypeError, ValueError):
        price_level = 0

    return {
        "restaurant_id": f"foodpanda_{vendor_id}",
        "foodpanda_id": vendor_id,
        "foodpanda_url": f"https://www.foodpanda.hk/restaurant/{vendor_id}",
        "source": "foodpanda",
        "city": "香港",
        "name": name,
        "address": address,
        "district": vendor.get("area") or vendor.get("district") or "",
        "cuisine_type": cuisine_type,
        "price_level": price_level,
        "rating": float(rating) if rating else None,
        "rating_count": int(rating_count) if rating_count else None,
        "phone": vendor.get("phone") or "",
        "opening_hours": "",
        "images": [image] if image else [],
        "menu_items": [],
        "diet_labels": [],
        "allergens": [],
        "allergen_free": [],
        "geo": {
            "lat": float(lat) if lat else None,
            "lng": float(lng) if lng else None,
        },
        "tags": [],
    }


class FoodpandaScraper:
    """
    Scrapes Foodpanda HK via Playwright API interception.

    Phase 1: scroll the pickup restaurant list, intercepting the vendor list API.
    Phase 2: for each restaurant, navigate to its page and intercept the menu API.

    Usage:
        async with FoodpandaScraper(headless=False) as scraper:
            async for doc in scraper.crawl(max_items=500, resume_ids=set()):
                save(doc)
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._list_page = None
        self._menu_page = None

    async def __aenter__(self) -> "FoodpandaScraper":
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if not self.headless:
            launch_kwargs["slow_mo"] = 300
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        ctx_kwargs: dict[str, Any] = dict(
            viewport={"width": 1280, "height": 800},
            locale="en-HK",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        if os.path.exists(_STATE_PATH):
            ctx_kwargs["storage_state"] = _STATE_PATH
            logger.info("Foodpanda: loading saved session from %s", _STATE_PATH)
        self._context = await self._browser.new_context(**ctx_kwargs)
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._list_page = await self._context.new_page()
        self._menu_page = await self._context.new_page()
        return self

    async def __aexit__(self, *_: Any) -> None:
        for obj, method in [(self._browser, "close"), (self._playwright, "stop")]:
            if obj:
                try:
                    await asyncio.wait_for(getattr(obj, method)(), timeout=5.0)
                except Exception:
                    pass

    async def _collect_vendor_links(self, max_items: int) -> list[str]:
        """Scroll each district list page, collect restaurant hrefs from DOM."""
        seen_codes: set[str] = set()
        links: list[str] = []

        async def _harvest() -> None:
            hrefs: list[str] = await self._list_page.eval_on_selector_all(
                "a[href*='/restaurant/']",
                "els => els.map(e => e.href)",
            )
            for href in hrefs:
                m = re.search(r"/restaurant/([^/]+)/", href)
                if not m:
                    continue
                code = m.group(1)
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                # Normalise to pickup URL
                base = re.sub(r"\?.*", "", href)
                links.append(base + "?opening_type=pickup")

        for district_url in _DISTRICT_URLS:
            if len(links) >= max_items:
                break
            logger.info("Foodpanda: loading %s", district_url)
            try:
                await self._list_page.goto(district_url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:
                logger.warning("Foodpanda: failed to load district page: %s", exc)
                continue
            # Wait for restaurant cards — long timeout so user can solve any CAPTCHA manually
            logger.info("Foodpanda: waiting for restaurant cards (solve any CAPTCHA now)...")
            try:
                await self._list_page.wait_for_selector("a[href*='/restaurant/']", timeout=120_000)
            except Exception:
                logger.warning("Foodpanda: no restaurant cards appeared for %s — skipping district", district_url)
                continue
            # Scroll to load more
            prev = 0
            for _ in range(30):
                await _harvest()
                if len(links) >= max_items:
                    break
                await self._list_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2.0, 3.0))
                if len(links) == prev:
                    break
                prev = len(links)
            logger.info("Foodpanda: %d links so far after district", len(links))

        logger.info("Foodpanda: collected %d restaurant links total", len(links))
        return links[:max_items]

    async def _fetch_menu(self, doc: dict) -> list[dict]:
        """Navigate to restaurant page and extract metadata + menu via DOM."""
        shop_url = doc.get("foodpanda_url", "")
        if not shop_url:
            return []

        # Add a central HK location so the menu renders
        if "lat=" not in shop_url:
            shop_url += "&lat=22.2783&lng=114.1747"

        try:
            await self._menu_page.goto(shop_url, wait_until="domcontentloaded", timeout=60_000)
            try:
                await self._menu_page.wait_for_selector("h2.dish-category-title", timeout=120_000)
            except Exception:
                logger.warning("Foodpanda: menu did not render for %s", shop_url)
        except Exception as exc:
            logger.warning("Foodpanda: page load failed for %r: %s", doc.get("name"), exc)
            return []

        data: dict = await self._menu_page.evaluate("""() => {
            const txt = el => (el ? el.innerText.trim() : "");

            const name    = txt(document.querySelector("h1.main-info__title"));
            const cuisine = txt(document.querySelector("span.cl-neutral-secondary"));

            const ratingEl = document.querySelector(".bds-c-rating__label-primary");
            const rating = ratingEl ? parseFloat(ratingEl.innerText) || null : null;

            const rcEl = document.querySelector(".bds-c-rating__label-secondary");
            const rcMatch = rcEl ? rcEl.innerText.match(/\\d+/) : null;
            const ratingCount = rcMatch ? parseInt(rcMatch[0]) : null;

            // Address: plain span containing commas + street keywords
            let address = "";
            for (const el of document.querySelectorAll("span")) {
                if (address) break;
                const t = el.innerText.trim();
                if (el.className === "" && t.length > 10 && t.includes(",") &&
                    /Street|Road|Avenue|Bay|Wan|\/F|Lane|Plaza|Building/i.test(t)) {
                    address = t;
                }
            }

            // Opening hours
            let openDays = ""; const times = [];
            for (const el of document.querySelectorAll("span")) {
                const t = el.innerText.trim();
                if (!openDays && /Monday|Tuesday|Wednesday/.test(t)) openDays = t;
                if (openDays && /^\\d{2}:\\d{2}$/.test(t) && times.length < 2) times.push(t);
            }
            const openingHours = openDays ? openDays + " " + times.join("-") : "";

            // Menu: h2.dish-category-title interleaved with span.vertical-align-middle
            const items = [];
            let category = "";
            for (const el of document.querySelectorAll("h2.dish-category-title, span.vertical-align-middle")) {
                if (el.tagName === "H2") {
                    category = txt(el);
                } else {
                    const name = txt(el);
                    if (!name) continue;
                    const container = el.closest("li, article") ||
                                      el.parentElement?.parentElement?.parentElement;
                    let priceStr = "", desc = "";
                    if (container) {
                        const pe = container.querySelector("p.cl-deal-text-on-white");
                        if (pe) priceStr = txt(pe);
                        const de = container.querySelector("p.product-tile__description");
                        if (de) desc = txt(de).replace(/^For ref(erence)? only:?\\s*/i, "").trim();
                    }
                    const pm = priceStr.match(/HK\\$\\s*([\\d.]+)/);
                    items.push({ name, category, price: pm ? parseFloat(pm[1]) : null, description: desc });
                }
            }

            return { name, cuisine, rating, ratingCount, address, openingHours, items };
        }""")

        if data.get("name"):   doc["name"]          = data["name"]
        if data.get("cuisine"): doc["cuisine_type"]  = data["cuisine"]
        if data.get("rating") is not None: doc["rating"] = data["rating"]
        if data.get("ratingCount") is not None: doc["rating_count"] = data["ratingCount"]
        if data.get("address"):       doc["address"]       = data["address"]
        if data.get("openingHours"):  doc["opening_hours"] = data["openingHours"]

        items = [i for i in data.get("items", []) if i.get("name")]
        logger.debug("Foodpanda menu: %r → %d items", doc.get("name"), len(items))
        return items

    async def crawl(
        self,
        max_items: int = 500,
        resume_ids: set[str] | None = None,
    ):
        """Async generator yielding one enriched doc per restaurant."""
        resume_ids = resume_ids or set()
        links = await self._collect_vendor_links(max_items)

        for url in links:
            m = re.search(r"/restaurant/([^/?]+)", url)
            code = m.group(1) if m else ""
            restaurant_id = f"foodpanda_{code}"
            if restaurant_id in resume_ids:
                logger.debug("Foodpanda: skip (already done) %s", restaurant_id)
                continue
            # Stub doc — menu fetch will fill name/address/etc from the page
            stub = {
                "restaurant_id": restaurant_id,
                "foodpanda_id": code,
                "foodpanda_url": url,
                "source": "foodpanda",
                "city": "香港",
                "name": "", "address": "", "district": "", "cuisine_type": "",
                "price_level": 0, "rating": None, "rating_count": None,
                "phone": "", "opening_hours": "",
                "images": [], "menu_items": [],
                "diet_labels": [], "allergens": [], "allergen_free": [],
                "geo": {"lat": None, "lng": None}, "tags": [],
            }
            menu_items = await self._fetch_menu(stub)
            stub["menu_items"] = menu_items
            if not stub.get("name"):
                # URL: /restaurant/CODE/name-slug → skip the code segment
                parts = url.split("/restaurant/")[-1].split("?")[0].split("/")
                slug = parts[1] if len(parts) > 1 else parts[0]
                stub["name"] = slug.replace("-", " ").title()
            logger.info(
                "Foodpanda: scraped %r  district=%s  menu=%d items",
                stub["name"], stub["district"], len(menu_items),
            )
            yield stub
            await asyncio.sleep(random.uniform(1.5, 3.5))
