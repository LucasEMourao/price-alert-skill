"""Application orchestration for scan flows."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def extract_deals_from_products(
    products: list[dict[str, Any]],
    marketplace: str,
    query: str,
    min_discount: float,
    *,
    calculate_discount_fn: Callable[[float, float], float | None],
) -> list[dict[str, Any]]:
    """Extract products that have a displayed discount >= min_discount."""
    deals = []
    for product in products:
        current_price = product.get("price")
        list_price = product.get("list_price")
        title = product.get("title", "")
        url = product.get("url", "")

        if not current_price or not title or not url:
            continue

        discount_pct = None
        previous_price = None

        if list_price and list_price > current_price:
            discount_pct = calculate_discount_fn(current_price, list_price)
            previous_price = list_price

        if discount_pct is None or discount_pct < min_discount:
            continue

        deals.append(
            {
                "title": title,
                "url": url,
                "product_url": url,
                "dedup_key": url,
                "image_url": product.get("image_url"),
                "marketplace": marketplace,
                "current_price": current_price,
                "current_price_text": product.get("price_text"),
                "previous_price": previous_price,
                "previous_price_text": product.get("list_price_text"),
                "discount_pct": discount_pct,
                "query": query,
                "source_query": query,
            }
        )

    return deals


def scan_marketplace(
    marketplace: str,
    query: str,
    max_results: int,
    min_discount: float,
    *,
    amazon_runner: Callable[..., dict[str, Any]],
    mercadolivre_runner: Callable[..., dict[str, Any]],
    calculate_discount_fn: Callable[[float, float], float | None],
) -> list[dict[str, Any]]:
    """Scan a single marketplace for deals."""
    if marketplace == "amazon_br":
        result = amazon_runner(query=query, max_results=max_results)
    elif marketplace == "mercadolivre_br":
        result = mercadolivre_runner(query=query, max_results=max_results)
    else:
        return []

    products = result.get("products", [])
    return extract_deals_from_products(
        products,
        marketplace,
        query,
        min_discount,
        calculate_discount_fn=calculate_discount_fn,
    )


def scan_all(
    max_results: int,
    min_discount: float,
    marketplaces: list[str],
    queries: list[str],
    *,
    scan_marketplace_fn: Callable[..., list[dict[str, Any]]],
    logger: Callable[[str], None] = print,
) -> list[dict[str, Any]]:
    """Scan multiple queries across marketplaces."""
    all_deals = []
    for query in queries:
        for marketplace in marketplaces:
            try:
                deals = scan_marketplace_fn(marketplace, query, max_results, min_discount)
                if deals:
                    logger(f"  ✓ {marketplace} / {query}: {len(deals)} deals found")
                all_deals.extend(deals)
            except Exception as exc:
                logger(f"  ✗ {marketplace} / {query}: {exc}")
    return all_deals


def deduplicate_run_deals(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate deals within the same scan run by product URL."""
    seen_urls: set[str] = set()
    unique_deals = []
    for deal in deals:
        product_url = deal.get("product_url") or deal.get("url")
        if product_url not in seen_urls:
            seen_urls.add(product_url)
            unique_deals.append(deal)
    return unique_deals


def apply_affiliate_links(
    deals: list[dict[str, Any]],
    *,
    generate_links_fn: Callable[[list[str]], dict[str, str]],
    logger: Callable[[str], None] = print,
) -> None:
    """Replace Mercado Livre URLs with generated affiliate links when possible."""
    ml_deals = [deal for deal in deals if deal["marketplace"] == "mercadolivre_br"]
    if not ml_deals:
        return

    ml_urls = [deal["product_url"] for deal in ml_deals]
    logger(f"\nGenerating meli.la links for {len(ml_urls)} ML deals...")
    try:
        melila_map = generate_links_fn(ml_urls)
        for deal in ml_deals:
            product_url = deal["product_url"]
            affiliate_url = melila_map.get(product_url, product_url)
            deal["affiliate_url"] = affiliate_url
            deal["url"] = affiliate_url
        generated = sum(
            1
            for url in ml_urls
            if melila_map.get(url) and melila_map[url] != url
        )
        logger(f"  Generated {generated}/{len(ml_urls)} meli.la links")
    except Exception as exc:
        logger(f"  WARNING: meli.la generation failed: {exc}")
        logger("  Falling back to original URLs")
        for deal in ml_deals:
            deal["affiliate_url"] = deal["product_url"]


def build_messages_payload(
    deals: list[dict[str, Any]],
    *,
    format_message_fn: Callable[[dict[str, Any]], str],
) -> list[dict[str, Any]]:
    """Build printable/savable message payloads from normalized deals."""
    messages = []
    for deal in deals:
        message = format_message_fn(deal)
        deal["message"] = message
        deal["dedup_key"] = deal.get("dedup_key") or deal.get("offer_key") or deal["url"]
        messages.append(
            {
                "title": deal["title"],
                "marketplace": deal["marketplace"],
                "current_price": deal["current_price"],
                "discount_pct": deal["discount_pct"],
                "url": deal["url"],
                "image_url": deal.get("image_url"),
                "message": message,
                "category": deal.get("category"),
                "lane": deal.get("lane"),
                "is_super_promo": deal.get("is_super_promo", False),
                "savings_brl": deal.get("savings_brl"),
                "offer_key": deal.get("offer_key"),
                "product_key": deal.get("product_key"),
            }
        )
    return messages


def save_messages_file(
    messages: list[dict[str, Any]],
    now: datetime,
    messages_dir: Path,
    output_path: str | None = None,
) -> str | None:
    """Persist message payloads to disk for inspection/debugging."""
    if not messages:
        return None

    messages_dir.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%Y%m%d_%H%M%S")
    destination = output_path or str(messages_dir / f"deals_{ts}.json")
    Path(destination).write_text(
        json.dumps(
            {
                "messages": messages,
                "count": len(messages),
                "generated_at": now.isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination


def print_messages(
    messages: list[dict[str, Any]],
    *,
    logger: Callable[[str], None] = print,
) -> None:
    """Print formatted deal messages to stdout."""
    for msg in messages:
        logger(f"\n{'=' * 50}")
        logger(msg["message"])
        logger(f"{'=' * 50}")


def run_cadence_scan(
    deals: list[dict[str, Any]],
    *,
    now: datetime,
    output_path: str | None,
    load_sent_deals_fn: Callable[[], dict[str, Any]],
    load_deal_queue_fn: Callable[[], dict[str, Any]],
    begin_scan_run_fn: Callable[[dict[str, Any], datetime], int],
    can_send_again_fn: Callable[..., bool],
    remove_entry_by_product_key_fn: Callable[[dict[str, Any], str], bool],
    upsert_pool_deal_fn: Callable[..., str],
    build_messages_payload_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    save_messages_file_fn: Callable[[list[dict[str, Any]], datetime, str | None], str | None],
    prune_expired_entries_fn: Callable[..., dict[str, Any]],
    save_deal_queue_fn: Callable[[dict[str, Any]], None],
    format_message_fn: Callable[[dict[str, Any]], str],
    logger: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Collect deals into expiring pools for the single-sender flow."""
    sent_data = load_sent_deals_fn()
    queue = load_deal_queue_fn()
    scan_sequence = begin_scan_run_fn(queue, now)
    eligible_deals = []
    skipped_sent = 0
    discarded = 0
    lane_counts = {"urgent": 0, "priority": 0, "normal": 0}

    for deal in deals:
        lane = deal.get("lane", "discarded")
        if lane == "discarded":
            remove_entry_by_product_key_fn(queue, deal.get("product_key", ""))
            discarded += 1
            continue
        if not can_send_again_fn(deal, sent_data, now=now):
            remove_entry_by_product_key_fn(queue, deal.get("product_key", ""))
            skipped_sent += 1
            continue

        deal["message"] = deal.get("message") or format_message_fn(deal)
        deal["dedup_key"] = deal.get("dedup_key") or deal.get("offer_key") or deal["url"]
        upsert_pool_deal_fn(
            queue,
            deal,
            lane,
            now=now,
            scan_sequence=scan_sequence,
        )
        lane_counts[lane] += 1
        eligible_deals.append(deal)

    if discarded:
        logger(f"Skipped {discarded} deals outside the lane thresholds")
    if skipped_sent:
        logger(f"Skipped {skipped_sent} deals blocked by cooldown/dedup")

    messages = build_messages_payload_fn(eligible_deals)
    saved_output_path = save_messages_file_fn(messages, now, output_path)
    if saved_output_path:
        logger(f"Saved to: {saved_output_path}")
    queue = prune_expired_entries_fn(queue, now=now)
    save_deal_queue_fn(queue)

    logger(
        "\nCadence scan summary: "
        f"{lane_counts['urgent']} urgent, "
        f"{lane_counts['priority']} priority, "
        f"{lane_counts['normal']} normal"
    )
    return {
        "eligible_deals": eligible_deals,
        "messages": messages,
        "output_path": saved_output_path,
        "discarded": discarded,
        "skipped_sent": skipped_sent,
        "lane_counts": lane_counts,
    }


def run_legacy_flow(
    deals: list[dict[str, Any]],
    *,
    now: datetime,
    output_path: str | None,
    send_whatsapp: bool,
    group_name: str,
    headed: bool,
    reset_session: bool,
    filter_new_deals_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]],
    build_messages_payload_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    save_messages_file_fn: Callable[[list[dict[str, Any]], datetime, str | None], str | None],
    print_messages_fn: Callable[[list[dict[str, Any]]], None],
    whatsapp_sender_fn: Callable[..., dict[str, Any]] | None,
    mark_deals_as_sent_fn: Callable[..., dict[str, Any]],
    logger: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Keep the direct scan-and-send flow working for manual use."""
    unique_deals, sent_data = filter_new_deals_fn(
        deals,
        auto_save=not send_whatsapp,
        mark_as_sent=not send_whatsapp,
    )
    skipped = len(deals) - len(unique_deals)
    if skipped > 0:
        logger(f"Skipped {skipped} already-sent deals")

    logger(f"\nTotal new deals: {len(unique_deals)}")
    messages = build_messages_payload_fn(unique_deals)
    saved_output_path = save_messages_file_fn(messages, now, output_path)
    if saved_output_path:
        logger(f"Saved to: {saved_output_path}")
        print_messages_fn(messages)
    else:
        logger("No deals found matching criteria.")

    send_results = None
    if send_whatsapp and unique_deals and whatsapp_sender_fn is not None:
        send_results = whatsapp_sender_fn(
            deals=unique_deals,
            group_name=group_name,
            headed=headed,
            reset_session=reset_session,
        )

        logger(f"\nWhatsApp results: {send_results['sent']} sent, {send_results['failed']} failed")
        if send_results["errors"]:
            for err in send_results["errors"]:
                logger(f"  - {err['title']}: {err['reason']}")

        successful_keys = set(send_results.get("successful_keys", []))
        if successful_keys:
            mark_deals_as_sent_fn(
                [
                    deal for deal in unique_deals
                    if deal.get("offer_key", deal["dedup_key"]) in successful_keys
                ],
                sent_data=sent_data,
                auto_save=True,
            )

    return {
        "unique_deals": unique_deals,
        "messages": messages,
        "output_path": saved_output_path,
        "send_results": send_results,
    }
