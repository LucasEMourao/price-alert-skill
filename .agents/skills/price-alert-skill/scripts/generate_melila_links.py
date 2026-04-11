#!/usr/bin/env python3

"""Generate meli.la affiliate links via the ML affiliate panel.

Uses agent-browser to generate shortened affiliate links via the
Link Builder (Gerador de Links) at mercadolivre.com.br/afiliados/linkbuilder.

Requirements:
  - agent-browser installed globally: npm install -g agent-browser
  - Chrome installed: agent-browser install
  - Proxy configured (env var ML_PROXY or --proxy flag) for server IPs blocked by ML

Usage:
  python3 generate_melila_links.py "https://www.mercadolivre.com.br/mouse-gamer/p/MLB123"
  python3 generate_melila_links.py --urls url1 url2 url3
  python3 generate_melila_links.py --batch urls.txt
  python3 generate_melila_links.py --no-login --urls url1 url2
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_FILE = ROOT / "data" / "melila_cache.json"
SESSION_NAME = "ml-affiliado"
LINK_BUILDER_URL = "https://www.mercadolivre.com.br/afiliados/linkbuilder"
AFFILIATE_HUB_URL = "https://www.mercadolivre.com.br/afiliados"

# Proxy configuration
PROXY = os.environ.get("ML_PROXY", "")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _agent_browser_flags() -> str:
    """Build agent-browser flags string."""
    flags = f'--session-name {SESSION_NAME}'
    if PROXY:
        flags += f' --proxy "{PROXY}"'
    return flags


def _run(cmd: str, timeout: int = 30) -> str:
    """Run an agent-browser command and return stdout."""
    full_cmd = f"agent-browser {_agent_browser_flags()} {cmd}"
    result = subprocess.run(
        ["sh", "-c", full_cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


# --- Cache ---

def load_cache() -> dict[str, str]:
    """Load cached meli.la URLs from disk."""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(cache: dict[str, str]) -> None:
    """Save meli.la URLs cache to disk."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


# --- Link Generation ---

def _extract_links_from_result(snapshot: str) -> list[str]:
    """Extract meli.la links from the result textbox snapshot."""
    links = []
    # Look for meli.la URLs in the snapshot
    matches = re.findall(r'https://meli\.la/[A-Za-z0-9]+', snapshot)
    if matches:
        links.extend(matches)
    return links


def generate_links(urls: list[str], delay_between: float = 3.0) -> dict[str, str]:
    """Generate meli.la links for multiple URLs using the bulk link builder.

    Supports generating multiple links at once by pasting URLs separated by newlines.
    Falls back to one-by-one generation if bulk fails.

    Returns a mapping of original_url -> meli.la_url.
    """
    cache = load_cache()
    results = {}
    to_generate = []

    # Separate cached and uncached
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

    # Try bulk generation first (all URLs at once)
    print(f"[ml-affiliado] Generating {len(to_generate)} links via bulk mode...")

    _run(f'open "{LINK_BUILDER_URL}"')
    time.sleep(3)

    snapshot = _run("snapshot -i")

    # Check if we're logged in
    if "iniciar sess" in snapshot.lower():
        print("[ml-affiliado] ERROR: Not logged in to ML affiliate panel")
        print("[ml-affiliado] Run with --headed first to log in, or set ML_PROXY env var")
        for url in to_generate:
            results[url] = url
        return results

    # Find the input field (textbox with "Insira" in its label)
    input_ref = None
    for line in snapshot.split('\n'):
        if 'textbox' in line.lower() and 'insira' in line.lower():
            match = re.search(r'ref=(e\d+)', line)
            if match:
                input_ref = match.group(1)
                break

    if not input_ref:
        print("[ml-affiliado] ERROR: Could not find URL input field")
        for url in to_generate:
            results[url] = url
        return results

    # Fill input with all URLs (one per line)
    urls_text = "\n".join(to_generate)
    _run(f'fill @{input_ref} "{urls_text}"')
    time.sleep(1)

    # Find and click the Gerar button
    _run('click button:has-text("Gerar")')
    time.sleep(4)

    # Extract results
    snapshot = _run("snapshot -i")
    generated_links = _extract_links_from_result(snapshot)

    if generated_links and len(generated_links) == len(to_generate):
        # Success - map URLs to meli.la links
        for i, url in enumerate(to_generate):
            melila = generated_links[i]
            results[url] = melila
            cache[url] = melila
        save_cache(cache)
        print(f"[ml-affiliado] Generated {len(generated_links)} meli.la links (bulk)")
        return results

    # Bulk failed or partial - try one by one
    print(f"[ml-affiliado] Bulk mode returned {len(generated_links)}/{len(to_generate)} links, falling back to one-by-one")

    for i, url in enumerate(to_generate):
        print(f"[ml-affiliado] Generating {i+1}/{len(to_generate)}: {url[:80]}...")

        _run(f'open "{LINK_BUILDER_URL}"')
        time.sleep(3)

        snapshot = _run("snapshot -i")

        # Find input field
        input_ref = None
        for line in snapshot.split('\n'):
            if 'textbox' in line.lower() and 'insira' in line.lower():
                match = re.search(r'ref=(e\d+)', line)
                if match:
                    input_ref = match.group(1)
                    break

        if not input_ref:
            print("[ml-affiliado]   -> ERROR: Input field not found, using original URL")
            results[url] = url
            continue

        # Fill URL
        _run(f'fill @{input_ref} "{url}"')
        time.sleep(1)

        # Click Gerar
        _run('click button:has-text("Gerar")')
        time.sleep(4)

        # Extract result
        snapshot = _run("snapshot -i")
        links = _extract_links_from_result(snapshot)

        if links:
            melila = links[0]
            results[url] = melila
            cache[url] = melila
            save_cache(cache)
            print(f"[ml-affiliado]   -> {melila}")
        else:
            results[url] = url
            print("[ml-affiliado]   -> FAILED, using original URL")

        # Delay between generations
        if i < len(to_generate) - 1:
            time.sleep(delay_between)

    return results


# --- Main ---

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate meli.la affiliate links via ML affiliate panel."
    )
    parser.add_argument("url", nargs="?", help="Single product URL to generate link for")
    parser.add_argument("--urls", nargs="+", help="Multiple product URLs")
    parser.add_argument("--batch", help="File with one URL per line")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between generations (seconds)")
    parser.add_argument("--no-login", action="store_true", help="Skip login check (assumes already logged in)")
    parser.add_argument("--proxy", help="Proxy server URL (e.g., http://host:port)")
    parser.add_argument("--output", help="Output file for JSON results")
    args = parser.parse_args()

    # Set proxy if provided
    global PROXY
    if args.proxy:
        PROXY = args.proxy

    # Collect URLs
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

    # Generate links
    results = generate_links(urls, delay_between=args.delay)

    # Output
    if args.output:
        Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(f"Results saved to: {args.output}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
