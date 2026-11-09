"""Ahmedabad Urban Development Authority (AUDA) development plans. See docs/sources.md §10.2.

One server-rendered ASP.NET page, ``https://www.auda.org.in/RDP/``, with one ``table.gridtable``
(Sr. No. | Title | View Detail). Each row's title is in ``span.name`` and its file in a
"Click Here" link. Map rows are titled "AUDA REVISED DEVELOPMENT PLAN <year> MAP"; one record
is made per plan year that has a map row. The other rows (notifications, notes, GDCR) are
attached to the plan whose year appears in their title, else to the newest plan.

Links are published as ``http://www.auda.org.in/uploads/Assets/rdp/<file>`` with raw spaces;
the research found they 301 to https, so they are stored as https (spaces percent-encoded).
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit, urlunsplit

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, links, soup_of
from opennaksha.scrapers.uda_common import find_col

log = logging.getLogger(__name__)

LISTING_URL = "https://www.auda.org.in/RDP/"

AREA_NAME = "AUDA area"
OLD_PLAN_LABEL = "Earlier development plan (superseded)"
# Hosts whose http:// links were verified to 301 to https (docs/sources.md §10.2).
HTTPS_HOSTS = frozenset({"www.auda.org.in", "auda.org.in"})

MIN_ROWS = 8
MIN_PLANS = 3

_MAP_TITLE = re.compile(r"development\s+plan\D*?((?:19|20)\d{2})\D*\bmap\b", re.IGNORECASE)
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
# A real file link ends in an extension; see the truncated-href note in parse_listing.
_HAS_EXT = re.compile(r"\.[A-Za-z0-9]{2,5}$")
_GDCR = re.compile(r"gdcr|development\s+control\s+regulation", re.IGNORECASE)
_NOTIFICATION = re.compile(
    r"notif|notication|gazet|gazzate|corrigendum|section\s+\d+|sec\.", re.IGNORECASE
)


class AhmedabadAUDADP(BaseScraper):
    city_id = "ahmedabad"
    authority = "AUDA"
    scheme_types = frozenset({"DP"})

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    table = soup.select_one("table.gridtable")
    if table is None:
        raise ScraperError("AUDA DP: table.gridtable not found")
    headers = [clean(th.get_text(" ")).lower() for th in table.select("thead th")]
    title_col = find_col(headers, "title")
    link_col = find_col(headers, "view", "detail", "download")

    rows: list[tuple[str, str]] = []  # (title, url)
    for tr in table.select("tbody tr") or table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) <= max(title_col, link_col):
            continue
        span = cells[title_col].select_one("span.name")
        title = clean((span or cells[title_col]).get_text(" "))
        for url, _text in links(cells[link_col], page_url):
            # Row "Gujarat Nagar Rachna Adhiniyam 1976 Act under Sec..26, 27, 28 & 49" has its
            # href cut off at a comma ("…Sec..26, 27,"), which returns 404. Any href whose last
            # path segment has no file extension is treated as broken like this and skipped.
            if not _HAS_EXT.search(urlsplit(url).path):
                log.warning("AUDA DP: skipping broken link %r for row %r", url, title)
                continue
            rows.append((title, _https(url)))
    if len(rows) < MIN_ROWS:
        raise ScraperError(
            f"AUDA DP: only {len(rows)} linked rows (expected at least {MIN_ROWS}); layout change?"
        )

    # Pass 1: plan records from map rows, in page order.
    plans: dict[str, list[DiscoveredFile]] = {}
    map_titles: dict[str, str] = {}
    others: list[tuple[str, str]] = []
    for title, url in rows:
        m = _MAP_TITLE.search(title)
        if m:
            year = m.group(1)
            plans.setdefault(year, []).append(DiscoveredFile(kind="map", title=title, url=url))
            map_titles.setdefault(year, title)
        else:
            others.append((title, url))
    if len(plans) < MIN_PLANS:
        raise ScraperError(
            f"AUDA DP: only {len(plans)} plan map rows (expected at least {MIN_PLANS}); "
            "layout change?"
        )
    newest = max(plans, key=int)

    # Pass 2: other rows go to the plan named in their title, else to the newest plan.
    for title, url in others:
        year = next((y for y in _YEAR.findall(title) if y in plans), newest)
        plans[year].append(DiscoveredFile(kind=_kind(title), title=title, url=url))

    found: list[DiscoveredScheme] = []
    for year in sorted(plans, key=int):
        is_newest = year == newest
        found.append(
            DiscoveredScheme(
                city_id="ahmedabad",
                authority="AUDA",
                scheme_type="DP",
                scheme_no=year,
                name_en=AREA_NAME,
                status="final" if is_newest else "unknown",
                status_label=map_titles[year] if is_newest else OLD_PLAN_LABEL,
                source_page_url=page_url,
                files=_dedupe(plans[year]),
            )
        )
    return found


def _kind(title: str) -> FileKind:
    if _GDCR.search(title):
        return "other"
    if _NOTIFICATION.search(title):
        return "notification"
    # "Note on Revised Development Plan 2021", "Affordable Housing": explanatory documents.
    return "other"


def _https(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.hostname in HTTPS_HOSTS:
        return urlunsplit(("https", *parts[1:]))
    return url


def _dedupe(files: list[DiscoveredFile]) -> list[DiscoveredFile]:
    """Drop repeated URLs (the pipeline keys file state by URL), keeping the first."""
    seen: set[str] = set()
    out: list[DiscoveredFile] = []
    for f in files:
        if f.url not in seen:
            seen.add(f.url)
            out.append(f)
    return out
