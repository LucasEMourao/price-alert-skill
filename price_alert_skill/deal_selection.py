#!/usr/bin/env python3

"""Selection rules and lane ranking for cadence-based deal delivery."""

from __future__ import annotations

from typing import Any

from price_alert_skill.core.domain.identity import (
    build_offer_key,
    build_product_key,
    calculate_savings_brl,
    normalize_url_for_key,
)
from price_alert_skill.core.domain.lane_rules import (
    ACTIVE_LANES,
    CATEGORY_RULES,
    DEFAULT_CATEGORY,
    LANE_PRIORITY,
    classify_deal_lane,
    get_category_rule,
    get_lane_rank,
    passes_quality_filters,
    qualifies_normal,
    qualifies_priority,
    qualifies_urgent,
)
from price_alert_skill.core.domain.ranking import (
    deal_sort_key,
    is_better_deal,
    sort_deals_for_sending,
)


CADENCE_CONFIG = {
    "scan_interval_minutes": 15,
    "urgent_window_minutes": 45,
    "urgent_window_scans": 3,
    "priority_window_minutes": 90,
    "priority_window_scans": 6,
    "normal_window_minutes": 180,
    "normal_window_scans": 12,
    "sender_poll_seconds": 20,
    "sender_idle_exit_seconds": 300,
    "same_offer_cooldown_hours": 24,
    "urgent_offer_cooldown_hours": 6,
    "min_discount_improvement_points": 5.0,
    "min_savings_improvement_brl": 50.0,
    "max_send_retries": 2,
    "retry_backoff_seconds": 180,
    "non_urgent_lane_sequence": ("priority", "priority", "priority", "normal"),
}


DEFAULT_QUERY_PROFILE = "tech"

TECH_QUERY_DEFINITIONS = [
    {"query": "mouse gamer", "category": "perifericos"},
    {"query": "teclado mecanico gamer", "category": "perifericos"},
    {"query": "mousepad gamer", "category": "perifericos"},
    {"query": "headset gamer", "category": "audio_comunicacao"},
    {"query": "webcam full hd", "category": "audio_comunicacao"},
    {"query": "microfone usb", "category": "audio_comunicacao"},
    {"query": "air cooler", "category": "refrigeracao_leve"},
    {"query": "ssd nvme 1tb", "category": "armazenamento"},
    {"query": "ssd nvme 2tb", "category": "armazenamento"},
    {"query": "ssd sata 1tb", "category": "armazenamento"},
    {"query": "ssd 2tb", "category": "armazenamento"},
    {"query": "memoria ram ddr4", "category": "memoria"},
    {"query": "memoria ram ddr5", "category": "memoria"},
    {"query": "fonte 650w", "category": "fontes"},
    {"query": "fonte 750w", "category": "fontes"},
    {"query": "gabinete gamer", "category": "gabinetes"},
    {"query": "water cooler", "category": "refrigeracao_premium"},
    {"query": "monitor gamer", "category": "monitores"},
    {"query": "processador ryzen", "category": "processadores"},
    {"query": "processador intel core", "category": "processadores"},
    {"query": "placa mae am5", "category": "placas_mae"},
    {"query": "placa mae lga1700", "category": "placas_mae"},
    {"query": "placa de video rtx", "category": "placas_video"},
    {"query": "placa de video rx", "category": "placas_video"},
    {"query": "notebook gamer", "category": "notebooks_gamer"},
    {"query": "pc gamer", "category": "pc_gamer"},
    {"query": "computador gamer", "category": "pc_gamer"},
    {"query": "desktop gamer", "category": "pc_gamer"},
]


BEAUTY_QUERY_DEFINITIONS = [
    {"query": "perfume feminino", "category": "beleza_perfumes"},
    {"query": "body splash", "category": "beleza_perfumes"},
    {"query": "kit perfume feminino", "category": "beleza_perfumes"},
    {"query": "perfume importado feminino", "category": "beleza_perfumes"},
    {"query": "perfume arabe feminino", "category": "beleza_perfumes"},
    {"query": "miniatura perfume feminino", "category": "beleza_perfumes"},
    {"query": "kit skincare", "category": "beleza_skincare"},
    {"query": "protetor solar facial", "category": "beleza_skincare"},
    {"query": "protetor solar com cor", "category": "beleza_skincare"},
    {"query": "protetor solar corporal", "category": "beleza_skincare"},
    {"query": "serum facial", "category": "beleza_skincare"},
    {"query": "serum vitamina c", "category": "beleza_skincare"},
    {"query": "serum acido hialuronico", "category": "beleza_skincare"},
    {"query": "serum niacinamida", "category": "beleza_skincare"},
    {"query": "hidratante facial", "category": "beleza_skincare"},
    {"query": "gel hidratante facial", "category": "beleza_skincare"},
    {"query": "creme anti idade", "category": "beleza_skincare"},
    {"query": "creme para area dos olhos", "category": "beleza_skincare"},
    {"query": "creme clareador facial", "category": "beleza_skincare"},
    {"query": "creme para melasma", "category": "beleza_skincare"},
    {"query": "retinol facial", "category": "beleza_skincare"},
    {"query": "acido glicolico", "category": "beleza_skincare"},
    {"query": "acido salicilico", "category": "beleza_skincare"},
    {"query": "esfoliante facial", "category": "beleza_skincare"},
    {"query": "sabonete facial", "category": "beleza_skincare"},
    {"query": "gel de limpeza facial", "category": "beleza_skincare"},
    {"query": "tonico facial", "category": "beleza_skincare"},
    {"query": "agua micelar", "category": "beleza_skincare"},
    {"query": "demaquilante", "category": "beleza_skincare"},
    {"query": "cleansing oil", "category": "beleza_skincare"},
    {"query": "mascara facial", "category": "beleza_skincare"},
    {"query": "mascara de argila", "category": "beleza_skincare"},
    {"query": "lip balm", "category": "beleza_skincare"},
    {"query": "hidratante labial", "category": "beleza_skincare"},
    {"query": "mascara capilar", "category": "beleza_cabelo_tratamento"},
    {"query": "cronograma capilar", "category": "beleza_cabelo_tratamento"},
    {"query": "kit cronograma capilar", "category": "beleza_cabelo_tratamento"},
    {"query": "shampoo profissional", "category": "beleza_cabelo_tratamento"},
    {"query": "condicionador profissional", "category": "beleza_cabelo_tratamento"},
    {"query": "kit shampoo e condicionador", "category": "beleza_cabelo_tratamento"},
    {"query": "leave-in cabelo", "category": "beleza_cabelo_tratamento"},
    {"query": "creme de pentear", "category": "beleza_cabelo_tratamento"},
    {"query": "oleo reparador de pontas", "category": "beleza_cabelo_tratamento"},
    {"query": "oleo capilar", "category": "beleza_cabelo_tratamento"},
    {"query": "protetor termico cabelo", "category": "beleza_cabelo_tratamento"},
    {"query": "reconstrutor capilar", "category": "beleza_cabelo_tratamento"},
    {"query": "acidificante capilar", "category": "beleza_cabelo_tratamento"},
    {"query": "matizador cabelo", "category": "beleza_cabelo_tratamento"},
    {"query": "tonalizante cabelo", "category": "beleza_cabelo_tratamento"},
    {"query": "tinta de cabelo", "category": "beleza_cabelo_tratamento"},
    {"query": "ampola capilar", "category": "beleza_cabelo_tratamento"},
    {"query": "tratamento cabelo loiro", "category": "beleza_cabelo_tratamento"},
    {"query": "tratamento cabelo cacheado", "category": "beleza_cabelo_tratamento"},
    {"query": "ativador de cachos", "category": "beleza_cabelo_tratamento"},
    {"query": "finalizador cabelo", "category": "beleza_cabelo_tratamento"},
    {"query": "spray fixador cabelo", "category": "beleza_cabelo_tratamento"},
    {"query": "shampoo anticaspa feminino", "category": "beleza_cabelo_tratamento"},
    {"query": "shampoo a seco", "category": "beleza_cabelo_tratamento"},
    {"query": "escova secadora", "category": "beleza_cabelo_ferramentas"},
    {"query": "secador de cabelo", "category": "beleza_cabelo_ferramentas"},
    {"query": "chapinha cabelo", "category": "beleza_cabelo_ferramentas"},
    {"query": "babyliss", "category": "beleza_cabelo_ferramentas"},
    {"query": "modelador de cachos", "category": "beleza_cabelo_ferramentas"},
    {"query": "escova alisadora", "category": "beleza_cabelo_ferramentas"},
    {"query": "difusor secador", "category": "beleza_cabelo_ferramentas"},
    {"query": "escova rotativa", "category": "beleza_cabelo_ferramentas"},
    {"query": "triondas cabelo", "category": "beleza_cabelo_ferramentas"},
    {"query": "maquina aparadora pelos feminino", "category": "beleza_cabelo_ferramentas"},
    {"query": "depilador eletrico feminino", "category": "beleza_cabelo_ferramentas"},
    {"query": "massageador facial", "category": "beleza_cabelo_ferramentas"},
    {"query": "escova de limpeza facial", "category": "beleza_cabelo_ferramentas"},
    {"query": "led mask facial", "category": "beleza_cabelo_ferramentas"},
    {"query": "base maquiagem", "category": "beleza_maquiagem"},
    {"query": "base matte", "category": "beleza_maquiagem"},
    {"query": "base glow", "category": "beleza_maquiagem"},
    {"query": "corretivo maquiagem", "category": "beleza_maquiagem"},
    {"query": "po compacto", "category": "beleza_maquiagem"},
    {"query": "po translucido", "category": "beleza_maquiagem"},
    {"query": "blush", "category": "beleza_maquiagem"},
    {"query": "bronzer", "category": "beleza_maquiagem"},
    {"query": "contorno maquiagem", "category": "beleza_maquiagem"},
    {"query": "iluminador maquiagem", "category": "beleza_maquiagem"},
    {"query": "primer facial", "category": "beleza_maquiagem"},
    {"query": "fixador de maquiagem", "category": "beleza_maquiagem"},
    {"query": "paleta maquiagem", "category": "beleza_maquiagem"},
    {"query": "paleta de sombras", "category": "beleza_maquiagem"},
    {"query": "mascara de cilios", "category": "beleza_maquiagem"},
    {"query": "rimel", "category": "beleza_maquiagem"},
    {"query": "delineador", "category": "beleza_maquiagem"},
    {"query": "lapis de olho", "category": "beleza_maquiagem"},
    {"query": "lapis de sobrancelha", "category": "beleza_maquiagem"},
    {"query": "gel para sobrancelha", "category": "beleza_maquiagem"},
    {"query": "batom", "category": "beleza_maquiagem"},
    {"query": "batom liquido", "category": "beleza_maquiagem"},
    {"query": "gloss labial", "category": "beleza_maquiagem"},
    {"query": "lip tint", "category": "beleza_maquiagem"},
    {"query": "kit maquiagem", "category": "beleza_maquiagem"},
    {"query": "esponja maquiagem", "category": "beleza_maquiagem"},
    {"query": "pincel maquiagem", "category": "beleza_maquiagem"},
    {"query": "maleta maquiagem", "category": "beleza_maquiagem"},
    {"query": "hidratante corporal", "category": "beleza_corpo_banho"},
    {"query": "creme corporal", "category": "beleza_corpo_banho"},
    {"query": "oleo corporal", "category": "beleza_corpo_banho"},
    {"query": "body butter", "category": "beleza_corpo_banho"},
    {"query": "sabonete liquido", "category": "beleza_corpo_banho"},
    {"query": "sabonete intimo feminino", "category": "beleza_corpo_banho"},
    {"query": "esfoliante corporal", "category": "beleza_corpo_banho"},
    {"query": "desodorante feminino", "category": "beleza_corpo_banho"},
    {"query": "clareador axilas", "category": "beleza_corpo_banho"},
    {"query": "creme para maos", "category": "beleza_corpo_banho"},
    {"query": "creme para pes", "category": "beleza_corpo_banho"},
    {"query": "oleo de banho", "category": "beleza_corpo_banho"},
    {"query": "kit banho feminino", "category": "beleza_corpo_banho"},
    {"query": "esmalte", "category": "beleza_unhas"},
    {"query": "kit esmaltes", "category": "beleza_unhas"},
    {"query": "base fortalecedora unha", "category": "beleza_unhas"},
    {"query": "top coat unha", "category": "beleza_unhas"},
    {"query": "removedor de esmalte", "category": "beleza_unhas"},
    {"query": "alicate de cuticula", "category": "beleza_unhas"},
    {"query": "kit manicure", "category": "beleza_unhas"},
    {"query": "unhas posticas", "category": "beleza_unhas"},
    {"query": "gel para unhas", "category": "beleza_unhas"},
    {"query": "cabine uv led unha", "category": "beleza_unhas"},
    {"query": "necessaire feminina", "category": "beleza_acessorios"},
    {"query": "organizador maquiagem", "category": "beleza_acessorios"},
    {"query": "porta maquiagem", "category": "beleza_acessorios"},
    {"query": "espelho maquiagem led", "category": "beleza_acessorios"},
    {"query": "penteadeira portatil", "category": "beleza_acessorios"},
    {"query": "touca de cetim", "category": "beleza_acessorios"},
    {"query": "fronha de cetim", "category": "beleza_acessorios"},
    {"query": "faixa skincare", "category": "beleza_acessorios"},
    {"query": "tiara skincare", "category": "beleza_acessorios"},
    {"query": "presilhas de cabelo", "category": "beleza_acessorios"},
    {"query": "scrunchie", "category": "beleza_acessorios"},
    {"query": "escova desembaracante", "category": "beleza_acessorios"},
    {"query": "pente cabelo cacheado", "category": "beleza_acessorios"},
]


QUERY_PROFILE_DEFINITIONS = {
    "tech": TECH_QUERY_DEFINITIONS,
    "beauty": BEAUTY_QUERY_DEFINITIONS,
}

# Backward-compatible names used by older tests/scripts. The default profile remains tech.
QUERY_DEFINITIONS = TECH_QUERY_DEFINITIONS


def _normalize_query_profile(profile: str | None) -> str:
    normalized = (profile or DEFAULT_QUERY_PROFILE).strip().lower()
    if normalized not in QUERY_PROFILE_DEFINITIONS:
        available = ", ".join(sorted(QUERY_PROFILE_DEFINITIONS))
        raise ValueError(f"Unknown query profile '{profile}'. Available profiles: {available}")
    return normalized


def get_query_profiles() -> tuple[str, ...]:
    """Return available query profile names."""
    return tuple(QUERY_PROFILE_DEFINITIONS)


def get_query_definitions(profile: str | None = DEFAULT_QUERY_PROFILE) -> list[dict[str, str]]:
    """Return query definitions for the requested product profile."""
    normalized = _normalize_query_profile(profile)
    return [dict(definition) for definition in QUERY_PROFILE_DEFINITIONS[normalized]]


QUERY_TO_CATEGORY = {
    definition["query"]: definition["category"]
    for definitions in QUERY_PROFILE_DEFINITIONS.values()
    for definition in definitions
}

QUERY_TO_PROFILE = {
    definition["query"]: profile
    for profile, definitions in QUERY_PROFILE_DEFINITIONS.items()
    for definition in definitions
}

ALL_QUERIES = [definition["query"] for definition in TECH_QUERY_DEFINITIONS]


def get_queries(profile: str | None = DEFAULT_QUERY_PROFILE) -> list[str]:
    """Return the cadence query list in the configured profile order."""
    return [definition["query"] for definition in get_query_definitions(profile)]


def get_query_profile(query: str) -> str | None:
    """Resolve the configured product profile for a scan query."""
    return QUERY_TO_PROFILE.get((query or "").strip().lower())


def get_query_category(query: str) -> str:
    """Resolve the category for a scan query."""
    return QUERY_TO_CATEGORY.get((query or "").strip().lower(), DEFAULT_CATEGORY)


def prepare_deal_for_selection(deal: dict[str, Any]) -> dict[str, Any]:
    """Add selection metadata to a scanned deal."""
    prepared = dict(deal)
    source_query = prepared.get("source_query") or prepared.get("query", "")
    category = prepared.get("category") or get_query_category(source_query)
    product_url = prepared.get("product_url") or prepared.get("url", "")
    current_price = prepared.get("current_price")
    previous_price = prepared.get("previous_price")

    prepared["source_query"] = source_query
    prepared["category"] = category
    prepared["product_url"] = product_url
    prepared["product_key"] = prepared.get("product_key") or build_product_key(product_url)
    prepared["offer_key"] = prepared.get("offer_key") or build_offer_key(
        prepared["product_key"],
        current_price,
    )
    prepared["savings_brl"] = prepared.get("savings_brl")
    if prepared["savings_brl"] is None:
        prepared["savings_brl"] = calculate_savings_brl(current_price, previous_price)

    prepared["quality_passed"] = passes_quality_filters(prepared)
    prepared["lane"] = classify_deal_lane(prepared)
    prepared["is_super_promo"] = prepared["lane"] == "urgent"
    return prepared
