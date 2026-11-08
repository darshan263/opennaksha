from collections import Counter
from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.surat_suda import SANCTIONED_URL, SUBMITTED_URL, SuratSUDA, parse_page

FIXTURES = Path(__file__).parent.parent / "fixtures" / "suda"
PAGES = {
    SANCTIONED_URL: (FIXTURES / "tp_sanctioned.html").read_text(encoding="utf-8"),
    SUBMITTED_URL: (FIXTURES / "tp_submitted_to_govt.html").read_text(encoding="utf-8"),
}


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.fetched: list[str] = []

    def get_text(self, url: str) -> str:
        self.fetched.append(url)
        if url not in self.pages:
            raise RuntimeError(f"HTTP 503 for {url}")
        return self.pages[url]


@pytest.fixture(scope="module")
def schemes():
    return SuratSUDA(FakeClient(PAGES)).discover()  # type: ignore[arg-type]


def test_counts_by_status(schemes):
    # 17 sanctioned draft + 5 sanctioned preliminary + 11 submitted (docs/sources.md)
    assert len(schemes) == 33
    labels = Counter((s.status, s.status_label) for s in schemes)
    assert labels[("draft", "Draft – sanctioned")] == 17
    assert labels[("preliminary", None)] == 5
    assert labels[("draft", "Draft – submitted to Govt. for sanction")] == 11


def test_ids_unique(schemes):
    assert len({s.id for s in schemes}) == len(schemes)
    assert all(s.city_id == "surat" and s.authority == "SUDA" for s in schemes)


def test_name_formats(schemes):
    by_no = {s.scheme_no: s for s in schemes}
    assert by_no["35"].name_en == "Kumbharia-Sania Hemad-Saroli-Devadh"
    assert by_no["102"].name_en == "Kanad"
    assert by_no["86"].name_en == "Vedchha-Niyol"
    assert by_no["66"].name_en == "Dhoran Pardi"
    assert by_no["47"].name_en == "Kholvad-Bhada"
    assert by_no["62-A"].id == "surat-suda-tp-62-a-chhedchha-oviyan-sabargam-antroli"
    assert {"62-A", "62-B", "62-C"} <= set(by_no)


def test_sanctioned_scheme_files(schemes):
    s = next(s for s in schemes if s.id == "surat-suda-tp-35-kumbharia-sania-hemad-saroli-devadh")
    assert s.source_page_url == SANCTIONED_URL
    assert [(f.kind, f.title) for f in s.files] == [
        ("notification", "Notification"),
        ("map", "Map"),
        ("other", "F-Form"),
    ]
    assert s.files[1].url == (
        "https://www.sudaonline.org/wp-content/uploads/2025/11/"
        "1.T.P.S.NO-35-Kumbharia-Sania-Hemad-Saroli-Devadh_Plan-3-MAP.pdf"
    )


def test_submitted_scheme_files(schemes):
    s = next(s for s in schemes if s.id == "surat-suda-tp-66-dhoran-pardi")
    assert s.source_page_url == SUBMITTED_URL
    assert [(f.kind, f.title) for f in s.files] == [("map", "Map"), ("other", "F-Form")]


def test_every_scheme_has_map_and_absolute_urls(schemes):
    for s in schemes:
        assert any(f.kind == "map" for f in s.files), s.id
        for f in s.files:
            assert f.url.startswith("https://www.sudaonline.org/wp-content/uploads/")
            assert " " not in f.url


def test_stray_tr_rows_do_not_create_schemes():
    found = parse_page(PAGES[SUBMITTED_URL], SUBMITTED_URL)
    assert [s.scheme_no for s in found] == [
        "66",
        "67",
        "70",
        "71",
        "72",
        "73",
        "90",
        "91",
        "62-A",
        "62-B",
        "62-C",
    ]


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_page("<html><body><p>Under maintenance</p></body></html>", SANCTIONED_URL)


def test_missing_second_table_raises():
    html = PAGES[SANCTIONED_URL].replace("Sanctioned Preliminary", "Something Else")
    with pytest.raises(ScraperError):
        parse_page(html, SANCTIONED_URL)


def test_failed_page_fails_whole_source():
    client = FakeClient({SANCTIONED_URL: PAGES[SANCTIONED_URL]})
    with pytest.raises(RuntimeError):
        SuratSUDA(client).discover()  # type: ignore[arg-type]


def _page(*captions: str) -> str:
    tables = "".join(
        f"<table class='table-customized'><caption>{c}</caption>"
        "<thead><tr><th>Sr. No.</th><th>Name</th><th>Area</th><th>Map</th><th>F-Form</th></tr>"
        "</thead><tbody><tr><td>1</td><td>T.P.S.NO 35 (Vav)</td><td>1</td>"
        "<td><a href='/m.pdf'>Map</a></td><td></td></tr></tbody></table>"
        for c in captions
    )
    return f"<html><body><div class='entry-content'>{tables}</div></body></html>"


def test_implausibly_few_schemes_raises():
    pages = {
        SANCTIONED_URL: _page("Sanctioned Draft", "Sanctioned Preliminary"),
        SUBMITTED_URL: _page("submitted to Govt. for Sanction"),
    }
    with pytest.raises(ScraperError, match="only 1 schemes"):
        SuratSUDA(FakeClient(pages)).discover()  # type: ignore[arg-type]
