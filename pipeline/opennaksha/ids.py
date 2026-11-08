"""Deterministic scheme ids (PLAN.md §5)."""

import re

SCHEME_TYPES = frozenset({"TP", "DP", "LAP", "VILLAGE"})

# Runs of whitespace, forward slashes and backslashes become a single dash.
_SEPARATORS = re.compile(r"[\s/\\]+")
_DASHES = re.compile(r"-{2,}")


def make_scheme_id(city_id: str, scheme_type: str, scheme_no: str) -> str:
    """Return ``{city_id}-{type}-{scheme_no}``, lowercase, with slashes and spaces as dashes.

    >>> make_scheme_id("surat", "TP", "57")
    'surat-tp-57'
    >>> make_scheme_id("ahmedabad", "TP", "12/A")
    'ahmedabad-tp-12-a'
    """
    if scheme_type.upper() not in SCHEME_TYPES:
        raise ValueError(f"unknown scheme_type: {scheme_type!r}")
    parts = [city_id, scheme_type, scheme_no]
    if any(not p.strip() for p in parts):
        raise ValueError("city_id, scheme_type and scheme_no must be non-empty")
    raw = "-".join(_SEPARATORS.sub("-", p.strip()) for p in parts)
    return _DASHES.sub("-", raw.lower()).strip("-")
