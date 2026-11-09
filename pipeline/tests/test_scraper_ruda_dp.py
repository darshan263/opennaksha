from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.rajkot_ruda_dp import (
    BASE,
    DOWNLOAD_URL,
    LISTING_URL,
    SUPERSEDED_LABEL,
    RajkotRUDADP,
    add_download_rows,
    parse_grid_page,
    parse_plans_page,
    plan_key,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "ruda"
GRID_2031 = BASE + "devlopment-plan-2031.html"
GRID_DP_2012 = BASE + "grid-wise-existing-devlopment-plan.html"
GRID_LU_2012 = BASE + "grid-wise-existing-land-use-plan.html"
PAGES = {
    LISTING_URL: "development_plans.html",
    DOWNLOAD_URL: "development_plans_download.html",
    GRID_2031: "dp2031_grid_sheets.html",
    GRID_DP_2012: "existing_dp2012_grid_sheets.html",
    GRID_LU_2012: "existing_lu2012_grid_sheets.html",
}
HTML = {url: (FIXTURES / name).read_text(encoding="utf-8") for url, name in PAGES.items()}


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
    return RajkotRUDADP(FakeClient(HTML)).discover()  # type: ignore[arg-type]


def by_no(schemes):
    return {s.scheme_no: s for s in schemes}


def test_source_id_and_types():
    assert RajkotRUDADP.source_id() == "rajkot-ruda-dp"
    assert RajkotRUDADP.owner_keys() == {"rajkot-ruda:DP"}


def test_fetches_exactly_the_linked_pages():
    client = FakeClient(HTML)
    RajkotRUDADP(client).discover()  # type: ignore[arg-type]
    assert client.fetched == [LISTING_URL, GRID_2031, GRID_DP_2012, GRID_LU_2012, DOWNLOAD_URL]


def test_records_ids_and_statuses(schemes):
    assert [s.scheme_no for s in schemes] == ["1988", "2004", "2031", "existing-2012"]
    assert [s.id for s in schemes] == [
        "rajkot-ruda-dp-1988-ruda-area",
        "rajkot-ruda-dp-2004-ruda-area",
        "rajkot-ruda-dp-2031-ruda-area",
        "rajkot-ruda-dp-existing-2012-ruda-area",
    ]
    assert [(s.status, s.status_label) for s in schemes] == [
        ("unknown", SUPERSEDED_LABEL),
        ("unknown", SUPERSEDED_LABEL),
        ("final", "Development Plan 2031"),
        ("unknown", "Existing land use 2012"),
    ]
    for s in schemes:
        assert (s.city_id, s.authority, s.scheme_type, s.name_en) == (
            "rajkot",
            "RUDA",
            "DP",
            "RUDA area",
        )
        assert s.source_page_url == LISTING_URL


def test_file_counts(schemes):
    # 1988: plan; 2004: plan + land use; 2031: plan + land use + 29 sheets;
    # existing 2012: plan (= the "Land Use" link, same URL) + 2 × 29 sheets.
    assert [len(s.files) for s in schemes] == [1, 2, 31, 59]
    for s in schemes:
        assert len({f.url for f in s.files}) == len(s.files), s.id
        assert len({f.title for f in s.files}) == len(s.files), s.id


def test_main_files(schemes):
    s = by_no(schemes)
    assert [(f.kind, f.title, f.url) for f in s["1988"].files] == [
        ("map", "Development Plan 1988", BASE + "pdf/proposed-dp-1988.pdf"),
    ]
    assert [(f.kind, f.title, f.url) for f in s["2004"].files] == [
        ("map", "Development Plans", BASE + "pdf/index-2004.pdf"),
        ("other", "Land Use", BASE + "pdf/land-use-2004.pdf"),
    ]
    assert [(f.kind, f.title, f.url) for f in s["2031"].files[:2]] == [
        ("map", "Development Plans", BASE + "pdf/dp2031/dp.pdf"),
        ("other", "Land Use", BASE + "pdf/land-use2031.pdf"),
    ]
    first = s["existing-2012"].files[0]
    assert (first.kind, first.title, first.url) == (
        "map",
        "Existing Development Plans 2012",
        BASE + "pdf/Existing-Land-Use-2012.pdf",
    )


def test_grid_sheets_follow_page_label_with_folder_in_title(schemes):
    s = by_no(schemes)
    sheets_2031 = s["2031"].files[2:]
    assert [f.title for f in sheets_2031[:2]] == [
        "Sheet 01 (Existing-Land-use-2031-Index-Plan)",
        "Sheet 02 (Existing-Land-use-2031-Index-Plan)",
    ]
    assert sheets_2031[-1].url == BASE + "pdf/Existing-Land-use-2031-Index-Plan/29.pdf"
    assert all(f.kind == "map" for f in sheets_2031)

    sheets_2012 = s["existing-2012"].files[1:]
    assert sheets_2012[0].title == "Sheet E-01 (Existing-Land-use-2012-Index-Plan)"
    assert sheets_2012[28].title == "Sheet E-29 (Existing-Land-use-2012-Index-Plan)"
    # The "existing land use" grid page links into pdf/development-plan-2031/.
    assert (sheets_2012[29].title, sheets_2012[29].url) == (
        "Sheet 1 (development-plan-2031)",
        BASE + "pdf/development-plan-2031/1.pdf",
    )
    assert sheets_2012[-1].title == "Sheet 29 (development-plan-2031)"


def test_urls_absolute_without_spaces(schemes):
    for s in schemes:
        for f in s.files:
            assert f.url.startswith(BASE + "pdf/"), f.url
            assert " " not in f.url


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Development Plan 1988", ("1988", 1988, False)),
        ("Development Plans 2004", ("2004", 2004, False)),
        ("Existing Development Plans 2012", ("existing-2012", 2012, True)),
        ("Town Planning Scheme", None),
        ("Tender 2015", None),
    ],
)
def test_plan_key(label, expected):
    assert plan_key(label) == expected


def test_download_page_adds_only_new_files():
    plans, _grid = parse_plans_page(HTML[LISTING_URL])
    before = {k: len(p.files) for k, p in plans.items()}
    add_download_rows(plans, HTML[DOWNLOAD_URL])
    assert {k: len(p.files) for k, p in plans.items()} == before  # all 4 already covered

    extra = HTML[DOWNLOAD_URL].replace("pdf/index-2004.pdf", "pdf/index-2004-new.pdf")
    add_download_rows(plans, extra)
    f = plans["2004"].files[-1]
    assert (f.kind, f.title, f.url) == (
        "map",
        "Development Plans 2004",
        BASE + "pdf/index-2004-new.pdf",
    )


def test_commented_out_tenders_ignored():
    plans, _grid = parse_plans_page(HTML[LISTING_URL])
    add_download_rows(plans, HTML[DOWNLOAD_URL])
    assert not any("tender" in f.url for p in plans.values() for f in p.files)


def test_failed_grid_page_fails_whole_source():
    pages = dict(HTML)
    del pages[GRID_LU_2012]
    with pytest.raises(RuntimeError):
        RajkotRUDADP(FakeClient(pages)).discover()  # type: ignore[arg-type]


def test_failed_download_page_fails_whole_source():
    pages = dict(HTML)
    del pages[DOWNLOAD_URL]
    with pytest.raises(RuntimeError):
        RajkotRUDADP(FakeClient(pages)).discover()  # type: ignore[arg-type]


def test_layout_change_raises():
    with pytest.raises(ScraperError, match="ul.bullet3"):
        parse_plans_page("<html><body><p>Under maintenance</p></body></html>")
    with pytest.raises(ScraperError, match="table.tbl1"):
        add_download_rows({}, "<html><body></body></html>")


def test_grid_page_without_sheets_raises():
    with pytest.raises(ScraperError, match="only 0 grid sheets"):
        parse_grid_page("<html><body><img usemap='#Map'></body></html>", GRID_2031)
    page = HTML[GRID_2031].replace('href="pdf/Existing', 'href="#pdf/Existing')
    with pytest.raises(ScraperError, match="grid sheets"):
        parse_grid_page(page, GRID_2031)


def test_implausibly_few_plans_raises():
    listing = '<ul class="bullet3"><li><a href="pdf/a.pdf">Development Plan 1988</a></li></ul>'
    download = (
        '<table class="tbl1"><tr><td>Development Plan 1988</td>'
        '<td><a href="pdf/a.pdf">Download</a></td></tr></table>'
    )
    pages = {LISTING_URL: listing, DOWNLOAD_URL: download}
    with pytest.raises(ScraperError, match="only 1 schemes"):
        RajkotRUDADP(FakeClient(pages)).discover()  # type: ignore[arg-type]
