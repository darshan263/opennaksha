"""Scraper interface (PLAN.md §6)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from opennaksha.http import PoliteClient
from opennaksha.models import DiscoveredScheme, SchemeType, owner_key, source_id


class ScraperError(Exception):
    """The source site could not be scraped (down, layout changed, ...)."""


class BaseScraper(ABC):
    city_id: ClassVar[str]
    authority: ClassVar[str]
    # Hosts with broken TLS chains (documented in docs/sources.md). Verification is skipped
    # for these hosts only.
    insecure_hosts: ClassVar[frozenset[str]] = frozenset()
    # Hosts needing TLS legacy renegotiation (certificates still verified).
    legacy_tls_hosts: ClassVar[frozenset[str]] = frozenset()
    enabled: ClassVar[bool] = True
    # Map types this scraper produces (and owns) for its authority.
    scheme_types: ClassVar[frozenset[SchemeType]] = frozenset({"TP"})

    def __init__(self, client: PoliteClient) -> None:
        self.client = client

    @classmethod
    def source_id(cls) -> str:
        """e.g. ``surat-suda`` (TP scraper) or ``surat-suda-dp`` (DP scraper)."""
        base = source_id(cls.city_id, cls.authority)
        if cls.scheme_types == frozenset({"TP"}):
            return base
        return base + "-" + "-".join(sorted(t.lower() for t in cls.scheme_types))

    @classmethod
    def owner_keys(cls) -> set[str]:
        return {owner_key(cls.city_id, cls.authority, t) for t in cls.scheme_types}

    @abstractmethod
    def discover(self) -> list[DiscoveredScheme]:
        """Return scheme metadata and file URLs found on the source site.

        Must raise (any exception) if the site can't be read or yields nothing it
        recognises, so the run keeps the previous data for this source instead of
        marking every scheme as removed.
        """
