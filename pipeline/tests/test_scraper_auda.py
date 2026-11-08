from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from opennaksha.scrapers.ahmedabad_auda import LISTING_URL, AhmedabadAUDA, parse_listing
from opennaksha.scrapers.base import ScraperError

FIXTURE = Path(__file__).parent.parent / "fixtures" / "auda" / "tp_scheme.html"
HTML = FIXTURE.read_text(encoding="utf-8")


class FakeClient:
    def get_text(self, url: str) -> str:
        assert url == LISTING_URL
        return HTML


@pytest.fixture(scope="module")
def schemes():
    return AhmedabadAUDA(FakeClient()).discover()  # type: ignore[arg-type]


def test_counts_by_status(schemes):
    # 94 rows: status from the latest filled sanction date (docs/sources.md)
    assert len(schemes) == 94
    labels = Counter((s.status, s.status_label) for s in schemes)
    assert labels[("final", "Final sanctioned")] == 2  # 109, 9 Sanand
    assert labels[("preliminary", "Preliminary sanctioned")] == 1  # 4/A Sanand
    assert labels[("draft", "Draft sanctioned")] == 85
    # 139/B, 139/A, 413, 417/B, 151, 307 have no dates at all
    assert labels[("unknown", None)] == 6


def test_ids_unique_and_six_tp1s_distinct(schemes):
    assert len({s.id for s in schemes}) == len(schemes)
    tp1 = sorted(s.id for s in schemes if s.scheme_no == "1")
    assert tp1 == [
        "ahmedabad-auda-tp-1-bareja",
        "ahmedabad-auda-tp-1-barejadi-nandej-devdi",
        "ahmedabad-auda-tp-1-dahegam",
        "ahmedabad-auda-tp-1-mahemdabad-khatraj",
        "ahmedabad-auda-tp-1-sanand",
        "ahmedabad-auda-tp-1-shela",
    ]


def test_first_row(schemes):
    s = schemes[0]
    assert s.id == "ahmedabad-auda-tp-419-aslali"
    assert s.name_en == "Aslali"
    assert (s.status, s.status_date) == ("draft", date(2019, 12, 4))
    assert [(f.kind, f.title, f.url) for f in s.files] == [
        ("map", "Map (JPG)", "https://www.auda.org.in/uploads/TPScheme/116.jpg"),
        ("other", "F-Form", "https://www.auda.org.in/uploads/TPScheme/116.pdf"),
    ]


def test_final_and_preliminary_dates(schemes):
    by_id = {s.id: s for s in schemes}
    s = by_id["ahmedabad-auda-tp-109-muthia-bilasia-hansapura"]
    assert (s.status, s.status_date) == ("final", date(2019, 6, 10))
    s = by_id["ahmedabad-auda-tp-4-a-sanand"]
    assert (s.status, s.status_date) == ("preliminary", date(2018, 10, 12))
    s = by_id["ahmedabad-auda-tp-139-b-chharodi"]
    assert (s.status, s.status_label, s.status_date) == ("unknown", None, None)


def test_scheme_numbers_and_names(schemes):
    by_id = {s.id: s for s in schemes}
    assert (
        by_id["ahmedabad-auda-tp-440-352-chekhla-godhavi-garodiya-vasajada-dh-unali"].scheme_no
        == "440+352"
    )
    assert by_id["ahmedabad-auda-tp-134-iyava-rupavati-khoda"].name_en == "Iyava-Rupavati-Khoda"
    assert by_id["ahmedabad-auda-tp-128-geratpur"].name_en == "Geratpur"


def test_every_row_has_map_and_fform_with_absolute_urls(schemes):
    for s in schemes:
        assert [f.kind for f in s.files] == ["map", "other"], s.id
        for f in s.files:
            assert f.url.startswith("https://www.auda.org.in/uploads/TPScheme/")
            assert " " not in f.url


def test_empty_map_input_is_skipped():
    html = HTML.replace('value="/uploads/TPScheme/116.jpg"', 'value="/uploads/TPScheme/"')
    s = parse_listing(html)[0]
    assert [f.kind for f in s.files] == ["other"]


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_listing("<html><body><p>Under maintenance</p></body></html>")


def test_implausibly_few_schemes_raises():
    head = HTML.split("<tbody>")[0]
    with pytest.raises(ScraperError, match="only 0 schemes"):
        parse_listing(head + "<tbody></tbody></table></body></html>")
