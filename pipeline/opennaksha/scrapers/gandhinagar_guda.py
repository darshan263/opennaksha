"""Gandhinagar Urban Development Authority (GUDA). See docs/sources.md §10.5.

Use the bare host ``guda.gujarat.gov.in``: ``www.guda.gujarat.gov.in`` serves a certificate
for another name. Static ``.htm`` pages (IIS).

**DP** (``resources.htm``): under a ``td.heading`` "First Revised D.P. Scheme", rows of
``h3.download_pdf > a[href="download/dpscheme/<n>.pdf"]`` with link text ``1`` … ``35``, then a
``ul.smallpoint`` with ``<a><h2>Final Development Plan-2024(First Revised)</h2></a>`` (full
plan) and ``<a><h2>Key Map</h2></a>``. The same ``download/dpscheme/`` folder also holds forms
(Gujarati names, "Final list structure expert.pdf"), so only numeric link texts and the two
named items are taken. One record, scheme_no = the plan year.

**TP** (``tpscheme.htm``): one ``table.gridbdr``: Sr.No. | Name of the T.P.Scheme | Area in
(Hac.) | Draft … U/S 48(2) | Preliminary … U/S 65 | Final … U/S 65 | Remarks, split by
full-width section rows ("Final Town Planning Scheme Sanctioned by Govt." …). Dates are
dd/mm/yyyy or '-'; a date cell may link to that stage's PDF (``download/dpscheme/draft/19.pdf``,
``…/preliminary/…``, ``…/final/…``, ``download/tpscheme/TPS-17.pdf``). Status comes from the latest
filled date. Names: ``T.P.S No.19 (Raisan- Randesan- koba)``, ``T.P.S. No-11 (Adalaj) PART-A``,
``T.P.S. No-9/B (…)``.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit

from bs4 import Tag

from opennaksha.models import DiscoveredFile, DiscoveredScheme
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import abs_url, clean, expand_table, links, parse_dmy, soup_of
from opennaksha.scrapers.uda_common import (
    find_col,
    merge_duplicates,
    require_min,
    stage_from_dates,
    tidy_area,
)

log = logging.getLogger(__name__)

BASE = "https://guda.gujarat.gov.in/"
DP_URL = BASE + "resources.htm"
TP_URL = BASE + "tpscheme.htm"

MIN_DP_SHEETS = 20
MIN_TP_SCHEMES = 15

_DP_YEAR = re.compile(r"development\s+plan\D{0,5}((?:19|20)\d{2})", re.IGNORECASE)
_TPS_NAME = re.compile(
    r"""^T\.?\s*P\.?\s*S\.?\s*No\.?\s*[-.:]?\s*
    (?P<no>\d+(?:\s*/\s*[A-Z])?)\s*                  # 19, 9/B, 23/A
    (?:\((?P<area>[^)]*)\))?\s*
    (?:PART\s*-?\s*(?P<part>[A-Z]))?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Titles for the stage PDFs linked from the date cells. What these PDFs contain (scheme plan,
# sanction notification or both) is not verified (docs/sources.md §10.5 only says "the stage
# PDF"), so they are kind "other" with the stage in the title.
STAGE_TITLES = {
    "draft": "Draft TP scheme (sanctioned U/S 48(2))",
    "preliminary": "Preliminary TP scheme (sanctioned U/S 65)",
    "final": "Final TP scheme (sanctioned U/S 65)",
}


# --------------------------------------------------------------------------- DP


class GandhinagarGUDADP(BaseScraper):
    city_id = "gandhinagar"
    authority = "GUDA"
    scheme_types = frozenset({"DP"})

    def discover(self) -> list[DiscoveredScheme]:
        return parse_dp_page(self.client.get_text(DP_URL), DP_URL)


def _is_dp_file(url: str) -> bool:
    segs = [s.lower() for s in urlsplit(url).path.split("/") if s]
    return len(segs) >= 2 and segs[-2] == "dpscheme" and segs[-1].endswith(".pdf")


def parse_dp_page(html: str, page_url: str = DP_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    sheets: dict[int, str] = {}
    full_plan: tuple[str, str] | None = None  # (link text, url)
    key_map: str | None = None
    for a in soup.find_all("a", href=True):
        url = abs_url(page_url, str(a["href"]))
        if not _is_dp_file(url):
            continue
        text = clean(a.get_text(" "))
        if text.isdigit():
            sheets.setdefault(int(text), url)
        elif full_plan is None and _DP_YEAR.search(text):
            full_plan = (text, url)
        elif key_map is None and re.fullmatch(r"key\s*map", text, re.IGNORECASE):
            key_map = url
        # anything else in the folder is a form or list, not a map
    if full_plan is None:
        raise ScraperError(f"GUDA DP {page_url}: full development plan link not found")
    if len(sheets) < MIN_DP_SHEETS:
        raise ScraperError(
            f"GUDA DP {page_url}: only {len(sheets)} DP sheets found "
            f"(expected at least {MIN_DP_SHEETS}); layout change?"
        )
    if key_map is None:
        log.warning("GUDA DP: key map link not found")
    text, url = full_plan
    year = _DP_YEAR.search(text).group(1)  # type: ignore[union-attr]
    # "Final Development Plan-2024(First Revised)" → "… Plan-2024 (First Revised)"
    label = clean(re.sub(r"\s*\(", " (", text))
    files = [DiscoveredFile(kind="map", title="Full plan", url=url)]
    if key_map:
        files.append(DiscoveredFile(kind="map", title="Key map", url=key_map))
    files += [
        DiscoveredFile(kind="map", title=f"Sheet {n}", url=u) for n, u in sorted(sheets.items())
    ]
    return [
        DiscoveredScheme(
            city_id="gandhinagar",
            authority="GUDA",
            scheme_type="DP",
            scheme_no=year,
            name_en="GUDA area",
            status="final",
            status_label=label,
            source_page_url=page_url,
            files=files,
        )
    ]


# --------------------------------------------------------------------------- TP


class GandhinagarGUDA(BaseScraper):
    city_id = "gandhinagar"
    authority = "GUDA"

    def discover(self) -> list[DiscoveredScheme]:
        return parse_tp_page(self.client.get_text(TP_URL), TP_URL)


def parse_tps_name(text: str) -> tuple[str, str | None] | None:
    """'T.P.S. No-11 (Adalaj) PART-A' → ('11-A', 'Adalaj'); 'T.P.S. No-9/B (…)' → ('9/B', …)."""
    m = _TPS_NAME.match(clean(text))
    if not m:
        return None
    no = re.sub(r"\s+", "", m.group("no")).upper()
    if m.group("part"):
        no = f"{no}-{m.group('part').upper()}"
    area = tidy_area(m.group("area"))
    if area:  # "Raisan-Randesan-koba" → "Raisan-Randesan-Koba"
        area = re.sub(r"(?<![A-Za-z])[a-z]", lambda c: c.group(0).upper(), area)
    return no, area


def _is_section_row(row: list[Tag | None]) -> bool:
    return len(row) > 1 and all(c is row[0] for c in row)


def parse_tp_page(html: str, page_url: str = TP_URL) -> list[DiscoveredScheme]:
    soup = soup_of(html)
    table = soup.select_one("table.gridbdr")
    if table is None:
        raise ScraperError("GUDA TP: table.gridbdr not found")
    grid = expand_table(table)
    header_i = next(
        (
            i
            for i, row in enumerate(grid)
            if any(
                c is not None and "name of the t.p" in clean(c.get_text(" ")).lower() for c in row
            )
            and not _is_section_row(row)
        ),
        None,
    )
    if header_i is None:
        raise ScraperError("GUDA TP: no header row ('Name of the T.P.Scheme') in table.gridbdr")
    headers = [clean(c.get_text(" ")).lower() if c else "" for c in grid[header_i]]
    name_col = find_col(headers, "name of the t.p")
    draft_col = find_col(headers, "draft")
    prelim_col = find_col(headers, "preliminary", "priliminary")
    final_col = find_col(headers, "final")
    stage_cols = {"draft": draft_col, "preliminary": prelim_col, "final": final_col}
    last_col = max(name_col, *stage_cols.values())

    found: list[DiscoveredScheme] = []
    for row in grid[header_i + 1 :]:
        if len(row) <= last_col or _is_section_row(row) or row[name_col] is None:
            continue
        name_text = clean(row[name_col].get_text(" "))  # type: ignore[union-attr]
        if name_text.isdigit():  # the "1 | 2 | 3 …" column-number row
            continue
        parsed = parse_tps_name(name_text)
        if parsed is None:
            log.warning("GUDA TP: can't parse scheme name %r; row skipped", name_text)
            continue
        no, area = parsed
        dates = {
            stage: parse_dmy(row[col].get_text(" ") if row[col] else None)
            for stage, col in stage_cols.items()
        }
        status, label, status_date = stage_from_dates(
            dates["draft"], dates["preliminary"], dates["final"]
        )
        # url → title. A PDF linked from several stage cells (TPS-17: the draft cell, which
        # has no date, and the preliminary cell link the same file) keeps its first position
        # and takes the latest stage's title.
        by_url: dict[str, str] = {}
        for stage, col in stage_cols.items():
            for url, _text in links(row[col], page_url):
                if url.lower().endswith(".pdf"):
                    by_url[url] = STAGE_TITLES[stage]
        files = [DiscoveredFile(kind="other", title=t, url=u) for u, t in by_url.items()]
        found.append(
            DiscoveredScheme(
                city_id="gandhinagar",
                authority="GUDA",
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
    require_min(found, MIN_TP_SCHEMES, "GUDA TP")
    return found
