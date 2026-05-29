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
        # Launch a visible browser so you can interact with it
        browser = await p.chromium.launch(headless=False)

        # Use iPhone emulation — ele.me mobile is simpler and less suspicious
        iphone = p.devices["iPhone 13"]
        context = await browser.new_context(
            **iphone,
            geolocation={"latitude": GEO_LAT, "longitude": GEO_LNG},
            permissions=["geolocation"],
            locale="zh-CN",
        )

        page = await context.new_page()

        # Open ele.me mobile homepage
        print("Opening ele.me...")
        await page.goto("https://h5.ele.me", wait_until="networkidle", timeout=30000)

        # Hand control to the human — wait until they confirm login is done
        print("\n" + "="*60)
        print("A browser window has opened.")
        print("Log in to ele.me manually (phone number + SMS code).")
        print("Once you can see the ele.me homepage (not the login screen),")
        print("come back here and press Enter.")
        print("="*60)
        input("\nPress Enter after you have logged in successfully... ")

        # Save the entire session: cookies, localStorage, sessionStorage
        await context.storage_state(path=STATE_PATH)
        print(f"\nSession saved to: {STATE_PATH}")
        print("You can now run the tester without logging in again.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(save_login())
