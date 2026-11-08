from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.rajkot_ruda import LISTING_URL, RajkotRUDA, parse_listing

FIXTURE = Path(__file__).parent.parent / "fixtures" / "ruda" / "town_planning_scheme.html"
HTML = FIXTURE.read_text(encoding="utf-8")


class FakeClient:
    def get_text(self, url: str) -> str:
        assert url == LISTING_URL
        return HTML


@pytest.fixture(scope="module")
def schemes():
    return RajkotRUDA(FakeClient()).discover()  # type: ignore[arg-type]


def test_counts_by_status(schemes):
    assert len(schemes) == 11
    labels = Counter((s.status, s.status_label) for s in schemes)
    assert labels[("preliminary", "Preliminary sanctioned")] == 1
    assert labels[("draft", "Draft sanctioned")] == 6
    assert labels[("draft", "Draft – submitted to Govt. for sanction")] == 4


def test_ids_unique(schemes):
    assert len({s.id for s in schemes}) == len(schemes)
    assert [s.scheme_no for s in schemes] == [
        "43",
        "41",
        "38/2",
        "77",
        "80",
        "81",
        "82",
        "53",
        "54",
        "55",
        "57",
    ]


def test_statuses_and_dates(schemes):
    by_id = {s.id: s for s in schemes}
    s = by_id["rajkot-ruda-tp-43-vajdi-vad"]
    assert (s.status, s.status_date, s.name_en) == ("preliminary", date(2025, 9, 26), "Vajdi Vad")
    s = by_id["rajkot-ruda-tp-41-sokhda-maliyasan"]
    assert (s.status, s.status_date) == ("draft", date(2022, 10, 21))
    s = by_id["rajkot-ruda-tp-53-khokhadadad"]
    assert (s.status, s.status_label, s.status_date) == (
        "draft",
        "Draft – submitted to Govt. for sanction",
        date(2026, 9, 11),
    )
    assert by_id["rajkot-ruda-tp-80-vajdi-gadh-vejagam"].name_en == "Vajdi-Gadh-Vejagam"


def test_files_and_urls(schemes):
    s = next(s for s in schemes if s.scheme_no == "41")
    assert [(f.kind, f.title, f.url) for f in s.files] == [
        ("map", "Plan", "https://rajkotuda.com/uploads/T.P.41%20plan%20no.3.pdf"),
        ("other", "F-Form", "https://rajkotuda.com/uploads/tp41_f-form.pdf"),
    ]
    for s in schemes:
        assert [f.kind for f in s.files] == ["map", "other"], s.id
        for f in s.files:
            assert f.url.startswith("https://rajkotuda.com/")
            assert " " not in f.url


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_listing("<html><body><p>Under maintenance</p></body></html>")


def test_missing_column_raises():
    with pytest.raises(ScraperError):
        parse_listing(HTML.replace("Submitted", "Sent"))


def test_implausibly_few_schemes_raises():
    head = HTML.split("<td>1</td>")[0]
    with pytest.raises(ScraperError, match="only 0 schemes"):
        parse_listing(head + "</tr></tbody></table>")
