from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pathlib import Path
from datetime import datetime
import time
import os
import re

TARGET_URL = "https://podcaster.xiaoyuzhoufm.com/podcasts/694b6081c1f27098798c74c4/data-analysis/content"
BASE_DIR = Path(__file__).parent
AUTH_FILE = BASE_DIR / "auth" / "storage_state.json"
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
HEADLESS = os.getenv("HEADLESS", "0") == "1"

def ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def find_first_trend_export(page):
    # Anchor by heading text, then find the nearest following "导出数据".
    target = page.locator(
        "xpath=(//*[self::h1 or self::h2 or self::h3 or self::div][starts-with(normalize-space(.), '增量数据趋势')]"
        "/following::*[normalize-space(.)='导出数据'])[1]"
    ).first
    if target.count() == 0:
        return None
    return target


def find_episode_table_export(page):
    # Anchor by "单集数据" keyword, then select its following export control.
    target = page.locator(
        "xpath=(//*[self::h1 or self::h2 or self::h3 or self::div][starts-with(normalize-space(.), '单集数据')]"
        "/following::*[normalize-space(.)='导出数据'])[1]"
    ).first
    if target.count() == 0:
        return None
    return target


def js_click_closest_clickable(locator):
    locator.evaluate(
        """el => {
            let cur = el;
            for (let i = 0; i < 10 && cur; i++) {
                const style = window.getComputedStyle(cur);
                const isClickable =
                  cur.tagName === 'BUTTON' ||
                  cur.tagName === 'A' ||
                  cur.getAttribute('role') === 'button' ||
                  cur.getAttribute('tabindex') !== null ||
                  style.cursor === 'pointer' ||
                  typeof cur.onclick === 'function';
                if (isClickable) {
                    cur.click();
                    return;
                }
                cur = cur.parentElement;
            }
            el.click();
        }"""
    )


def click_and_download(page, button, timeout_ms=30000):
    # Try normal click, force click, then click a likely clickable ancestor.
    attempts = [
        lambda: button.click(timeout=10000),
        lambda: button.click(timeout=10000, force=True),
        lambda: js_click_closest_clickable(button),
    ]

    for action in attempts:
        try:
            with page.expect_download(timeout=timeout_ms) as download_info:
                action()
            return {"kind": "download", "data": download_info.value}
        except PlaywrightTimeoutError:
            pass

    # Fallback: some sites export via XHR/fetch response instead of browser download.
    response = None
    for action in attempts:
        try:
            with page.expect_response(
                lambda r: (
                    r.status == 200
                    and (
                        "export" in r.url.lower()
                        or "download" in r.url.lower()
                        or "csv" in r.url.lower()
                        or "excel" in r.url.lower()
                    )
                ),
                timeout=timeout_ms,
            ) as resp_info:
                action()
            response = resp_info.value
            if response:
                break
        except PlaywrightTimeoutError:
            pass

    if not response:
        raise PlaywrightTimeoutError("未捕获到浏览器下载事件，也未捕获到导出接口响应")

    headers = {k.lower(): v for k, v in response.headers.items()}
    cd = headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    if m:
        api_name = m.group(1)
    else:
        api_name = f"export_{int(time.time())}.bin"

    return {"kind": "response", "data": response, "filename": api_name}

with sync_playwright() as p:
    if not AUTH_FILE.exists():
        raise FileNotFoundError(f"未找到登录态文件：{AUTH_FILE}，请先运行 login.py")

    browser = p.chromium.launch(headless=HEADLESS)
    context = browser.new_context(
        storage_state=str(AUTH_FILE),
        accept_downloads=True
    )
    page = context.new_page()

    try:
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        if "/data-analysis/content" not in page.url:
            raise RuntimeError(f"可能登录失效，当前页面不是目标页：{page.url}")

        trend_export = find_first_trend_export(page)
        if trend_export is None:
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
            trend_export = find_first_trend_export(page)

        if trend_export is None:
            body_text = page.locator("body").inner_text()
            (BASE_DIR / "debug_page_text.txt").write_text(body_text, encoding="utf-8")
            raise RuntimeError("未找到『增量数据趋势』里的“导出数据”，已输出 debug_page_text.txt 便于排查")

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1200)
        episode_export = find_episode_table_export(page)
        if episode_export is None:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1200)
            episode_export = find_episode_table_export(page)

        if episode_export is None:
            body_text = page.locator("body").inner_text()
            (BASE_DIR / "debug_page_text.txt").write_text(body_text, encoding="utf-8")
            raise RuntimeError("未找到『单集数据』里的“导出数据”，已输出 debug_page_text.txt 便于排查")

        saved_files = []

        jobs = [
            ("增量数据趋势", trend_export),
            ("单集数据", episode_export),
        ]

        for idx, (label, target) in enumerate(jobs, start=1):
            target.scroll_into_view_if_needed()
            page.wait_for_timeout(1200)
            print(f"[导出{idx}] 已定位到『{label}』中的“导出数据”，准备点击")

            result = click_and_download(page, target, timeout_ms=60000)

            if result["kind"] == "download":
                download = result["data"]
                out_name = download.suggested_filename
                filename = f"{ts()}_export_{idx}_{out_name}"
                save_path = DOWNLOAD_DIR / filename
                download.save_as(str(save_path))
                print(f"[导出{idx}] 通过浏览器下载事件保存: {save_path.name}")
            else:
                response = result["data"]
                out_name = result["filename"]
                filename = f"{ts()}_export_{idx}_{out_name}"
                save_path = DOWNLOAD_DIR / filename
                save_path.write_bytes(response.body())
                print(f"[导出{idx}] 通过接口响应保存: {save_path.name} ({response.url})")

            saved_files.append(save_path)
            time.sleep(2)

        print("导出完成：")
        for f in saved_files:
            print(f)

    except PlaywrightTimeoutError:
        print("下载超时：可能按钮不是直接下载，或者页面加载较慢")
        raise
    finally:
        context.close()
        browser.close()
