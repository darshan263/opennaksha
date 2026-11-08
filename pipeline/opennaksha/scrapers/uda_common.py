"""Helpers shared by the urban-development-authority scrapers (SUDA, AUDA, RUDA, VUDA)."""

from __future__ import annotations

import re
from datetime import date

from opennaksha.models import DiscoveredScheme, Status
from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.common import clean

# Higher = later stage. Used to pick the winner when one scheme is listed twice.
STATUS_RANK: dict[str, int] = {
    "unknown": 0,
    "draft": 1,
    "preliminary": 2,
    "final": 3,
    "sanctioned_variation": 4,
}

SUBMITTED_LABEL = "Draft – submitted to Govt. for sanction"


def stage_from_dates(
    draft: date | None,
    preliminary: date | None,
    final: date | None,
    submitted: date | None = None,
) -> tuple[Status, str | None, date | None]:
    """(status, status_label, status_date) from the latest filled sanction stage.

    Precedence is by stage, not by date: final > preliminary > draft > submitted-to-Govt.
    Nothing filled → ("unknown", None, None).
    """
    if final:
        return "final", "Final sanctioned", final
    if preliminary:
        return "preliminary", "Preliminary sanctioned", preliminary
    if draft:
        return "draft", "Draft sanctioned", draft
    if submitted:
        return "draft", SUBMITTED_LABEL, submitted
    return "unknown", None, None


def tidy_area(text: str | None) -> str | None:
    """Normalise an area/village name for display.

    'IYAVA -RUPAVATI- KHODA' → 'Iyava-Rupavati-Khoda'; 'Vajdi-Gadh_Vejagam' → 'Vajdi-Gadh-Vejagam'.
    """
    t = clean((text or "").replace("_", "-").replace("–", "-"))
    t = re.sub(r"\s*-\s*", "-", t).strip(" .-")
    if t.isupper() or t.islower():
        t = t.title()
    return t or None


def find_col(headers: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int:
    """Index of the first (lowercased) header containing any needle and no excluded word."""
    for i, h in enumerate(headers):
        if any(n in h for n in needles) and not any(x in h for x in exclude):
            return i
    raise ScraperError(f"no column matching {needles!r} in headers {headers!r}")


def merge_duplicates(schemes: list[DiscoveredScheme]) -> list[DiscoveredScheme]:
    """Combine schemes with the same id. The latest stage wins the metadata; files are united.

    Files from the losing listing whose title clashes get the losing stage appended, e.g.
    "Map (preliminary)". Order of first appearance is kept.
    """
    by_id: dict[str, DiscoveredScheme] = {}
    for s in schemes:
        prev = by_id.get(s.id)
        if prev is None:
            by_id[s.id] = s
            continue
        win, lose = (s, prev) if STATUS_RANK[s.status] > STATUS_RANK[prev.status] else (prev, s)
        files = list(win.files)
        urls = {f.url for f in files}
        titles = {f.title for f in files}
        for f in lose.files:
            if f.url in urls:
                continue
            if f.title in titles:
                f = f.model_copy(
                    update={"title": f"{f.title} ({lose.status_label or lose.status})"}
                )
            files.append(f)
            urls.add(f.url)
            titles.add(f.title)
        by_id[s.id] = win.model_copy(update={"files": files})
    return list(by_id.values())


def require_min(schemes: list[DiscoveredScheme], minimum: int, source: str) -> None:
    if len(schemes) < minimum:
        raise ScraperError(
            f"{source}: only {len(schemes)} schemes found (expected at least {minimum}); "
            "layout change?"
        )
