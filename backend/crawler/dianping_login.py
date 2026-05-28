"""
大众点评扫码登录工具（Playwright）。

用法：
    pip install playwright
    python -m playwright install chromium
    python dianping_login.py

流程：
  1. 打开 PC 登录页（默认显示二维码）
  2. 将二维码截图保存到 /tmp/dp_qr.png
  3. 用「大众点评」App 扫码确认
  4. 等待页面自动跳转，保存 Cookie 到 dianping_cookies.json
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

OUTPUT   = Path(__file__).parent / "dianping_cookies.json"
SHOT_DIR = Path("/tmp/dp_login_shots")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None

LOGIN_URL = "https://account.dianping.com/pclogin"
HOME_URL  = "https://www.dianping.com"


def _is_logged_in(url: str) -> bool:
    return (
        "dianping.com" in url
        and "account.dianping.com" not in url
        and "mlogin" not in url
        and "login" not in url
        and "verify" not in url
    )


def _screenshot_loop(page_ref: list, stop: threading.Event) -> None:
    """每 5s 截一张图，文件名含序号，方便逐帧排查。"""
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    idx = 0
    while not stop.is_set():
        try:
            path = SHOT_DIR / f"{idx:03d}.png"
            page_ref[0].screenshot(path=str(path))
            print(f"  [截图] {path}")
        except Exception:
            pass
        idx += 1
        stop.wait(5)


def _save_cookies(ctx, page) -> int:
    cookies = ctx.cookies()
    try:
        ls_raw = page.evaluate(
            "() => JSON.stringify(Object.fromEntries(Object.entries(localStorage)))"
        )
        local_storage = json.loads(ls_raw) if ls_raw else {}
    except Exception:
        local_storage = {}

    OUTPUT.write_text(
        json.dumps(
            {
                "cookies": cookies,
                "local_storage": local_storage,
                "headers": {
                    "User-Agent": UA,
                    "Referer": "https://www.dianping.com/",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(cookies)


def main():
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("请先安装：pip install playwright && python -m playwright install chromium")
        sys.exit(1)

    headless = bool(_PROXY)
    launch_kw: dict = {
        "headless": headless,
        "slow_mo": 50,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    if _PROXY:
        launch_kw["proxy"] = {"server": _PROXY}
        print(f"[代理] {_PROXY}，headless=True")
    else:
        print("[本机] headless=False，将弹出浏览器窗口")

    print(f"[截图] 每 5s 存一张到 {SHOT_DIR}/")

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kw)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=UA,
            locale="zh-CN",
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        page = ctx.new_page()

        # 启动截图线程
        stop_event = threading.Event()
        page_ref   = [page]
        shot_thread = threading.Thread(
            target=_screenshot_loop, args=(page_ref, stop_event), daemon=True
        )
        shot_thread.start()

        try:
            # ── 打开登录页 ────────────────────────────────────────────────────
            print("\n[1/3] 打开二维码登录页...")
            page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
            time.sleep(3)
            print(f"  当前 URL: {page.url[:80]}")

            # ── 等待 QR 码图片渲染 ────────────────────────────────────────────
            try:
                page.wait_for_selector("img.qrcode-img", timeout=10_000)
                # 单独截下 QR 码区域，方便手机扫
                qr_el = page.query_selector("img.qrcode-img")
                if qr_el:
                    qr_path = "/tmp/dp_qr.png"
                    qr_el.screenshot(path=qr_path)
                    print(f"\n[2/3] 二维码已保存到 {qr_path}")
                    print("      请用「大众点评」App 扫码登录...")
                else:
                    print("[2/3] QR 元素未找到，请看截图确认页面状态")
            except PWTimeout:
                print("[2/3] QR 码未在 10s 内出现，请看截图排查")

            # ── 等待扫码跳转（最多 3 分钟）────────────────────────────────────
            print("\n[3/3] 等待扫码完成（最多 3 分钟）...")
            try:
                page.wait_for_url(
                    lambda url: _is_logged_in(url),
                    timeout=180_000,
                )
                print(f"  ✅ 登录成功：{page.url[:80]}")
            except PWTimeout:
                print(f"  ⚠️  超时，当前 URL：{page.url[:80]}")
                print("  请手动完成后按回车继续...")
                input()

            # 等待 Cookie 写入
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            time.sleep(2)

            # 确保在首页（session cookie 完整）
            if not _is_logged_in(page.url):
                page.goto(HOME_URL, wait_until="domcontentloaded", timeout=20_000)
                time.sleep(2)

            # 验证登录状态
            try:
                check = page.request.get(
                    "https://m.dianping.com/account/ajax/checkLogin",
                    headers={"Referer": HOME_URL, "Accept": "application/json"},
                )
                result = check.json()
                logged = result.get("login", False)
                print(f"  Session 验证：{'✅ 已登录' if logged else '❌ 未登录'} → {result}")
            except Exception as e:
                print(f"  Session 验证失败: {e}")

            # 保存 Cookie
            n = _save_cookies(ctx, page)
            print(f"\n✅ Cookie 已保存到 {OUTPUT}（共 {n} 条）")
            if n < 5:
                print("  ⚠️  Cookie 数量偏少，登录可能不完整")

        finally:
            stop_event.set()
            shot_thread.join(timeout=6)
            if not headless:
                input("\n按回车关闭浏览器...")
            browser.close()


if __name__ == "__main__":
    main()
