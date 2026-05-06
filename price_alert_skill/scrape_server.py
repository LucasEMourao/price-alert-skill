#!/usr/bin/env python3

"""Local Playwright-based scraping server that replaces Steel Browser.

Exposes the API surface the fetchers expect:
  POST /v1/scrape                    {"url": "...", "delay": N}

Usage:
  pip install fastapi uvicorn playwright
  playwright install chromium
  python scripts/scrape_server.py --port 3000
"""

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from price_alert_skill.paths import resolve_data_dir

# ---------------------------------------------------------------------------
# Stealth helpers
# ---------------------------------------------------------------------------

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(parameters);
delete navigator.__proto__.webdriver;
"""

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

playwright_instance: Playwright | None = None
browser: Browser | None = None
DATA_DIR = resolve_data_dir()


async def get_browser() -> Browser:
    global playwright_instance, browser
    if browser is None or not browser.is_connected():
        playwright_instance = await async_playwright().start()
        browser = await playwright_instance.chromium.launch(
            headless=True,
            channel="chromium",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--disable-extensions",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-software-rasterizer",
            ],
        )
    return browser


def random_viewport() -> dict[str, int]:
    import random
    return random.choice(VIEWPORTS)


def random_user_agent() -> str:
    import random
    return random.choice(USER_AGENTS)


async def create_stealth_context(
    b: Browser,
    *,
    storage_state: dict[str, Any] | str | None = None,
) -> BrowserContext:
    viewport = random_viewport()
    ua = random_user_agent()

    context_options: dict[str, Any] = {
        "viewport": viewport,
        "user_agent": ua,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "color_scheme": "light",
        "java_script_enabled": True,
        "ignore_https_errors": True,
        "extra_http_headers": {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
        },
    }

    if storage_state:
        context_options["storage_state"] = storage_state

    context = await b.new_context(**context_options)
    await context.add_init_script(STEALTH_JS)
    return context


async def scrape_url(
    url: str,
    delay_ms: int = 2500,
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    b = await get_browser()
    context = await create_stealth_context(b, storage_state=session_context)

    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        final_url = page.url
        title = await page.title()
        html = await page.content()

        return {
            "html": html,
            "metadata": {
                "urlSource": final_url,
                "title": title,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    finally:
        await context.close()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    global browser, playwright_instance
    if browser and browser.is_connected():
        await browser.close()
    if playwright_instance:
        await playwright_instance.stop()


app = FastAPI(title="Playwright Scrape Server", lifespan=lifespan)


@app.post("/v1/scrape")
async def v1_scrape(body: dict[str, Any]):
    url = body.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url' in request body")

    delay_ms = body.get("delay", 2500)
    session_context = body.get("sessionContext")

    try:
        result = await scrape_url(url, delay_ms, session_context)
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Playwright-based scrape server replacing Steel Browser.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=3000, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print(f"Starting scrape server on http://{args.host}:{args.port}")
    print("Endpoints:")
    print("  POST /v1/scrape                     - Scrape a URL")
    uvicorn.run(
        "scrape_server:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
