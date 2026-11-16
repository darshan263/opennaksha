"""DSIRDA (Dholera SIR) scraper. Fixtures only; no network."""

from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.dholera_dsirda import (
    BASE,
    DholeraDSIRDA,
    parse_documents,
    parse_menu,
)

FIX = Path(__file__).parent.parent / "fixtures" / "dholera"


class FakeClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get_text(self, url: str) -> str:
        self.urls.append(url)
        slug, page_id = url.removeprefix(BASE + "/").split("/")
        return (FIX / f"{slug}_{page_id}.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def found():
    return DholeraDSIRDA(FakeClient()).discover()  # type: ignore[arg-type]


def test_source_id():
    assert DholeraDSIRDA.source_id() == "dholera-dsirda-dp-tp"
    assert DholeraDSIRDA.owner_keys() == {"dholera-dsirda:TP", "dholera-dsirda:DP"}


def test_menu_lists_all_planning_pages():
    pages = parse_menu((FIX / "finaldp_15.html").read_text(encoding="utf-8"))
    by = {s: [p.label for p in pages if p.section == s] for s in ("dp", "preliminary", "draft")}
    assert by["preliminary"][:2] == ["TP 2A", "TP 4A"]
    assert len(by["preliminary"]) == 13
    assert len(by["draft"]) == 6
    assert "Final Development Plan" in by["dp"] and "Notifications" in by["dp"]


def test_tp_records(found):
    tps = {s.scheme_no: s for s in found if s.scheme_type == "TP"}
    assert sorted(tps) == sorted(
        ["1", "2", "3", "4", "5", "6", "2A", "4A", "1A1", "1A2", "2B1", "2B2", "2B3", "3A", "3B",
         "4B1", "5A", "5B", "6A"]
    )  # fmt: skip
    assert tps["1"].status == "draft"
    assert [f.kind for f in tps["1"].files] == ["map", "notification"]
    assert tps["1A2"].status == "preliminary"
    assert [f.title for f in tps["1A2"].files] == ["1A2 Preliminary", "1A2 DSIR"]
    # The Notifications page is attached to the scheme it names.
    assert [f.kind for f in tps["2A"].files] == ["map", "notification"]
    assert tps["2A"].files[1].title == "Notifications TPS- 2A"
    for s in tps.values():
        assert s.id.startswith("dholera-dsirda-tp-")
        assert all(f.url.startswith(BASE + "/web/document/download?") for f in s.files)
        assert all(" " not in f.url for f in s.files)
        assert len({f.url for f in s.files}) == len(s.files)


def test_dp_record(found):
    dp = next(s for s in found if s.scheme_type == "DP")
    assert (dp.scheme_no, dp.status, dp.name_en) == ("final", "final", "Dholera SIR")
    titles = {f.title: f.kind for f in dp.files}
    assert titles["Final Proposed Land Use Plan"] == "map"
    assert titles["DP Villages Map"] == "map"
    assert titles["DP Report 1"] == "other"


def test_documents_are_deduplicated():
    heading, docs = parse_documents(
        (FIX / "dtps1_16.html").read_text(encoding="utf-8"), BASE + "/dtps1/16"
    )
    assert heading == "Draft Town Planning Scheme No.1"
    assert [t for t, _ in docs] == ["OP FP Plan DTPS-1", "Notification DTPS-1"]


def test_layout_change_fails():
    with pytest.raises(ScraperError):
        parse_menu("<html><body><ul></ul></body></html>")
