from collections import Counter
from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.surat_smc import parse_listing

FIXTURE = Path(__file__).parent.parent / "fixtures" / "smc" / "tp_all_schemes.html"


@pytest.fixture(scope="module")
def schemes():
    return parse_listing(FIXTURE.read_text(encoding="utf-8"))


def test_counts_by_status(schemes):
    # 74 final / 18 preliminary / 49 draft-with-TPO / 5 submitted (docs/sources.md)
    assert len(schemes) == 146
    labels = Counter((s.status, s.status_label) for s in schemes)
    assert labels[("final", None)] == 74
    assert labels[("preliminary", None)] == 18
    assert labels[("draft", "Draft – pending with Town Planning Officer")] == 49
    assert labels[("draft", "Draft – submitted to Govt. for sanction")] == 5


def test_three_different_tp1_schemes_get_distinct_ids(schemes):
    tp1 = sorted(s.id for s in schemes if s.scheme_no == "1")
    assert tp1 == [
        "surat-smc-tp-1-laldarwaja",
        "surat-smc-tp-1-udhna-majura",
        "surat-smc-tp-1-vesu",
    ]
    assert len({s.id for s in schemes}) == len(schemes)


def test_first_scheme_files(schemes):
    s = next(s for s in schemes if s.id == "surat-smc-tp-1-laldarwaja")
    assert s.name_en == "Laldarwaja"
    assert [(f.kind, f.title) for f in s.files] == [("map", "Map"), ("other", "B-Form")]
    assert s.files[0].url == (
        "https://www.suratmunicipal.gov.in/Content/Documents/Departments/FinalSchemes/"
        "TP01%20Laldarwaja/CTP01(LALDARWAJA)FINAL.pdf"
    )


def test_all_urls_absolute_and_encoded(schemes):
    for s in schemes:
        for f in s.files:
            assert f.url.startswith("https://www.suratmunicipal.gov.in/")
            assert " " not in f.url


def test_most_schemes_have_a_map(schemes):
    with_map = sum(1 for s in schemes if any(f.kind == "map" for f in s.files))
    assert with_map >= 140


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_listing("<html><body><p>Under maintenance</p></body></html>")
