"""Dholera Special Investment Region Development Authority (DSIRDA). See docs/sources.md §11.1.

https://dholera.gujarat.gov.in is an Odoo site with static, server-rendered pages (robots.txt
allows everything). The home page is ~29 MB, so the scraper starts from the Final DP page,
``/finaldp/15``, whose navigation menu lists every planning page:

- "Development Plan" dropdown: Final Development Plan, DP Report 1, DP Report 2 (GDCR),
  DP Villages Map, Split TP Schemes Map, DP Variation, Notifications.
- "Town Planning Schemes" → "Preliminary": TP 2A, TP 4A, 1A1, 1A2, 2B1 … 6A (one page each).
- "Town Planning Schemes" → "Draft": DTPS 1 … DTPS 6.

Each page: ``h3.p_heading`` title and ``table.document_download``, one row per document
(``h3.p_heading_normal > span`` title, PDF link to ``/web/document/download?…&id=<n>``; the same
link is repeated on a "Download" button, so links are de-duplicated). No dates are shown.

Records:
- one TP record per scheme page; the menu section gives the status (Preliminary / Draft);
- the "Notifications" page holds "Notifications TPS- 2A" etc.; each is attached to that scheme;
- one DP record (``scheme_no`` "final") holding the DP pages' files.

The site's own labels disagree in places (files named "Prelim_…" sit on a "Finalised TP
Schemes" page), so that page is not used: the menu section is the status.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import Tag

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind, Status
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import abs_url, clean, soup_of

log = logging.getLogger(__name__)

BASE = "https://dholera.gujarat.gov.in"
START_URL = f"{BASE}/finaldp/15"
DP_NO = "final"
DP_NAME = "Dholera SIR"
DP_LABEL = "Final Development Plan (DSIRDA)"
MIN_TP = 10

_NOTICE_TPS = re.compile(r"TPS?\s*-?\s*([0-9][0-9A-Z]*)\s*$", re.IGNORECASE)
_DRAFT_NO = re.compile(r"(?:DTPS|Scheme\s+No\.?)\s*-?\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class MenuPage:
    section: str  # "dp", "preliminary" or "draft"
    label: str
    url: str


class DholeraDSIRDA(BaseScraper):
    city_id = "dholera"
    authority = "DSIRDA"
    scheme_types = frozenset({"TP", "DP"})

    def discover(self) -> list[DiscoveredScheme]:
        start = self.client.get_text(START_URL)
        pages: list[tuple[MenuPage, str]] = []
        for page in parse_menu(start):
            html = start if page.url == START_URL else self.client.get_text(page.url)
            pages.append((page, html))
        return build_records(pages)


def _dropdown_links(dropdown: Tag) -> list[tuple[str, str]]:
    menu = dropdown.find("ul", recursive=False)
    if menu is None:
        return []
    out = []
    for a in menu.select("a[role=menuitem][href]"):
        href = str(a["href"])
        if href.startswith("/"):
            out.append((clean(a.get_text(" ")), abs_url(BASE, href)))
    return out


def _toggle_text(li: Tag) -> str:
    a = li.find("a", class_="dropdown-toggle", recursive=False)
    return clean(a.get_text(" ")).lower() if a else ""


def parse_menu(html: str) -> list[MenuPage]:
    """The planning pages listed in the site's navigation menu, in menu order."""
    soup = soup_of(html)
    pages: dict[str, MenuPage] = {}
    for li in soup.select("li.dropdown"):
        title = _toggle_text(li)
        section = {"development plan": "dp", "preliminary": "preliminary", "draft": "draft"}.get(
            title
        )
        if section is None:
            continue
        for label, url in _dropdown_links(li):
            pages.setdefault(url, MenuPage(section, label, url))
    found = list(pages.values())
    if sum(1 for p in found if p.section != "dp") < MIN_TP or not any(
        p.section == "dp" for p in found
    ):
        raise ScraperError("DSIRDA: planning menu not found (layout changed?)")
    return found


def parse_documents(html: str, page_url: str) -> tuple[str, list[tuple[str, str]]]:
    """(page heading, [(document title, url)]) from one Odoo documents page."""
    soup = soup_of(html)
    heading = soup.select_one("h3.p_heading")
    docs: dict[str, str] = {}
    for table in soup.select("table.document_download"):
        title = ""
        for el in table.find_all(["h3", "a"]):
            classes = el.get("class") or []
            if el.name == "h3" and "p_heading_normal" in classes:
                title = clean(el.get_text(" "))
            elif el.name == "a" and "download" in str(el.get("href", "")):
                url = abs_url(page_url, str(el["href"]))
                docs.setdefault(url, title or url.rsplit("=", 1)[-1])
    return clean(heading.get_text(" ")) if heading else "", [(t, u) for u, t in docs.items()]


def _scheme_no(page: MenuPage, heading: str) -> str:
    if page.section == "draft":
        m = _DRAFT_NO.search(heading) or _DRAFT_NO.search(page.label)
        if not m:
            raise ScraperError(f"DSIRDA: no scheme number in draft page {heading!r}")
        return m.group(1)
    # "TP 2A" → "2A"; "1A1" → "1A1". The menu label is used (two pages share the slug "1a1").
    return re.sub(r"^TP\s*", "", page.label, flags=re.IGNORECASE).upper().replace(" ", "")


def _tp_kind(title: str) -> FileKind:
    return "notification" if "notification" in title.lower() else "map"


def _dp_kind(page_label: str) -> FileKind:
    low = page_label.lower()
    if "report" in low:
        return "other"
    return "map"


def build_records(pages: list[tuple[MenuPage, str]]) -> list[DiscoveredScheme]:
    tps: dict[str, DiscoveredScheme] = {}
    dp_files: list[DiscoveredFile] = []
    notices: list[tuple[str, str]] = []
    for page, html in pages:
        heading, docs = parse_documents(html, page.url)
        if not docs:
            log.warning("DSIRDA: no documents on %s", page.url)
            continue
        if page.section == "dp":
            if page.label.lower().startswith("notification"):
                notices += docs
                continue
            dp_files += [DiscoveredFile(kind=_dp_kind(page.label), title=t, url=u) for t, u in docs]
            continue
        no = _scheme_no(page, heading)
        status: Status = "draft" if page.section == "draft" else "preliminary"
        files = [DiscoveredFile(kind=_tp_kind(t), title=t, url=u) for t, u in docs]
        if no in tps:
            raise ScraperError(f"DSIRDA: TP {no} listed twice")
        tps[no] = DiscoveredScheme(
            city_id="dholera",
            authority="DSIRDA",
            scheme_type="TP",
            scheme_no=no,
            status=status,
            source_page_url=page.url,
            files=files,
        )
    for title, url in notices:
        m = _NOTICE_TPS.search(title)
        target = tps.get(m.group(1).upper()) if m else None
        if target is None:
            log.warning("DSIRDA: notification %r matches no scheme; added to the DP", title)
            dp_files.append(DiscoveredFile(kind="notification", title=title, url=url))
            continue
        target.files.append(DiscoveredFile(kind="notification", title=title, url=url))

    if len(tps) < MIN_TP:
        raise ScraperError(f"DSIRDA: only {len(tps)} TP schemes (layout changed?)")
    found = list(tps.values())
    if dp_files:
        found.append(
            DiscoveredScheme(
                city_id="dholera",
                authority="DSIRDA",
                scheme_type="DP",
                scheme_no=DP_NO,
                name_en=DP_NAME,
                status="final",
                status_label=DP_LABEL,
                source_page_url=START_URL,
                files=dp_files,
            )
        )
    return found
