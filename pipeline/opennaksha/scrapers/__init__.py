"""One scraper module per authority. Register new scrapers in ``all_scrapers``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opennaksha.scrapers.base import BaseScraper


def all_scrapers() -> list[type[BaseScraper]]:
    return []
