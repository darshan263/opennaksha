"""One scraper module per authority (and map type). Register new scrapers in ``all_scrapers``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opennaksha.scrapers.base import BaseScraper


def all_scrapers() -> list[type[BaseScraper]]:
    from opennaksha.scrapers.ahmedabad_amc import AhmedabadAMC
    from opennaksha.scrapers.ahmedabad_auda import AhmedabadAUDA
    from opennaksha.scrapers.ahmedabad_auda_dp import AhmedabadAUDADP
    from opennaksha.scrapers.gandhinagar_guda import GandhinagarGUDA, GandhinagarGUDADP
    from opennaksha.scrapers.rajkot_ruda import RajkotRUDA
    from opennaksha.scrapers.rajkot_ruda_dp import RajkotRUDADP
    from opennaksha.scrapers.surat_smc import SuratSMC
    from opennaksha.scrapers.surat_suda import SuratSUDA
    from opennaksha.scrapers.surat_suda_dp import SuratSUDADP
    from opennaksha.scrapers.vadodara_vuda import VadodaraVUDA
    from opennaksha.scrapers.vadodara_vuda_villages import VadodaraVUDAVillages

    return [
        # TP schemes
        SuratSMC,
        SuratSUDA,
        AhmedabadAMC,
        AhmedabadAUDA,
        RajkotRUDA,
        VadodaraVUDA,
        GandhinagarGUDA,
        # Development plans
        SuratSUDADP,
        AhmedabadAUDADP,
        RajkotRUDADP,
        GandhinagarGUDADP,
        # Village maps
        VadodaraVUDAVillages,
    ]
