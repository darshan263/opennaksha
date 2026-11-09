from pathlib import Path

import pytest

from opennaksha.scrapers.ahmedabad_auda_dp import LISTING_URL, AhmedabadAUDADP, parse_listing
from opennaksha.scrapers.base import ScraperError

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "auda" / "rdp.html").read_text(
    encoding="utf-8"
)
RDP = "https://www.auda.org.in/uploads/Assets/rdp/"


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def get_text(self, url: str) -> str:
        if url not in self.pages:
            raise RuntimeError(f"HTTP 503 for {url}")
        return self.pages[url]


@pytest.fixture(scope="module")
def schemes():
    return AhmedabadAUDADP(FakeClient({LISTING_URL: FIXTURE})).discover()  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def by_year(schemes):
    return {s.scheme_no: s for s in schemes}


def test_scraper_identity():
    assert AhmedabadAUDADP.source_id() == "ahmedabad-auda-dp"
    assert AhmedabadAUDADP.owner_keys() == {"ahmedabad-auda:DP"}


def test_one_record_per_map_year(schemes):
    assert [s.scheme_no for s in schemes] == ["1987", "2002", "2021", "2022"]
    assert len({s.id for s in schemes}) == 4
    assert schemes[0].id == "ahmedabad-auda-dp-1987-auda-area"
    for s in schemes:
        assert (s.city_id, s.authority, s.scheme_type) == ("ahmedabad", "AUDA", "DP")
        assert s.name_en == "AUDA area"
        assert s.source_page_url == LISTING_URL
        assert [f.kind for f in s.files].count("map") == 1


def test_statuses(by_year):
    assert by_year["2022"].status == "final"
    assert by_year["2022"].status_label == "AUDA REVISED DEVELOPMENT PLAN 2022 MAP"
    for year in ("1987", "2002", "2021"):
        assert by_year[year].status == "unknown"
        assert by_year[year].status_label == "Earlier development plan (superseded)"


def test_file_counts_and_attachment(by_year):
    # 17 rows: 4 maps, 1 broken (skipped), "Note on … 2021" → 2021, 11 others → newest (2022)
    assert {y: len(s.files) for y, s in by_year.items()} == {
        "1987": 1,
        "2002": 1,
        "2021": 2,
        "2022": 12,
    }
    assert [(f.kind, f.title) for f in by_year["2021"].files] == [
        ("map", "AUDA REVISED DEVELOPMENT PLAN 2021 MAP"),
        ("other", "Note on Revised Development Plan 2021"),
    ]
    kinds = {f.title: f.kind for f in by_year["2022"].files}
    assert kinds["AUDA REVISED DEVELOPMENT PLAN 2022 MAP"] == "map"
    assert kinds["DP-Corrigendum"] == "notification"
    assert kinds["Gazette(10-06-13)"] == "notification"
    assert kinds["Govt Notification 04.03.2014 section 17"] == "notification"
    assert kinds["Notication of AUDA Sanctioned Revised Development Plan"] == "notification"
    assert kinds["COMMON GDCR PART1"] == "other"
    assert (
        kinds[
            "Notification - Final Comprehensive General Development Control Regulation-2017"
            " dt 12 10 17"
        ]
        == "other"
    )


def test_urls_https_encoded(by_year):
    assert by_year["1987"].files[0].url == RDP + "audadp-198702062016045328297.pdf"
    assert by_year["2021"].files[0].url == RDP + "Basemap-36X36.jpg"
    assert (
        by_year["2021"].files[1].url == RDP + "Note%20on%20Revised%20Development%20Plan%202021.pdf"
    )
    for s in by_year.values():
        for f in s.files:
            assert f.url.startswith(RDP)
            assert " " not in f.url


def test_truncated_href_row_skipped(schemes):
    titles = {f.title for s in schemes for f in s.files}
    assert not any("Adhiniyam" in t for t in titles)
    assert not any(f.url.endswith(",") for s in schemes for f in s.files)


def _page(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><td><span class='name'>{i}</span></td><td><span class='name'>{t}</span></td>"
        f"<td><a href='{h}'>Click Here</a></td></tr>"
        for i, (t, h) in enumerate(rows, 1)
    )
    return (
        "<table class='gridtable'><thead><th>Sr. No.</th><th>Title</th><th>View Detail</th>"
        f"</thead><tbody>{body}</tbody></table>"
    )


def test_extensionless_href_detected_generically():
    rows = [(f"AUDA REVISED DEVELOPMENT PLAN {y} MAP", f"/u/dp{y}.pdf") for y in (1990, 2000, 2010)]
    rows += [(f"Doc {i}", f"/u/doc{i}.pdf") for i in range(5)]
    rows.append(("Some Act 1976 Sec. 26, 27, 28", "/u/Some Act 1976 Sec. 26, 27,"))
    found = parse_listing(_page(rows), LISTING_URL)
    assert sum(len(s.files) for s in found) == 8
    assert found[-1].scheme_no == "2010" and found[-1].status == "final"


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_listing("<html><body><p>Under maintenance</p></body></html>")
    with pytest.raises(ScraperError):
        parse_listing(FIXTURE.replace("gridtable", "othertable"))


def test_too_few_map_rows_raises():
    html = FIXTURE.replace("DEVELOPMENT PLAN 1987 MAP", "DEVELOPMENT PLAN 1987").replace(
        "DEVELOPMENT PLAN 2002 MAP", "DEVELOPMENT PLAN 2002"
    )
    with pytest.raises(ScraperError, match="only 2 plan map rows"):
        parse_listing(html)


def test_failed_fetch_fails_source():
    with pytest.raises(RuntimeError):
        AhmedabadAUDADP(FakeClient({})).discover()  # type: ignore[arg-type]
