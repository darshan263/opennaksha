import re
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.gandhinagar_guda import (
    BASE,
    DP_URL,
    STAGE_TITLES,
    TP_URL,
    GandhinagarGUDA,
    GandhinagarGUDADP,
    parse_dp_page,
    parse_tp_page,
    parse_tps_name,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "guda"
DP_HTML = (FIXTURES / "downloads.html").read_text(encoding="utf-8")
TP_HTML = (FIXTURES / "tp_scheme.html").read_text(encoding="utf-8")
DL = BASE + "download/"


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def get_text(self, url: str) -> str:
        if url not in self.pages:
            raise RuntimeError(f"HTTP 503 for {url}")
        return self.pages[url]


def test_source_ids():
    assert GandhinagarGUDADP.source_id() == "gandhinagar-guda-dp"
    assert GandhinagarGUDA.source_id() == "gandhinagar-guda"
    assert GandhinagarGUDADP.owner_keys() == {"gandhinagar-guda:DP"}
    assert GandhinagarGUDA.owner_keys() == {"gandhinagar-guda:TP"}
    assert BASE == "https://guda.gujarat.gov.in/"  # not www. (wrong certificate)


# --------------------------------------------------------------------------- DP


@pytest.fixture(scope="module")
def dp():
    found = GandhinagarGUDADP(FakeClient({DP_URL: DP_HTML})).discover()  # type: ignore[arg-type]
    assert len(found) == 1
    return found[0]


def test_dp_record(dp):
    assert dp.id == "gandhinagar-guda-dp-2024-guda-area"
    assert (dp.city_id, dp.authority, dp.scheme_type, dp.scheme_no, dp.name_en) == (
        "gandhinagar",
        "GUDA",
        "DP",
        "2024",
        "GUDA area",
    )
    assert (dp.status, dp.status_label) == ("final", "Final Development Plan-2024 (First Revised)")
    assert dp.source_page_url == DP_URL


def test_dp_files(dp):
    assert len(dp.files) == 37  # full plan + key map + 35 sheets
    assert all(f.kind == "map" for f in dp.files)
    assert [(f.title, f.url) for f in dp.files[:3]] == [
        ("Full plan", DL + "dpscheme/First%20Revised%20DP%202024.pdf"),
        ("Key map", DL + "dpscheme/key%20map.pdf"),
        ("Sheet 1", DL + "dpscheme/1.pdf"),
    ]
    assert [f.title for f in dp.files[2:]] == [f"Sheet {n}" for n in range(1, 36)]
    assert dp.files[-1].url == DL + "dpscheme/35.pdf"
    assert len({f.url for f in dp.files}) == 37
    for f in dp.files:
        assert f.url.startswith(DL + "dpscheme/")
        assert " " not in f.url
        # forms in the same folder and the TP files are left out
        assert "%E0" not in f.url and "structure" not in f.url and "tpscheme" not in f.url


def test_dp_missing_full_plan_raises():
    page = DP_HTML.replace("Final Development Plan-2024", "Final Plan")
    with pytest.raises(ScraperError, match="full development plan"):
        parse_dp_page(page)


def test_dp_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_dp_page("<html><body><p>Under maintenance</p></body></html>")


def test_dp_too_few_sheets_raises():
    page = re.sub(r">(\d+)</a>", r">Sheet \1</a>", DP_HTML)  # sheet links no longer numeric
    with pytest.raises(ScraperError, match="only 0 DP sheets"):
        parse_dp_page(page)


def test_dp_fetch_error_propagates():
    with pytest.raises(RuntimeError):
        GandhinagarGUDADP(FakeClient({})).discover()  # type: ignore[arg-type]


# --------------------------------------------------------------------------- TP


@pytest.fixture(scope="module")
def tp():
    return GandhinagarGUDA(FakeClient({TP_URL: TP_HTML})).discover()  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("T.P.S No.19 (Raisan- Randesan- koba)", ("19", "Raisan-Randesan-Koba")),
        ("T.P.S. No-11  (Adalaj) PART-A", ("11-A", "Adalaj")),
        ("T.P.S.    No-13  (Vavol)", ("13", "Vavol")),
        (
            "T.P.S. No-9/B (Vasanahadmatia-Sargasan-Uvarsad-Tarapur)",
            ("9/B", "Vasanahadmatia-Sargasan-Uvarsad-Tarapur"),
        ),
        ("T.P.S. No-23/A (Adalaj)", ("23/A", "Adalaj")),
        ("Final Town Planning Scheme Sanctioned by Govt.", None),
    ],
)
def test_parse_tps_name(text, expected):
    assert parse_tps_name(text) == expected


def test_tp_counts_by_status(tp):
    # 8 final + 3 preliminary + 19 draft rows (the draft section skips Sr.No 3); sources.md
    # said "about 32".
    assert len(tp) == 30
    assert Counter(s.status for s in tp) == {"final": 8, "preliminary": 3, "draft": 19}
    assert Counter(s.status_label for s in tp) == {
        "Final sanctioned": 8,
        "Preliminary sanctioned": 3,
        "Draft sanctioned": 19,
    }


def test_tp_ids_unique(tp):
    assert len({s.id for s in tp}) == len(tp)
    for s in tp:
        assert (s.city_id, s.authority, s.scheme_type) == ("gandhinagar", "GUDA", "TP")
        assert s.source_page_url == TP_URL
        assert s.status_date is not None


def test_tp_records(tp):
    by_id = {s.id: s for s in tp}
    s = by_id["gandhinagar-guda-tp-19-raisan-randesan-koba"]
    assert (s.status, s.status_date, s.name_en) == (
        "final",
        date(2010, 12, 10),
        "Raisan-Randesan-Koba",
    )
    assert [(f.kind, f.title, f.url) for f in s.files] == [
        ("other", STAGE_TITLES["draft"], DL + "dpscheme/draft/19.pdf"),
        ("other", STAGE_TITLES["preliminary"], DL + "dpscheme/preliminary/19.pdf"),
        ("other", STAGE_TITLES["final"], DL + "dpscheme/final/19.pdf"),
    ]
    # final date without a link: status still final, only the linked PDF is a file
    s = by_id["gandhinagar-guda-tp-11-a-adalaj"]
    assert (s.status, s.status_date) == ("final", date(2020, 8, 27))
    assert [f.url for f in s.files] == [DL + "dpscheme/preliminary/11-A.pdf"]
    assert by_id["gandhinagar-guda-tp-11-b-adalaj"].status == "draft"
    s = by_id["gandhinagar-guda-tp-9-a-vasanahadmatia-sargasan-vavol"]
    assert (s.scheme_no, s.status, s.status_date) == ("9/A", "preliminary", date(2019, 10, 11))
    s = by_id["gandhinagar-guda-tp-32-palaj"]
    assert (s.status, s.status_date) == ("draft", date(2023, 3, 15))


def test_tp_pdf_linked_from_two_stages_kept_once(tp):
    # TPS-17: the undated draft cell and the preliminary cell link the same PDF.
    s = next(s for s in tp if s.scheme_no == "17")
    assert (s.status, s.status_date) == ("preliminary", date(2023, 9, 25))
    assert [(f.title, f.url) for f in s.files] == [
        (STAGE_TITLES["preliminary"], DL + "tpscheme/TPS-17.pdf"),
    ]


def test_tp_urls_absolute_without_spaces(tp):
    for s in tp:
        assert s.files, s.id
        assert len({f.url for f in s.files}) == len(s.files)
        for f in s.files:
            assert f.url.startswith(DL) and f.url.endswith(".pdf")
            assert " " not in f.url


def test_tp_layout_change_raises():
    with pytest.raises(ScraperError, match="gridbdr"):
        parse_tp_page("<html><body><p>Under maintenance</p></body></html>")
    with pytest.raises(ScraperError, match="header row"):
        parse_tp_page(TP_HTML.replace("Name of the T.P.Scheme", "Scheme"))


def test_tp_missing_column_raises():
    with pytest.raises(ScraperError, match="no column"):
        parse_tp_page(TP_HTML.replace("Preliminary TP scheme", "Second stage"))


def test_tp_implausibly_few_schemes_raises():
    head = TP_HTML.split("T.P.S No.19")[0]
    with pytest.raises(ScraperError, match="only 0 schemes"):
        parse_tp_page(head + "</td></tr></table>")
