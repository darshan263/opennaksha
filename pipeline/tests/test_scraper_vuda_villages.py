from collections import Counter
from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.vadodara_vuda_villages import (
    LISTING_URL,
    VadodaraVUDAVillages,
    parse_listing,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "vuda" / "dp_village_maps.html"
HTML = FIXTURE.read_text(encoding="utf-8")
LABEL = "DP village map (Sec. 17, 2nd Revised Development Plan 18-01-2012)"
DL = "https://www.vuda.co.in/download/DP%20MAPS/"


class FakeClient:
    def get_text(self, url: str) -> str:
        assert url == LISTING_URL
        return HTML


@pytest.fixture(scope="module")
def villages():
    return VadodaraVUDAVillages(FakeClient()).discover()  # type: ignore[arg-type]


def by_name(villages):
    return {v.name_en: v for v in villages}


def test_source_id_and_types():
    assert VadodaraVUDAVillages.source_id() == "vadodara-vuda-village"
    assert VadodaraVUDAVillages.owner_keys() == {"vadodara-vuda:VILLAGE"}


def test_counts(villages):
    # Matches the research: 123 villages (Sr.No 1–123, no duplicate names), 208 PDF links.
    assert len(villages) == 123
    assert sum(len(v.files) for v in villages) == 208
    assert Counter(len(v.files) for v in villages) == {1: 78, 2: 20, 3: 17, 4: 4, 5: 3, 8: 1}


def test_ids_unique_and_metadata(villages):
    assert len({v.id for v in villages}) == len(villages)
    assert villages[0].id == "vadodara-vuda-village-dp-2012-aamaliyara"
    for v in villages:
        assert (v.city_id, v.authority, v.scheme_type, v.scheme_no) == (
            "vadodara",
            "VUDA",
            "VILLAGE",
            "DP-2012",
        )
        assert (v.status, v.status_label, v.status_date) == ("unknown", LABEL, None)
        assert v.source_page_url == LISTING_URL
        assert all(f.kind == "map" for f in v.files)
        assert len({f.title for f in v.files}) == len(v.files)


def test_names_tidied(villages):
    names = by_name(villages)
    assert "Ampad" in names  # Name cell is "  AMPAD"
    assert "Vasna Kotaria" in names
    assert "V-Kasba" in names
    assert "Aamaliyara" in names  # from the Name cell, not the folder (AAMLIYARA)


def test_rowspan_sheets_and_titles(villages):
    v = by_name(villages)
    assert [(f.title, f.url) for f in v["Aamaliyara"].files] == [
        ("V95 AAMALIYARA", DL + "AAMLIYARA/V95.AAMLIYARA.pdf"),
        ("V96 AAMALIYARA", DL + "AAMLIYARA/V96.AAMLIYARApdf.pdf"),
    ]
    # raw spaces encoded; link text "V29 AKOTA.pdf" loses its ".pdf"
    assert [(f.title, f.url) for f in v["Akota"].files] == [
        ("TP-1", DL + "AKOTA/TP-1%20.pdf"),
        ("V29 AKOTA", DL + "AKOTA/V29%20AKOTA.pdf"),
    ]
    assert [(f.title, f.url) for f in v["Ajod"].files] == [("AJOD", DL + "AJOD/AJOD%20.pdf")]
    assert [f.title for f in v["Harni"].files][:2] == ["V102 HARNI.1", "V103 HARNI.2"]
    assert len(v["Harni"].files) == 5


def test_urls_absolute_without_spaces(villages):
    for v in villages:
        for f in v.files:
            assert f.url.startswith(DL), f.url
            assert f.url.endswith(".pdf")
            assert " " not in f.url


def test_duplicate_village_rows_are_merged():
    extra = (
        "<tr><td>124</td><td>AJOD</td>"
        '<td><a href="download/DP MAPS/AJOD/AJOD-2.pdf" class="pdf-link">AJOD</a></td></tr>'
        "</tbody>"
    )
    villages = parse_listing(HTML.replace("</tbody>", extra, 1))
    assert len(villages) == 123
    ajod = by_name(villages)["Ajod"]
    assert [(f.title, f.url) for f in ajod.files] == [
        ("AJOD", DL + "AJOD/AJOD%20.pdf"),
        ("AJOD (2)", DL + "AJOD/AJOD-2.pdf"),
    ]


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_listing("<html><body><p>Under maintenance</p></body></html>")
    with pytest.raises(ScraperError, match="styled-table"):
        parse_listing(HTML.replace("styled-table", "plain-table"))


def test_missing_heading_raises():
    with pytest.raises(ScraperError, match="heading"):
        parse_listing(HTML.replace("decorative-heading", "heading"))
    with pytest.raises(ScraperError, match="unexpected heading"):
        parse_listing(HTML.replace("18-01-2012", "2012"))


def test_missing_column_raises():
    with pytest.raises(ScraperError, match="no column"):
        parse_listing(HTML.replace("<th>Name</th>", "<th>Village</th>"))


def test_implausibly_few_villages_raises():
    head = HTML.split('<td rowspan="2">1</td>')[0]
    with pytest.raises(ScraperError, match="only 0 schemes"):
        parse_listing(head + "</tr></tbody></table>")
