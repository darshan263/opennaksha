from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.surat_smc_village import (
    LISTING_URL,
    STATUS_LABEL,
    SuratSMCVillage,
    parse_listing,
    village_list,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "smc" / "dp_sheets.html"
HTML = FIXTURE.read_text(encoding="utf-8")
ZIP = "https://www.suratmunicipal.gov.in/Images/Departments/TownPlanning/"


class FakeClient:
    def get_text(self, url: str) -> str:
        assert url == LISTING_URL
        return HTML


@pytest.fixture(scope="module")
def sheets():
    return SuratSMCVillage(FakeClient()).discover()  # type: ignore[arg-type]


def test_source_id_and_types():
    assert SuratSMCVillage.source_id() == "surat-smc-village"
    assert SuratSMCVillage.owner_keys() == {"surat-smc:VILLAGE"}


def test_all_26_sheets(sheets):
    assert [s.scheme_no for s in sheets] == [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    assert len({s.id for s in sheets}) == 26
    for s in sheets:
        assert (s.city_id, s.authority, s.scheme_type, s.status) == (
            "surat",
            "SMC",
            "VILLAGE",
            "unknown",
        )
        assert s.status_label == STATUS_LABEL
        assert s.source_page_url == LISTING_URL
        assert len(s.files) == 1
        f = s.files[0]
        assert (f.kind, f.title) == ("map", f"Sheet {s.scheme_no}")
        assert f.url.startswith(ZIP) and f.url.endswith(".zip")


def test_names_and_urls(sheets):
    by = {s.scheme_no: s for s in sheets}
    assert by["A"].name_en == "Ariyana, Ambheta, Kunkni, Sarol"
    assert by["A"].id == "surat-smc-village-a-ariyana-ambheta-kunkni-sarol"
    assert by["P"].name_en == "Abrama, Gothan"
    assert by["P"].files[0].url == ZIP + "P-Abrama,Gothan,.zip"
    # repeats dropped, spelling kept as published
    assert by["J"].name_en == "Variav, Segavasyadla, Gothan, Vaswari"
    assert by["M"].name_en.count("Bhimrad") == 1
    assert by["K"].name_en.startswith("Segavasysdla, Variav, Kosad")
    assert "Chap'bhatha" in by["K"].name_en
    # names SMC cut short on the page stay as published
    assert by["R"].name_en.endswith("Antroli, Oviy")
    # a village appears on several sheets
    assert sum("Vesu" in s.name_en.split(", ") for s in sheets) == 2


def test_village_list():
    assert village_list(" Segvachhama, Malgama, ") == "Segvachhama, Malgama"
    assert village_list("Bhimrad, Bamroli, Bhimrad,  Dumbhal..") == "Bhimrad, Bamroli, Dumbhal"
    assert village_list(" , ") == ""


def test_layout_change_fails():
    with pytest.raises(ScraperError):
        parse_listing("<html><body><p>moved</p></body></html>")
    rows = "".join(f'<tr><td>{c}</td><td><a href="/x/{c}.zip">V{c}</a></td></tr>' for c in "ABC")
    html = (
        '<table class="table-customized"><thead><tr><th>Sheet No.</th><th>Name</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )
    with pytest.raises(ScraperError, match="only 3"):
        parse_listing(html)
