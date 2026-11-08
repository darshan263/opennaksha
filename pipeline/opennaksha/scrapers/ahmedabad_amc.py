"""Ahmedabad Municipal Corporation (AMC). See docs/sources.md → AMC.

One page, one table (``div.AMCtable2.TP_Scheme table``, no id/class) of all TP schemes:
Sr No | TPS Name | TPS No | Type | Current Status | Current Status Date | Drawing Name.

A varied scheme spans several ``<tr>``: Sr No / TPS Name / TPS No (and usually Drawing Name)
carry ``rowspan`` and the extra rows hold only Type | Current Status | Current Status Date.
``expand_table`` resolves the spans; a new Sr No group starts wherever the Sr No cell changes.
Groups with the same TPS name + number (15 later Sr Nos re-list a variation of an earlier
scheme) are merged into one scheme, so 287 Sr Nos give 272 schemes.

The Drawing cell is full of junk: empty ``file:///E:/...`` anchors, ``portal/...`` hrefs, and the
real ``/Uploads/...`` link repeated 2-3 times because its text is split over ``<br>``. Only links
under ``/Uploads/`` are kept, de-duplicated by URL, with the split texts joined into a title.

The draft TPS PDFs in the "City Planning" header menu (``/ViewFile/ViewFile?...``, 9 in the
fixture) are not used: their link texts have no consistent shape
("DTPS No. 157/G (Badrabad), as Submit...", "DTPS-159-Fatehwadi-Okaf Published_Dt_...",
"TPS-152-G-SHILAJ Plan No.3"), so the scheme number and area can't be extracted reliably,
and some of them are schemes already in the table.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import NamedTuple

from bs4 import Tag

from opennaksha.ids import make_scheme_id
from opennaksha.models import DiscoveredFile, DiscoveredScheme, Status
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import abs_url, clean, expand_table, parse_dmy, soup_of

log = logging.getLogger(__name__)

LISTING_URL = "https://ahmedabadcity.gov.in/SP/TPSchemeInformation"
UPLOADS_PREFIX = "https://ahmedabadcity.gov.in/Uploads/"

# Fewer schemes than this means the page layout changed (the fixture has 287).
MIN_SCHEMES = 50

# column key → header text (lowercase, whitespace-collapsed)
COLUMNS = {
    "sr": "sr no",
    "name": "tps name",
    "no": "tps no",
    "type": "type",
    "status": "current status",
    "date": "current status date",
    "drawing": "drawing name",
}


class AhmedabadAMC(BaseScraper):
    city_id = "ahmedabad"
    authority = "AMC"
    # The server needs TLS legacy renegotiation (OpenSSL 3 refuses it by default).
    legacy_tls_hosts = frozenset({"ahmedabadcity.gov.in", "www.ahmedabadcity.gov.in"})

    def discover(self) -> list[DiscoveredScheme]:
        return parse_listing(self.client.get_text(LISTING_URL), LISTING_URL)


def map_status(label: str) -> Status:
    """Map the site's "Current Status" wording to the catalog enum."""
    s = clean(label).upper()
    if "VARIATION" in s or "AMENDMENT" in s:
        return "sanctioned_variation"
    if s.startswith("FINAL"):
        return "final"
    if s.startswith("PRELIMINARY"):
        return "preliminary"
    if s.startswith("DRAFT SANCTION"):
        return "draft"
    return "unknown"


def parse_listing(html: str, page_url: str = LISTING_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    table = soup.select_one("div.AMCtable2.TP_Scheme table")
    if table is None:
        raise ScraperError("AMC: TP scheme table (div.AMCtable2.TP_Scheme table) not found")

    trs = table.find_all("tr")
    grid = expand_table(table)
    header_idx, cols = _find_header(trs)

    # Group the data rows by Sr No: a new group starts when the Sr No cell changes.
    groups: list[list[_Row]] = []
    prev_sr: Tag | None = None
    for tr, cells in zip(trs[header_idx + 1 :], grid[header_idx + 1 :], strict=True):
        sr = _cell(cells, cols["sr"])
        if sr is None:
            continue
        if sr is not prev_sr:
            groups.append([])
            prev_sr = sr
        groups[-1].append(_Row(tr, cells, first_of_group=not groups[-1]))

    # Some schemes appear under several Sr Nos (e.g. TPS 23 Sabarmati: Sr 60 with its varied
    # rows, then Sr 61 and Sr 171 for its 4th "greenbelt" variation). Those are one scheme with
    # one id, so their rows are merged before the status is chosen.
    by_key: dict[str, tuple[str, str, list[_Row]]] = {}
    for group in groups:
        first = group[0].cells
        name = _text(_cell(first, cols["name"]))
        no = re.sub(r"\s+", "", _text(_cell(first, cols["no"]))).upper()
        if not name or not no:
            log.warning("AMC: skipping Sr %r without TPS name/number", _text(first[cols["sr"]]))
            continue
        if name.isupper() or name.islower():
            name = name.title()
        key = make_scheme_id("ahmedabad", "AMC", "TP", no, name)
        if key in by_key:
            log.info("AMC: %s listed under more than one Sr No; merging", key)
            by_key[key][2].extend(group)
        else:
            by_key[key] = (no, name, list(group))

    found = [_scheme(no, name, rows, cols, page_url) for no, name, rows in by_key.values()]
    if len(found) < MIN_SCHEMES:
        raise ScraperError(f"AMC: only {len(found)} schemes found (expected >= {MIN_SCHEMES})")
    return found


class _Row(NamedTuple):
    tr: Tag
    cells: list[Tag | None]
    first_of_group: bool  # first <tr> of its Sr No (rowspan) group


def _find_header(trs: list[Tag]) -> tuple[int, dict[str, int]]:
    for i, tr in enumerate(trs):
        cells = tr.find_all(["th", "td"], recursive=False)
        texts = [clean(c.get_text(" ")).lower() for c in cells]
        if COLUMNS["name"] in texts and COLUMNS["no"] in texts:
            missing = [h for h in COLUMNS.values() if h not in texts]
            if missing:
                raise ScraperError(f"AMC: header row lacks columns {missing}")
            return i, {key: texts.index(h) for key, h in COLUMNS.items()}
    raise ScraperError("AMC: header row (TPS Name / TPS No) not found")


def _cell(cells: list[Tag | None], i: int) -> Tag | None:
    return cells[i] if i < len(cells) else None


def _text(cell: Tag | None) -> str:
    return clean(cell.get_text(" ")) if cell is not None else ""


def _latest_date(text: str) -> date | None:
    """Latest dd/mm/yyyy in a cell; '16/12/2015 19/02/2016' (with a corrigendum) has two."""
    dates = [parse_dmy(m) for m in re.findall(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4}", text)]
    return max((d for d in dates if d is not None), default=None)


def _scheme(
    no: str, name: str, rows: list[_Row], cols: dict[str, int], page_url: str
) -> DiscoveredScheme:
    def row_type(r: _Row) -> str:
        return _text(_cell(r.cells, cols["type"])).upper()

    # The principal row: the first row of the first Sr group that doesn't start with a varied
    # row. Every other row is a variation, even when its Type cell is spanned from the
    # principal row (TPS 5 City Wall Improvement) or says PRINCIPAL in a later Sr group
    # (TPS 21 Ambawadi, Sr 55).
    principal = next(
        (i for i, r in enumerate(rows) if r.first_of_group and "VARIED" not in row_type(r)), None
    )

    # Status: the most recent dated row (later rows win ties); the first row if none is dated.
    best_i, best_date = 0, None
    for i, r in enumerate(rows):
        d = _latest_date(_text(_cell(r.cells, cols["date"])))
        if d is not None and (best_date is None or d >= best_date):
            best_i, best_date = i, d
    best = rows[best_i]
    label = _text(_cell(best.cells, cols["status"]))
    kind = row_type(best)
    status = map_status(label)
    if best_i != principal or "VARIED" in kind:
        status = "sanctioned_variation"
    if "VARIED" in kind:
        label = f"{label} ({kind})" if label else kind

    return DiscoveredScheme(
        city_id="ahmedabad",
        authority="AMC",
        scheme_type="TP",
        scheme_no=no,
        name_en=name,
        status=status,
        status_label=label or None,
        status_date=best_date,
        source_page_url=page_url,
        files=_drawing_files(rows, cols, page_url),
    )


def _drawing_files(rows: list[_Row], cols: dict[str, int], page_url: str) -> list[DiscoveredFile]:
    # Only Drawing cells that sit in one of this scheme's own <tr>s. A cell can rowspan into the
    # next scheme (SOLA 43/A's drawing spans SOLA 43/B's row); that is not taken as 43/B's map.
    own_trs = {id(r.tr) for r in rows}
    cells: dict[int, Tag] = {}  # by identity: bs4 Tag equality compares content
    for r in rows:
        cell = _cell(r.cells, cols["drawing"])
        if cell is not None and id(cell.parent) in own_trs:
            cells.setdefault(id(cell), cell)

    texts: dict[str, list[str]] = {}  # url → anchor texts, in document order
    for cell in cells.values():
        in_cell: dict[str, list[str]] = {}
        for a in cell.find_all("a", href=True):
            url = abs_url(page_url, str(a["href"]))
            if not url.startswith(UPLOADS_PREFIX):
                continue  # file:///E:/..., portal/..., etc.
            in_cell.setdefault(url, []).append(clean(a.get_text(" ")))
        # A URL repeated in a later cell keeps the title from the first cell it appeared in.
        for url, parts in in_cell.items():
            texts.setdefault(url, parts)
    return [
        DiscoveredFile(kind="map", title=_join_title(parts), url=url)
        for url, parts in texts.items()
    ]


def _join_title(parts: list[str]) -> str:
    """Rebuild a drawing name split over <br>: 'TPS_1_X_PRINC_' + '01011993' → glued at '_'."""
    title = ""
    for p in (p for p in parts if p):
        if title and not title.endswith("_") and not p.startswith("_"):
            title += " "
        title += p
    title = clean(title).strip(" _-")
    return title if re.search(r"[A-Za-z]", title) else "Map"
