"""One scraper module per authority. Register new scrapers in ``all_scrapers``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opennaksha.scrapers.base import BaseScraper


def all_scrapers() -> list[type[BaseScraper]]:
    from opennaksha.scrapers.ahmedabad_amc import AhmedabadAMC
    from opennaksha.scrapers.ahmedabad_auda import AhmedabadAUDA
    from opennaksha.scrapers.rajkot_ruda import RajkotRUDA
    from opennaksha.scrapers.surat_smc import SuratSMC
    from opennaksha.scrapers.surat_suda import SuratSUDA
    from opennaksha.scrapers.vadodara_vuda import VadodaraVUDA

    return [SuratSMC, SuratSUDA, AhmedabadAMC, AhmedabadAUDA, RajkotRUDA, VadodaraVUDA]
