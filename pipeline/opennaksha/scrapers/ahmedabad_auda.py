"""Ahmedabad Urban Development Authority (AUDA). See docs/sources.md → AUDA.

One server-rendered ASP.NET page, ``table.gridtable.myTable`` (94 rows, no pagination):
Sr. No. | T.P.S. No | Area/Village | draft / preliminary / final sanction dates (dd/mm/yyyy) |
"F" Form. Status is the latest filled stage. The map is a JPG whose root-relative URL sits in
a hidden input ``#Body_container_rptTPScheme_hfImageUrl_<i>`` in the Area/Village cell (the
page's JS treats a bare ``/uploads/TPScheme/`` as "no image"). Scheme numbers repeat across
villages (six "1"s), so the village is part of the id.
"""

from __future__ import annotations

import logging
import re

from opennaksha.models import DiscoveredFile, DiscoveredScheme
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import abs_url, clean, links, parse_dmy, soup_of
from opennaksha.scrapers.uda_common import (
    find_col,
    merge_duplicates,
    require_min,
    stage_from_dates,
    tidy_area,
)

log = logging.getLogger(__name__)

LISTING_URL = "https://www.auda.org.in/TPScheme.aspx"

MIN_SCHEMES = 50
_MAP_INPUT = re.compile(r"hfImageUrl")


class AhmedabadAUDA(BaseScraper):
    city_id = "ahmedabad"
    authority = "AUDA"

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    table = soup.select_one("table.gridtable.myTable")
    if table is None:
        raise ScraperError("AUDA: table.gridtable.myTable not found")
    headers = [clean(th.get_text(" ")).lower() for th in table.select("thead th")]
    no_col = find_col(headers, "t.p.s")
    area_col = find_col(headers, "area", "village")
    draft_col = find_col(headers, "draft")
    prelim_col = find_col(headers, "preliminary")
    final_col = find_col(headers, "final")
    fform_col = find_col(headers, "form")
    last_col = max(no_col, area_col, draft_col, prelim_col, final_col)

    found: list[DiscoveredScheme] = []
    for tr in table.select("tbody > tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) <= last_col:
            continue
        no = re.sub(r"\s+", "", clean(cells[no_col].get_text(" "))).upper()
        area = tidy_area(cells[area_col].get_text(" "))
        if not no:
            log.warning("AUDA: row without scheme number (area %r)", area)
            continue
        status, label, status_date = stage_from_dates(
            parse_dmy(cells[draft_col].get_text()),
            parse_dmy(cells[prelim_col].get_text()),
            parse_dmy(cells[final_col].get_text()),
        )
        files: list[DiscoveredFile] = []
        hidden = cells[area_col].find("input", id=_MAP_INPUT)
        value = clean(str(hidden.get("value", ""))) if hidden is not None else ""
        if value and not value.endswith("/"):
            files.append(
                DiscoveredFile(kind="map", title="Map (JPG)", url=abs_url(page_url, value))
            )
        if fform_col < len(cells):
            fform_links = links(cells[fform_col], page_url)
            for n, (url, _text) in enumerate(fform_links, 1):
                title = f"F-Form ({n})" if len(fform_links) > 1 else "F-Form"
                files.append(DiscoveredFile(kind="other", title=title, url=url))
        found.append(
            DiscoveredScheme(
                city_id="ahmedabad",
                authority="AUDA",
                scheme_type="TP",
                scheme_no=no,
                name_en=area,
                status=status,
                status_label=label,
                status_date=status_date,
                source_page_url=page_url,
                files=files,
            )
        )
    found = merge_duplicates(found)
    require_min(found, MIN_SCHEMES, "AUDA")
    return found
