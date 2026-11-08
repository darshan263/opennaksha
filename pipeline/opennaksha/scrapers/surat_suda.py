"""Surat Urban Development Authority (SUDA). See docs/sources.md → SUDA.

Two WordPress pages, each with ``div.entry-content table.table-customized`` tables whose
(hidden) caption names the status:

- "Sanction Tp Schemes": sanctioned draft (17) and sanctioned preliminary (5) tables, columns
  Sr. No. | Name | Area In Hectare | Notifications | Map | F-Form.
- "Submitted to Govt. TP Scheme": one table (11), no Notifications column, with stray ``<tr>``
  openers (rows with fewer than 5 cells are skipped).

All file links are absolute wp-content/uploads PDFs. The "Published TP Scheme" page (rows
commented out) and the "TP Scheme Intention" page (one empty row) are not scraped.
"""

from __future__ import annotations

import logging

from bs4 import Tag

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind, Status
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, links, parse_tps_name, soup_of
from opennaksha.scrapers.uda_common import (
    SUBMITTED_LABEL,
    find_col,
    merge_duplicates,
    require_min,
    tidy_area,
)

log = logging.getLogger(__name__)

SANCTIONED_URL = "https://www.sudaonline.org/services/tp-schemes/"
SUBMITTED_URL = "https://www.sudaonline.org/submitted-to-govt-tp-scheme/"

# caption fragment (lowercase) → (status, status_label)
TableSpec = tuple[str, Status, str | None]
PAGES: dict[str, list[TableSpec]] = {
    SANCTIONED_URL: [
        ("sanctioned draft", "draft", "Draft – sanctioned"),
        ("sanctioned preliminary", "preliminary", None),
    ],
    SUBMITTED_URL: [
        ("submitted to govt", "draft", SUBMITTED_LABEL),
    ],
}

# column header (lowercase) → (file kind, title)
FILE_COLUMNS: dict[str, tuple[FileKind, str]] = {
    "map": ("map", "Map"),
    "notifications": ("notification", "Notification"),
    "f-form": ("other", "F-Form"),
}

MIN_CELLS = 5
MIN_SCHEMES = 15


class SuratSUDA(BaseScraper):
    city_id = "surat"
    authority = "SUDA"

    def discover(self) -> list[DiscoveredScheme]:
        found: list[DiscoveredScheme] = []
        for url in PAGES:
            # Any fetch error propagates: partial data would mark schemes as removed.
            found += parse_page(self.client.get_text(url), url)
        found = merge_duplicates(found)
        require_min(found, MIN_SCHEMES, "SUDA")
        return found


def parse_page(html: str, page_url: str) -> list[DiscoveredScheme]:
    """Parse one SUDA listing page. Raises if any table expected on that page is missing."""
    specs = PAGES.get(page_url)
    if specs is None:
        raise ValueError(f"not a SUDA listing URL: {page_url}")
    soup = soup_of(html)
    found: list[DiscoveredScheme] = []
    matched: set[str] = set()
    for table in soup.select("div.entry-content table.table-customized"):
        caption = clean(table.caption.get_text(" ") if table.caption else "").lower()
        spec = next((t for t in specs if t[0] in caption), None)
        if spec is None:
            continue
        matched.add(spec[0])
        found += _parse_table(table, page_url, spec[1], spec[2])
    missing = [t[0] for t in specs if t[0] not in matched]
    if missing:
        raise ScraperError(f"SUDA {page_url}: tables not found: {missing}")
    return found


def _parse_table(
    table: Tag, page_url: str, status: Status, label: str | None
) -> list[DiscoveredScheme]:
    headers = [clean(th.get_text(" ")).lower() for th in table.select("thead th")]
    name_col = find_col(headers, "name")
    found: list[DiscoveredScheme] = []
    # Iterate every <tr> (not just tbody > tr): stray unclosed <tr>s make html.parser nest rows.
    for tr in table.find_all("tr"):
        if tr.find_parent("thead") is not None:
            continue
        cells = tr.find_all("td", recursive=False)
        if len(cells) < MIN_CELLS or len(cells) <= name_col:
            continue
        name = clean(cells[name_col].get_text(" "))
        parsed = parse_tps_name(name)
        if parsed is None:
            if name:
                log.warning("SUDA: unrecognised scheme name %r", name)
            continue
        no, area = parsed
        files: list[DiscoveredFile] = []
        for i, header in enumerate(headers):
            spec = FILE_COLUMNS.get(header)
            if spec is None or i >= len(cells):
                continue
            kind, title = spec
            cell_links = links(cells[i], page_url)
            for n, (url, _text) in enumerate(cell_links, 1):
                t = f"{title} ({n})" if len(cell_links) > 1 else title
                files.append(DiscoveredFile(kind=kind, title=t, url=url))
        found.append(
            DiscoveredScheme(
                city_id="surat",
                authority="SUDA",
                scheme_type="TP",
                scheme_no=no,
                name_en=tidy_area(area),
                status=status,
                status_label=label,
                source_page_url=page_url,
                files=files,
            )
        )
    return found
