"""Statewide planning notifications from TPVD (docs/sources.md §9.1) → ``catalog/notices.json``.

``https://townplanning.gujarat.gov.in/ecitizen/Notifications`` is one static table
(``tbody#documentRows``): Date | Category | Subject | Title | Reference No. | Description | Action.
The Action cell links ``/FetchFile?guid=<uuid>&filename=<title>.pdf``. The GUID is the notice id.

The rows are not sorted on the site; notices.json is sorted newest first. ``first_seen`` is kept
from the previous file so the app can badge notices that appeared since the user's last visit.
A failed fetch keeps the previous file unchanged (the caller decides).
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from opennaksha.models import Notice, NoticeKind, NoticesFile
from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.common import abs_url, clean, parse_dmy, soup_of

SOURCE_ID = "state-tpvd-notices"
LISTING_URL = "https://townplanning.gujarat.gov.in/ecitizen/Notifications"
MIN_ROWS = 20

_TP = re.compile(r"town\s*planning\s*scheme|\bT\.?\s*P\.?\s*S\b|\bTP\s*scheme", re.IGNORECASE)
# The site misspells it ("Dvelopment", "Developement"), so match loosely.
_DP = re.compile(r"\bd[ea]?v[ea]?lop?e?ment\s*plan\b|\bD\.?\s*P\.?\s*20\d\d\b", re.IGNORECASE)


def notice_kind(title: str) -> NoticeKind:
    if _TP.search(title):
        return "TP"
    if _DP.search(title):
        return "DP"
    return "other"


def parse_notices(html: str, page_url: str = LISTING_URL) -> list[Notice]:
    """Parse the table. ``first_seen`` is a placeholder; :func:`build_notices` sets it."""
    soup = soup_of(html)
    body = soup.select_one("tbody#documentRows")
    if body is None:
        raise ScraperError("TPVD notifications: tbody#documentRows not found (layout changed?)")
    rows: dict[str, Notice] = {}
    placeholder = datetime(1970, 1, 1)
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        a = tr.select_one("a[href*='FetchFile']")
        if len(cells) < 5 or a is None:
            continue
        url = abs_url(page_url, a["href"])
        guid = (parse_qs(urlsplit(url).query).get("guid") or [""])[0].lower()
        if not re.fullmatch(r"[0-9a-f-]{36}", guid):
            continue
        title = clean(cells[3].get_text(" "))
        if not title:
            continue
        rows[guid] = Notice(
            id=guid,
            date=parse_dmy(cells[0].get_text(" ")),
            kind=notice_kind(title),
            title=title,
            description=(clean(cells[5].get_text(" ")) or None) if len(cells) > 6 else None,
            reference_no=clean(cells[4].get_text(" ")) or None,
            branch=clean(cells[2].get_text(" ")) or None,
            url=url,
            first_seen=placeholder,
        )
    if len(rows) < MIN_ROWS:
        raise ScraperError(f"TPVD notifications: only {len(rows)} rows (layout changed?)")
    return list(rows.values())


def build_notices(
    html: str, previous: NoticesFile | None, now: datetime, page_url: str = LISTING_URL
) -> tuple[NoticesFile, list[str]]:
    """Parse the page and merge with the previous file. Returns (file, ids of new notices).

    Notices that disappear from the site are dropped (they are links, not catalog records).
    On the very first run nothing is reported as new.
    """
    prev = {n.id: n for n in previous.notices} if previous else {}
    notices, new = [], []
    for n in parse_notices(html, page_url):
        old = prev.get(n.id)
        first_seen = old.first_seen if old else now
        if old is None and previous is not None:
            new.append(n.id)
        notices.append(n.model_copy(update={"first_seen": first_seen}))
    notices.sort(key=lambda n: (n.date.isoformat() if n.date else "", n.title), reverse=True)
    return NoticesFile(generated_at=now, source_page_url=page_url, notices=notices), new
