#!/usr/bin/env python3

"""Local Playwright-based scraping server that replaces Steel Browser.

Exposes the same API surface the fetchers expect:
  POST /v1/scrape                    {"url": "...", "delay": N}
  POST /v1/sessions                  {}
  GET  /v1/sessions/{id}/context
  POST /v1/sessions/{id}/save        (saves cookies from a live interactive session)

Usage:
  pip install fastapi uvicorn playwright
  playwright install chromium
  python scripts/scrape_server.py --port 3000
"""

import argparse
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

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
sessions: dict[str, dict[str, Any]] = {}
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
SHOPEE_LOGIN_URL = "https://shopee.com.br/buyer/login"


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


def save_session_cookies(session_id: str, context: BrowserContext) -> str:
    """Save storage state (cookies + localStorage) to disk and return path."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{session_id}.json"
    state = context.storage_state()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    return str(path)


def load_session_cookies(session_id: str) -> dict[str, Any] | None:
    """Load storage state from disk."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
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

    # If sessionContext is a string (session_id), load from disk
    if isinstance(session_context, str):
        session_context = load_session_cookies(session_context)

    try:
        result = await scrape_url(url, delay_ms, session_context)
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/v1/sessions")
async def v1_create_session():
    """Create a new interactive session for login.

    Opens a browser with the Shopee login page. The user should:
    1. Connect via Chrome DevTools (see sessionViewerUrl in response)
    2. Log in to Shopee
    3. Call POST /v1/sessions/{id}/save to persist cookies
    """
    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "storage_state_path": None,
        "status": "ready",
    }

    return {
        "id": session_id,
        "sessionViewerUrl": f"http://localhost:9222",
        "debugUrl": f"http://localhost:9222",
        "instructions": (
            "Interactive login is not available in headless mode via this server. "
            "Use POST /v1/sessions/{id}/login to open Shopee login and capture cookies via script, "
            "or POST /v1/sessions/{id}/save with explicit cookies."
        ),
    }


@app.get("/v1/sessions/{session_id}/context")
async def v1_get_session_context(session_id: str):
    """Return stored cookies for a session."""
    state = load_session_cookies(session_id)
    if state is None:
        session = sessions.get(session_id)
        if session:
            return session.get("storage_state") or {}
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return state


@app.post("/v1/sessions/{session_id}/save")
async def v1_save_session(session_id: str, body: dict[str, Any] | None = None):
    """Save cookies for a session. Can accept explicit cookies or use a headless scrape."""
    state = load_session_cookies(session_id)
    if state:
        return {"status": "already_saved", "session_id": session_id}

    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Accept cookies passed in the body
    if body and ("cookies" in body or "origins" in body):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{session_id}.json"
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2))
        sessions[session_id]["storage_state_path"] = str(path)
        sessions[session_id]["status"] = "saved"
        return {"status": "saved", "session_id": session_id, "path": str(path)}

    raise HTTPException(
        status_code=400,
        detail="Provide cookies in request body or use the login flow first"
    )


@app.post("/v1/sessions/{session_id}/login")
async def v1_login_session(session_id: str, body: dict[str, Any] | None = None):
    """Open Shopee login in a VISIBLE browser window for manual login.

    Opens Chromium with GUI so the user can manually log in to Shopee.
    The server polls for Shopee login cookies and saves them automatically.
    """
    if session_id not in sessions:
        sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "storage_state_path": None,
            "status": "created",
        }

    wait_seconds = (body or {}).get("wait_seconds", 180)
    login_url = (body or {}).get("url", SHOPEE_LOGIN_URL)

    # Launch a VISIBLE browser (not headless) for manual login
    pw = await async_playwright().start()
    visible_browser = await pw.chromium.launch(
        headless=False,
        channel="chromium",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ],
    )

    ua = random_user_agent()
    context = await visible_browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=ua,
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
    )
    await context.add_init_script(STEALTH_JS)
    page = await context.new_page()

    try:
        await page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
        print(f"[session {session_id}] Browser opened. Waiting for Shopee login (up to {wait_seconds}s)...")

        # Wait for Shopee login cookies to appear
        logged_in = False
        elapsed = 0
        poll_interval = 5

        while elapsed < wait_seconds:
            cookies = await context.cookies()
            cookie_names = {c["name"] for c in cookies}
            if "SPC_F" in cookie_names or "SPC_SC_UDAT" in cookie_names:
                # Navigate to search to verify we're truly logged in
                try:
                    await page.goto(
                        "https://shopee.com.br/search?keyword=teste",
                        wait_until="domcontentloaded",
                        timeout=15000,
                    )
                    await asyncio.sleep(2)
                    cookies = await context.cookies()
                    cookie_names = {c["name"] for c in cookies}
                except Exception:
                    pass

                if "SPC_F" in cookie_names or "SPC_SC_UDAT" in cookie_names:
                    logged_in = True
                    break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if logged_in:
            path = save_session_cookies(session_id, context)
            sessions[session_id]["storage_state_path"] = path
            sessions[session_id]["status"] = "logged_in"
            result = {
                "status": "success",
                "session_id": session_id,
                "message": "Login detected! Cookies saved.",
                "path": path,
            }
        else:
            path = save_session_cookies(session_id, context)
            sessions[session_id]["storage_state_path"] = path
            sessions[session_id]["status"] = "timeout"
            result = {
                "status": "timeout",
                "session_id": session_id,
                "message": f"Login not detected after {wait_seconds}s. Cookies may work partially.",
                "path": path,
            }

        return result
    finally:
        await context.close()
        await visible_browser.close()
        await pw.stop()


@app.get("/v1/sessions/{session_id}/check")
async def v1_check_session(session_id: str):
    """Check if a session has valid Shopee login cookies."""
    state = load_session_cookies(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    cookies = state.get("cookies", [])
    cookie_names = {c["name"] for c in cookies}
    has_shopee_login = "SPC_F" in cookie_names or "SPC_SC_UDAT" in cookie_names

    return {
        "session_id": session_id,
        "has_login_cookies": has_shopee_login,
        "cookie_names": sorted(cookie_names),
        "cookie_count": len(cookies),
    }


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
    print("  POST /v1/sessions                   - Create session")
    print("  GET  /v1/sessions/{id}/context       - Get session cookies")
    print("  POST /v1/sessions/{id}/login         - Open Shopee login & wait for auth")
    print("  POST /v1/sessions/{id}/save          - Save explicit cookies")
    print("  GET  /v1/sessions/{id}/check         - Check login status")
    uvicorn.run(
        "scrape_server:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
