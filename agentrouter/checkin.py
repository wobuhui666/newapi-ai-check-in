"""AgentRouter 每日签到：每天用全新浏览器重新登录一次，登录即自动签到。

凭据从环境变量读取（GitHub Actions Secrets），不要写进代码：
  AGENTROUTER_EMAIL     邮箱或用户名
  AGENTROUTER_PASSWORD  密码
"""
import asyncio
import os
import re
import sys

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

BASE = os.environ.get("AGENTROUTER_BASE", "https://agentrouter.org").rstrip("/")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
SHOT = "failure.png"


def log(msg):
    print(msg, flush=True)


async def first_visible(page, selectors, timeout=15000):
    """返回第一个可见的元素。"""
    deadline = asyncio.get_event_loop().time() + timeout / 1000
    while asyncio.get_event_loop().time() < deadline:
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                if await loc.count() and await loc.is_visible():
                    return loc
            except Exception:
                pass
        await page.wait_for_timeout(500)
    return None


async def run(email, password):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 860})
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = await ctx.new_page()


        try:
            log(f"打开 {BASE}/login")
            await page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=30000)

            # 阿里云 WAF 的 JS 质询一般会自动通过并刷新页面；出现滑块就说明这个 IP 被拦了
            pwd = await first_visible(page, ["input[type=password]"], timeout=3000)
            if not pwd:
                btn = await first_visible(page, [
                    "button:has-text('邮箱或用户名')",
                    "button:has-text('Email or Username')",
                    "text=/邮箱或用户名|Email or Username/i",
                ], timeout=25000)
                if btn:
                    await btn.click()
                pwd = await first_visible(page, ["input[type=password]"], timeout=15000)
            if not pwd:
                if await page.locator("#aliyunCaptcha-sliding-slider, .aliyun-captcha, meta[name=aliyun_waf_aa]").count():
                    raise RuntimeError("被阿里云 WAF 滑块验证拦截（当前运行 IP 不受信任）")
                raise RuntimeError("没找到登录表单，页面结构可能变了")

            user = await first_visible(page, [
                "input[name=username]", "input[type=email]", "input[type=text]",
            ], timeout=5000)
            await user.fill(email)
            await pwd.fill(password)

            submit = await first_visible(page, [
                "button[type=submit]",
                "button:has-text('继续')", "button:has-text('登录')",
                "button:has-text('Continue')", "button:has-text('Sign in')",
            ], timeout=5000)
            if submit:
                await submit.click()
            else:
                await pwd.press("Enter")

            try:
                await page.wait_for_url(re.compile(r"/console"), timeout=45000)
            except PWTimeout:
                body = (await page.inner_text("body"))[:300]
                raise RuntimeError(f"登录后没有进入控制台：{body}")
            log("登录成功")

            # 签到成功会弹出“签到成功，新增额度已到账”
            msg = None
            try:
                t = page.get_by_text(re.compile(r"签到|check.?in", re.I)).first
                await t.wait_for(timeout=15000)
                msg = (await t.inner_text()).strip()
            except PWTimeout:
                pass
            log(f"签到提示：{msg or '未捕获到提示（可能今天已签过）'}")

            info = await page.evaluate("""async () => {
                let id = null;
                try { id = JSON.parse(localStorage.getItem('user') || '{}').id; } catch (e) {}
                const r = await fetch('/api/user/self', {
                    credentials: 'include',
                    headers: id ? {'New-Api-User': String(id)} : {},
                });
                return await r.json();
            }""")
            if info.get("success"):
                d = info["data"]
                log(f"账号：{d.get('username')}  余额：${d.get('quota', 0) / 500000:.2f}  "
                    f"已用：${d.get('used_quota', 0) / 500000:.2f}")
            else:
                log(f"读取余额失败：{info.get('message')}")
            return True
        except Exception as e:
            log(f"失败：{e}")
            try:
                await page.screenshot(path=SHOT, full_page=True)
            except Exception:
                pass
            return False
        finally:
            await browser.close()


def main():
    email = os.environ.get("AGENTROUTER_EMAIL")
    password = os.environ.get("AGENTROUTER_PASSWORD")
    if not email or not password:
        sys.exit("缺少 AGENTROUTER_EMAIL / AGENTROUTER_PASSWORD")
    for attempt in range(1, 4):
        log(f"第 {attempt} 次尝试")
        if asyncio.run(run(email, password)):
            return
    sys.exit(1)


if __name__ == "__main__":
    main()
