"""Rajkot Urban Development Authority (RUDA). See docs/sources.md → RUDA.

One static page, ``table.tbl2`` (11 recent schemes; older ones are not on the site). No thead:
the first row has the ``<th>``s: Sr. No. | T.P.S. NO. | Area/village | draft | preliminary |
final sanction dates | Submitted to Govt. for Draft Approval (dd/mm/yyyy or '-') | Plan |
F forms. Status is the latest filled stage; a scheme only submitted to Govt. is a draft with
label "Draft – submitted to Govt. for sanction". Links are relative and may contain spaces.
"""

from __future__ import annotations

import logging
import re

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, links, parse_dmy, soup_of
from opennaksha.scrapers.uda_common import (
    find_col,
    merge_duplicates,
    require_min,
    stage_from_dates,
    tidy_area,
)

log = logging.getLogger(__name__)

LISTING_URL = "https://rajkotuda.com/town-planning-scheme.html"

MIN_SCHEMES = 5


class RajkotRUDA(BaseScraper):
    city_id = "rajkot"
    authority = "RUDA"

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    table = soup.select_one("table.tbl2")
    if table is None:
        raise ScraperError("RUDA: table.tbl2 not found")
    rows = table.find_all("tr")
    header_row = next((tr for tr in rows if tr.find("th")), None)
    if header_row is None:
        raise ScraperError("RUDA: no header row in table.tbl2")
    headers = [clean(th.get_text(" ")).lower() for th in header_row.find_all(["th", "td"])]
    no_col = find_col(headers, "t.p.s")
    area_col = find_col(headers, "area", "village")
    submitted_col = find_col(headers, "submitted")
    draft_col = find_col(headers, "draft", exclude=("submitted",))
    prelim_col = find_col(headers, "priliminary", "preliminary")
    final_col = find_col(headers, "final")
    plan_col = find_col(headers, "plan")
    fform_col = find_col(headers, "f form", "f-form")
    file_cols: list[tuple[int, FileKind, str]] = [
        (plan_col, "map", "Plan"),
        (fform_col, "other", "F-Form"),
    ]
    last_col = max(no_col, area_col, submitted_col, draft_col, prelim_col, final_col)

    found: list[DiscoveredScheme] = []
    for tr in rows:
        if tr is header_row:
            continue
        cells = tr.find_all("td", recursive=False)
        if len(cells) <= last_col:
            continue
        no = re.sub(r"\s+", "", clean(cells[no_col].get_text(" "))).upper()
        if not no:
            continue
        status, label, status_date = stage_from_dates(
            parse_dmy(cells[draft_col].get_text()),
            parse_dmy(cells[prelim_col].get_text()),
            parse_dmy(cells[final_col].get_text()),
            parse_dmy(cells[submitted_col].get_text()),
        )
        files: list[DiscoveredFile] = []
        for col, kind, title in file_cols:
            if col >= len(cells):
                continue
            cell_links = links(cells[col], page_url)
            for n, (url, _text) in enumerate(cell_links, 1):
                t = f"{title} ({n})" if len(cell_links) > 1 else title
                files.append(DiscoveredFile(kind=kind, title=t, url=url))
        found.append(
            DiscoveredScheme(
                city_id="rajkot",
                authority="RUDA",
                scheme_type="TP",
                scheme_no=no,
                name_en=tidy_area(cells[area_col].get_text(" ")),
                status=status,
                status_label=label,
                status_date=status_date,
                source_page_url=page_url,
                files=files,
            )
        )
    found = merge_duplicates(found)
    require_min(found, MIN_SCHEMES, "RUDA")
    return found
