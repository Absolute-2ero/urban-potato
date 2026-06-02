from __future__ import annotations

"""
Save a logged-in Foodpanda session to foodpanda_state.json.

Run this once if Foodpanda blocks the crawler with a login wall or CAPTCHA.
After saving, the main crawler will load the session automatically.

Usage (from backend/):
    py -3.12 -m crawler.hk.foodpanda_login_saver
"""

import asyncio
import os

_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "foodpanda_state.json")


async def main() -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            slow_mo=200,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-HK",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await ctx.new_page()
        await page.goto("https://www.foodpanda.hk/", wait_until="domcontentloaded")

        print("\nFoodpanda is open in the browser.")
        print("Log in manually (or solve any CAPTCHA), then press Enter here to save the session.")
        input("Press Enter when logged in > ")

        await ctx.storage_state(path=_STATE_PATH)
        print(f"Session saved to {_STATE_PATH}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
