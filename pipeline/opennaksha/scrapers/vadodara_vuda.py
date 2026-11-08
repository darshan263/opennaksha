"""Vadodara Urban Development Authority (VUDA). See docs/sources.md → VUDA.

Four static status pages (draft, sanctioned draft, preliminary, final), each a plain list of
file links ``TPSchemeVuda/<status>/<scheme-folder>/<file>.pdf``. Files are grouped by scheme
folder; the scheme number and area come from the folder name, which is inconsistent:

    TP-21-SAMIYALA-BIL, TPS-27-A-BILL, TP-24-A      → number first
    bhayali-tp-1, Bil-Tp1, SEVASI-2-FINAL, ANKODIYA-1 → number last
    SAMA-DUMAD-VEMALI, padra                        → no number: taken from the file names
                                                      ("…-NO-2", "PADRA-NO1"); padra holds
                                                      two schemes (1 and 2)

A file whose name contains "FORM" is the F-form, anything else is a map. A scheme listed on
two pages (Sevasi 2: preliminary and final) is merged; the later stage wins. The legacy
``tpscheme.htm`` page (overlaps the draft page) and home-page-only files (Padra TP 3/4) are
not scraped.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from urllib.parse import unquote, urlsplit

from opennaksha.models import DiscoveredFile, DiscoveredScheme, Status
from opennaksha.scrapers.base import BaseScraper, ScraperError
from opennaksha.scrapers.common import clean, links, soup_of
from opennaksha.scrapers.uda_common import merge_duplicates, require_min, tidy_area

log = logging.getLogger(__name__)

BASE = "https://www.vuda.co.in/"
# listing URL → (status, status_label)
PAGES: dict[str, tuple[Status, str | None]] = {
    BASE + "tp_scheme_vuda_draft.htm": ("draft", None),
    BASE + "tp_scheme_vuda_sanctioned_draft.htm": ("draft", "Draft – sanctioned"),
    BASE + "tp_scheme_vuda_priliminary.htm": ("preliminary", None),
    BASE + "tp_scheme_vuda_final.htm": ("final", None),
}

MIN_SCHEMES = 15

# "TP-21-SAMIYALA-BIL", "TPS-27-A-BILL", "TP-24-A"
_NO_FIRST = re.compile(r"TPS?-(?P<no>\d+(?:-[A-Z](?=-|$))?)(?:-(?P<area>.+))?", re.IGNORECASE)
# "bhayali-tp-1", "Bil-Tp1", "SEVASI-2-FINAL", "GORWA-ANKODIYA-1", "Vemali-TP-1"
_NO_LAST = re.compile(r"(?P<area>.+?)-(?:T-?P-?S?-?)?(?P<no>\d+)(?:-FINAL)?", re.IGNORECASE)
# number at the end of a file stem: "T-P-S-NO-S.D-V-NO-2", "PADARA-T-P-S-NO-01", "PADRA-NO1"
_FILE_NO = re.compile(r"NO-?0*(\d+)$", re.IGNORECASE)


class VadodaraVUDA(BaseScraper):
    city_id = "vadodara"
    authority = "VUDA"

    def discover(self) -> list[DiscoveredScheme]:
        found: list[DiscoveredScheme] = []
        for url in PAGES:
            # Any fetch error propagates: partial data would mark schemes as removed.
            found += parse_page(self.client.get_text(url), url)
        found = merge_duplicates(found)
        require_min(found, MIN_SCHEMES, "VUDA")
        return found


def parse_folder(folder: str) -> tuple[str, str | None] | None:
    """Scheme folder name → (scheme_no, area), or None if it carries no number."""
    f = folder.strip().replace("_", "-")
    m = _NO_FIRST.fullmatch(f) or _NO_LAST.fullmatch(f)
    if not m:
        return None
    return m.group("no").upper(), tidy_area(m.group("area"))


def parse_page(html: str, page_url: str) -> list[DiscoveredScheme]:
    """Parse one VUDA status page. Raises if it has no TPSchemeVuda file links."""
    spec = PAGES.get(page_url)
    if spec is None:
        raise ValueError(f"not a VUDA listing URL: {page_url}")
    status, label = spec
    soup = soup_of(html)
    # folder → [(url, link text, file stem)], in page order
    folders: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for url, text in links(soup, page_url):
        segs = [unquote(s) for s in urlsplit(url).path.split("/") if s]
        try:
            i = [s.lower() for s in segs].index("tpschemevuda")
        except ValueError:
            continue
        if len(segs) < i + 4:  # TPSchemeVuda/<status>/<folder>/<file>
            log.warning("VUDA: file link outside a scheme folder: %s", url)
            continue
        folder, filename = segs[i + 2], segs[-1]
        stem = clean(filename.rsplit(".", 1)[0])
        folders[folder].append((url, text, stem))
    if not folders:
        raise ScraperError(f"VUDA {page_url}: no TPSchemeVuda file links found")

    found: list[DiscoveredScheme] = []
    for folder, items in folders.items():
        parsed = parse_folder(folder)
        groups = {parsed: items} if parsed else _split_by_file_number(folder, items)
        for (no, area), group in groups.items():
            found.append(
                DiscoveredScheme(
                    city_id="vadodara",
                    authority="VUDA",
                    scheme_type="TP",
                    scheme_no=no,
                    name_en=area,
                    status=status,
                    status_label=label,
                    source_page_url=page_url,
                    files=_files(group),
                )
            )
    return found


def _split_by_file_number(
    folder: str, items: list[tuple[str, str, str]]
) -> dict[tuple[str, str | None], list[tuple[str, str, str]]]:
    """For a folder without a number: group its files by the number at the end of the name.

    Unnumbered files go with the folder's only scheme; if there are several, they are skipped.
    """
    area = tidy_area(folder)
    numbered: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    unnumbered: list[tuple[str, str, str]] = []
    for item in items:
        m = _FILE_NO.search(item[2])
        if m:
            numbered[m.group(1)].append(item)
        else:
            unnumbered.append(item)
    if not numbered:
        log.warning("VUDA: no scheme number in folder %r or its files; skipped", folder)
        return {}
    if unnumbered:
        if len(numbered) == 1:
            next(iter(numbered.values())).extend(unnumbered)
        else:
            log.warning(
                "VUDA: folder %r: can't assign %s to a scheme",
                folder,
                [i[2] for i in unnumbered],
            )
    return {(no, area): group for no, group in numbered.items()}


def _files(items: list[tuple[str, str, str]]) -> list[DiscoveredFile]:
    maps = [i for i in items if not _is_f_form(i)]
    forms = [i for i in items if _is_f_form(i)]
    out: list[DiscoveredFile] = []
    for kind, title, group in (("map", "Map", maps), ("other", "F-Form", forms)):
        for url, text, stem in group:
            t = f"{title} ({text or stem})" if len(group) > 1 else title
            out.append(DiscoveredFile(kind=kind, title=t, url=url))  # type: ignore[arg-type]
    return out


def _is_f_form(item: tuple[str, str, str]) -> bool:
    _url, text, stem = item
    return "FORM" in f"{text} {stem}".upper()
