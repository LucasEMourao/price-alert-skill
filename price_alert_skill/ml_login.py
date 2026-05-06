#!/usr/bin/env python3
"""Helper script to open Playwright browser for ML login and save session.

Run this script, login manually in the browser window, then create
the signal file to save the session:
    touch data/ml_login_done

The script will save the session and close the browser.
"""
import signal
import sys
from playwright.sync_api import sync_playwright

from price_alert_skill.config import configure_utf8_stdio
from price_alert_skill.paths import resolve_data_dir

DATA_DIR = resolve_data_dir()
SESSION_FILE = DATA_DIR / "ml_session.json"
SIGNAL_FILE = DATA_DIR / "ml_login_done"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
delete navigator.__proto__.webdriver;
"""

def main():
    configure_utf8_stdio()
    print("[ml-login] Opening browser for manual login...")
    print("[ml-login] Login with email, CAPTCHA, 2FA in the browser window.")
    print(f"[ml-login] After logging in, run: touch {SIGNAL_FILE}")
    print("[ml-login] The session will be saved automatically.")

    # Clean up signal file
    SIGNAL_FILE.unlink(missing_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"},
        )
        context.add_init_script(STEALTH_JS)
        page = context.new_page()
        page.goto("https://www.mercadolivre.com.br/afiliados/linkbuilder", wait_until="domcontentloaded", timeout=30000)

        print("[ml-login] Browser opened. Waiting for login...")

        # Poll for signal file
        import time
        while True:
            if SIGNAL_FILE.exists():
                print("[ml-login] Signal received! Saving session...")
                break
            time.sleep(2)

        # Save session
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(SESSION_FILE))
        print(f"[ml-login] Session saved to {SESSION_FILE}")

        # Clean up
        SIGNAL_FILE.unlink(missing_ok=True)
        context.close()
        browser.close()

    print("[ml-login] Done! You can now use generate_melila_links.py normally.")


if __name__ == "__main__":
    main()
