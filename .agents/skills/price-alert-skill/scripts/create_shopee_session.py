#!/usr/bin/env python3

import argparse
import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def normalize_local_url(url: str, api_base: str) -> str:
    parsed = urlparse(url)
    api = urlparse(api_base)
    host = api.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else (f":{api.port}" if api.port else "")
    scheme = parsed.scheme or api.scheme or "http"
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    if parsed.hostname in {"0.0.0.0", "", None}:
        return f"{scheme}://{host}{port}{path}{query}"
    return url


def create_session(api_base: str) -> dict:
    request = Request(
        url=f"{api_base.rstrip('/')}/v1/sessions",
        data=b"{}",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Steel session for Shopee login reuse.")
    parser.add_argument("--api-base", default="http://localhost:3000", help="Steel API base URL")
    args = parser.parse_args()

    session = create_session(args.api_base)
    output = {
        "session_id": session.get("id"),
        "session_viewer_url": normalize_local_url(session.get("sessionViewerUrl", ""), args.api_base),
        "debug_url": normalize_local_url(session.get("debugUrl", ""), args.api_base),
        "instructions": [
            "Open session_viewer_url in your browser.",
            "Log in to Shopee inside that Steel session.",
            "Reuse the returned session_id with fetch_shopee_br.py --session-id <id>.",
        ],
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
