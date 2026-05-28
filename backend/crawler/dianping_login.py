"""
大众点评登录 Cookie 获取工具（Playwright）。

用法：
    pip install playwright
    python -m playwright install chromium
    python dianping_login.py

流程：
  1. 打开移动端登录页（选择器简洁，无 QR 干扰）
  2. 自动填手机号 → 点「发送验证码」
  3. 终端输入短信验证码 → 点「登录」
  4. 等待跳转首页，保存 Cookie 到 dianping_cookies.json
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

OUTPUT = Path(__file__).parent / "dianping_cookies.json"

# 移动端 UA（对应 mlogin 页面）
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

# 代理：优先读环境变量
_PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None

# 移动端短信登录页（探索确认的选择器最简洁）
LOGIN_URL = "https://mlogin.dianping.com/mlogin/smslogin"
HOME_URL  = "https://m.dianping.com"


def _is_logged_in(url: str) -> bool:
    return (
        "dianping.com" in url
        and "mlogin" not in url
        and "login" not in url
        and "account" not in url
        and "verify" not in url
    )


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
                    "Referer": "https://m.dianping.com/",
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

    phone = input("请输入手机号（11 位，不含 +86）：").strip()
    if not phone.isdigit() or len(phone) != 11:
        print("手机号格式错误")
        sys.exit(1)

    headless = bool(_PROXY)
    launch_kw: dict = {
        "headless": headless,
        "slow_mo": 80,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    if _PROXY:
        launch_kw["proxy"] = {"server": _PROXY}
        print(f"[代理] {_PROXY}，headless=True")
    else:
        print("[本机] headless=False，将弹出浏览器窗口")

    print("\n[1/4] 打开浏览器...")

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kw)
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=UA,
            locale="zh-CN",
            is_mobile=True,
        )
        # 隐藏 webdriver 特征
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}};
        """)
        page = ctx.new_page()

        # ── [2/4] 打开登录页 ──────────────────────────────────────────────────
        print("[2/4] 打开登录页...")
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
        time.sleep(2)
        print(f"  当前 URL: {page.url[:80]}")

        # ── 勾选协议（图片按钮，点击变为已选状态）──────────────────────────
        try:
            agreement_img = page.wait_for_selector(
                ".agreement img, .agreement > div:first-child",
                timeout=5_000,
            )
            if agreement_img:
                agreement_img.click()
                time.sleep(0.3)
                print("  已勾选协议")
        except PWTimeout:
            print("  (未找到协议勾选框，跳过)")

        # ── 填手机号 ──────────────────────────────────────────────────────────
        print(f"[3/4] 填写手机号 {phone}...")
        phone_input = page.wait_for_selector("#mobile", timeout=10_000)
        phone_input.click()
        phone_input.fill(phone)
        time.sleep(0.5)

        # ── 点「发送验证码」──────────────────────────────────────────────────
        send_btn = page.wait_for_selector("#send-vcode", timeout=5_000)
        send_btn.click()
        print("  已点击「发送验证码」，等待 2s...")
        time.sleep(2)

        # 检查是否有 Yoda 滑块验证
        try:
            yoda = page.wait_for_selector(
                "#yoda-root:not([style*='display: none']), "
                ".yoda-root:not([style*='display: none'])",
                timeout=3_000,
            )
            if yoda and yoda.is_visible():
                print("  ⚠️  出现滑块验证，请在浏览器里手动完成，然后按回车继续...")
                input()
        except PWTimeout:
            pass  # 没有滑块，继续

        # ── 输入验证码 ────────────────────────────────────────────────────────
        code = input("请输入收到的短信验证码：").strip()
        code_input = page.wait_for_selector("#vcode", timeout=5_000)
        code_input.click()
        code_input.fill(code)
        time.sleep(0.5)

        # ── 点「登录」────────────────────────────────────────────────────────
        # 按钮 class 在填写完后从 button-primary-disable 变为 button-primary
        for sel in [".button-primary", ".btn-box .button-primary-disable", "text=登录"]:
            try:
                btn = page.wait_for_selector(sel, timeout=3_000)
                if btn and btn.is_visible():
                    btn.click()
                    print("  已点击「登录」")
                    break
            except PWTimeout:
                continue

        # ── [4/4] 等待跳转 ───────────────────────────────────────────────────
        print("[4/4] 等待登录完成（最多 60s）...")
        try:
            page.wait_for_url(
                lambda url: _is_logged_in(url),
                timeout=60_000,
            )
            print(f"  ✅ 跳转成功：{page.url[:80]}")
        except PWTimeout:
            print(f"  ⚠️  超时，当前 URL：{page.url[:80]}")
            print("  请在浏览器里手动完成，完成后按回车...")
            input()

        # 等待 Cookie 写入
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        time.sleep(2)

        # 访问首页确保 session cookie 完整
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

        # 保存
        n = _save_cookies(ctx, page)
        print(f"\n✅ Cookie 已保存到 {OUTPUT}（共 {n} 条）")
        if n < 5:
            print("  ⚠️  Cookie 数量偏少，登录可能不完整")

        if not headless:
            input("\n按回车关闭浏览器...")
        browser.close()


if __name__ == "__main__":
    main()
