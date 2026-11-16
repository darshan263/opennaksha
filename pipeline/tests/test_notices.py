"""TPVD notifications → notices.json. Fixture only; no network."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from opennaksha.models import NoticesFile
from opennaksha.notices import build_notices, notice_kind, parse_notices
from opennaksha.scrapers.base import ScraperError
from tests.helpers import T0, T1

FIXTURE = (
    Path(__file__).resolve().parent.parent / "fixtures" / "tpvd" / "ecitizen_notifications.html"
)


@pytest.fixture(scope="module")
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parses_all_rows(html: str) -> None:
    notices = parse_notices(html)
    assert len(notices) == 107
    assert len({n.id for n in notices}) == 107
    first = next(n for n in notices if n.id == "bf7d93c2-f8ba-41b4-9105-5ae20786b168")
    assert first.date == date(2024, 10, 30)
    assert first.kind == "DP"
    assert first.branch == "L Branch"
    assert first.reference_no == "NOTIFICATION No.GH/V/382 OF 2024/TPS-192022-2284-L"
    assert first.title.startswith("Notification related to Modification in Final Development Plan")
    assert first.url.startswith("https://townplanning.gujarat.gov.in/FetchFile?guid=bf7d93c2")
    assert " " not in first.url


def test_kinds() -> None:
    assert notice_kind("Notification Related to Final Town Planning Scheme No 54 (Bhestan)") == "TP"
    assert (
        notice_kind("Modification in Dvelopment Plan of Ahemedabad Urban Development Authority")
        == "DP"
    )
    assert (
        notice_kind("Modification in Final Development Plan Ahmedabad Urban Developement Authority")
        == "DP"
    )
    assert notice_kind("Amendment in CGDCR") == "other"


def test_kind_counts(html: str) -> None:
    kinds = [n.kind for n in parse_notices(html)]
    assert kinds.count("TP") > 30
    assert kinds.count("DP") > 30


def test_first_run_reports_nothing_new_and_sorts_newest_first(html: str) -> None:
    f, new = build_notices(html, None, T0)
    assert new == []
    dates = [n.date for n in f.notices if n.date]
    assert dates == sorted(dates, reverse=True)
    assert all(n.first_seen == T0 for n in f.notices)


def test_keeps_first_seen_and_reports_new(html: str) -> None:
    f0, _ = build_notices(html, None, T0)
    dropped = f0.notices[0]
    prev = NoticesFile(generated_at=T0, source_page_url=f0.source_page_url, notices=f0.notices[1:])
    f1, new = build_notices(html, prev, T1)
    assert new == [dropped.id]
    by_id = {n.id: n for n in f1.notices}
    assert by_id[dropped.id].first_seen == T1
    assert by_id[f0.notices[1].id].first_seen == T0


def test_layout_change_fails() -> None:
    with pytest.raises(ScraperError):
        parse_notices("<html><body><table><tbody></tbody></table></body></html>")
    with pytest.raises(ScraperError):
        parse_notices('<table><tbody id="documentRows"><tr><td>x</td></tr></tbody></table>')
