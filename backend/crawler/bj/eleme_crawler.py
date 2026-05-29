from __future__ import annotations

"""
饿了么爬虫 — 使用 Playwright 网络拦截方式。

ele.me 使用阿里巴巴 Tiga 小程序框架（自定义 <tiga-view> 元素），无法直接
抓取 DOM。本模块拦截 ele.me 在加载搜索结果页时向后端发起的 JSON API 请求，
提取餐厅信息和菜单数据。

首次使用前需保存登录 session:
    py -3.12 -m crawler.test.eleme_login_saver

在 pipeline 中使用示例:
    from crawler.eleme_crawler import ElemeScraper

    async with ElemeScraper() as scraper:
        for record in gaode_records:
            await scraper.enrich(record)
"""

import asyncio
import json
import logging
import math
import os
import random
import re
from typing import Any
from urllib.parse import quote, unquote

logger = logging.getLogger(__name__)

_STATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "eleme", "eleme_state.json"
)

# ele.me numeric city IDs
_CITY_IDS: dict[str, str] = {
    "北京": "110001",
    "上海": "310001",
    "广州": "440100",
    "深圳": "440300",
    "成都": "510100",
    "杭州": "330100",
    "武汉": "420100",
    "西安": "610100",
}

# ele.me food image CDN: hash split as /h[0]/h[1:3]/h[3:].ext
_FOOD_CDN = "https://cube.elemecdn.com"

# API substring that identifies the search recommendation response
_RECOMMEND_API = "elemetinyapprecommend.recommend"


def _food_image_url(image_path: str) -> str | None:
    """Convert ele.me imageHash to a full CDN URL.

    The hash includes the extension as part of the filename, which is then
    repeated as the URL extension:
        847805c002cd88df63ce0e1c64e914ecjpg
        → https://cube.elemecdn.com/8/47/805c002cd88df63ce0e1c64e914ecjpg.jpg
    """
    ext_match = re.search(r"(jpe?g|png|gif|webp)$", image_path, re.IGNORECASE)
    if not ext_match:
        return None
    ext = ext_match.group(1)
    h = image_path  # keep full hash including extension suffix
    if len(h) < 4:
        return None
    return f"{_FOOD_CDN}/{h[0]}/{h[1:3]}/{h[3:]}.{ext}"


def _name_similarity(a: str, b: str) -> float:
    """Character-set Jaccard similarity — good enough for Chinese restaurant names."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _strip_branch(name: str) -> str:
    """Remove branch qualifiers so matching works on the core brand name.

    '胡大饭馆(簋街三店)' → '胡大饭馆'
    '麦当劳（王府井店）' → '麦当劳'
    """
    return re.sub(r'[（(][^）)]*[）)]', '', name).strip()


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance in metres between two GPS coordinates."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _extract_latlng(data_list: list[dict]) -> tuple[float, float] | tuple[None, None]:
    """Extract lat/lng from Ele.me detail API responses.

    The storeInfo.jumpLink field contains URL-encoded JSON with latitude/longitude,
    e.g. %22latitude%22%3A39.905603%2C...%22longitude%22%3A116.413642
    """
    for data in data_list:
        text = json.dumps(data)
        lat_m = re.search(r'"latitude"\s*[:\s]*([0-9]{2}\.[0-9]+)', text)
        lng_m = re.search(r'"longitude"\s*[:\s]*([0-9]{3}\.[0-9]+)', text)
        if lat_m and lng_m:
            return float(lat_m.group(1)), float(lng_m.group(1))
    return None, None


def _parse_list_item(item: dict) -> dict[str, Any] | None:
    """Extract a clean restaurant dict from a listItems entry."""
    info = item.get("info", {})
    r = info.get("restaurant")
    if not r:
        return None

    foods = info.get("foods", [])
    menu_items: list[dict] = []
    for f in foods:
        img_path = f.get("imagePath", "")
        menu_items.append({
            "food_id": str(f.get("foodId", "")),
            "name": f.get("name", ""),
            "price": f.get("price") or f.get("sellPrice"),
            "description": f.get("description", ""),
            "image_url": _food_image_url(img_path) if img_path else None,
        })

    return {
        "eleme_id": r.get("id", ""),
        "name": r.get("name", ""),
        "brand_name": r.get("brandName", ""),
        "image_url": r.get("imagePath", ""),   # full URL for restaurant cover
        "shop_url": r.get("scheme", ""),        # deep-link to restaurant detail page
        "rating": r.get("rating"),
        "monthly_sales": r.get("recentOrderNum"),
        "monthly_sales_display": r.get("recentOrderNumDisplay", ""),
        "distance_m": r.get("distance"),
        "avg_cost": r.get("averageCost", ""),
        "delivery_time": r.get("deliveryTime", ""),
        "menu_items": menu_items,  # Phase 1 preview — replaced by full menu in Phase 2
        "source": "eleme",
    }


def _extract_list_items(raw_response: dict) -> list[dict[str, Any]]:
    """Walk the nested API response and return parsed restaurant dicts."""
    results: list[dict] = []
    api_data = raw_response.get("data", {})
    for result_block in api_data.get("result", []):
        for item in result_block.get("listItems", []):
            parsed = _parse_list_item(item)
            if parsed:
                results.append(parsed)
    return results


def _scheme_to_h5(scheme: str, city_id: str) -> str:
    """Convert an Ele.me app deep-link to a navigable h5 web URL.

    eleme://tabContainer/shopDetail/menu?restaurant_id=E16908297129995106949
      → https://h5.ele.me/shop/E16908297129995106949/?cityid=110001
    """
    if scheme.startswith("http://") or scheme.startswith("https://"):
        return scheme
    m = re.search(r"restaurant_id=([^&\s]+)", scheme)
    if m:
        rid = m.group(1)
        return f"https://h5.ele.me/shop/{rid}/?cityid={city_id}"
    return ""


def _collect_dishes(obj: object, out: list, seen: set, depth: int = 0) -> None:
    """Recursively collect full menu items from the restaurant detail API response.

    The detail API (store.detail.body.query.v2) stores items under
    resultMap.storeWindow[].items[] where each item has imageHash, itemId,
    name, price, and specFoods[0].foodId.
    """
    if depth > 15:
        return
    if isinstance(obj, dict):
        name       = obj.get("name", "")
        price      = obj.get("price") or obj.get("sellPrice") or obj.get("originPrice")
        item_id    = str(obj.get("itemId") or "")
        image_hash = obj.get("imageHash") or obj.get("imagePath") or obj.get("image") or ""

        # image_hash is optional — don't exclude items that lack a photo
        if item_id and item_id not in seen and name and price is not None:
            spec_foods = obj.get("specFoods", [])
            food_id = str(spec_foods[0].get("foodId", "")) if spec_foods else item_id
            seen.add(item_id)
            img_url = None
            if image_hash and not image_hash.startswith("http"):
                img_url = _food_image_url(image_hash)
            elif image_hash:
                img_url = image_hash
            out.append({
                "food_id":     food_id,
                "item_id":     item_id,
                "name":        name,
                "price":       price,
                "description": obj.get("description", "").strip(),
                "image_url":   img_url,
            })
        for v in obj.values():
            _collect_dishes(v, out, seen, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _collect_dishes(v, out, seen, depth + 1)


class ElemeScraper:
    """
    Reusable ele.me scraper that keeps one Playwright browser alive across
    multiple restaurant lookups.

    Usage:
        async with ElemeScraper() as scraper:
            matches = await scraper.search("麦当劳")
            # or enrich a Gaode record in-place:
            await scraper.enrich(gaode_record)
    """

    def __init__(
        self,
        city: str = "北京",
        geo_lat: float = 39.9042,
        geo_lng: float = 116.4074,
        state_path: str | None = None,
        headless: bool = True,
        page_wait_s: float = 6.0,
    ) -> None:
        self.city = city
        self.city_id = _CITY_IDS.get(city, "110001")
        self.geo_lat = geo_lat
        self.geo_lng = geo_lng
        self.state_path = state_path or _STATE_PATH
        self.headless = headless
        self.page_wait_s = page_wait_s
        self._playwright = None
        self._browser = None
        self._context = None
        self._search_page = None
        self._menu_page = None

    async def __aenter__(self) -> "ElemeScraper":
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if not self.headless:
            launch_kwargs["slow_mo"] = 800
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        ctx_kwargs: dict[str, Any] = dict(
            viewport={"width": 1280, "height": 800},
            geolocation={"latitude": self.geo_lat, "longitude": self.geo_lng},
            permissions=["geolocation"],
            locale="zh-CN",
        )
        if os.path.exists(self.state_path):
            ctx_kwargs["storage_state"] = self.state_path
        else:
            logger.warning(
                "eleme_state.json not found at %s — run eleme_login_saver first",
                self.state_path,
            )
        self._context = await self._browser.new_context(**ctx_kwargs)
        await self._context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        # Persistent pages — reused for all requests so CAPTCHA only needs solving once
        self._search_page = await self._context.new_page()
        self._menu_page = await self._context.new_page()
        # Warm up: visit homepage first so the session looks natural
        try:
            await self._search_page.goto(
                f"https://h5.ele.me/?cityid={self.city_id}",
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            await asyncio.sleep(random.uniform(1.5, 3.0))
        except Exception:
            pass
        return self

    async def __aexit__(self, *_: Any) -> None:
        for obj, method in [
            (self._browser, "close"),
            (self._playwright, "stop"),
        ]:
            if obj:
                try:
                    await asyncio.wait_for(getattr(obj, method)(), timeout=5.0)
                except Exception:
                    pass

    async def _wait_if_no_data(
        self, page: Any, captured: list, label: str, reload_url: str = ""
    ) -> None:
        """If captured is empty after the normal wait, assume CAPTCHA blocked the API.

        For search pages (reload_url set): reload/re-navigate so the API call re-fires.
        For detail pages (no reload_url): the page is loading in the background — just
        wait; reloading would discard that in-progress work.
        """
        if captured:
            return
        print("\n" + "=" * 60)
        print(f"  No API data for {label!r} — possible CAPTCHA.")
        if self.headless:
            print("  Re-run with --show-browser so you can solve the CAPTCHA slider.")
        else:
            print("  Solve the CAPTCHA slider in the browser window,")
            print("  then press Enter here to resume...")
        print("=" * 60)
        await asyncio.get_event_loop().run_in_executor(None, input, "")
        if reload_url:
            # Search page: CAPTCHA blocked the request — re-navigate to re-fire it
            try:
                await page.goto(reload_url, wait_until="domcontentloaded", timeout=20_000)
                await asyncio.sleep(2.0)
            except Exception as exc:
                logger.debug("Post-CAPTCHA navigation failed: %s", exc)
        else:
            # Detail page: the page is already loading behind the CAPTCHA — just wait
            await asyncio.sleep(5.0)
        # Poll for up to 60 seconds
        extra_deadline = asyncio.get_event_loop().time() + 60.0
        while not captured and asyncio.get_event_loop().time() < extra_deadline:
            await asyncio.sleep(0.5)
        # Save updated session so the CAPTCHA verification cookie persists next run
        if self._context and self.state_path:
            try:
                await self._context.storage_state(path=self.state_path)
                logger.info("Session saved to %s after CAPTCHA solve", self.state_path)
            except Exception as exc:
                logger.debug("Could not save session: %s", exc)

    async def search(self, restaurant_name: str) -> list[dict[str, Any]]:
        """
        Search ele.me for restaurants matching *restaurant_name*.
        Returns a list of parsed restaurant dicts (may include multiple results).
        """
        assert self._context is not None, "Use ElemeScraper as a context manager"

        captured: list[dict] = []
        search_url = f"https://h5.ele.me/search?keyword={quote(restaurant_name)}&cityid={self.city_id}"

        async def on_response(response: Any) -> None:
            if _RECOMMEND_API not in response.url:
                return
            if "json" not in response.headers.get("content-type", ""):
                return
            try:
                captured.append(await response.json())
            except Exception:
                pass

        page = self._search_page
        page.on("response", on_response)

        try:
            typed = False
            # Try to find the search input and type into it (human-like)
            search_input_selectors = [
                'input[type="search"]',
                'input[type="text"]',
                'input[placeholder*="搜"]',
                'input[placeholder*="Search"]',
                '[class*="search"] input',
                '[class*="Search"] input',
            ]
            for selector in search_input_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        await el.click()
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                        await el.select_text()
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                        await el.type(restaurant_name, delay=random.randint(60, 160))
                        await asyncio.sleep(random.uniform(0.3, 0.7))
                        await page.keyboard.press("Enter")
                        typed = True
                        logger.debug("Typed %r into search box (%s)", restaurant_name, selector)
                        break
                except Exception:
                    continue

            if not typed:
                # Fallback: direct URL navigation
                logger.debug("No search input found — falling back to URL navigation for %r", restaurant_name)
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

            try:
                await page.wait_for_function(
                    "() => document.body.innerText.trim().length > 50",
                    timeout=15_000,
                )
            except Exception:
                pass
            # Poll until the recommend API response arrives or page_wait_s elapses
            deadline = asyncio.get_event_loop().time() + self.page_wait_s
            while not captured and asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.3)
            if captured:
                await asyncio.sleep(1.0)  # brief extra wait for any trailing responses
        except Exception as exc:
            logger.warning("Ele.me load failed for %r: %s", restaurant_name, exc)

        # Keep listener active so CAPTCHA-solve responses are captured; remove after
        await self._wait_if_no_data(page, captured, restaurant_name, reload_url=search_url)
        page.remove_listener("response", on_response)

        results: list[dict] = []
        for raw in captured:
            results.extend(_extract_list_items(raw))

        logger.debug("ele.me search %r → %d results", restaurant_name, len(results))
        # Random jitter between requests to reduce bot-detection risk
        await asyncio.sleep(random.uniform(2.0, 5.0))
        return results

    async def _fetch_full_menu(self, shop_url: str) -> list[dict]:
        """Phase 2: navigate to the restaurant detail page and capture all menu items.

        The detail page fires a store.detail API that returns the complete menu
        (all categories, all items) with imageHash for each dish.
        """
        assert self._context is not None
        captured: list[dict] = []

        async def on_response(response: Any) -> None:
            if not any(d in response.url for d in ["ele.me", "elemecdn.com"]):
                return
            if "json" not in response.headers.get("content-type", ""):
                return
            try:
                captured.append(await response.json())
            except Exception:
                pass

        # Try clicking the restaurant card on the search results page first (more human-like).
        # Fall back to direct URL navigation on _menu_page if clicking fails.
        clicked = False
        page = self._search_page
        page.on("response", on_response)
        try:
            # Extract restaurant ID from shop_url to find the right card
            rid_match = re.search(r"/shop/([^/?]+)", shop_url)
            rid = rid_match.group(1) if rid_match else ""
            click_selectors = [
                f'a[href*="{rid}"]' if rid else None,
                'a[href*="/shop/"]',
                '[class*="shop"] a',
                '[class*="restaurant"] a',
                '[class*="item"] a',
            ]
            for selector in click_selectors:
                if not selector:
                    continue
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        await asyncio.sleep(random.uniform(0.5, 1.2))
                        await el.click()
                        clicked = True
                        logger.debug("Clicked restaurant card (%s)", selector)
                        break
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("Click attempt failed: %s", exc)

        if not clicked:
            # Fallback: navigate directly on _menu_page
            page.remove_listener("response", on_response)
            page = self._menu_page
            page.on("response", on_response)
            logger.debug("Falling back to URL navigation for %s", shop_url[:60])

        try:
            if not clicked:
                await page.goto(shop_url, wait_until="domcontentloaded", timeout=30_000)
            try:
                await page.wait_for_function(
                    "() => document.body.innerText.trim().length > 100", timeout=15_000
                )
            except Exception:
                pass
            # Poll until menu API responses arrive — detail page lazy-loads them.
            # Use a longer window when running headed (CAPTCHA overlay may slow load).
            max_wait = random.uniform(20.0, 28.0) if not self.headless else random.uniform(10.0, 14.0)
            deadline = asyncio.get_event_loop().time() + max_wait
            prev_count = 0
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.5)
                if len(captured) > prev_count:
                    prev_count = len(captured)
                    deadline = asyncio.get_event_loop().time() + 3.0
        except Exception as exc:
            logger.warning("Restaurant page load failed for %r: %s", shop_url[:60], exc)

        # No reload_url: detail page is loading in background — just wait for responses
        await self._wait_if_no_data(page, captured, shop_url)
        page.remove_listener("response", on_response)

        dishes: list[dict] = []
        seen: set = set()
        raw_data = [e["data"] if isinstance(e, dict) and "data" in e else e for e in captured]
        for data in raw_data:
            _collect_dishes(data, dishes, seen)

        eleme_lat, eleme_lng = _extract_latlng(raw_data)
        logger.debug("Phase 2 full menu: %d dishes, coords=(%s, %s)", len(dishes), eleme_lat, eleme_lng)
        return dishes, eleme_lat, eleme_lng

    async def enrich(self, gaode_record: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a Gaode restaurant record with Ele.me menu/image/rating data.

        Matching strategy (in order of reliability):
          1. Move the browser's GPS to the restaurant's actual Gaode coordinates so
             Ele.me reports realistic distances in its results.
          2. Search by full name first; if 0 results, retry with the branch-stripped
             name (e.g. '胡大饭馆(簋街三店)' → '胡大饭馆').
          3. Score each candidate by name similarity PLUS a distance bonus:
               < 200 m  → +0.35  (almost certainly the same place)
               < 600 m  → +0.15
             This means a geographically close result can win even with imperfect
             name overlap, which is the common case for chain branches.
        """
        name     = gaode_record.get("name", "")
        base     = _strip_branch(name)
        geo      = gaode_record.get("geo", {})
        lat, lng = geo.get("lat"), geo.get("lng")

        # Move browser GPS to the restaurant's actual location so Ele.me distance
        # data is meaningful for this specific restaurant.
        if lat and lng and self._context:
            try:
                await self._context.set_geolocation({"latitude": lat, "longitude": lng})
            except Exception as exc:
                logger.debug("set_geolocation failed: %s", exc)

        # Search stripped name first (avoids parentheses in URL that can cause Ele.me timeouts),
        # then fall back to the full name if the stripped search returns nothing.
        results = await self.search(base)
        if not results and base != name:
            logger.debug("No results for stripped name %r — retrying with full name %r", base, name)
            results = await self.search(name)

        if not results:
            logger.debug("No Ele.me results for %r", name)
            return gaode_record

        best: dict[str, Any] | None = None
        best_score = 0.12  # lower base threshold; distance bonus does heavy lifting

        for r in results:
            eleme_name  = r.get("name", "")
            eleme_brand = r.get("brand_name", "")
            name_score  = max(
                _name_similarity(name,  eleme_name),
                _name_similarity(name,  eleme_brand),
                _name_similarity(base,  eleme_name),
                _name_similarity(base,  eleme_brand),
            )
            dist = r.get("distance_m")
            if dist is not None:
                dist_bonus = 0.35 if dist < 200 else (0.15 if dist < 600 else 0.0)
            else:
                dist_bonus = 0.0

            score = name_score + dist_bonus
            if score > best_score:
                best_score = score
                best = r

        if best is None:
            logger.debug("No Ele.me match for %r (best score below threshold)", name)
            return gaode_record

        gaode_record["eleme_id"]   = best["eleme_id"]
        gaode_record["eleme_name"] = best["name"]

        if best.get("image_url") and not gaode_record.get("images"):
            gaode_record["images"] = [best["image_url"]]

        if best.get("rating") is not None and gaode_record.get("rating") is None:
            gaode_record["rating"] = best["rating"]

        if best.get("monthly_sales") is not None:
            gaode_record["monthly_sales"] = best["monthly_sales"]

        # Phase 2: navigate to restaurant page for the full menu
        raw_scheme = best.get("shop_url", "")
        shop_url = _scheme_to_h5(raw_scheme, self.city_id)
        eleme_lat = eleme_lng = None
        if shop_url:
            full_menu, eleme_lat, eleme_lng = await self._fetch_full_menu(shop_url)
            gaode_record["menu_items"] = full_menu if full_menu else best.get("menu_items", [])
        else:
            gaode_record["menu_items"] = best.get("menu_items", [])

        # Verify match using actual GPS coordinates extracted from the detail page
        if eleme_lat and eleme_lng and lat and lng:
            dist_m = _haversine_m(lat, lng, eleme_lat, eleme_lng)
            gaode_record["eleme_distance_m"] = round(dist_m)
            if dist_m > 1000:
                logger.warning(
                    "Possible wrong branch for %r → ele.me %r is %.0fm away "
                    "(Gaode: %.5f,%.5f  Ele.me: %.5f,%.5f)",
                    name, best["name"], dist_m, lat, lng, eleme_lat, eleme_lng,
                )
            else:
                logger.debug("Location verified: %r is %.0fm away", best["name"], dist_m)

        logger.info(
            "Enriched %r → ele.me %r (score=%.2f dist=%sm %d items)",
            name, best["name"], best_score, best.get("distance_m", "?"),
            len(gaode_record["menu_items"]),
        )
        return gaode_record
