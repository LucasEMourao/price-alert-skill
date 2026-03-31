#!/usr/bin/env python3

import argparse
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.request import Request, urlopen


def parse_brl_amount(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"R\$\s*([\d\.\,]+)", text)
    if not match:
        return None
    normalized = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


class HistoryTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.text_parts.append(text)


def fetch_steel_payload(url: str, api_base: str, scrape_endpoint: str, timeout_seconds: int, delay_ms: int) -> dict[str, Any]:
    payload = json.dumps({"url": url, "delay": delay_ms}).encode("utf-8")
    request = Request(
        url=f"{api_base.rstrip('/')}{scrape_endpoint}",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def extract_next_data(html: str) -> dict[str, Any]:
    marker = '<script id="__NEXT_DATA__" type="application/json">'
    start = html.find(marker)
    if start == -1:
        return {}
    start += len(marker)
    end = html.find("</script>", start)
    if end == -1:
        return {}
    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError:
        return {}


def extract_json_ld(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    values = metadata.get("jsonLd")
    if isinstance(values, list):
        return [item for item in values if isinstance(item, dict)]
    return []


def flatten_json_ld_product(json_ld: list[dict[str, Any]]) -> dict[str, Any]:
    for item in json_ld:
        graph = item.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                if isinstance(node, dict) and node.get("@type") == "Product":
                    return node
        if item.get("@type") == "Product":
            return item
    return {}


def extract_visible_ranges(html: str) -> list[str]:
    parser = HistoryTextParser()
    parser.feed(html)
    text = " ".join(parser.text_parts)
    ranges = []
    for label in ("40 dias", "3 meses", "6 meses", "1 ano"):
        if label in text:
            ranges.append(label)
    return ranges


def extract_price_tip_text(html: str) -> str | None:
    match = re.search(
        r"Com base nos últimos\s*<span>([^<]+)</span>,\s*o valor está.*?<span>(R\$\s*[\d\.\,]+)</span>\s*(mais caro|mais barato)\s*que o normal",
        html,
        re.I | re.S,
    )
    if not match:
        return None
    return f"Com base nos últimos {match.group(1)}, o valor está {match.group(2)} {match.group(3)} que o normal"


def parse_tip_delta(text: str | None) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    amount = parse_brl_amount(text)
    direction = None
    if "mais caro" in text:
        direction = "above_normal"
    elif "mais barato" in text:
        direction = "below_normal"
    return amount, direction


def build_summary(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    html = (payload.get("content") or {}).get("html", "")
    next_data = extract_next_data(html)
    json_ld = extract_json_ld(metadata)
    product_ld = flatten_json_ld_product(json_ld)

    page_props = (((next_data.get("props") or {}).get("pageProps") or {}))
    route = page_props.get("route") or {}
    redux_state = ((page_props.get("initialReduxState") or {}))
    product_state = (((redux_state.get("products") or {}).get("product") or {}))
    product_info = product_state.get("product") or {}
    price_tip_state = redux_state.get("priceTip") or {}
    product_id = route.get("entityID") or product_info.get("id") or product_ld.get("sku")
    price_tip_entry = (((price_tip_state.get(str(product_id)) or {}).get("priceTip")) if product_id is not None else None) or {}

    aggregate_offers = product_ld.get("offers") if isinstance(product_ld.get("offers"), dict) else {}
    low_price = aggregate_offers.get("lowPrice")
    high_price = aggregate_offers.get("highPrice")
    offer_count = aggregate_offers.get("offerCount")

    current_price = price_tip_entry.get("price") or low_price
    median_price = price_tip_entry.get("median_price")
    tip_description = price_tip_entry.get("description")
    tip_range = price_tip_entry.get("date_range") or {}
    tip_text = extract_price_tip_text(html)
    tip_delta, tip_direction = parse_tip_delta(tip_text)
    inferred_normal_price = None
    if isinstance(current_price, (int, float)) and isinstance(tip_delta, (int, float)):
        if tip_direction == "above_normal":
            inferred_normal_price = round(current_price - tip_delta, 2)
        elif tip_direction == "below_normal":
            inferred_normal_price = round(current_price + tip_delta, 2)

    return {
        "source": "zoom_br",
        "zoom_url": url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "zoom_product_id": str(product_id) if product_id is not None else None,
        "title": product_ld.get("name") or product_info.get("name") or metadata.get("title"),
        "canonical_url": metadata.get("canonical") or url,
        "image_url": metadata.get("ogImage"),
        "brand": (((product_ld.get("brand") or {}).get("name")) if isinstance(product_ld.get("brand"), dict) else None) or None,
        "model": product_info.get("model") or next((item.get("value") for item in (product_ld.get("additionalProperty") or []) if item.get("name") == "Modelo"), None),
        "current_best_price": current_price,
        "current_best_price_text": f"R$ {current_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(current_price, (int, float)) else None,
        "low_offer_price": low_price,
        "high_offer_price": high_price,
        "offer_count": offer_count,
        "median_price": median_price or inferred_normal_price,
        "tip_description": tip_description,
        "tip_window_start": tip_range.get("start"),
        "tip_window_end": tip_range.get("end"),
        "tip_text": tip_text,
        "visible_history_ranges": extract_visible_ranges(html),
        "raw_summary": {
            "price_tip": price_tip_entry,
            "aggregate_offers": aggregate_offers,
            "inferred_normal_price": inferred_normal_price,
        },
        "errors": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Zoom product-page price-history summary via Steel API.")
    parser.add_argument("zoom_url", help="Zoom product URL")
    parser.add_argument("--api-base", default="http://localhost:3000", help="Steel API base URL")
    parser.add_argument("--scrape-endpoint", default="/v1/scrape", help="Steel scrape endpoint path")
    parser.add_argument("--timeout-seconds", type=int, default=40, help="HTTP timeout")
    parser.add_argument("--delay-ms", type=int, default=2500, help="Extra wait requested from Steel before capture")
    args = parser.parse_args()

    try:
        payload = fetch_steel_payload(args.zoom_url, args.api_base, args.scrape_endpoint, args.timeout_seconds, args.delay_ms)
        result = build_summary(args.zoom_url, payload)
    except Exception as exc:  # noqa: BLE001
        result = {
            "source": "zoom_br",
            "zoom_url": args.zoom_url,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
