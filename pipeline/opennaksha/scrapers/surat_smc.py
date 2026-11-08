"""Surat Municipal Corporation (SMC). See docs/sources.md → SMC.

One page lists all TP schemes in 4 tables (final / preliminary / draft pending with TPO /
draft submitted to Govt.). Columns: Sr. No | Name | Area in Hectare | Notifications | Map |
B-Form or Redistribution Statement or F-Form. File links are root-relative with raw spaces.
The per-scheme "Notifications" pages are not crawled (one extra request per scheme for a
checklist of stage PDFs); see docs/decisions.md.
"""

from __future__ import annotations

import logging

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind, Status
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, links, parse_tps_name, soup_of

log = logging.getLogger(__name__)

LISTING_URL = "https://www.suratmunicipal.gov.in/Departments/TownPlanningAllTPSchemes"

# caption fragment (lowercase) → (status, status_label)
TABLES: list[tuple[str, Status, str | None]] = [
    ("final schemes", "final", None),
    ("preliminary", "preliminary", None),
    ("pending with town plan", "draft", "Draft – pending with Town Planning Officer"),
    ("submitted to govt", "draft", "Draft – submitted to Govt. for sanction"),
]

# column header (lowercase) → file kind
FILE_COLUMNS: dict[str, FileKind] = {
    "map": "map",
    "b-form": "other",
    "f-form": "other",
    "redistribution statement": "redistribution_statement",
}


class SuratSMC(BaseScraper):
    city_id = "surat"
    authority = "SMC"

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    tables = soup.select("table.table-customized")
    found: list[DiscoveredScheme] = []
    matched = 0
    for table in tables:
        caption = clean(table.caption.get_text(" ") if table.caption else "").lower()
        spec = next((t for t in TABLES if t[0] in caption), None)
        if spec is None:
            continue
        matched += 1
        _, status, label = spec
        headers = [clean(th.get_text(" ")).lower() for th in table.select("thead th")]
        try:
            name_col = headers.index("name")
        except ValueError as e:
            raise ScraperError(f"no Name column in table {caption!r}") from e
        for tr in table.select("tbody > tr"):
            if "total" in (tr.get("class") or []):
                continue
            cells = tr.find_all("td", recursive=False)
            if len(cells) <= name_col:
                continue
            parsed = parse_tps_name(cells[name_col].get_text(" "))
            if parsed is None:
                log.warning("SMC: unrecognised scheme name %r", clean(cells[name_col].text))
                continue
            no, area = parsed
            files: list[DiscoveredFile] = []
            for i, header in enumerate(headers):
                kind = FILE_COLUMNS.get(header)
                if kind is None or i >= len(cells):
                    continue
                cell_links = links(cells[i], page_url)
                for n, (url, _text) in enumerate(cell_links, 1):
                    title = header.title() if header != "b-form" else "B-Form"
                    if header == "f-form":
                        title = "F-Form"
                    if len(cell_links) > 1:
                        title = f"{title} ({n})"
                    files.append(DiscoveredFile(kind=kind, title=title, url=url))
            found.append(
                DiscoveredScheme(
                    city_id="surat",
                    authority="SMC",
                    scheme_type="TP",
                    scheme_no=no,
                    name_en=area,
                    status=status,
                    status_label=label,
                    source_page_url=page_url,
                    files=files,
                )
            )
    if matched < len(TABLES):
        raise ScraperError(f"expected {len(TABLES)} scheme tables, found {matched}")
    return found
