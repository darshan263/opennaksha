"""Deterministic scheme ids.

PLAN.md §5 proposed ``{city_id}-{type}-{scheme_no}``. Milestone 1 research showed that collides:
SMC alone has three different "TP 1" schemes (Laldarwaja, Udhna-Majura, Vesu), AMC has fifteen
"1"s, and SMC and SUDA both have a TP 86. So the id also carries the authority and the area name:

    {city_id}-{authority}-{type}-{scheme_no}[-{area}]

All parts lowercase; anything that isn't a-z/0-9 becomes a dash (see docs/decisions.md).
"""

import re
import unicodedata

SCHEME_TYPES = frozenset({"TP", "DP", "LAP", "VILLAGE"})

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    """ASCII slug: 'Udhna-Majura (Part)' → 'udhna-majura-part'. Non-Latin text is dropped."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _NON_ALNUM.sub("-", ascii_text.lower()).strip("-")


def make_scheme_id(
    city_id: str,
    authority: str,
    scheme_type: str,
    scheme_no: str,
    area: str | None = None,
) -> str:
    """
    >>> make_scheme_id("surat", "SMC", "TP", "1", "Laldarwaja")
    'surat-smc-tp-1-laldarwaja'
    >>> make_scheme_id("ahmedabad", "AMC", "TP", "152/G", "Ghatlodia")
    'ahmedabad-amc-tp-152-g-ghatlodia'
    """
    if scheme_type.upper() not in SCHEME_TYPES:
        raise ValueError(f"unknown scheme_type: {scheme_type!r}")
    parts = [slug(city_id), slug(authority), slug(scheme_type), slug(scheme_no)]
    if not all(parts):
        raise ValueError("city_id, authority, scheme_type and scheme_no must be non-empty")
    area_slug = slug(area or "")
    if area_slug:
        parts.append(area_slug)
    return "-".join(parts)
