from playwright.sync_api import sync_playwright
from pathlib import Path

AUTH_DIR = Path("auth")
AUTH_DIR.mkdir(exist_ok=True)
STATE_FILE = AUTH_DIR / "storage_state.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    page.goto("https://podcaster.xiaoyuzhoufm.com/", wait_until="domcontentloaded")

    input("请在浏览器里手动登录小宇宙主播后台，登录完成后回到终端按回车...")

    context.storage_state(path=str(STATE_FILE))
    print(f"登录状态已保存到: {STATE_FILE}")

    browser.close()