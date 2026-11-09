"""Surat Urban Development Authority (SUDA) development plans. See docs/sources.md §10.1.

Five WordPress pages on www.sudaonline.org, all server-rendered:

- DP index (``/development-plans/``): only used for the sanction notification PDF of DP-2035.
- Sanctioned DP-2035 sheets: ``h1.entry-title`` carries the notification and corrigendum dates;
  an index-map JPG link sits before ``div#gallery-1``, whose ``dl.gallery-item``s are BASE MAP
  and the sheets A … Z (46 items). One record, scheme_no ``2035``.
- DP-2035 variations (u/s 19): ``div.entry-content`` holds groups separated by ``<hr>``, each a
  header ``<p>`` "(૧) … તારીખ: ૦૯/૦૭/૨૦૨૪ …" (Gujarati digits), an optional village line
  "મોજે : …" and a ``table.table-customized`` of label | ``a[href]`` rows. One record per group,
  scheme_no ``2035-var-<yyyy-mm-dd>``.
- DP 2004 and DP 1986: ``dl.gallery-item`` galleries of low-res JPGs. One record each. The
  server is case-sensitive (``2013/08/a.jpg`` ≠ ``2013/08/A.jpg``), so URLs are never lowercased.

The three draft DP-2035 galleries (2016, 2017 u/s 16, 2019 "online data") are superseded drafts
and are deliberately not scraped.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup, Tag

from opennaksha.models import DiscoveredFile, DiscoveredScheme, FileKind, Status
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import abs_url, clean, links, parse_dmy, soup_of

log = logging.getLogger(__name__)

INDEX_URL = "https://www.sudaonline.org/development-plans/"
SHEETS_URL = (
    "https://www.sudaonline.org/development-plans/"
    "dp-2035-sheet-dt-08-10-2020-corrigendum-9-11-2020/"
)
VARIATIONS_URL = "https://www.sudaonline.org/development-plans/sanction-dp-2035-proposed-variation/"
DP2004_URL = "https://www.sudaonline.org/development-plans/development-plan-2004/"
DP1986_URL = "https://www.sudaonline.org/development-plans/development-plan-1986/"

AREA_NAME = "SUDA area"
OLD_DP_LABEL = "Earlier development plan (superseded; low resolution)"

# Plausibility floors (counts seen on 2026-11-09: 46, 11, 27, 20).
MIN_DP2035_SHEETS = 40
MIN_VARIATION_GROUPS = 5
MIN_OLD_SHEETS = 15

_GU_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")
_IMAGE_EXT = re.compile(r"\.(?:jpe?g|png|gif|tiff?|pdf)$", re.IGNORECASE)
_GROUP_NO = re.compile(r"^\s*\(\s*(\d+)\s*\)\s*")
_VILLAGES = re.compile(r"^\s*મોજે\s*[:：]\s*(.*)$")
_SHEET_RANGE = re.compile(r"શીટ\s*નંબર\s*(\d+)\s*થી\s*(\d+)")
# "મંજુર વિકાસ યોજના" names the sanctioned base plan in every header; it says nothing about
# the stage of the variation itself, so it is removed before looking for status words.
_BASE_PLAN = re.compile(
    r"મંજ[ુૂ]ર\s+વિકાસ\s+યોજના|sanctioned\s+(?:dp|development\s+plan)", re.IGNORECASE
)
_PROPOSED = re.compile(r"proposed|પ્રસ્તાવિત|સૂચિત|સુચિત", re.IGNORECASE)
_SANCTIONED = re.compile(r"sanction|મંજૂર|મંજુર", re.IGNORECASE)


class SuratSUDADP(BaseScraper):
    city_id = "surat"
    authority = "SUDA"
    scheme_types = frozenset({"DP"})

    def discover(self) -> list[DiscoveredScheme]:
        # Every fetch error propagates: a partial result would mark records as removed.
        index_html = self.client.get_text(INDEX_URL)
        sheets_html = self.client.get_text(SHEETS_URL)
        variations_html = self.client.get_text(VARIATIONS_URL)
        dp2004_html = self.client.get_text(DP2004_URL)
        dp1986_html = self.client.get_text(DP1986_URL)

        found = [parse_dp2035(sheets_html, parse_sanction_notification(index_html))]
        found += parse_variations(variations_html)
        found.append(parse_old_dp(dp2004_html, DP2004_URL, "2004"))
        found.append(parse_old_dp(dp1986_html, DP1986_URL, "1986"))
        ids = Counter(s.id for s in found)
        dupes = [i for i, n in ids.items() if n > 1]
        if dupes:
            raise ScraperError(f"SUDA DP: duplicate ids {dupes}")
        return found


# --------------------------------------------------------------------------- pages


def parse_sanction_notification(html: str, page_url: str = INDEX_URL) -> DiscoveredFile | None:
    """The DP-2035 sanction notification PDF linked from the DP index page (None if absent)."""
    content = _entry_content(soup_of(html), page_url)
    for url, text in links(content, page_url):
        haystack = f"{url} {text}".lower()
        if url.lower().endswith(".pdf") and "2035" in haystack and "sanction" in haystack:
            return DiscoveredFile(kind="notification", title=text or "Notification", url=url)
    log.warning("SUDA DP: sanction notification PDF not found on %s", page_url)
    return None


def parse_dp2035(
    html: str,
    notification: DiscoveredFile | None = None,
    page_url: str = SHEETS_URL,
) -> DiscoveredScheme:
    """The sanctioned DP-2035 record: index map, base map, sheets (+ sanction notification)."""
    soup = soup_of(html)
    content = _entry_content(soup, page_url)
    title = _page_title(soup)
    label, status_date = _sanction_label(title)

    files: list[DiscoveredFile] = []
    gallery = content.select_one("div.gallery")
    if gallery is None:
        raise ScraperError(f"SUDA DP: no gallery on {page_url}")
    # The index map is a plain image link placed before the gallery.
    for a in content.find_all("a", href=True):
        if a.find_parent("div", class_="gallery") is not None:
            break
        if _IMAGE_EXT.search(str(a["href"]).strip()):
            files.append(DiscoveredFile(kind="map", title="Index map", url=_url(page_url, a)))
            break
    else:
        log.warning("SUDA DP: index map link not found on %s", page_url)

    sheets = parse_gallery(content, page_url, MIN_DP2035_SHEETS)
    for caption, url in sheets:
        t = "Base map" if caption.lower() == "base map" else f"Sheet {caption}"
        files.append(DiscoveredFile(kind="map", title=t, url=url))
    if notification is not None:
        files.append(notification)

    return DiscoveredScheme(
        city_id="surat",
        authority="SUDA",
        scheme_type="DP",
        scheme_no="2035",
        name_en=AREA_NAME,
        status="final",
        status_label=label,
        status_date=status_date,
        source_page_url=page_url,
        files=_dedupe(files),
    )


def parse_variations(html: str, page_url: str = VARIATIONS_URL) -> list[DiscoveredScheme]:
    """One record per variation group (header paragraph + optional village line + table)."""
    soup = soup_of(html)
    content = _entry_content(soup, page_url)
    page_title = _page_title(soup)

    groups: list[list[Tag]] = [[]]
    for el in content.find_all(recursive=False):
        if el.name == "hr":
            groups.append([])
        else:
            groups[-1].append(el)
    parsed = [g for g in (_parse_group(els, page_url) for els in groups if els) if g]
    if len(parsed) < MIN_VARIATION_GROUPS:
        raise ScraperError(
            f"SUDA DP: only {len(parsed)} variation groups on {page_url} "
            f"(expected at least {MIN_VARIATION_GROUPS}); layout change?"
        )

    by_date = Counter(g.group_date for g in parsed)
    found: list[DiscoveredScheme] = []
    for g in parsed:
        no = f"2035-var-{g.group_date.isoformat()}"
        if by_date[g.group_date] > 1:
            no += f"-{g.number}"
        found.append(
            DiscoveredScheme(
                city_id="surat",
                authority="SUDA",
                scheme_type="DP",
                scheme_no=no,
                name_en=g.name_en,
                name_gu=g.villages,
                status=_variation_status(g.header, page_title),
                status_label=g.header,
                status_date=g.group_date,
                source_page_url=page_url,
                files=g.files,
            )
        )
    return found


def parse_old_dp(html: str, page_url: str, year: str) -> DiscoveredScheme:
    """DP 2004 / DP 1986: one record with one map per gallery item."""
    content = _entry_content(soup_of(html), page_url)
    sheets = parse_gallery(content, page_url, MIN_OLD_SHEETS)
    return DiscoveredScheme(
        city_id="surat",
        authority="SUDA",
        scheme_type="DP",
        scheme_no=year,
        name_en=AREA_NAME,
        status="unknown",
        status_label=OLD_DP_LABEL,
        source_page_url=page_url,
        files=_dedupe([DiscoveredFile(kind="map", title=f"Sheet {c}", url=u) for c, u in sheets]),
    )


def parse_gallery(content: Tag, page_url: str, minimum: int) -> list[tuple[str, str]]:
    """(caption, absolute full-size URL) for each ``dl.gallery-item``, in page order."""
    out: list[tuple[str, str]] = []
    for item in content.select("dl.gallery-item"):
        a = item.select_one("dt.gallery-icon a[href]")
        if a is None:
            continue
        dd = item.select_one("dd.gallery-caption")
        caption = clean(dd.get_text(" ") if dd else "") or clean(
            str(a.get("data-lbwps-caption", ""))
        )
        if not caption:
            log.warning("SUDA DP: gallery item without caption on %s", page_url)
            continue
        out.append((caption, _url(page_url, a)))
    if len(out) < minimum:
        raise ScraperError(
            f"SUDA DP: only {len(out)} gallery items on {page_url} "
            f"(expected at least {minimum}); layout change?"
        )
    return out


# --------------------------------------------------------------------------- helpers


@dataclass
class _Group:
    number: int
    header: str
    group_date: date
    villages: str | None
    name_en: str | None
    files: list[DiscoveredFile]


def _parse_group(els: list[Tag], page_url: str) -> _Group | None:
    header_p = next(
        (e for e in els if e.name == "p" and _GROUP_NO.match(to_ascii_digits(e.get_text()))),
        None,
    )
    table = next((e for e in els if e.name == "table"), None)
    if header_p is None and table is None:
        return None  # e.g. an empty trailing block
    if header_p is None or table is None:
        raise ScraperError(f"SUDA DP: variation group without header or table on {page_url}")

    raw_header = clean(header_p.get_text(" "))
    m = _GROUP_NO.match(to_ascii_digits(raw_header))
    assert m is not None
    number = int(m.group(1))
    header = clean(raw_header[m.end() :])
    group_date = parse_dmy(to_ascii_digits(header))
    if group_date is None:
        raise ScraperError(f"SUDA DP: no date in variation group ({number}) on {page_url}")

    villages: str | None = None
    for e in els:
        vm = _VILLAGES.match(clean(e.get_text(" "))) if e.name == "p" else None
        if vm:
            villages = clean(vm.group(1)).rstrip(" .") or None
            break
    name_en = None
    if villages is None:
        sm = _SHEET_RANGE.search(to_ascii_digits(header))
        if sm:
            name_en = f"Sheets {sm.group(1)}-{sm.group(2)}"

    rows: list[tuple[str, str]] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        label = clean(cells[1].get_text(" "))
        for url, _text in links(cells[2], page_url):
            rows.append((label, url))
    if not rows:
        raise ScraperError(f"SUDA DP: variation group ({number}) has no file links")
    counts = Counter(label for label, _ in rows)
    seen: Counter[str] = Counter()
    files: list[DiscoveredFile] = []
    for label, url in rows:
        seen[label] += 1
        title = f"{label} ({seen[label]})" if counts[label] > 1 else label
        files.append(DiscoveredFile(kind=_variation_kind(label), title=title, url=url))
    return _Group(number, header, group_date, villages, name_en, _dedupe(files))


def _variation_kind(label: str) -> FileKind:
    # "જાહેરનામાંને સંલગ્ન નકશા" (maps attached to the notification) and the sheet-range rows
    # "શીટ નંબર ૨ થી ૮" are maps; gazette and notification-number rows are notifications.
    if "નકશા" in label or "શીટ" in label or "map" in label.lower():
        return "map"
    return "notification"


def _variation_status(header: str, page_title: str) -> Status:
    """Status from the group header's wording, falling back to the page title's wording.

    Today every group header only says "notification dated …"; the page title says
    "સૂચિત ફેરફારો" (proposed changes) → draft.
    """
    for text in (header, page_title):
        t = _BASE_PLAN.sub(" ", text)
        if _PROPOSED.search(t):
            return "draft"
        if _SANCTIONED.search(t):
            return "sanctioned_variation"
    return "unknown"


def _sanction_label(title: str) -> tuple[str, date | None]:
    """'Sanctioned 08-10-2020 (corrigendum 09-11-2020)' from the DP-2035 sheet page title."""
    t = to_ascii_digits(title)
    dates = [
        d for d in (parse_dmy(m.group(0)) for m in re.finditer(r"\d{1,2}/\d{1,2}/\d{4}", t)) if d
    ]
    if not dates:
        log.warning("SUDA DP: no sanction date in title %r", title)
        return clean(title), None
    label = f"Sanctioned {dates[0]:%d-%m-%Y}"
    if len(dates) > 1 and "corrigendum" in t.lower():
        label += f" (corrigendum {dates[1]:%d-%m-%Y})"
    return label, dates[0]


def to_ascii_digits(text: str) -> str:
    """Gujarati digits ૦–૯ → 0–9."""
    return text.translate(_GU_DIGITS)


def _entry_content(soup: BeautifulSoup, page_url: str) -> Tag:
    content = soup.select_one("div.entry-content")
    if content is None:
        raise ScraperError(f"SUDA DP: div.entry-content not found on {page_url}")
    return content


def _page_title(soup: BeautifulSoup) -> str:
    h1 = soup.select_one("h1.entry-title")
    return clean(h1.get_text(" ")) if h1 else ""


def _url(page_url: str, a: Tag) -> str:
    return abs_url(page_url, str(a["href"]))


def _dedupe(files: list[DiscoveredFile]) -> list[DiscoveredFile]:
    """Drop repeated URLs (the pipeline keys file state by URL), keeping the first."""
    seen: set[str] = set()
    out: list[DiscoveredFile] = []
    for f in files:
        if f.url not in seen:
            seen.add(f.url)
            out.append(f)
    return out
