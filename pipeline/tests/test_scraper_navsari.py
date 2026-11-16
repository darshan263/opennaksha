"""NMC (Navsari) scraper. Fixture only; no network."""

from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.navsari_nmc import LISTING_URL, NavsariNMC, parse_listing

HTML = (
    Path(__file__).parent.parent / "fixtures" / "navsari" / "townplaning_estate.html"
).read_text(encoding="utf-8")


class FakeClient:
    def get_text(self, url: str) -> str:
        assert url == LISTING_URL
        return HTML


@pytest.fixture(scope="module")
def found():
    return NavsariNMC(FakeClient()).discover()  # type: ignore[arg-type]


def test_source_id():
    assert NavsariNMC.source_id() == "navsari-nmc-dp-tp"


def test_tp_schemes(found):
    tps = {s.scheme_no: s for s in found if s.scheme_type == "TP"}
    assert sorted(tps) == ["1", "2", "3", "4"]
    assert all(s.status == "final" for s in tps.values())
    tp1 = tps["1"]
    assert [(f.kind, f.title) for f in tp1.files] == [
        ("map", "FINAL TP Scheme No. 1 MAP"),
        ("notification", "T.P.1 final NOTIFICATION"),
        ("notification", "DRAFT T.P.1 NOTIFICATION"),
    ]
    assert [f.kind for f in tps["4"].files] == ["map", "notification", "other"]
    assert tp1.files[0].url.startswith("https://nmc.gujarat.gov.in/Home/DownloadDocument/")
    assert tp1.id == "navsari-nmc-tp-1"


def test_dp(found):
    dp = next(s for s in found if s.scheme_type == "DP")
    assert dp.scheme_no == "2039"
    assert dp.files[0].kind == "map"
    assert dp.files[0].title.startswith("Devlopment Plan 2039")
    kinds = [f.kind for f in dp.files]
    assert kinds.count("notification") == 4 and kinds.count("other") == 3


def test_layout_change_fails():
    with pytest.raises(ScraperError):
        parse_listing("<html></html>")
