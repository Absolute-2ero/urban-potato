"""
Ele.me one-time login saver.

Opens ele.me in a real browser window so you can log in manually with your
phone number and SMS code. Once you are logged in and can see the homepage,
press Enter in this terminal and Playwright saves your session (cookies +
localStorage) to eleme_state.json next to this file.

All future scraping scripts load eleme_state.json instead of logging in again.
The session typically stays valid for several days to weeks. When it expires
(ele.me starts showing the login screen again), just run this script once more.

Usage (run from the backend/ directory):
    py -3.12 -m crawler.eleme.eleme_login_saver

Output file:
    backend/crawler/eleme/eleme_state.json
"""

from __future__ import annotations

import asyncio
import os

# eleme_state.json is saved next to this file so the tester can find it easily
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eleme_state.json")

# Beijing coordinates — ele.me uses location to show nearby restaurants
GEO_LAT = 39.9042
GEO_LNG = 116.4074


async def save_login() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Run: py -3.12 -m pip install playwright && py -3.12 -m playwright install chromium")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            geolocation={"latitude": GEO_LAT, "longitude": GEO_LNG},
            permissions=["geolocation"],
            locale="zh-CN",
        )

        # Hide the webdriver flag so CAPTCHA sliders don't detect automation
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page = await context.new_page()

        print("Opening ele.me...")
        await page.goto("https://h5.ele.me", wait_until="networkidle", timeout=30000)

        print("\n" + "=" * 60)
        print("A browser window has opened.")
        print("Log in to ele.me manually (phone number + SMS code).")
        print("If a CAPTCHA slider appears, drag it with your mouse.")
        print("Once you can see the ele.me homepage (not the login screen),")
        print("come back here and press Enter.")
        print("=" * 60)
        input("\nPress Enter after you have logged in successfully... ")

        await context.storage_state(path=STATE_PATH)
        print(f"\nSession saved to: {STATE_PATH}")
        print("You can now run the scraper without logging in again.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(save_login())
