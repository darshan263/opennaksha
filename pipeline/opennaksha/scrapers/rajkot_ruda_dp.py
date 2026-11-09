"""Rajkot Urban Development Authority (RUDA) development plans. See docs/sources.md §10.3.

Main page ``development-plans.html``: a ``ul.bullet3`` with one top-level ``<li>`` per plan.
The ``<li>``'s own text is the plan label ("Development Plan 1988", "Development Plans 2004",
"Development Plan 2031", "Existing Development Plans 2012"). Its links are either directly in
the ``<li>`` (the plan PDF, link text = label) or in a nested ``<ul>``:

    "Development Plans"                → main plan PDF       (kind "map")
    "Land Use"                         → land-use table PDF  (kind "other")
    "Grid wise existing …" (*.html)    → grid sheet page     (sheets, kind "map")

A grid sheet page is an ``<img usemap>`` + ``<map>`` of ``<area href="pdf/<folder>/<stem>.pdf">``
(29 sheets each, no link text). The older ``development-plans-download.html`` (``table.tbl1``,
``label | Download``) lists the same four main PDFs; its rows only add files not already found.

One record per plan: scheme_no "1988" / "2004" / "2031" / "existing-2012". The newest
non-"existing" plan is the current one ("final"); older ones are superseded ("unknown").
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from bs4 import Comment, NavigableString, Tag

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import abs_url, clean, soup_of
from opennaksha.scrapers.uda_common import require_min

log = logging.getLogger(__name__)

BASE = "https://rajkotuda.com/"
LISTING_URL = BASE + "development-plans.html"
DOWNLOAD_URL = BASE + "development-plans-download.html"

MIN_PLANS = 3
MIN_GRID_SHEETS = 10

SUPERSEDED_LABEL = "Earlier development plan (superseded)"

_YEAR = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class _Plan:
    scheme_no: str
    label: str
    year: int
    existing: bool
    files: list[DiscoveredFile] = field(default_factory=list)

    def add(self, kind: FileKind, title: str, url: str) -> None:
        if any(f.url == url for f in self.files):
            return
        self.files.append(DiscoveredFile(kind=kind, title=title, url=url))


class RajkotRUDADP(BaseScraper):
    city_id = "rajkot"
    authority = "RUDA"
    scheme_types = frozenset({"DP"})

    def discover(self) -> list[DiscoveredScheme]:
        # Any fetch error propagates: a missing grid page would silently drop 29 sheets.
        plans, grid_pages = parse_plans_page(self.client.get_text(LISTING_URL), LISTING_URL)
        for scheme_no, page_url in grid_pages:
            for title, url in parse_grid_page(self.client.get_text(page_url), page_url):
                plans[scheme_no].add("map", title, url)
        add_download_rows(plans, self.client.get_text(DOWNLOAD_URL), DOWNLOAD_URL)
        return build_schemes(plans)


def plan_key(label: str) -> tuple[str, int, bool] | None:
    """'Existing Development Plans 2012' → ('existing-2012', 2012, True); None if no year."""
    m = _YEAR.search(label)
    if not m or "plan" not in label.lower():
        return None
    year = int(m.group(0))
    existing = "existing" in label.lower()
    return (f"existing-{year}" if existing else str(year)), year, existing


def _own_text(li: Tag) -> str:
    """The ``<li>``'s text without its nested lists and HTML comments."""
    parts: list[str] = []
    for child in li.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, Tag):
            if child.name not in ("ul", "ol"):
                parts.append(child.get_text(" "))
        elif isinstance(child, NavigableString):
            parts.append(str(child))
    return clean(" ".join(parts))


def _href(a: Tag) -> str | None:
    href = str(a.get("href", "")).strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return None
    return href


def parse_plans_page(
    html: str, page_url: str = LISTING_URL
) -> tuple[dict[str, _Plan], list[tuple[str, str]]]:
    """Plans (by scheme_no, page order) and the grid pages to follow as (scheme_no, url)."""
    soup = soup_of(html)
    ul = soup.select_one("ul.bullet3")
    if ul is None:
        raise ScraperError("RUDA DP: ul.bullet3 (plan list) not found")
    plans: dict[str, _Plan] = {}
    grid_pages: list[tuple[str, str]] = []
    for li in ul.find_all("li", recursive=False):
        label = _own_text(li)
        key = plan_key(label)
        if key is None:
            log.warning("RUDA DP: no plan year in list item %r; skipped", label)
            continue
        scheme_no, year, existing = key
        plan = plans.setdefault(scheme_no, _Plan(scheme_no, label, year, existing))
        # A link directly in the <li> is the plan itself, titled with the plan label. For
        # "Existing Development Plans 2012" it is the same PDF as the nested "Land Use" link
        # (Existing-Land-Use-2012.pdf, 22 MB, so a map rather than a land-use table); the
        # first occurrence wins, so it is kept once as a map.
        for a in li.find_all("a", recursive=False):
            if href := _href(a):
                plan.add("map", clean(a.get_text(" ")) or label, abs_url(page_url, href))
        nested = li.find(["ul", "ol"])
        for a in nested.find_all("a") if nested else []:
            href = _href(a)
            if href is None:
                continue
            url = abs_url(page_url, href)
            text = clean(a.get_text(" "))
            if urlsplit(url).path.lower().endswith((".html", ".htm")):
                grid_pages.append((scheme_no, url))
            elif "land use" in text.lower():
                plan.add("other", text, url)
            else:
                plan.add("map", text or label, url)
    if not plans:
        raise ScraperError("RUDA DP: no plans found in ul.bullet3")
    return plans, grid_pages


def parse_grid_page(html: str, page_url: str) -> list[tuple[str, str]]:
    """(title, url) per sheet of a grid page, in page order.

    The research found page labels that contradict the PDF folder names: the page listed
    under "Development Plan 2031" links into ``pdf/Existing-Land-use-2031-Index-Plan/``,
    while "Grid wise existing land use plan" (listed under Existing 2012) links into
    ``pdf/development-plan-2031/``. Which set is really the proposed DP-2031 is not verified.
    The sheets therefore stay with the plan whose list item links the page, and the folder
    name goes into the title ("Sheet 01 (development-plan-2031)") so nothing is lost.
    """
    soup = soup_of(html)
    sheets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for area in soup.select("map area[href]"):
        href = _href(area)
        if href is None or not href.lower().endswith(".pdf"):
            continue
        url = abs_url(page_url, href)
        if url in seen:
            continue
        seen.add(url)
        segs = [unquote(s) for s in urlsplit(url).path.split("/") if s]
        stem = segs[-1].rsplit(".", 1)[0]
        folder = segs[-2] if len(segs) >= 2 else ""
        title = f"Sheet {stem} ({folder})" if folder else f"Sheet {stem}"
        sheets.append((title, url))
    if len(sheets) < MIN_GRID_SHEETS:
        raise ScraperError(
            f"RUDA DP {page_url}: only {len(sheets)} grid sheets found "
            f"(expected at least {MIN_GRID_SHEETS}); layout change?"
        )
    return sheets


def add_download_rows(plans: dict[str, _Plan], html: str, page_url: str = DOWNLOAD_URL) -> None:
    """Add files from the older download page (``table.tbl1``) that the main page lacks."""
    soup = soup_of(html)
    tables = soup.select("table.tbl1")
    if not tables:
        raise ScraperError(f"RUDA DP {page_url}: table.tbl1 not found")
    rows = 0
    for table in tables:
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 2:
                continue
            label = clean(cells[0].get_text(" "))
            key = plan_key(label)
            if key is None:  # unrelated rows (tenders etc.)
                continue
            rows += 1
            scheme_no, year, existing = key
            plan = plans.setdefault(scheme_no, _Plan(scheme_no, label, year, existing))
            for a in cells[1].find_all("a"):
                if href := _href(a):
                    plan.add("map", label, abs_url(page_url, href))
    if rows == 0:
        raise ScraperError(f"RUDA DP {page_url}: no development plan rows in table.tbl1")


def build_schemes(plans: dict[str, _Plan]) -> list[DiscoveredScheme]:
    proposed = [p.year for p in plans.values() if not p.existing]
    current = max(proposed) if proposed else None
    found: list[DiscoveredScheme] = []
    for p in plans.values():
        if p.existing:
            status, label = "unknown", f"Existing land use {p.year}"
        elif p.year == current:
            status, label = "final", p.label
        else:
            status, label = "unknown", SUPERSEDED_LABEL
        found.append(
            DiscoveredScheme(
                city_id="rajkot",
                authority="RUDA",
                scheme_type="DP",
                scheme_no=p.scheme_no,
                name_en="RUDA area",
                status=status,  # type: ignore[arg-type]
                status_label=label,
                source_page_url=LISTING_URL,
                files=p.files,
            )
        )
    require_min(found, MIN_PLANS, "RUDA DP")
    return found
