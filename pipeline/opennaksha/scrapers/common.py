"""Small parsing helpers shared by scrapers."""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

_WS = re.compile(r"\s+")

# "T.P.S.NO.1 (Laldarwaja)", "T.P.S 91 (VESU)", "T.P.S.NO 35 (...)", "102.(kanad)",
# "62-A( Kosad - Amroli )", "TPS No. 14 - Rander". Group 1 = number, group 2 = area.
_TPS_NAME = re.compile(
    r"""^\s*
    (?:T\.?\s*P\.?\s*S\.?|TP\s*Scheme|T\.?P\.?)?\s*      # optional TPS prefix
    (?:NO\.?|NUMBER)?\s*[-:.]?\s*                         # optional "No."
    (?P<no>\d+(?:\s*[-/_]?\s*[A-Z](?![a-z]))?(?:[-/_]\d+)?)  # 57, 62-A, 12A, 152/G, 35_1
    \s*\.?\s*[-–:]?\s*
    (?:\((?P<area>.+)\)|(?P<area2>[^()].*))?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def clean(text: str | None) -> str:
    """Collapse whitespace (incl. &nbsp;) and strip."""
    return _WS.sub(" ", (text or "").replace("\xa0", " ")).strip()


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def abs_url(base: str, href: str) -> str:
    """Resolve ``href`` against ``base`` and percent-encode raw spaces/brackets in the path.

    Handles Windows backslashes (``..\\Content\\x.pdf``) seen on SMC pages.
    """
    href = clean(href).replace("\\", "/")
    full = urljoin(base, href)
    parts = urlsplit(full)
    path = quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="=&%:/?+,;@!$'()*-._~")
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def parse_tps_name(text: str) -> tuple[str, str | None] | None:
    """Split a listing name into (scheme_no, area). Returns None if it doesn't look like one."""
    t = clean(text).replace("–", "-").replace("&#8211;", "-")
    m = _TPS_NAME.match(t)
    if not m:
        return None
    no = re.sub(r"\s+", "", m.group("no")).upper()
    area = clean(m.group("area") or m.group("area2") or "") or None
    if area:
        area = area.strip(" .-")
        if area.isupper() or area.islower():
            area = area.title()
    return no, area or None


def parse_dmy(text: str | None) -> date | None:
    """Parse dd/mm/yyyy or dd-mm-yyyy or dd.mm.yyyy; None for blanks and '-'."""
    t = clean(text)
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", t)
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
    except ValueError:
        return None


def expand_table(table: Tag) -> list[list[Tag | None]]:
    """Rows of cells with rowspan/colspan expanded (spanned positions repeat the same cell)."""
    grid: list[list[Tag | None]] = []
    pending: dict[int, tuple[Tag, int]] = {}  # column → (cell, rows remaining)
    for tr in table.find_all("tr"):
        row: list[Tag | None] = []
        cells = tr.find_all(["td", "th"], recursive=False)
        col = 0
        it = iter(cells)
        nxt = next(it, None)
        while nxt is not None or any(c >= col for c in pending):
            if col in pending:
                cell, left = pending[col]
                row.append(cell)
                if left <= 1:
                    del pending[col]
                else:
                    pending[col] = (cell, left - 1)
                col += 1
                continue
            if nxt is None:
                break
            cell = nxt
            nxt = next(it, None)
            span = _int_attr(cell, "colspan")
            rows = _int_attr(cell, "rowspan")
            for _ in range(span):
                row.append(cell)
                if rows > 1:
                    pending[col] = (cell, rows - 1)
                col += 1
        grid.append(row)
    return grid


def _int_attr(cell: Tag, name: str) -> int:
    try:
        return max(1, int(str(cell.get(name, "1")).strip() or 1))
    except ValueError:
        return 1


def links(cell: Tag | None, base: str) -> list[tuple[str, str]]:
    """(absolute url, link text) for each real link in a cell, de-duplicated by URL."""
    out: dict[str, str] = {}
    if cell is None:
        return []
    for a in cell.find_all("a", href=True):
        href = str(a["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "file:")):
            continue
        url = abs_url(base, href)
        text = clean(a.get_text(" "))
        out[url] = clean(f"{out.get(url, '')} {text}") if url in out else text
    return list(out.items())
