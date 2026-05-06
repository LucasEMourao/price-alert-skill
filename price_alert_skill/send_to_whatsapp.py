#!/usr/bin/env python3

"""Send deal messages to WhatsApp groups via WhatsApp Web automation.

Uses Playwright to automate WhatsApp Web. Sends product images with
formatted deal messages as captions.

Usage:
    python3 send_to_whatsapp.py --deals deals.json
    python3 send_to_whatsapp.py --deals deals.json --headed
    python3 send_to_whatsapp.py --message "Test message" --image-url "https://..." --group "Grupo de Teste"

Session is persisted in data/whatsapp_session/ so you only need to scan
the QR code once. Use --headed on first run to scan the QR code.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from price_alert_skill.config import (
    configure_utf8_stdio,
    resolve_whatsapp_chrome_path,
    resolve_whatsapp_group,
    resolve_whatsapp_profile_dir,
)
from price_alert_skill.paths import resolve_data_dir

DATA_DIR = resolve_data_dir()
SESSION_DIR = DATA_DIR / "whatsapp_session"
DEBUG_DIR = DATA_DIR / "debug"

_WHATSAPP_URL = "https://web.whatsapp.com"

_GROUP_ITEM_SELECTOR = '[role="gridcell"]'
_GROUP_RESULT_TITLE_SELECTORS = [
    '#pane-side [data-testid="cell-frame-title"] span[title]',
    '#pane-side span[title]',
]
_GROUP_RESULT_CONTAINER_SELECTORS = [
    '#pane-side [data-testid="cell-frame-container"]',
    '#pane-side [data-testid^="chatlist-message-"]',
]
_ATTACH_BUTTON_SELECTORS = [
    'button[aria-label="Anexar"]',
    'button[title="Anexar"]',
    'button[aria-label="Attach"]',
    'button[title="Attach"]',
    '[data-testid="attach-menu-plus"]',
    'span[data-icon="plus-rounded"]',
]
_PHOTO_VIDEO_SELECTORS = [
    'button[aria-label="Fotos e vídeos"]',
    'button[title="Fotos e vídeos"]',
    'button[aria-label="Photos & videos"]',
    'button[title="Photos & videos"]',
    '[data-testid="attach-image"]',
]
_FILE_INPUT_SELECTORS = [
    'input[type="file"][accept*="image"]',
    'input[type="file"]',
]
_CAPTION_SELECTORS = [
    'div[contenteditable="true"][data-lexical-editor="true"]',
    'div[contenteditable="true"][role="textbox"]',
    'div[contenteditable="true"]',
]
_SEND_BUTTON_SELECTORS = [
    'button[aria-label="Enviar"]',
    'button[title="Enviar"]',
    'button[aria-label="Send"]',
    'button[title="Send"]',
    'button[data-testid="compose-btn-send"]',
    'span[data-icon="send"]',
]
_COMPOSER_READY_SELECTORS = [
    'footer div[contenteditable="true"][role="textbox"]',
    '#main footer [contenteditable="true"]',
    '#main footer button',
]
_CHAT_HEADER_TITLE_SELECTORS = [
    '#main header [data-testid="conversation-info-header-chat-title"] span[title]',
    '#main header span[title]',
    '#main header [title]',
]
_QR_CODE_SELECTORS = [
    'canvas[aria-label*="Scan"]',
    'canvas[aria-label*="QR"]',
    'img[alt*="QR"]',
    '[data-testid="qrcode"] canvas',
]
_MAIN_PANEL_SELECTOR = '#pane-side'
_LOGGED_IN_SELECTORS = [
    _MAIN_PANEL_SELECTOR,
    "#side",
    '[data-testid="chat-list-search"]',
]
_LOADING_CHATS_TEXT_MARKERS = (
    "carregando suas conversas",
    "loading your chats",
)
_UNSUPPORTED_BROWSER_TEXT_MARKERS = (
    "whatsapp works with google chrome",
    "update google chrome",
    "navegador incompat?vel",
    "navegador nao suportado",
    "navegador n?o suportado",
)
_DEFAULT_HEADLESS_CHROME_VERSION = "120.0.0.0"
_GROUP_SEARCH_SELECTORS = [
    'input[aria-label="Search or start a new chat"]',
    'input[aria-label="Pesquisar ou começar uma nova conversa"]',
    'div[role="textbox"][contenteditable="true"]',
]
_LOGOUT_URL_MARKERS = ("post_logout", "logout_reason")
_GROUP_SEARCH_SELECTORS.extend(
    [
        'input[aria-label="Pesquisar ou começar uma nova conversa"]',
        'div[aria-label="Pesquisar ou começar uma nova conversa"]',
    ]
)


def _resolve_user_data_dir() -> str:
    """Resolve the active WhatsApp browser profile for this process."""
    return resolve_whatsapp_profile_dir()


def _clear_stale_profile_lock_files(user_data_dir: str | None = None) -> None:
    profile_dir = Path(user_data_dir or _resolve_user_data_dir())
    for pattern in ("Singleton*", "DevToolsActivePort"):
        for lock_file in profile_dir.glob(pattern):
            try:
                lock_file.unlink()
                print(f"  Removed stale profile file: {lock_file.name}")
            except OSError:
                pass


def _download_image(url: str, timeout: int = 30) -> str | None:
    """Download image to a temp file and return the path."""
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()

        parsed = urlparse(url)
        ext = Path(parsed.path).suffix or ".jpg"
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            ext = ".jpg"

        with tempfile.NamedTemporaryFile(
            suffix=ext, delete=False, prefix="whatsapp_deal_"
        ) as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
            return f.name
    except Exception as exc:
        print(f"  WARNING: Failed to download image: {exc}")
        return None


def _reset_whatsapp_session(user_data_dir: str | None = None) -> None:
    """Remove the persisted WhatsApp Web browser profile."""
    session_path = Path(user_data_dir or _resolve_user_data_dir())
    if not session_path.exists():
        return

    print(f"  Resetting WhatsApp session at: {session_path}")
    shutil.rmtree(session_path, ignore_errors=True)


def _capture_whatsapp_debug_artifacts(page, prefix: str = "whatsapp_auth") -> None:
    """Persist a screenshot and HTML snapshot to help debug auth issues."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    screenshot_path = DEBUG_DIR / f"{prefix}_{timestamp}.png"
    html_path = DEBUG_DIR / f"{prefix}_{timestamp}.html"
    meta_path = DEBUG_DIR / f"{prefix}_{timestamp}.txt"

    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"  Saved WhatsApp debug screenshot to: {screenshot_path}")
    except Exception as exc:
        print(f"  WARNING: Failed to save WhatsApp screenshot: {exc}")

    try:
        html_path.write_text(page.content(), encoding="utf-8")
        print(f"  Saved WhatsApp debug HTML to: {html_path}")
    except Exception as exc:
        print(f"  WARNING: Failed to save WhatsApp HTML snapshot: {exc}")

    try:
        meta_path.write_text(
            f"url={page.url}\nstate={_get_whatsapp_state(page)}\n",
            encoding="utf-8",
        )
        print(f"  Saved WhatsApp debug metadata to: {meta_path}")
    except Exception as exc:
        print(f"  WARNING: Failed to save WhatsApp metadata: {exc}")


def _wait_for_whatsapp_load(page, timeout_ms: int = 60000) -> bool:
    """Wait for WhatsApp Web to load. Returns True if logged in, False if QR code shown."""
    try:
        page.wait_for_selector('#side', timeout=timeout_ms)
        return True
    except Exception:
        return False


def _page_has_any_visible_selector(page, selectors: list[str]) -> bool:
    """Return True when at least one selector is visible on the page."""
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator and locator.is_visible():
                return True
        except Exception:
            continue
    return False


def _page_contains_any_text(page, markers: tuple[str, ...]) -> bool:
    """Return True when the page body contains one of the given text markers."""
    try:
        body_text = page.locator("body").inner_text(timeout=1000)
    except Exception:
        return False

    if not isinstance(body_text, str):
        return False

    normalized = body_text.lower()
    return any(marker in normalized for marker in markers)


def _normalize_text(value: str | None) -> str:
    """Normalize UI text before comparing labels or titles."""
    return " ".join((value or "").split()).strip().lower()


def _chat_matches_group(page, group_name: str) -> bool:
    """Return True when the currently opened chat header matches the target group."""
    expected = _normalize_text(group_name)
    for selector in _CHAT_HEADER_TITLE_SELECTORS:
        try:
            locator = page.locator(selector).first
            if not locator or not locator.is_visible():
                continue

            title = None
            try:
                title = locator.get_attribute("title")
            except Exception:
                title = None

            if not title:
                try:
                    title = locator.text_content()
                except Exception:
                    title = None

            if _normalize_text(title) == expected:
                return True
        except Exception:
            continue
    return False


def _wait_for_group_chat_open(page, group_name: str, timeout_ms: int = 15000) -> bool:
    """Wait until the target chat is actually opened in the right-side panel."""
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        composer_ready = _page_has_any_visible_selector(
            page, _COMPOSER_READY_SELECTORS + _ATTACH_BUTTON_SELECTORS
        )
        if composer_ready and (_chat_matches_group(page, group_name) or composer_ready):
            return True
        time.sleep(0.5)
    return False


def _click_group_candidate(candidate) -> None:
    """Click a search result, preferring the container that owns the row."""
    try:
        candidate.evaluate(
            """
            (el) => {
              const container =
                el.closest('[data-testid="cell-frame-container"]') ||
                el.closest('[data-testid^="chatlist-message-"]') ||
                el.closest('[role="gridcell"]') ||
                el;
              container.click();
            }
            """
        )
        return
    except Exception:
        pass

    candidate.click()


def _try_open_group_from_exact_titles(page, group_name: str) -> bool:
    """Try to open the group by clicking an exact title match in the search results."""
    expected = _normalize_text(group_name)
    for selector in _GROUP_RESULT_CONTAINER_SELECTORS:
        try:
            candidates = page.query_selector_all(selector)
        except Exception:
            candidates = []

        for candidate in candidates:
            title = ""
            try:
                title_el = candidate.query_selector('[data-testid="cell-frame-title"] span[title]')
            except Exception:
                title_el = None

            if title_el:
                try:
                    title = title_el.get_attribute("title") or title_el.text_content() or ""
                except Exception:
                    title = ""
            else:
                try:
                    title = candidate.get_attribute("title") or candidate.text_content() or ""
                except Exception:
                    title = ""

            if _normalize_text(title) != expected:
                continue

            try:
                _click_group_candidate(candidate)
                time.sleep(0.8)
                if _wait_for_group_chat_open(page, group_name, timeout_ms=5000):
                    return True
            except Exception:
                continue

    for selector in _GROUP_RESULT_TITLE_SELECTORS:
        try:
            candidates = page.query_selector_all(selector)
        except Exception:
            candidates = []

        for candidate in candidates:
            try:
                title = candidate.get_attribute("title") or candidate.text_content() or ""
            except Exception:
                title = ""

            if _normalize_text(title) != expected:
                continue

            try:
                _click_group_candidate(candidate)
                time.sleep(0.8)
                if _wait_for_group_chat_open(page, group_name, timeout_ms=5000):
                    return True
            except Exception:
                continue
    return False


def _get_whatsapp_state(page) -> str:
    """Classify the current WhatsApp Web state."""
    try:
        current_url = (page.url or "").lower()
    except Exception:
        current_url = ""

    if any(marker in current_url for marker in _LOGOUT_URL_MARKERS):
        return "logged_out"

    if _page_has_any_visible_selector(page, _LOGGED_IN_SELECTORS):
        return "logged_in"

    if _page_has_any_visible_selector(page, _QR_CODE_SELECTORS):
        return "qr"

    if _page_contains_any_text(page, _UNSUPPORTED_BROWSER_TEXT_MARKERS):
        return "unsupported_browser"

    if _page_contains_any_text(page, _LOADING_CHATS_TEXT_MARKERS):
        return "loading_chats"

    return "loading"


def _is_logged_in(page) -> bool:
    """Check if WhatsApp Web is logged in (no QR code visible)."""
    return _get_whatsapp_state(page) == "logged_in"


def _detect_chrome_version(executable_path: str | None) -> str:
    """Return the full Chrome/Chromium version for UA normalization."""
    if not isinstance(executable_path, str) or not executable_path:
        return ""

    try:
        result = subprocess.run(
            [executable_path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return ""

    output = f"{result.stdout} {result.stderr}"
    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
    return match.group(1) if match else ""


def _chrome_major_version(chrome_version: str | None) -> str:
    version = chrome_version or _DEFAULT_HEADLESS_CHROME_VERSION
    return version.split(".", 1)[0]


def _chrome_ua_version(chrome_version: str | None) -> str:
    return f"{_chrome_major_version(chrome_version)}.0.0.0"


def _build_headless_chrome_user_agent(chrome_version: str | None) -> str:
    ua_version = _chrome_ua_version(chrome_version)
    return (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{ua_version} Safari/537.36"
    )


def _build_headless_chrome_client_hints(chrome_version: str | None) -> dict[str, str]:
    major_version = _chrome_major_version(chrome_version)
    return {
        "sec-ch-ua": f'"Chromium";v="{major_version}", "Not.A/Brand";v="8"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
    }


def _resolve_headless_user_agent(
    headed: bool,
    chrome_version: str | None = None,
) -> str | None:
    """Return a regular Chrome UA for headless runs so WhatsApp does not reject it."""
    explicit_user_agent = os.environ.get("WHATSAPP_USER_AGENT", "").strip()
    if explicit_user_agent:
        return explicit_user_agent
    if headed:
        return None
    return _build_headless_chrome_user_agent(chrome_version)


def _find_group_search_box(page, timeout_ms: int = 15000):
    """Find the WhatsApp group search input across UI locales/variants."""
    _, locator = _wait_for_any_selector(
        page,
        _GROUP_SEARCH_SELECTORS,
        timeout_ms=timeout_ms,
        error_message="Could not find the WhatsApp search input.",
    )
    return locator


def _wait_for_any_selector(
    page,
    selectors: list[str],
    timeout_ms: int = 15000,
    error_message: str = "Could not find any matching selector.",
):
    """Wait until one of the selectors appears and return (selector, element)."""
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        for selector in selectors:
            try:
                locator = page.wait_for_selector(selector, timeout=1000)
                if locator:
                    return selector, locator
            except Exception:
                continue
    raise TimeoutError(error_message)


def _ensure_logged_in(page, headed: bool = False, timeout_ms: int = 300000) -> None:
    """Ensure we are logged in to WhatsApp Web. If not, wait for QR scan."""
    print("  Waiting for WhatsApp to load...")

    try:
        page.wait_for_load_state("domcontentloaded", timeout=30000)
    except Exception:
        pass

    state = _get_whatsapp_state(page)
    if state == "logged_in":
        print("  Session found, already logged in.")
        return

    print(f"  WhatsApp state detected: {state}")
    try:
        print(f"  WhatsApp URL: {page.url}")
    except Exception:
        pass

    if not headed:
        try:
            timeout_seconds = float(
                os.environ.get("WHATSAPP_HEADLESS_TIMEOUT_SECONDS", timeout_ms / 1000)
            )
        except ValueError:
            timeout_seconds = timeout_ms / 1000
        debug_after_seconds = min(60, max(10, timeout_seconds / 3))
        reload_after_seconds = min(120, max(30, timeout_seconds / 2))
        print(
            "  Running without --headed. Waiting up to %ss for the existing session "
            "and chats to finish loading..." % int(timeout_seconds)
        )
        start = time.time()
        deadline = start + timeout_seconds
        last_state = None
        debug_captured = False
        reload_attempted = False

        while time.time() < deadline:
            elapsed = time.time() - start
            state = _get_whatsapp_state(page)
            if state != last_state:
                print(f"  WhatsApp auth state: {state}")
                try:
                    print(f"  WhatsApp auth URL: {page.url}")
                except Exception:
                    pass
                last_state = state

            if state == "logged_in":
                print("  Session found, already logged in.")
                return

            if state in {"logged_out", "qr"}:
                raise RuntimeError(
                    "Not logged in. Run with --headed to scan QR code first. "
                    "Session will be saved for future runs."
                )

            if state == "unsupported_browser":
                _capture_whatsapp_debug_artifacts(page, prefix="whatsapp_headless_unsupported")
                raise RuntimeError(
                    "WhatsApp rejected the headless browser as unsupported. "
                    "The adapter will use a regular Chrome user-agent in headless mode; "
                    "set WHATSAPP_USER_AGENT if WhatsApp changes this check again."
                )

            if elapsed >= debug_after_seconds and not debug_captured:
                print("  WhatsApp is still loading chats in headless mode; saving debug artifacts...")
                _capture_whatsapp_debug_artifacts(page, prefix="whatsapp_headless_loading")
                debug_captured = True

            if elapsed >= reload_after_seconds and not reload_attempted:
                print(
                    "  WhatsApp is still loading in headless mode after %ss. "
                    "Trying a single refresh..." % int(elapsed)
                )
                try:
                    page.reload(wait_until="domcontentloaded", timeout=60000)
                except Exception as exc:
                    print(f"  WARNING: Headless refresh failed: {exc}")
                reload_attempted = True
                time.sleep(2)
                continue

            time.sleep(2)

        _capture_whatsapp_debug_artifacts(page, prefix="whatsapp_headless_timeout")
        raise RuntimeError(
            "WhatsApp session is authenticated, but chats did not finish loading "
            "in headless mode before the timeout. Check the saved debug artifacts "
            "or run once with --headed to refresh the session if needed."
        )

    print("  Waiting up to %ss for authentication..." % (timeout_ms // 1000))
    qr_prompt_shown = False
    last_state = None
    login_reload_attempted = False
    early_debug_captured = False
    start = time.time()

    while time.time() - start < timeout_ms / 1000:
        state = _get_whatsapp_state(page)
        elapsed = time.time() - start

        if state != last_state:
            print(f"  WhatsApp auth state: {state}")
            try:
                print(f"  WhatsApp auth URL: {page.url}")
            except Exception:
                pass
            last_state = state

        if state == "logged_in":
            print("  Logged in successfully!")
            return

        if state == "logged_out":
            if not qr_prompt_shown:
                print("  WhatsApp is still preparing the login screen. Waiting for the QR to finish loading...")

            if elapsed >= 45 and not early_debug_captured:
                _capture_whatsapp_debug_artifacts(page, prefix="whatsapp_auth_stuck")
                early_debug_captured = True

            if elapsed >= 90 and not login_reload_attempted:
                print("  Login screen is still stuck after 90s. Trying a single refresh...")
                page.reload(wait_until="domcontentloaded", timeout=60000)
                login_reload_attempted = True
                time.sleep(2)
                continue

        if state == "qr" and not qr_prompt_shown:
            print("  QR code detected. Please scan with your phone...")
            qr_prompt_shown = True
        elif qr_prompt_shown and state == "loading":
            print("  QR scan detected, waiting for WhatsApp to finish loading...")
            qr_prompt_shown = False
        elif state == "loading" and elapsed >= 45 and not early_debug_captured:
            print("  WhatsApp login screen is still loading after 45s; saving debug artifacts...")
            _capture_whatsapp_debug_artifacts(page, prefix="whatsapp_auth_loading")
            early_debug_captured = True

        time.sleep(2)

    _capture_whatsapp_debug_artifacts(page, prefix="whatsapp_auth_timeout")

    raise TimeoutError(
        "WhatsApp authentication timed out. If you scanned the QR code, "
        "keep the browser open a bit longer and try again with --headed."
    )


def _search_and_open_group(page, group_name: str, timeout_ms: int = 15000) -> None:
    """Search for and open a WhatsApp group by name."""
    print(f"  Searching for group: {group_name}")

    try:
        search_box = _find_group_search_box(page, timeout_ms=timeout_ms)
        search_box.click()
        time.sleep(0.5)
        try:
            search_box.press("Control+A")
            search_box.press("Backspace")
        except Exception:
            pass
        search_box.fill(group_name)
        time.sleep(2)

        page.wait_for_selector('#side', timeout=timeout_ms)

        if _try_open_group_from_exact_titles(page, group_name):
            print(f"  Opened group: {group_name}")
            return

        try:
            search_box.press("Enter")
            time.sleep(0.8)
            if _wait_for_group_chat_open(page, group_name, timeout_ms=5000):
                print(f"  Opened group: {group_name}")
                return
        except Exception:
            pass

        found_match = False
        group_items = page.query_selector_all(_GROUP_ITEM_SELECTOR)
        for item in group_items:
            text = item.text_content() or ""
            if group_name.lower() in text.lower():
                found_match = True
                _click_group_candidate(item)
                time.sleep(1.2)
                if _wait_for_group_chat_open(page, group_name, timeout_ms=5000):
                    print(f"  Opened group: {group_name}")
                    return

        if found_match:
            raise RuntimeError(
                f"Group '{group_name}' appeared in search results but the chat panel did not open."
            )
        raise RuntimeError(f"Group '{group_name}' not found in search results.")
    except Exception as exc:
        raise RuntimeError(f"Failed to find group '{group_name}': {exc}")


def _send_image_with_caption(
    page,
    image_path: str,
    caption: str,
    delay_between: float = 2.0,
) -> bool:
    """Send an image with a caption to the currently open chat."""
    try:
        # Wait for the composer to settle after opening the chat.
        _wait_for_any_selector(
            page,
            _COMPOSER_READY_SELECTORS + _ATTACH_BUTTON_SELECTORS,
            timeout_ms=15000,
            error_message="WhatsApp composer did not become ready.",
        )

        # Click the attach button with pt-BR selectors first, then fall back.
        attach_selector, _ = _wait_for_any_selector(
            page,
            _ATTACH_BUTTON_SELECTORS,
            timeout_ms=10000,
            error_message="Could not find the WhatsApp attach button.",
        )
        page.click(attach_selector)
        time.sleep(1)

        # Prefer the explicit photos/videos action; fall back to a direct file input.
        media_selector = None
        try:
            media_selector, _ = _wait_for_any_selector(
                page,
                _PHOTO_VIDEO_SELECTORS,
                timeout_ms=5000,
                error_message="Could not find the WhatsApp photos/videos action.",
            )
        except Exception:
            media_selector = None

        if media_selector:
            with page.expect_file_chooser() as fc_info:
                page.click(media_selector)
            file_chooser = fc_info.value
            file_chooser.set_files(image_path)
        else:
            _, file_input = _wait_for_any_selector(
                page,
                _FILE_INPUT_SELECTORS,
                timeout_ms=5000,
                error_message="Could not find a WhatsApp file input.",
            )
            file_input.set_input_files(image_path)
        
        # Wait for image preview to appear
        time.sleep(3)
        print(f"  Image loaded, adding caption...")

        # Find and fill the caption field.
        caption_el = None
        try:
            _, caption_el = _wait_for_any_selector(
                page,
                _CAPTION_SELECTORS,
                timeout_ms=9000,
                error_message="Could not find the WhatsApp caption field.",
            )
        except Exception:
            caption_el = None

        if caption_el:
            caption_el.click()
            time.sleep(0.3)
            caption_el.fill(caption)
            time.sleep(0.5)
        else:
            print(f"  WARNING: Could not find caption field, sending without caption")

        # Click the send button, preferring pt-BR labels first.
        sent = False
        for selector in _SEND_BUTTON_SELECTORS:
            try:
                send_btn = page.wait_for_selector(selector, timeout=3000)
                if send_btn:
                    send_btn.click()
                    sent = True
                    break
            except Exception:
                continue
        
        if not sent:
            print(f"  WARNING: Could not find send button, trying keyboard Enter")
            page.keyboard.press("Enter")
        
        time.sleep(delay_between)

        print(f"  Sent: {caption[:60]}...")
        return True

    except Exception as exc:
        print(f"  ERROR: Failed to send image: {exc}")
        _capture_whatsapp_debug_artifacts(page, prefix="whatsapp_send_failure")
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass
        return False


def open_whatsapp_session(
    *,
    group_name: str,
    headed: bool = False,
    reset_session: bool = False,
):
    """Open a persistent WhatsApp Web session and land on the target group."""
    from playwright.sync_api import sync_playwright

    configure_utf8_stdio()
    playwright = None
    context = None

    try:
        playwright = sync_playwright().start()
        user_data_dir = _resolve_user_data_dir()

        if reset_session:
            _reset_whatsapp_session(user_data_dir)

        _clear_stale_profile_lock_files(user_data_dir)

        chrome_path = resolve_whatsapp_chrome_path()
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
        launch_kwargs = {
            "user_data_dir": user_data_dir,
            "headless": not headed,
            "viewport": {"width": 1280, "height": 720},
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo",
            "ignore_default_args": ["--enable-automation"],
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-infobars",
            ],
        }
        browser_executable = chrome_path or getattr(playwright.chromium, "executable_path", "")
        chrome_version = _detect_chrome_version(browser_executable)
        user_agent = _resolve_headless_user_agent(headed, chrome_version)
        if user_agent:
            launch_kwargs["user_agent"] = user_agent
            launch_kwargs["extra_http_headers"] = _build_headless_chrome_client_hints(
                chrome_version
            )
            launch_kwargs["args"].append(f"--user-agent={user_agent}")
        if chrome_path:
            print(f"Using Chrome executable for WhatsApp Web: {chrome_path}")
            launch_kwargs["executable_path"] = chrome_path
        else:
            print("Using Playwright Chromium for WhatsApp Web.")
        print(f"Using WhatsApp Chrome profile dir: {user_data_dir}")

        try:
            context = playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as first_exc:
            print(f"  WARNING: Failed to launch WhatsApp persistent context: {first_exc}")
            print("  Retrying once after clearing stale profile files...")
            _clear_stale_profile_lock_files(user_data_dir)
            time.sleep(2)
            context = playwright.chromium.launch_persistent_context(**launch_kwargs)
        init_script = """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined,
            });
            window.chrome = window.chrome || { runtime: {} };
            Object.defineProperty(navigator, 'languages', {
              get: () => ['pt-BR', 'pt', 'en-US', 'en'],
            });
            Object.defineProperty(navigator, 'plugins', {
              get: () => [1, 2, 3, 4, 5],
            });
            """
        if user_agent:
            chrome_major_version = _chrome_major_version(chrome_version)
            chrome_ua_version = _chrome_ua_version(chrome_version)
            init_script += f"""
            Object.defineProperty(navigator, 'userAgent', {{
              get: () => {json.dumps(user_agent)},
            }});
            if (navigator.userAgentData) {{
              Object.defineProperty(navigator, 'userAgentData', {{
                get: () => ({{
                  brands: [
                    {{brand: 'Chromium', version: {json.dumps(chrome_major_version)}}},
                    {{brand: 'Not.A/Brand', version: '8'}},
                  ],
                  mobile: false,
                  platform: 'Linux',
                  getHighEntropyValues: async () => ({{
                    architecture: 'x86',
                    bitness: '64',
                    brands: [
                      {{brand: 'Chromium', version: {json.dumps(chrome_major_version)}}},
                      {{brand: 'Not.A/Brand', version: '8'}},
                    ],
                    fullVersionList: [
                      {{brand: 'Chromium', version: {json.dumps(chrome_ua_version)}}},
                      {{brand: 'Not.A/Brand', version: '8.0.0.0'}},
                    ],
                    mobile: false,
                    model: '',
                    platform: 'Linux',
                    platformVersion: '6.0.0',
                    uaFullVersion: {json.dumps(chrome_ua_version)},
                  }}),
                  toJSON: () => ({{
                    brands: [
                      {{brand: 'Chromium', version: {json.dumps(chrome_major_version)}}},
                      {{brand: 'Not.A/Brand', version: '8'}},
                    ],
                    mobile: false,
                    platform: 'Linux',
                  }}),
                }}),
              }});
            }}
            """
        context.add_init_script(init_script)

        page = context.new_page()

        print("Opening WhatsApp Web...")
        page.goto(_WHATSAPP_URL, wait_until="domcontentloaded", timeout=60000)

        _ensure_logged_in(page, headed=headed)

        print("  Waiting for app to fully load (this may take 30-60s)...")
        try:
            _find_group_search_box(page, timeout_ms=60000)
            print("  App loaded successfully!")
        except Exception:
            print("  WARNING: Search input did not appear, trying to continue anyway...")
            time.sleep(15)

        _search_and_open_group(page, group_name)
        return {"playwright": playwright, "context": context, "page": page}
    except Exception:
        close_whatsapp_session({"playwright": playwright, "context": context})
        raise


def close_whatsapp_session(session: dict[str, Any] | None) -> None:
    """Close a session opened with open_whatsapp_session safely."""
    if not session:
        return

    context = session.get("context")
    playwright = session.get("playwright")

    try:
        if context:
            try:
                context.close()
            except Exception as exc:
                print(f"  WARNING: Ignoring WhatsApp context shutdown error: {exc}")
    finally:
        if playwright:
            try:
                playwright.stop()
            except Exception as exc:
                print(f"  WARNING: Ignoring Playwright shutdown error: {exc}")


def send_deal_in_open_chat(
    page,
    deal: dict[str, Any],
    *,
    delay_between: float = 5.0,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Send one deal using an already-open WhatsApp group page."""
    title = deal.get("title", "Unknown")
    deal_url = deal.get("url", "")
    dedup_key = deal.get("dedup_key") or deal_url
    image_url = deal.get("image_url")
    message = deal.get("message", "")

    if not image_url:
        return {
            "success": False,
            "dedup_key": dedup_key,
            "title": title,
            "url": deal_url,
            "reason": "no image_url",
        }

    image_path = _download_image(image_url)
    if not image_path:
        return {
            "success": False,
            "dedup_key": dedup_key,
            "title": title,
            "url": deal_url,
            "reason": "download failed",
        }

    try:
        success = False
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"  Retry {attempt}/{max_retries}...")
                time.sleep(2)

            success = _send_image_with_caption(page, image_path, message, delay_between)
            if success:
                break

        if success:
            return {
                "success": True,
                "dedup_key": dedup_key,
                "title": title,
                "url": deal_url,
            }

        return {
            "success": False,
            "dedup_key": dedup_key,
            "title": title,
            "url": deal_url,
            "reason": "send failed",
        }
    finally:
        try:
            Path(image_path).unlink()
        except Exception:
            pass


def send_deals_to_whatsapp(
    deals: list[dict[str, Any]],
    group_name: str,
    headed: bool = False,
    delay_between: float = 5.0,
    max_retries: int = 2,
    reset_session: bool = False,
) -> dict[str, Any]:
    """Send deal messages to a WhatsApp group.

    Args:
        deals: List of deal dicts with 'title', 'url', 'image_url', 'message'.
        group_name: Name of the WhatsApp group to send to.
        headed: Open browser window (needed for first-time QR scan).
        delay_between: Seconds to wait between messages.
        max_retries: Number of retries per failed message.
        reset_session: Remove the persisted browser profile before opening WhatsApp.

    Returns:
        Dict with 'sent', 'failed', 'errors', and 'successful_keys'.
    """
    results = {"sent": 0, "failed": 0, "errors": [], "successful_keys": []}
    session = open_whatsapp_session(
        group_name=group_name,
        headed=headed,
        reset_session=reset_session,
    )
    page = session["page"]
    try:
        for i, deal in enumerate(deals):
            title = deal.get("title", "Unknown")
            print(f"\n[{i + 1}/{len(deals)}] Sending: {title[:50]}...")
            attempt_result = send_deal_in_open_chat(
                page,
                deal,
                delay_between=delay_between,
                max_retries=max_retries,
            )
            if attempt_result["success"]:
                results["sent"] += 1
                results["successful_keys"].append(attempt_result["dedup_key"])
            else:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "title": attempt_result["title"],
                        "url": attempt_result["url"],
                        "reason": attempt_result["reason"],
                    }
                )

        # Wait before closing to ensure messages are fully sent
        print("\n  Waiting for messages to sync...")
        time.sleep(5)
    finally:
        close_whatsapp_session(session)

    return results


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Send deal messages to WhatsApp groups via WhatsApp Web."
    )
    parser.add_argument(
        "--group",
        default="",
        help="Name of the WhatsApp group to send to (defaults to WHATSAPP_GROUP from .env)",
    )
    parser.add_argument(
        "--deals", help="Path to deals JSON file (from scan_deals.py output)"
    )
    parser.add_argument(
        "--message", help="Single message to send (use with --image-url)"
    )
    parser.add_argument(
        "--image-url", help="Image URL to send (use with --message)"
    )
    parser.add_argument(
        "--headed", action="store_true",
        help="Open browser window (needed for first-time QR scan)"
    )
    parser.add_argument(
        "--delay", type=float, default=3.0,
        help="Seconds to wait between messages (default: 3)"
    )
    parser.add_argument(
        "--max-retries", type=int, default=2,
        help="Max retries per failed message (default: 2)"
    )
    parser.add_argument(
        "--reset-session",
        action="store_true",
        help="Delete the persisted WhatsApp Web session before opening the browser",
    )
    args = parser.parse_args()
    group_name = resolve_whatsapp_group(args.group)
    if not group_name:
        parser.error("Provide --group or set WHATSAPP_GROUP in .env")

    deals = []

    if args.deals:
        deals_path = Path(args.deals)
        if not deals_path.exists():
            print(f"Error: File not found: {deals_path}")
            return
        data = json.loads(deals_path.read_text(encoding="utf-8"))
        deals = data.get("messages", data.get("deals", []))
        if not deals:
            print("No deals found in the file.")
            return
        print(f"Loaded {len(deals)} deals from {deals_path.name}")

    elif args.message and args.image_url:
        deals = [{
            "title": "Custom deal",
            "url": "",
            "image_url": args.image_url,
            "message": args.message,
        }]

    else:
        parser.error("Provide either --deals or both --message and --image-url")

    print(f"\nSending {len(deals)} deal(s) to group: {group_name}\n")

    results = send_deals_to_whatsapp(
        deals=deals,
        group_name=group_name,
        headed=args.headed,
        delay_between=args.delay,
        max_retries=args.max_retries,
        reset_session=args.reset_session,
    )

    print(f"\n{'=' * 40}")
    print(f"Results: {results['sent']} sent, {results['failed']} failed")
    if results["errors"]:
        print("Errors:")
        for err in results["errors"]:
            print(f"  - {err['title']}: {err['reason']}")
    print(f"{'=' * 40}")


if __name__ == "__main__":
    main()
