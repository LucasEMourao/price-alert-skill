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
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from config import resolve_whatsapp_group

ROOT = Path(__file__).resolve().parents[1]
SESSION_DIR = ROOT / "data" / "whatsapp_session"
USER_DATA_DIR = str(SESSION_DIR / "chrome_profile")
USER_DATA_DIR = str(SESSION_DIR / "chrome_profile")

_WHATSAPP_URL = "https://web.whatsapp.com"

_ATTACH_BUTTON_SELECTOR = 'button[aria-label="Attach"]'
_CAPTION_SELECTOR = 'div[contenteditable="true"][data-lexical-editor="true"]'
_SEND_BUTTON_SELECTOR = 'button[aria-label="Send"]'
_GROUP_SEARCH_SELECTOR = 'input[aria-label="Search or start a new chat"]'
_GROUP_ITEM_SELECTOR = '[role="gridcell"]'
_QR_CODE_SELECTOR = 'canvas[aria-label*="Scan"], img[alt*="QR"]'
_MAIN_PANEL_SELECTOR = '#pane-side'


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


def _wait_for_whatsapp_load(page, timeout_ms: int = 60000) -> bool:
    """Wait for WhatsApp Web to load. Returns True if logged in, False if QR code shown."""
    try:
        page.wait_for_selector('#side', timeout=timeout_ms)
        return True
    except Exception:
        return False


def _is_logged_in(page) -> bool:
    """Check if WhatsApp Web is logged in (no QR code visible)."""
    try:
        qr = page.query_selector(_QR_CODE_SELECTOR)
        return qr is None
    except Exception:
        return True


def _ensure_logged_in(page, headed: bool = False, timeout_ms: int = 120000) -> None:
    """Ensure we are logged in to WhatsApp Web. If not, wait for QR scan."""
    print("  Waiting for WhatsApp to load...")
    
    app_loaded = False
    try:
        page.wait_for_selector('#side', timeout=30000)
        app_loaded = True
    except Exception:
        pass
    
    if not app_loaded:
        print("  App did not load, checking for QR code...")
    
    if _is_logged_in(page):
        print("  Session found, already logged in.")
        return

    if headed:
        print("  QR code detected. Please scan with your phone...")
        print(f"  Waiting up to {timeout_ms // 1000}s for authentication...")
        start = time.time()
        while time.time() - start < timeout_ms / 1000:
            if _is_logged_in(page):
                print("  Logged in successfully!")
                return
            time.sleep(2)
        raise TimeoutError("QR code scan timed out. Try again with --headed.")
    else:
        raise RuntimeError(
            "Not logged in. Run with --headed to scan QR code first. "
            "Session will be saved for future runs."
        )


def _search_and_open_group(page, group_name: str, timeout_ms: int = 15000) -> None:
    """Search for and open a WhatsApp group by name."""
    print(f"  Searching for group: {group_name}")

    try:
        search_box = page.wait_for_selector(_GROUP_SEARCH_SELECTOR, timeout=5000)
        search_box.click()
        time.sleep(0.5)
        search_box.fill(group_name)
        time.sleep(3)

        page.wait_for_selector('#side', timeout=timeout_ms)

        group_items = page.query_selector_all(_GROUP_ITEM_SELECTOR)
        for item in group_items:
            text = item.text_content() or ""
            if group_name.lower() in text.lower():
                item.click()
                time.sleep(1)
                print(f"  Opened group: {group_name}")
                return

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
        # Click attach button
        page.wait_for_selector(_ATTACH_BUTTON_SELECTOR, timeout=5000)
        page.click(_ATTACH_BUTTON_SELECTOR)
        time.sleep(1)

        # Click "Photos & videos" to open file chooser
        with page.expect_file_chooser() as fc_info:
            page.click('button[aria-label="Photos & videos"]')

        file_chooser = fc_info.value
        file_chooser.set_files(image_path)
        
        # Wait for image preview to appear
        time.sleep(3)
        print(f"  Image loaded, adding caption...")

        # Find and fill the caption field
        # The caption field is the "Type a message" input that appears when image is selected
        caption_selectors = [
            'div[contenteditable="true"][data-lexical-editor="true"]',
            'div[contenteditable="true"][role="textbox"]',
            'div[contenteditable="true"]',
        ]
        
        caption_el = None
        for selector in caption_selectors:
            try:
                caption_el = page.wait_for_selector(selector, timeout=3000)
                if caption_el:
                    break
            except Exception:
                continue
        
        if caption_el:
            caption_el.click()
            time.sleep(0.3)
            caption_el.fill(caption)
            time.sleep(0.5)
        else:
            print(f"  WARNING: Could not find caption field, sending without caption")

        # Click the green send button
        send_selectors = [
            'button[aria-label="Send"]',
            'button[data-testid="compose-btn-send"]',
            'span[data-icon="send"]',
        ]
        
        sent = False
        for selector in send_selectors:
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
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except Exception:
            pass
        return False


def send_deals_to_whatsapp(
    deals: list[dict[str, Any]],
    group_name: str,
    headed: bool = False,
    delay_between: float = 5.0,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Send deal messages to a WhatsApp group.

    Args:
        deals: List of deal dicts with 'title', 'url', 'image_url', 'message'.
        group_name: Name of the WhatsApp group to send to.
        headed: Open browser window (needed for first-time QR scan).
        delay_between: Seconds to wait between messages.
        max_retries: Number of retries per failed message.

    Returns:
        Dict with 'sent', 'failed', 'errors' counts and details.
    """
    from playwright.sync_api import sync_playwright

    results = {"sent": 0, "failed": 0, "errors": []}

    with sync_playwright() as p:
        import glob as _glob
        # Clean up old lock file that can prevent browser from starting
        for lock_file in _glob.glob(str(Path(USER_DATA_DIR) / "SingletonLock")):
            try:
                Path(lock_file).unlink()
            except OSError:
                pass

        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=not headed,
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        page = context.new_page()

        print("Opening WhatsApp Web...")
        page.goto(_WHATSAPP_URL, wait_until="domcontentloaded", timeout=60000)
        
        _ensure_logged_in(page, headed=headed)
        
        print("  Waiting for app to fully load (this may take 30-60s)...")
        try:
            page.wait_for_selector('input[aria-label="Search or start a new chat"]', timeout=60000)
            print("  App loaded successfully!")
        except Exception:
            print("  WARNING: Search input did not appear, trying to continue anyway...")
            time.sleep(15)
        
        _search_and_open_group(page, group_name)

        for i, deal in enumerate(deals):
            title = deal.get("title", "Unknown")
            message = deal.get("message", "")
            image_url = deal.get("image_url")

            print(f"\n[{i + 1}/{len(deals)}] Sending: {title[:50]}...")

            if not image_url:
                print(f"  WARNING: No image_url for '{title}', skipping.")
                results["failed"] += 1
                results["errors"].append({"title": title, "reason": "no image_url"})
                continue

            image_path = _download_image(image_url)
            if not image_path:
                results["failed"] += 1
                results["errors"].append({"title": title, "reason": "download failed"})
                continue

            success = False
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    print(f"  Retry {attempt}/{max_retries}...")
                    time.sleep(2)

                success = _send_image_with_caption(page, image_path, message, delay_between)
                if success:
                    break

            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({"title": title, "reason": "send failed"})

            try:
                Path(image_path).unlink()
            except Exception:
                pass

        # Wait before closing to ensure messages are fully sent
        print("\n  Waiting for messages to sync...")
        time.sleep(5)

        context.close()

    return results


def main() -> None:
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
        data = json.loads(deals_path.read_text())
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
