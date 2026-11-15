"""Surat Municipal Corporation (SMC) development plan sheets, by village. See docs/sources.md §10.6.

One static page, ``/Departments/TownPlanningDevelopmentPlans``: ``table.table-customized`` with
``Sheet No.`` | ``Name``. 26 rows, sheets A–Z. The Name cell is one link whose text is the
comma-separated list of villages on that sheet; the link is a root-relative ZIP
(``/Images/Departments/TownPlanning/<L>-<villages>.zip``) holding one large JPG of the sheet
(checked for sheet P: a 4000×3527 JPG with survey numbers, village boundaries and zoning).

The page does not state the plan year, so the label says so. Village names are kept exactly as
SMC publishes them (some are cut short on the page, e.g. "Oviy"); only repeats are dropped.

One record per sheet: scheme_type "VILLAGE", scheme_no = the sheet letter,
name_en = the village list.
"""

from __future__ import annotations

import logging
import re

from opennaksha.models import DiscoveredFile, DiscoveredScheme
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, links, soup_of
from opennaksha.scrapers.uda_common import find_col, require_min

log = logging.getLogger(__name__)

LISTING_URL = "https://www.suratmunicipal.gov.in/Departments/TownPlanningDevelopmentPlans"

STATUS_LABEL = (
    "Older SMC development plan sheet, by village (plan year not stated by SMC; "
    "see SUDA DP-2035 for the current plan)"
)

MIN_SHEETS = 20

_SHEET = re.compile(r"^[A-Z]{1,2}\d?$")


class SuratSMCVillage(BaseScraper):
    city_id = "surat"
    authority = "SMC"
    scheme_types = frozenset({"VILLAGE"})

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def village_list(text: str) -> str:
    """'Variav, Segavasyadla, Gothan, Vaswari, Variav' → 'Variav, Segavasyadla, Gothan, Vaswari'."""
    seen: dict[str, str] = {}
    for part in clean(text).split(","):
        name = clean(part).strip(" .")
        if name and name.lower() not in seen:
            seen[name.lower()] = name
    return ", ".join(seen.values())


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    table = next(
        (
            t
            for t in soup.select("table.table-customized")
            if "sheet" in clean(t.get_text(" ")[:200]).lower()
        ),
        None,
    )
    if table is None:
        raise ScraperError("SMC DP sheets: table with a 'Sheet No.' column not found")
    headers = [clean(th.get_text(" ")).lower() for th in table.select("thead th")]
    sheet_col = find_col(headers, "sheet")
    name_col = find_col(headers, "name")

    found: list[DiscoveredScheme] = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td")
        if len(cells) <= max(sheet_col, name_col):
            continue
        sheet = clean(cells[sheet_col].get_text(" ")).upper()
        if not _SHEET.match(sheet):
            log.warning("SMC DP sheets: skipping row with sheet %r", sheet)
            continue
        cell_links = links(cells[name_col], page_url)
        if not cell_links:
            log.warning("SMC DP sheets: sheet %s has no link", sheet)
            continue
        villages = village_list(cell_links[0][1] or cells[name_col].get_text(" "))
        if not villages:
            log.warning("SMC DP sheets: sheet %s has no village names", sheet)
            continue
        found.append(
            DiscoveredScheme(
                city_id="surat",
                authority="SMC",
                scheme_type="VILLAGE",
                scheme_no=sheet,
                name_en=villages,
                status="unknown",
                status_label=STATUS_LABEL,
                source_page_url=page_url,
                files=[
                    DiscoveredFile(kind="map", title=f"Sheet {sheet}", url=url)
                    for url, _text in cell_links
                ],
            )
        )
    if len({s.scheme_no for s in found}) != len(found):
        raise ScraperError("SMC DP sheets: the same sheet letter appears twice")
    require_min(found, MIN_SHEETS, "SMC DP sheets")
    return found
