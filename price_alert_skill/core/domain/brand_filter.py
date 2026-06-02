"""Pure brand allowlist helpers for beauty deal filtering."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class BrandDefinition:
    """A canonical brand plus the marketplace title aliases that should match it."""

    canonical: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class BrandMatch:
    """Result of checking a deal title against the active allowlist."""

    passed: bool
    brand: str | None = None
    alias: str | None = None


DEFAULT_BEAUTY_BRAND_DEFINITIONS: tuple[BrandDefinition, ...] = (
    BrandDefinition("Bruna Tavares", ("bruna tavares",)),
    BrandDefinition("Eudora", ("eudora",)),
    BrandDefinition("Mari Maria Makeup", ("mari maria makeup", "mari maria")),
    BrandDefinition("Boca Rosa", ("boca rosa",)),
    BrandDefinition("O Boticario", ("o boticario", "boticario")),
    BrandDefinition("Natura", ("natura",)),
    BrandDefinition("Vizzela", ("vizzela",)),
    BrandDefinition("Oceane", ("oceane",)),
    BrandDefinition("Mascavo", ("mascavo",)),
    BrandDefinition("L'Oreal Paris", ("loreal paris", "l oreal paris", "loreal")),
    BrandDefinition(
        "FRAN by Franciny Ehlke",
        ("fran by franciny ehlke", "fran by franciny", "franciny ehlke", "franciny"),
    ),
    BrandDefinition("Granado", ("granado",)),
    BrandDefinition("Principia", ("principia",)),
    BrandDefinition("Creamy", ("creamy",)),
    BrandDefinition("Lola Cosmetics", ("lola cosmetics", "lola")),
    BrandDefinition("Haskell", ("haskell",)),
    BrandDefinition("Melu", ("melu",)),
    BrandDefinition(
        "L'Occitane au Bresil",
        (
            "l occitane au bresil",
            "loccitane au bresil",
            "l occitane au brasil",
            "loccitane au brasil",
        ),
    ),
    BrandDefinition("Nivea", ("nivea",)),
    BrandDefinition("Quem Disse Berenice", ("quem disse berenice", "qdb")),
    BrandDefinition("KIKO Milano", ("kiko milano", "kiko")),
    BrandDefinition("Dove", ("dove",)),
    BrandDefinition("Secret", ("secret",)),
    BrandDefinition("Ruby Rose", ("ruby rose",)),
    BrandDefinition("Sallve", ("sallve",)),
    BrandDefinition("Vult", ("vult",)),
    BrandDefinition("Essence", ("essence",)),
    BrandDefinition("Niina Secrets", ("niina secrets", "niina")),
    BrandDefinition("Maybelline New York", ("maybelline new york", "maybelline")),
    BrandDefinition("Catharine Hill", ("catharine hill",)),
    BrandDefinition("Biore", ("biore",)),
    BrandDefinition("Too Faced", ("too faced",)),
    BrandDefinition("Kerastase", ("kerastase",)),
    BrandDefinition("Armani Beauty", ("armani beauty", "armani", "giorgio armani")),
    BrandDefinition("Jean Paul Gaultier", ("jean paul gaultier",)),
    BrandDefinition("MAC Cosmetics", ("mac cosmetics", "m a c", "mac")),
    BrandDefinition("Shiseido", ("shiseido",)),
    BrandDefinition("The Ordinary", ("the ordinary",)),
    BrandDefinition("Wella Professionals", ("wella professionals", "wella profissional", "wella")),
    BrandDefinition("Redken", ("redken",)),
    BrandDefinition("Eucerin", ("eucerin",)),
    BrandDefinition("Rabanne", ("rabanne", "paco rabanne")),
    BrandDefinition("Vichy", ("vichy",)),
    BrandDefinition("Garnier", ("garnier",)),
    BrandDefinition("ISDIN", ("isdin",)),
    BrandDefinition("Karen Bachini Beauty", ("karen bachini beauty", "karen bachini")),
    BrandDefinition("Dapop", ("dapop",)),
    BrandDefinition("Guava", ("guava",)),
    BrandDefinition("Latika", ("latika",)),
    BrandDefinition("Medicube", ("medicube",)),
    BrandDefinition("SKIN1004", ("skin1004", "skin 1004")),
    BrandDefinition("Kerasys", ("kerasys",)),
    BrandDefinition("Banila Co", ("banila co", "banila")),
    BrandDefinition("Laneige", ("laneige",)),
    BrandDefinition("Skelt", ("skelt",)),
    BrandDefinition("NARS", ("nars",)),
    BrandDefinition("La Roche", ("la roche", "la roche posay")),
    BrandDefinition("Avene", ("avene",)),
    BrandDefinition("Bioderma", ("bioderma",)),
    BrandDefinition("Neutrogena", ("neutrogena",)),
    BrandDefinition("Payot", ("payot",)),
    BrandDefinition("Benefit Cosmetics", ("benefit cosmetics", "benefit", "benefite")),
)


def normalize_brand_text(value: object) -> str:
    """Normalize text for accent-insensitive, punctuation-tolerant brand matching."""
    text = str(value or "").replace("'", "").replace("’", "").replace("`", "")
    ascii_text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", ascii_text.lower())
    return " ".join(normalized.split())


def parse_configured_brand_names(raw_value: str | None) -> tuple[str, ...] | None:
    """Parse the optional env override for allowed beauty brands."""
    if raw_value is None or not raw_value.strip():
        return None

    delimiter = ";" if ";" in raw_value else ","
    values = tuple(part.strip() for part in raw_value.split(delimiter) if part.strip())
    return values or None


def _alias_pattern(alias: str) -> re.Pattern[str]:
    normalized_alias = normalize_brand_text(alias)
    escaped_tokens = [re.escape(token) for token in normalized_alias.split()]
    pattern = r"(?:^|\s)" + r"\s+".join(escaped_tokens) + r"(?:\s|$)"
    return re.compile(pattern)


def _definition_lookup() -> dict[str, BrandDefinition]:
    lookup: dict[str, BrandDefinition] = {}
    for definition in DEFAULT_BEAUTY_BRAND_DEFINITIONS:
        keys = (definition.canonical, *definition.aliases)
        for key in keys:
            lookup[normalize_brand_text(key)] = definition
    return lookup


def resolve_brand_definitions(
    allowed_brand_names: Iterable[str] | None = None,
) -> tuple[BrandDefinition, ...]:
    """Resolve default definitions or a configured subset/custom allowlist."""
    selected_names = tuple(
        name for name in (allowed_brand_names or ()) if str(name or "").strip()
    )
    if not selected_names:
        return DEFAULT_BEAUTY_BRAND_DEFINITIONS

    lookup = _definition_lookup()
    definitions: list[BrandDefinition] = []
    seen: set[str] = set()
    for name in selected_names:
        normalized_name = normalize_brand_text(name)
        definition = lookup.get(normalized_name) or BrandDefinition(
            str(name).strip(),
            (str(name).strip(),),
        )
        if definition.canonical in seen:
            continue
        definitions.append(definition)
        seen.add(definition.canonical)
    return tuple(definitions)


def match_allowed_beauty_brand(
    title: object,
    *,
    allowed_brand_names: Iterable[str] | None = None,
) -> BrandMatch:
    """Return the allowlisted brand found in a marketplace title, if any."""
    normalized_title = normalize_brand_text(title)
    if not normalized_title:
        return BrandMatch(False)

    for definition in resolve_brand_definitions(allowed_brand_names):
        for alias in definition.aliases:
            normalized_alias = normalize_brand_text(alias)
            if not normalized_alias:
                continue
            if _alias_pattern(normalized_alias).search(normalized_title):
                return BrandMatch(True, brand=definition.canonical, alias=alias)
    return BrandMatch(False)


def passes_beauty_brand_filter(
    deal: dict,
    *,
    allowed_brand_names: Iterable[str] | None = None,
) -> BrandMatch:
    """Only beauty profile deals must match the brand allowlist."""
    profile = str(deal.get("product_profile") or "").strip().lower()
    if profile != "beauty":
        return BrandMatch(True)
    return match_allowed_beauty_brand(
        deal.get("title", ""),
        allowed_brand_names=allowed_brand_names,
    )
