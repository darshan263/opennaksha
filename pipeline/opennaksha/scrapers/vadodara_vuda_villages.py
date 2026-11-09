"""Vadodara Urban Development Authority (VUDA) DP village maps. See docs/sources.md §10.4.

One static page, ``dpvillagemaps.htm``. Heading ``h3.decorative-heading`` "DP VILLAGE MAPS Under
SECTION 17" + ``span.small-text`` "(2nd Revised Development Plan 18-01-2012)", then one
``table.styled-table``: Sr.No | Name | Download Map. A village with several sheets has
``rowspan`` on Sr.No and Name; its continuation rows hold only the link cell. Links are
relative with raw spaces (``download/DP MAPS/<FOLDER>/<file>.pdf``). The village name comes from
the Name cell (the folder spelling sometimes differs); the sheet title is the link text
(``V95 AAMALIYARA``, ``TP-1``, ``ANGHADH-2`` …; the ``V<n>`` labels are not explained on the page).

One record per village: scheme_type "VILLAGE", scheme_no "DP-<year of the plan date>".
"""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from opennaksha.models import DiscoveredFile, DiscoveredScheme
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, expand_table, links, soup_of
from opennaksha.scrapers.uda_common import find_col, require_min, tidy_area

log = logging.getLogger(__name__)

LISTING_URL = "https://www.vuda.co.in/dpvillagemaps.htm"

MIN_VILLAGES = 80

_SECTION = re.compile(r"SECTION\s+(\d+)", re.IGNORECASE)
_PLAN_DATE = re.compile(r"\b\d{1,2}[-./]\d{1,2}[-./](\d{4})\b")


class VadodaraVUDAVillages(BaseScraper):
    city_id = "vadodara"
    authority = "VUDA"
    scheme_types = frozenset({"VILLAGE"})

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def parse_heading(soup: BeautifulSoup) -> tuple[str, str]:
    """(status_label, scheme_no) from the page heading.

    'DP VILLAGE MAPS Under SECTION 17' + '(2nd Revised Development Plan 18-01-2012)' →
    ('DP village map (Sec. 17, 2nd Revised Development Plan 18-01-2012)', 'DP-2012').
    """
    h = soup.select_one("h3.decorative-heading")
    if h is None:
        raise ScraperError("VUDA villages: heading h3.decorative-heading not found")
    sec = _SECTION.search(h.get_text(" "))
    small = h.select_one(".small-text")
    plan = clean(small.get_text(" ") if small else "").strip("() ")
    date_m = _PLAN_DATE.search(plan)
    if sec is None or not plan or date_m is None:
        raise ScraperError(
            f"VUDA villages: unexpected heading {clean(h.get_text(' '))!r} "
            "(expected 'Under SECTION n' and '(… Development Plan dd-mm-yyyy)')"
        )
    return f"DP village map (Sec. {sec.group(1)}, {plan})", f"DP-{date_m.group(1)}"


def _title(text: str, url: str) -> str:
    """Link text without a trailing '.pdf' ('V29 AKOTA.pdf'); the file stem if empty."""
    t = clean(re.sub(r"\.pdf\s*$", "", text, flags=re.IGNORECASE))
    if not t:
        t = clean(unquote(urlsplit(url).path.rsplit("/", 1)[-1]).rsplit(".", 1)[0])
    return t


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    label, scheme_no = parse_heading(soup)
    table = soup.select_one("table.styled-table")
    if table is None:
        raise ScraperError("VUDA villages: table.styled-table not found")
    grid = expand_table(table)
    header_i = next(
        (
            i
            for i, row in enumerate(grid)
            if row and all(c is not None and c.name == "th" for c in row)
        ),
        None,
    )
    if header_i is None:
        raise ScraperError("VUDA villages: no header row in table.styled-table")
    headers = [clean(c.get_text(" ")).lower() for c in grid[header_i] if c is not None]
    name_col = find_col(headers, "name")
    map_col = find_col(headers, "map", "download")

    # village name → [(title, url)], in page order. A village listed twice is merged.
    villages: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    for row in grid[header_i + 1 :]:
        if len(row) <= max(name_col, map_col):
            continue
        name = tidy_area(row[name_col].get_text(" ") if row[name_col] else "")
        if not name:
            continue
        cell_links = [
            (u, t) for u, t in links(row[map_col], page_url) if u.lower().endswith(".pdf")
        ]
        if not cell_links:
            log.warning("VUDA villages: row for %r has no PDF link", name)
        key = name.upper()
        _, sheets = villages.setdefault(key, (name, []))
        for url, text in cell_links:
            if any(u == url for _t, u in sheets):
                continue
            sheets.append((_title(text, url), url))

    found: list[DiscoveredScheme] = []
    for name, sheets in villages.values():
        if not sheets:
            continue
        files: list[DiscoveredFile] = []
        titles: set[str] = set()
        for title, url in sheets:
            t, n = title, 2
            while t in titles:  # keep titles unique within a village
                t, n = f"{title} ({n})", n + 1
            titles.add(t)
            files.append(DiscoveredFile(kind="map", title=t, url=url))
        found.append(
            DiscoveredScheme(
                city_id="vadodara",
                authority="VUDA",
                scheme_type="VILLAGE",
                scheme_no=scheme_no,
                name_en=name,
                status="unknown",
                status_label=label,
                source_page_url=page_url,
                files=files,
            )
        )
    require_min(found, MIN_VILLAGES, "VUDA villages")
    return found
