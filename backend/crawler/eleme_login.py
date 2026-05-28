"""
饿了么登录 Cookie 获取工具（本机有界面版）。

用法（本机）：
    pip install playwright
    python -m playwright install chromium
    python eleme_login.py

流程：
  1. 弹出浏览器窗口
  2. 脚本自动填手机号、勾协议、点「获取验证码」
  3. 如果出现「运营商验证」：按提示从手机发短信，回车继续
     如果出现普通验证码输入框：在终端输入收到的 6 位码
  4. 自动完成登录，保存 Cookie
"""
import json
import sys
import time
from pathlib import Path

OUTPUT = Path(__file__).parent / "eleme_cookies.json"

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)

# 本机不需要代理；服务器需要。自动检测：
import os
_PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None


def _drag_slider(frame, page) -> bool:
    """尝试自动拖动阿里 NoCaptcha 滑块。"""
    import random
    try:
        handle = frame.query_selector(
            ".nc_iconfont.btn_slide, .btn_slide, "
            "[class*='btn_slide'], [id*='nc'] .btn_slide"
        )
        if not handle or not handle.is_visible():
            return False

        box = handle.bounding_box()
        if not box:
            return False

        track = frame.query_selector(
            ".nc-lang-cnt, [class*='scale_text'], #nc_2__scale_text"
        )
        track_width = 250
        if track:
            tb = track.bounding_box()
            if tb:
                track_width = max(int(tb["width"]) - int(box["width"]), 100)

        sx = box["x"] + box["width"] / 2
        sy = box["y"] + box["height"] / 2

        page.mouse.move(sx, sy)
        page.mouse.down()
        time.sleep(0.15)

        steps = 35
        for i in range(steps):
            t = i / steps
            ease = t * t * (3 - 2 * t)
            page.mouse.move(
                sx + ease * track_width,
                sy + random.uniform(-1.5, 1.5),
            )
            time.sleep(random.uniform(0.008, 0.035))

        page.mouse.move(sx + track_width, sy)
        time.sleep(0.25)
        page.mouse.up()
        time.sleep(1.5)
        print("  滑块拖动完成")
        return True
    except Exception as e:
        print(f"  滑块拖动失败: {e}")
        return False


def _handle_carrier_verify(login_frame, page) -> bool:
    """
    处理运营商一键验证页面：
    页面显示「收件人」和「短信内容」，用户需要从手机发短信完成验证。
    返回 True 表示检测到并处理了该页面。
    """
    try:
        # 检测运营商验证页面特征
        carrier_tip = login_frame.query_selector(
            "text=请使用以下手机号发送短信完成验证, "
            "[class*='operator'], .operator-verify, "
            "[class*='carrier']"
        )
        # 更宽泛：找「去发送短信」按钮
        send_btn = login_frame.query_selector(
            "button:has-text('去发送短信'), "
            "a:has-text('去发送短信'), "
            ".go-send-btn"
        )
        done_btn = login_frame.query_selector(
            "button:has-text('已发送短信'), "
            "a:has-text('已发送短信'), "
            ".sent-btn, [class*='sent']"
        )

        if not (carrier_tip or send_btn or done_btn):
            return False

        print("\n  ⚠️  检测到「运营商验证」页面！")

        # 提取收件号码和短信内容
        try:
            recipient = login_frame.inner_text("[class*='phone'], .operator-phone, td:nth-child(2):first-of-type")
        except Exception:
            recipient = "(见浏览器窗口)"
        try:
            sms_content = login_frame.inner_text("[class*='content'], .operator-content, td:nth-child(2):last-of-type")
        except Exception:
            sms_content = "(见浏览器窗口)"

        print(f"  请用手机 {phone_global} 发送短信：")
        print(f"    收件人：{recipient.strip()}")
        print(f"    短信内容：{sms_content.strip()}")
        print("  发送完成后按回车继续...")
        input()

        # 点「已发送短信，下一步」
        if done_btn and done_btn.is_visible():
            done_btn.click()
        else:
            # 找所有橙色按钮中的第二个（「已发送短信」通常在「去发送短信」后面）
            btns = login_frame.query_selector_all("button, a.btn")
            for btn in btns:
                txt = btn.inner_text().strip()
                if "已发送" in txt or "下一步" in txt:
                    btn.click()
                    break

        time.sleep(2)
        return True

    except Exception as e:
        print(f"  运营商验证处理出错: {e}")
        return False


phone_global = ""   # 供 _handle_carrier_verify 访问


def main():
    global phone_global

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("请先安装：pip install playwright && python -m playwright install chromium")
        sys.exit(1)

    phone = input("请输入手机号（不含 +86）：").strip()
    if not phone.isdigit() or len(phone) != 11:
        print("手机号格式错误")
        sys.exit(1)
    phone_global = phone

    launch_args = {"headless": False, "slow_mo": 80}
    if _PROXY:
        launch_args["proxy"] = {"server": _PROXY}
        print(f"[代理] 使用 {_PROXY}")

    print("\n[1/4] 打开浏览器...")

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_args)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, user_agent=UA)
        page = ctx.new_page()

        page.goto("https://h5.ele.me/login/", wait_until="load", timeout=30_000)
        time.sleep(4)

        # 找 ipassport iframe
        login_frame = next(
            (f for f in page.frames if "ipassport.ele.me" in f.url), None
        )
        if login_frame is None:
            print("❌ 找不到登录 iframe，请截图检查")
            input("按回车关闭...")
            browser.close()
            sys.exit(1)

        # ── 填手机号 ─────────────────────────────────────────────────────
        print(f"[2/4] 填写手机号 {phone}...")
        phone_input = login_frame.wait_for_selector("#fm-sms-login-id", timeout=10_000)
        phone_input.click()
        phone_input.fill(phone)

        # 勾选协议
        try:
            cb = login_frame.wait_for_selector("input[type='checkbox']", timeout=3_000)
            if not cb.is_checked():
                cb.click()
                time.sleep(0.3)
                print("  已勾选协议")
        except PWTimeout:
            pass

        # 滑块（在发送前）
        captcha = login_frame.query_selector(".nc-container, [id*='nc'][id*='captcha']")
        if captcha and captcha.is_visible():
            print("  发现滑块，尝试拖动...")
            _drag_slider(login_frame, page)

        # ── 点「获取验证码」────────────────────────────────────────────────
        sms_btn = login_frame.wait_for_selector("a.send-btn-link", timeout=5_000)
        sms_btn.click()
        print("[3/4] 已点击「获取验证码」，等待 3s...")
        time.sleep(3)

        # 滑块（发送后可能出现）
        captcha2 = login_frame.query_selector(".nc-container, [id*='nc'][id*='captcha']")
        if captcha2 and captcha2.is_visible():
            print("  发现滑块，尝试拖动...")
            _drag_slider(login_frame, page)
            time.sleep(2)

        # ── 判断验证方式 ──────────────────────────────────────────────────
        # 方式 A：运营商验证（发短信）
        carrier_handled = _handle_carrier_verify(login_frame, page)

        if not carrier_handled:
            # 方式 B：普通短信验证码
            code_input = login_frame.query_selector("#fm-smscode")
            if code_input and code_input.is_visible():
                code = input("请输入收到的验证码：").strip()
                code_input.fill(code)
                time.sleep(0.5)
            else:
                print("  ⚠️  未识别验证方式，请在浏览器里手动完成登录，完成后按回车...")
                input()

        # ── 点登录按钮 ────────────────────────────────────────────────────
        try:
            login_btn = login_frame.wait_for_selector(
                "button.sms-login:not(.fm-button-disabled)", timeout=6_000
            )
            login_btn.click()
        except PWTimeout:
            # 已经跳走了（运营商验证自动跳转），或按钮找不到
            pass

        # ── 等待 session 建立 ─────────────────────────────────────────────
        print("[4/4] 等待登录完成（最多 60s）...")
        try:
            page.wait_for_url(
                lambda url: "login" not in url and "ipassport" not in url,
                timeout=60_000,
            )
            print(f"  ✅ 跳转成功：{page.url[:70]}")
        except PWTimeout:
            print(f"  ⚠️  超时，当前 URL：{page.url[:70]}")
            print("  请在浏览器里手动完成剩余步骤，完成后按回车...")
            input()

        # 确保 networkidle（等所有 cookie 写入）
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        time.sleep(3)

        # ── 验证 session ──────────────────────────────────────────────────
        try:
            check = page.evaluate("""
            async () => {
                const r = await fetch('/restapi/eus/v2/new_user_check', {credentials:'include'});
                return {status: r.status, url: location.href};
            }
            """)
            print(f"  Session 检查: status={check.get('status')}  url={check.get('url','')[:60]}")
        except Exception:
            pass

        # ── 保存 Cookie ───────────────────────────────────────────────────
        cookies = ctx.cookies()
        try:
            ls = page.evaluate(
                "() => JSON.stringify(Object.fromEntries(Object.entries(localStorage)))"
            )
            local_storage = json.loads(ls)
        except Exception:
            local_storage = {}

        OUTPUT.write_text(json.dumps({
            "cookies": cookies,
            "local_storage": local_storage,
            "headers": {
                "User-Agent": UA,
                "Referer": "https://h5.ele.me/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        }, ensure_ascii=False, indent=2))

        print(f"\n✅ Cookie 已保存：{OUTPUT}（共 {len(cookies)} 条）")
        if len(cookies) < 5:
            print("  ⚠️  Cookie 数量偏少，登录可能不完整")

        input("按回车关闭浏览器...")
        browser.close()


if __name__ == "__main__":
    main()
