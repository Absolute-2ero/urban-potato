"""
饿了么登录 Cookie 获取工具（服务器 / 本地通用）。

用法：
    python eleme_login.py

流程：
  1. 脚本在终端问你手机号
  2. headless 浏览器自动填手机号、点发送验证码
  3. 你在终端输入收到的验证码
  4. 脚本自动完成登录、保存 Cookie

无需 X display，服务器直接可用。
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


def _drag_captcha(frame, page) -> bool:
    """尝试自动拖动阿里 NoCaptcha 滑块。返回 True 表示尝试了拖动。"""
    import random
    try:
        # 找滑块手柄
        handle = frame.query_selector(".nc_iconfont.btn_slide, .btn_slide, [class*='btn_slide']")
        if not handle:
            handle = frame.query_selector("[id*='nc'] button, [id*='nc'] span[role]")
        if not handle:
            print("  找不到滑块手柄")
            return False

        box = handle.bounding_box()
        if not box:
            return False

        # 找轨道宽度
        track = frame.query_selector(".nc-lang-cnt, [class*='nc'][class*='track'], #nc_2__scale_text")
        track_width = 260  # 默认宽度
        if track:
            tb = track.bounding_box()
            if tb:
                track_width = int(tb["width"]) - int(box["width"])

        # 起点：滑块中心
        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2

        # 模拟人类拖动：慢启动、加速、减速
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        time.sleep(0.2)

        steps = 30
        for i in range(steps):
            # 非线性进度（缓入缓出）
            t = i / steps
            ease = t * t * (3 - 2 * t)  # smoothstep
            offset_x = ease * track_width
            jitter_y = random.uniform(-1, 1)
            page.mouse.move(start_x + offset_x, start_y + jitter_y,
                            steps=1)
            time.sleep(random.uniform(0.01, 0.04))

        page.mouse.move(start_x + track_width, start_y, steps=3)
        time.sleep(0.3)
        page.mouse.up()
        time.sleep(1.5)
        print("  滑块拖动完成")
        return True
    except Exception as e:
        print(f"  滑块拖动出错: {e}")
        return False


def main():
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("请先安装 playwright：pip install playwright && python -m playwright install chromium")
        sys.exit(1)

    phone = input("请输入手机号（不含 +86）：").strip()
    if not phone.isdigit() or len(phone) != 11:
        print("手机号格式不对，应为 11 位数字")
        sys.exit(1)

    print(f"\n[1/4] 启动 headless 浏览器，打开饿了么登录页...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            proxy={"server": "http://127.0.0.1:7890"},
        )
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=UA,
        )
        page = ctx.new_page()

        # 拦截并记录 API 请求，找到 token
        tokens: list = []
        def on_response(resp):
            if "restapi" in resp.url and resp.status == 200:
                try:
                    h = dict(resp.headers)
                    if "set-cookie" in h:
                        tokens.append(h["set-cookie"])
                except Exception:
                    pass
        page.on("response", on_response)

        page.goto("https://h5.ele.me/login/", wait_until="load", timeout=30_000)
        time.sleep(5)   # 等 iframe 渲染

        # 登录 form 在阿里 passport iframe 里
        login_frame = None
        for f in page.frames:
            if "ipassport.ele.me" in f.url:
                login_frame = f
                break

        if login_frame is None:
            page.screenshot(path="/tmp/eleme_debug.png")
            print("  ⚠️  找不到登录 iframe，截图已存 /tmp/eleme_debug.png")
            browser.close()
            sys.exit(1)

        print(f"[2/4] 填写手机号 {phone}...")
        phone_input = login_frame.wait_for_selector("#fm-sms-login-id", timeout=10_000)
        phone_input.click()
        phone_input.fill(phone)
        print("  手机号已填入")

        # 勾选「同意协议」复选框（让登录按钮从 disabled 变为可点击）
        try:
            checkbox = login_frame.wait_for_selector("input[type='checkbox']", timeout=3_000)
            if not checkbox.is_checked():
                checkbox.click()
                time.sleep(0.5)
                print("  已勾选协议")
        except PWTimeout:
            pass   # 没有复选框也无妨

        # ── 截图：发送 SMS 前的状态 ────────────────────────────────────────
        page.screenshot(path="/tmp/eleme_before_sms.png", full_page=True)

        # 检查是否有滑块验证码（需要先滑才能发 SMS）
        captcha_before = login_frame.query_selector("[id*='nc'][id*='captcha'], .nc-container")
        if captcha_before and captcha_before.is_visible():
            print("  检测到滑块验证码，尝试自动拖动...")
            _drag_captcha(login_frame, page)

        # 点「获取验证码」（是 <a> 标签，class=send-btn-link）
        sms_btn = login_frame.wait_for_selector("a.send-btn-link", timeout=5_000)
        sms_btn.click()
        print("[3/4] 已点击「获取验证码」，请查收短信...")
        time.sleep(3)

        # 截图：发送后状态（看有没有新滑块）
        page.screenshot(path="/tmp/eleme_after_sms.png", full_page=True)

        # 再次检查滑块（有时点完发送才出现）
        captcha_after = login_frame.query_selector("[id*='nc'][id*='captcha'], .nc-container, #nc_2_captcha_input")
        if captcha_after and captcha_after.is_visible():
            print("  发送后出现滑块，尝试拖动...")
            _drag_captcha(login_frame, page)
            time.sleep(2)

        code = input("请输入收到的验证码：").strip()

        code_input = login_frame.wait_for_selector("#fm-smscode", timeout=5_000)
        code_input.fill(code)
        time.sleep(1)

        # 截图：填完验证码的状态
        page.screenshot(path="/tmp/eleme_after_code.png", full_page=True)

        # 检查登录按钮状态
        btn_state = login_frame.eval_on_selector(
            "button.sms-login",
            "function(b){ return {text:b.innerText, disabled:b.disabled, class:b.className} }"
        )
        print(f"  登录按钮状态: {btn_state}")

        # 等登录按钮可点击
        try:
            login_btn = login_frame.wait_for_selector(
                "button.sms-login:not(.fm-button-disabled)", timeout=8_000
            )
        except PWTimeout:
            # 按钮还是 disabled？直接尝试强制点击
            print("  按钮仍 disabled，强制点击...")
            login_btn = login_frame.query_selector("button.sms-login")

        login_btn.click(force=True)
        time.sleep(2)
        page.screenshot(path="/tmp/eleme_after_login_click.png", full_page=True)
        print("  截图已保存 /tmp/eleme_after_login_click.png")

        print("[4/4] 等待登录完成...")
        # 等 ipassport 把 auth token 回传给 h5.ele.me，让它建立 session
        # 用 networkidle 确保所有后续请求（包括 session 建立）都完成
        try:
            page.wait_for_url(lambda url: "login" not in url, timeout=30_000)
            print("  URL 已跳转:", page.url[:60])
        except PWTimeout:
            print("  ⚠️  30s 内 URL 未跳转，尝试强制导航到首页...")
            # 尝试触发 auth callback：有时需要手动导航
            page.goto("https://h5.ele.me/minisite/", wait_until="networkidle", timeout=30_000)

        # 额外等待 session 完全建立
        time.sleep(5)
        page.wait_for_load_state("networkidle", timeout=15_000)

        # 验证 session 是否有效（不在登录页）
        final_url = page.url
        print(f"  最终 URL: {final_url[:80]}")
        if "login" in final_url:
            print("  ⚠️  仍在登录页，session 可能未建立，尝试再等 10s...")
            time.sleep(10)
            final_url = page.url
            print(f"  再次检查 URL: {final_url[:80]}")

        # 用页面内置 fetch 验证 session 是否真的有效
        try:
            session_ok = page.evaluate("""
            async () => {
                try {
                    const r = await fetch('/restapi/eus/v2/new_user_check', {credentials:'include'});
                    return {status: r.status, ok: r.ok};
                } catch(e) { return {error: e.toString()}; }
            }
            """)
            print(f"  Session 验证: {session_ok}")
        except Exception:
            pass

        # 保存 Cookie
        cookies = ctx.cookies()
        try:
            storage = page.evaluate("() => JSON.stringify(Object.fromEntries(Object.entries(localStorage)))")
            local_storage = json.loads(storage)
        except Exception:
            local_storage = {}

        result = {
            "cookies": cookies,
            "local_storage": local_storage,
            "headers": {
                "User-Agent": UA,
                "Referer": "https://h5.ele.me/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        }
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n✅ Cookie 已保存：{OUTPUT}（共 {len(cookies)} 条）")
        if len(cookies) < 3:
            print("  ⚠️  Cookie 数量很少，登录可能未成功，请检查截图 /tmp/eleme_debug*.png")

        browser.close()


if __name__ == "__main__":
    main()
