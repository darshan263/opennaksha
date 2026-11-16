"""Navsari Municipal Corporation (NMC): TP schemes 1–4 and DP 2039. See docs/sources.md §11.2.

One static page, ``/pdf/townplaning&estate``: ``table.table3`` with ``No. | File Name | Download``
(20 rows on 2026-11-16). Every row is one PDF behind
``/Home/DownloadDocument/<32 hex>?filename=Navsari_contentpdf_<timestamp>.pdf``.
The file name column is the only description, e.g.:

- ``FINAL TP Scheme No. 1 MAP``      → TP 1 map
- ``T.P.1 final NOTIFICATION``       → TP 1 notification (final)
- ``DRAFT T.P.1 NOTIFICATION``       → TP 1 notification (draft)
- ``F Form Final TP Scheme - 4``     → TP 4, other
- ``Devlopment Plan 2039 ( Navsari D.P. Map)`` → DP 2039 map
- ``NUDA NOTIFICATION 9-12-2015``, ``G.D.C.R..Part 1`` → DP 2039 notification / other

A TP scheme with a final map or final notification is "final". Rows that match nothing are
logged and skipped.
"""

from __future__ import annotations

import logging
import re

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind, Status
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, links, soup_of

log = logging.getLogger(__name__)

LISTING_URL = "https://nmc.gujarat.gov.in/pdf/townplaning&estate"
DP_NO = "2039"
DP_LABEL = "Development Plan 2039 (Navsari)"
MIN_TP = 3

_TP_MAP = re.compile(r"^final\s+tp\s+scheme\s+no\.?\s*(\d+)\s+map$", re.IGNORECASE)
_TP_NOTE = re.compile(r"^(draft\s+)?t\.?\s*p\.?\s*(\d+)\s+(final\s+)?notification$", re.IGNORECASE)
_TP_FORM = re.compile(r"^(\w)\s+form\s+final\s+tp\s+scheme\s*-?\s*(\d+)$", re.IGNORECASE)
_DP_MAP = re.compile(r"d[ea]?v[ea]?lop?e?ment\s+plan\s+2039", re.IGNORECASE)
_DP_NOTE = re.compile(r"^nuda\s+notification", re.IGNORECASE)
_GDCR = re.compile(r"^g\.?\s*d\.?\s*c\.?\s*r", re.IGNORECASE)


class NavsariNMC(BaseScraper):
    city_id = "navsari"
    authority = "NMC"
    scheme_types = frozenset({"TP", "DP"})

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    table = soup_of(html).select_one("table.table3")
    if table is None:
        raise ScraperError("NMC town planning: table.table3 not found (layout changed?)")

    tp_files: dict[str, list[DiscoveredFile]] = {}
    tp_final: set[str] = set()

    def add_tp(no: str, kind: FileKind, *, final: bool, title: str, url: str) -> None:
        tp_files.setdefault(no, []).append(DiscoveredFile(kind=kind, title=title, url=url))
        if final:
            tp_final.add(no)

    dp_files: list[DiscoveredFile] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        name = clean(cells[1].get_text(" "))
        urls = links(cells[2], page_url)
        if not name or not urls:
            continue
        url = urls[0][0]

        if m := _TP_MAP.match(name):
            add_tp(m.group(1), "map", final=True, title=name, url=url)
        elif m := _TP_NOTE.match(name):
            add_tp(m.group(2), "notification", final=bool(m.group(3)), title=name, url=url)
        elif m := _TP_FORM.match(name):
            add_tp(m.group(2), "other", final=True, title=name, url=url)
        elif _DP_MAP.search(name):
            dp_files.append(DiscoveredFile(kind="map", title=name, url=url))
        elif _DP_NOTE.match(name):
            dp_files.append(DiscoveredFile(kind="notification", title=name, url=url))
        elif _GDCR.match(name):
            dp_files.append(DiscoveredFile(kind="other", title=name, url=url))
        else:
            log.warning("NMC: unrecognised row %r, skipped", name)

    if len(tp_files) < MIN_TP:
        raise ScraperError(f"NMC town planning: only {len(tp_files)} TP schemes (layout changed?)")

    found: list[DiscoveredScheme] = []
    for no in sorted(tp_files, key=int):
        files = sorted(tp_files[no], key=lambda f: f.kind != "map")  # map first
        status: Status = "final" if no in tp_final else "draft"
        found.append(
            DiscoveredScheme(
                city_id="navsari",
                authority="NMC",
                scheme_type="TP",
                scheme_no=no,
                status=status,
                source_page_url=page_url,
                files=files,
            )
        )
    if any(f.kind == "map" for f in dp_files):
        found.append(
            DiscoveredScheme(
                city_id="navsari",
                authority="NMC",
                scheme_type="DP",
                scheme_no=DP_NO,
                name_en="Navsari",
                status="unknown",
                status_label=DP_LABEL,
                source_page_url=page_url,
                files=sorted(dp_files, key=lambda f: f.kind != "map"),
            )
        )
    else:
        log.warning("NMC: no DP 2039 map row found")
    return found
