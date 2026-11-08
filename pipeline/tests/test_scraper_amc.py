from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from opennaksha.scrapers.ahmedabad_amc import map_status, parse_listing
from opennaksha.scrapers.base import ScraperError

FIXTURE = Path(__file__).parent.parent / "fixtures" / "amc" / "tp_scheme_information.html"


@pytest.fixture(scope="module")
def schemes():
    return parse_listing(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(schemes):
    return {s.id: s for s in schemes}


def test_counts_by_status(schemes):
    # The page has 287 Sr Nos, but 15 of them repeat the TPS name + number of an earlier row
    # (separately listed "greenbelt" variations of TPS 11, 21, 22, 23, 25-31). They are the same
    # scheme, so they are merged: 287 - 15 = 272.
    assert len(schemes) == 272
    assert Counter(s.status for s in schemes) == {
        "draft": 114,
        "final": 80,
        "sanctioned_variation": 58,
        "preliminary": 20,
    }
    assert all(s.status_label for s in schemes)
    assert {(s.city_id, s.authority, s.scheme_type) for s in schemes} == {
        ("ahmedabad", "AMC", "TP")
    }


def test_ids_unique_even_for_repeated_numbers(schemes):
    assert len({s.id for s in schemes}) == len(schemes)
    tp1 = [s.id for s in schemes if s.scheme_no == "1"]
    assert len(tp1) == 15
    assert "ahmedabad-amc-tp-1-chandlodiya" in tp1
    assert "ahmedabad-amc-tp-1-bopal" in tp1


def test_scheme_numbers_kept_as_strings(by_id):
    for sid, no in [
        ("ahmedabad-amc-tp-1a-bodakdev", "1A"),
        ("ahmedabad-amc-tp-43-a-sola", "43/A"),
        ("ahmedabad-amc-tp-43-b-sola", "43/B"),
    ]:
        assert by_id[sid].scheme_no == no
    nos = {s.scheme_no for s in by_id.values()}
    assert {"152/G", "401-A", "35_1"} <= nos


def test_map_status():
    assert map_status("FINAL SANCTIONED") == "final"
    assert map_status("PRELIMINARY SANCTIONED & ITS CORRI.") == "preliminary"
    assert map_status("DRAFT SANCTION") == "draft"
    assert map_status("DRAFT SANCTIONED") == "draft"
    assert map_status("DRAFT AMENDMENT SANCTIONED") == "sanctioned_variation"
    assert map_status("DRAFT VARIATION SANCTIONED") == "sanctioned_variation"
    assert map_status("UNDER PREPARATION") == "unknown"
    assert map_status("") == "unknown"


def test_principal_only_scheme(by_id):
    s = by_id["ahmedabad-amc-tp-1b-bodakdev"]
    assert s.name_en == "Bodakdev"
    assert (s.status, s.status_label, s.status_date) == (
        "final",
        "FINAL SANCTIONED",
        date(1993, 1, 1),
    )
    # The portal/... and file:///E:/... anchors in the same cell are dropped.
    assert [(f.kind, f.title, f.url) for f in s.files] == [
        (
            "map",
            "TPS_1_B_Bodakde_PRINC_FINAL_SANC",
            "https://ahmedabadcity.gov.in/Uploads/TpInfo/TPS_1_B_BODAKDEV.pdf",
        )
    ]
    bopal = by_id["ahmedabad-amc-tp-1-bopal"]
    assert (bopal.status, bopal.status_date) == ("preliminary", date(2019, 6, 10))
    sola = by_id["ahmedabad-amc-tp-43-a-sola"]
    assert (sola.status, sola.status_label) == ("draft", "DRAFT SANCTION")


def test_latest_varied_row_gives_variation_status(by_id):
    # rowspan scheme: PRINCIPAL 01/01/1993, then 1ST VARIED FINAL SANCTIONED 27/04/2007
    s = by_id["ahmedabad-amc-tp-1a-bodakdev"]
    assert (s.status, s.status_label, s.status_date) == (
        "sanctioned_variation",
        "FINAL SANCTIONED (1ST VARIED)",
        date(2007, 4, 27),
    )
    s = by_id["ahmedabad-amc-tp-1-ghodasar"]
    assert (s.status, s.status_label, s.status_date) == (
        "sanctioned_variation",
        "DRAFT AMENDMENT SANCTIONED (2ND VARIED)",
        date(2010, 1, 5),
    )
    # 4TH and 5TH VARIED share the latest date; the later row wins.
    s = by_id["ahmedabad-amc-tp-3-ellisbridge"]
    assert (s.status_label, s.status_date) == (
        "DRAFT AMENDMENT SANCTIONED (5TH VARIED)",
        date(2010, 3, 9),
    )


def test_irregular_rows(by_id):
    # TPS 5 City Wall: Type/Status/Drawing span 6 rows, the extra rows hold only a date.
    s = by_id["ahmedabad-amc-tp-5-city-wall-improvement"]
    assert (s.status, s.status_label, s.status_date) == (
        "sanctioned_variation",
        "FINAL SANCTIONED",
        date(2013, 8, 22),
    )
    assert len(s.files) == 12
    assert s.files[0].title == "TPS_5_CITYWALL IMPROVEMENT_SECTION_1_ASTODIA GATE TO RAIPUR GATE"
    # SOLA 43/A's drawing cell rowspans into 43/B's row; 43/B has no link of its own.
    assert by_id["ahmedabad-amc-tp-43-b-sola"].files == []
    assert len(by_id["ahmedabad-amc-tp-43-a-sola"].files) == 1
    # "16/12/2015 19/02/2016" (with a corrigendum): the later date is used.
    assert by_id["ahmedabad-amc-tp-26-vasna-north-extension"].status_date == date(2017, 6, 13)
    assert by_id["ahmedabad-amc-tp-215-ambli"].status_date == date(2021, 3, 31)


def test_rows_repeated_under_another_sr_no_are_merged(by_id):
    # Sr 60 (with 3 varied rows), Sr 61 and Sr 171 are all TPS 23 Sabarmati.
    s = by_id["ahmedabad-amc-tp-23-sabarmati"]
    assert (s.status, s.status_label, s.status_date) == (
        "sanctioned_variation",
        "DRAFT SANCTION (4TH VARIED)",
        date(2017, 3, 21),
    )
    assert [f.title for f in s.files] == [
        "TPS_23_SABARMATI_UP_TO_3VF",
        "TPS_23_SABARMATI_GREENBELT_4TH",
        "TPS_23_SABARMATI_GREENBELT_4TH_VARIED_DRAFT_SANC_21032017",
    ]
    assert len({f.url for f in s.files}) == 3
    # A later Sr row that says PRINCIPAL is still a variation of the earlier principal (Sr 55).
    amb = by_id["ahmedabad-amc-tp-21-ambawadi"]
    assert (amb.status, amb.status_label) == ("sanctioned_variation", "DRAFT SANCTIONED")


def test_drawing_title_rebuilt_from_split_anchors(by_id):
    s = by_id["ahmedabad-amc-tp-1-ghodasar"]
    assert [(f.title, f.url) for f in s.files] == [
        (
            "TPS_1_GHODASAR_PRINC_FINAL_SANC_05011999_UP_TO_2VDA_05012010",
            "https://ahmedabadcity.gov.in/Uploads/TpInfo/TPS_1_GHODASAR.pdf",
        )
    ]


def test_all_dates_parsed(schemes):
    assert all(isinstance(s.status_date, date) for s in schemes)
    assert all(date(1900, 1, 1) < s.status_date < date(2026, 11, 9) for s in schemes)


def test_all_urls_absolute_encoded_and_under_uploads(schemes):
    urls = [f.url for s in schemes for f in s.files]
    assert len(urls) == 306
    for s in schemes:
        for f in s.files:
            assert f.kind == "map"
            assert f.title
            assert f.url.startswith("https://ahmedabadcity.gov.in/Uploads/")
            assert " " not in f.url
    assert (
        "https://ahmedabadcity.gov.in/Uploads/TpInfo/TPS_20_GULBAI%20TEKRA.pdf" in urls
    )  # raw space in the href
    with_map = sum(1 for s in schemes if s.files)
    assert with_map == len(schemes) - 1  # only SOLA 43/B has no drawing


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_listing("<html><body><p>Under maintenance</p></body></html>")


def test_too_few_schemes_raises():
    header = (
        "<tr><th>Sr No</th><th>TPS Name</th><th>TPS No</th><th>Type</th>"
        "<th>Current Status</th><th>Current Status Date</th><th>Drawing Name</th></tr>"
    )
    row = (
        "<tr><td>1</td><td>BOPAL</td><td>1</td><td>PRINCIPAL</td>"
        "<td>FINAL SANCTIONED</td><td>01/01/1993</td><td></td></tr>"
    )
    html = f'<div class="AMCtable2 TP_Scheme"><table><tbody>{header}{row}</tbody></table></div>'
    with pytest.raises(ScraperError, match="only 1 schemes"):
        parse_listing(html)


def test_renamed_columns_raise():
    html = (
        '<div class="AMCtable2 TP_Scheme"><table><tr><th>Sr No</th><th>TPS Name</th>'
        "<th>TPS No</th><th>Stage</th></tr></table></div>"
    )
    with pytest.raises(ScraperError, match="lacks columns"):
        parse_listing(html)
