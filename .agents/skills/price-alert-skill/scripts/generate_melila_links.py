#!/usr/bin/env python3

"""Generate meli.la affiliate links via the ML affiliate panel using Playwright.

Uses Playwright (not agent-browser) for full control over session persistence.
Cookies and localStorage are saved to data/ml_session.json after manual login,
and restored on subsequent runs. Only requires re-login when the session expires.

Usage:
  python3 generate_melila_links.py --login                    # First time: manual login (stores session)
  python3 generate_melila_links.py "https://.../p/MLB123"     # Generate single link
  python3 generate_melila_links.py --urls url1 url2 url3       # Generate multiple links
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_FILE = DATA_DIR / "melila_cache.json"
SESSION_FILE = DATA_DIR / "ml_session.json"
LINK_BUILDER_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder"
AFFILIATE_HUB_URL = "https://www.mercadolivre.com.br/afiliados"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
delete navigator.__proto__.webdriver;
"""


def _get_browser(p: sync_playwright) -> Browser:
    return p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
    )


def _create_context(browser: Browser, *, storage_state: str | dict | None = None) -> BrowserContext:
    opts: dict[str, Any] = {
        "viewport": {"width": 1280, "height": 720},
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "java_script_enabled": True,
        "ignore_https_errors": True,
        "extra_http_headers": {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }
    if storage_state:
        opts["storage_state"] = storage_state
    ctx = browser.new_context(**opts)
    ctx.add_init_script(STEALTH_JS)
    return ctx


# --- Cache ---

def load_cache() -> dict[str, str]:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(cache: dict[str, str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


# --- Session ---

def _is_logged_in(page: Page) -> bool:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    content = page.content().lower()
    title = page.title().lower()
    if "iniciar sess" in content or "iniciar sess" in title:
        return False
    if "digite seu e-mail" in content:
        return False
    if "hubo un error" in content:
        return False
    return True


def login_interactive() -> bool:
    """Open a headed browser for manual login. Saves session to ml_session.json.

    IMPORTANT: Login with your real IP (no proxy) for session persistence.
    The session file is reused by generate_links() — only re-login when it expires.
    """
    print("[ml-affiliado] Opening headed browser for manual login...")
    print("[ml-affiliado] Login with your real IP (no proxy).")
    print("[ml-affiliado] Resolve CAPTCHA, 2FA, etc. in the browser window.")
    print("[ml-affiliado] After logging in, press Enter here to continue.")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = _create_context(browser)
        page = context.new_page()

        page.goto(AFFILIATE_HUB_URL, wait_until="domcontentloaded", timeout=30000)
        input()

        if not _is_logged_in(page):
            page.goto(LINK_BUILDER_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            if not _is_logged_in(page):
                print("[ml-affiliado] Login verification failed. Try again.")
                context.close()
                browser.close()
                return False

        print("[ml-affiliado] Login successful! Navigating to link builder...")
        page.goto(LINK_BUILDER_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        print("[ml-affiliado] Saving session...")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(SESSION_FILE))
        print(f"[ml-affiliado] Session saved to {SESSION_FILE}")

        context.close()
        browser.close()
    return True


def _find_url_input(page: Page) -> Any | None:
    """Find the URL input field in the link builder page.

    The link builder has 2 inputs: the search bar and the URL input.
    The URL input has a placeholder containing 'Insira' or 'URL' or starts with 'Ex:'.
    """
    for selector in [
        'input[placeholder*="nsira"]',
        'input[placeholder*="URL"]',
        'input[placeholder*="url"]',
        'textarea[placeholder*="nsira"]',
        'textarea[placeholder*="URL"]',
    ]:
        loc = page.locator(selector)
        if loc.count() > 0 and loc.first.is_visible():
            return loc.first
    # Fallback: look for input whose placeholder starts with 'Ex:'
    inputs = page.locator('input[type="text"], textarea')
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            ph = inp.get_attribute("placeholder") or ""
            if ph.startswith("Ex:") or "Insira" in ph or "insira" in ph:
                return inp
        except Exception:
            continue
    return None


def _click_gerar(page: Page) -> None:
    """Click the Gerar button, handling the disabled state."""
    gerar = page.locator('button:has-text("Gerar")')
    if gerar.is_enabled():
        gerar.click()
    else:
        gerar.click(force=True)


def _generate_single(page: Page, url: str) -> str | None:
    """Generate a single meli.la link on the link builder page."""
    page.goto(LINK_BUILDER_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    url_input = _find_url_input(page)
    if not url_input:
        return None

    try:
        url_input.click()
        url_input.fill(url)
    except Exception:
        return None

    page.wait_for_timeout(500)
    _click_gerar(page)
    page.wait_for_timeout(5000)

    content = page.content()
    matches = re.findall(r'https://meli\.la/[A-Za-z0-9]+', content)
    return matches[0] if matches else None


def generate_links(urls: list[str], delay_between: float = 3.0) -> dict[str, str]:
    """Generate meli.la links using stored session cookies."""
    cache = load_cache()
    results: dict[str, str] = {}
    to_generate: list[str] = []

    for url in urls:
        if not url:
            continue
        if url in cache:
            results[url] = cache[url]
        else:
            to_generate.append(url)

    if not to_generate:
        print(f"[ml-affiliado] All {len(results)} links from cache")
        return results

    print(f"[ml-affiliado] {len(results)} from cache, {len(to_generate)} to generate")

    if not SESSION_FILE.exists():
        print("[ml-affiliado] ERROR: No session file found. Run --login first.")
        for url in to_generate:
            results[url] = url
        return results

    with sync_playwright() as p:
        browser = _get_browser(p)
        context = _create_context(browser, storage_state=str(SESSION_FILE))
        page = context.new_page()

        # Check if still logged in
        page.goto(LINK_BUILDER_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        if not _is_logged_in(page):
            print("[ml-affiliado] ERROR: Session expired. Run --login again.")
            context.close()
            browser.close()
            for url in to_generate:
                results[url] = url
            return results

        print(f"[ml-affiliado] Session valid. Generating {len(to_generate)} links...")

        for i, url in enumerate(to_generate):
            print(f"[ml-affiliado] Generating {i+1}/{len(to_generate)}: {url[:80]}...")

            melila = _generate_single(page, url)
            if melila:
                results[url] = melila
                cache[url] = melila
                save_cache(cache)
                print(f"[ml-affiliado]   -> {melila}")
            else:
                results[url] = url
                print("[ml-affiliado]   -> FAILED, using original URL")

            if i < len(to_generate) - 1:
                page.wait_for_timeout(int(delay_between * 1000))

        # Save updated session
        context.storage_state(path=str(SESSION_FILE))
        context.close()
        browser.close()

    return results


# --- Main ---

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate meli.la affiliate links via ML affiliate panel using Playwright."
    )
    parser.add_argument("url", nargs="?", help="Single product URL to generate link for")
    parser.add_argument("--urls", nargs="+", help="Multiple product URLs")
    parser.add_argument("--batch", help="File with one URL per line")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between generations (seconds)")
    parser.add_argument("--login", action="store_true", help="Open headed browser for manual login (stores session)")
    parser.add_argument("--output", help="Output file for JSON results")
    args = parser.parse_args()

    if args.login:
        ok = login_interactive()
        sys.exit(0 if ok else 1)

    urls = []
    if args.url:
        urls.append(args.url)
    if args.urls:
        urls.extend(args.urls)
    if args.batch:
        batch_path = Path(args.batch)
        if batch_path.exists():
            urls.extend(line.strip() for line in batch_path.read_text().splitlines() if line.strip())
        else:
            print(f"ERROR: Batch file not found: {args.batch}")
            sys.exit(1)

    if not urls:
        parser.error("Provide at least one URL (positional, --urls, or --batch)")

    results = generate_links(urls, delay_between=args.delay)

    if args.output:
        Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"Results saved to: {args.output}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()