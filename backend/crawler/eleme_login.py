"""
本地运行（你自己电脑上）：拿到饿了么登录 Cookie 并保存。

用法：
    pip install playwright
    python -m playwright install chromium
    python eleme_login.py

运行后会弹出浏览器窗口，按提示登录饿了么，完成后 Cookie 自动保存。
"""
import json
import sys
import time
from pathlib import Path

OUTPUT = Path(__file__).parent / "eleme_cookies.json"


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("请先安装 playwright：pip install playwright && python -m playwright install chromium")
        sys.exit(1)

    print("=== 饿了么 Cookie 获取工具 ===")
    print("即将打开浏览器，请在浏览器中完成手机号验证码登录。")
    print("登录成功后脚本会自动保存 Cookie 并关闭浏览器。\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,        # 有界面，你可以操作
            slow_mo=100,
            args=["--window-size=480,900"],
        )
        ctx = browser.new_context(
            viewport={"width": 480, "height": 900},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )
        page = ctx.new_page()

        # 打开登录页
        page.goto("https://h5.ele.me/login/", wait_until="networkidle")
        print("浏览器已打开饿了么登录页，请：")
        print("  1. 输入手机号")
        print("  2. 点击「获取验证码」")
        print("  3. 输入收到的验证码")
        print("  4. 点击登录")
        print("\n等待登录完成（最多 3 分钟）...")

        # 等待登录成功标志：URL 跳转到首页，或出现用户头像
        try:
            page.wait_for_url("**/index**", timeout=180_000)
        except Exception:
            pass  # 有些版本跳到别的 URL

        # 额外等待 2s 确保 Cookie 写入
        time.sleep(2)

        # 保存所有 Cookie
        cookies = ctx.cookies()
        # 保存当前 localStorage（含 token 等）
        try:
            storage = page.evaluate("() => JSON.stringify(localStorage)")
            local_storage = json.loads(storage)
        except Exception:
            local_storage = {}

        # 同时抓一下关键请求头
        result = {
            "cookies": cookies,
            "local_storage": local_storage,
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                    "Mobile/15E148 Safari/604.1"
                ),
                "Referer": "https://h5.ele.me/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        }
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n✅ Cookie 已保存到：{OUTPUT}")
        print(f"   共 {len(cookies)} 条 Cookie")
        print("\n请把这个文件上传到服务器的 backend/crawler/ 目录下。")

        browser.close()


if __name__ == "__main__":
    main()
