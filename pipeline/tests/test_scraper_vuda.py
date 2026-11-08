from collections import Counter
from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.vadodara_vuda import BASE, VadodaraVUDA, parse_folder, parse_page

FIXTURES = Path(__file__).parent.parent / "fixtures" / "vuda"
PAGES = {
    BASE + "tp_scheme_vuda_draft.htm": "tp_draft.html",
    BASE + "tp_scheme_vuda_sanctioned_draft.htm": "tp_sanctioned_draft.html",
    BASE + "tp_scheme_vuda_priliminary.htm": "tp_preliminary.html",
    BASE + "tp_scheme_vuda_final.htm": "tp_final.html",
}
HTML = {url: (FIXTURES / name).read_text(encoding="utf-8") for url, name in PAGES.items()}
FINAL_URL = BASE + "tp_scheme_vuda_final.htm"


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def get_text(self, url: str) -> str:
        if url not in self.pages:
            raise RuntimeError(f"HTTP 503 for {url}")
        return self.pages[url]


@pytest.fixture(scope="module")
def schemes():
    return VadodaraVUDA(FakeClient(HTML)).discover()  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("folder", "expected"),
    [
        ("TP-21-SAMIYALA-BIL", ("21", "Samiyala-Bil")),
        ("TP-24-A", ("24-A", None)),
        ("TPS-27-A-BILL", ("27-A", "Bill")),
        ("bhayali-tp-1", ("1", "Bhayali")),
        ("Bil-Tp1", ("1", "Bil")),
        ("SEVASI-2-FINAL", ("2", "Sevasi")),
        ("Khanpur-Ankodiya-2", ("2", "Khanpur-Ankodiya")),
        ("SAMIYALA-BIL-BHAYALI-5", ("5", "Samiyala-Bil-Bhayali")),
        ("Vemali-TP-1", ("1", "Vemali")),
        ("SAMA-DUMAD-VEMALI", None),
        ("padra", None),
    ],
)
def test_parse_folder(folder, expected):
    assert parse_folder(folder) == expected


def test_counts_by_status(schemes):
    # 10 draft + 5 sanctioned draft + 3 preliminary + 11 final = 29 listings; Sevasi 2 is on
    # both the preliminary and the final page, so 28 schemes.
    assert len(schemes) == 28
    labels = Counter((s.status, s.status_label) for s in schemes)
    assert labels[("draft", None)] == 10
    assert labels[("draft", "Draft – sanctioned")] == 5
    assert labels[("preliminary", None)] == 2
    assert labels[("final", None)] == 11


def test_ids_unique(schemes):
    assert len({s.id for s in schemes}) == len(schemes)


def test_scheme_files(schemes):
    by_id = {s.id: s for s in schemes}
    s = by_id["vadodara-vuda-tp-21-samiyala-bil"]
    assert [(f.kind, f.title, f.url) for f in s.files] == [
        ("map", "Map", BASE + "TPSchemeVuda/draft/TP-21-SAMIYALA-BIL/T.P.S.NO.-21.pdf"),
        ("other", "F-Form", BASE + "TPSchemeVuda/draft/TP-21-SAMIYALA-BIL/T.P.S.NO.-21-F-FORM.pdf"),
    ]
    # "SEVASI-3-Form" counts as the F-form
    assert [f.kind for f in by_id["vadodara-vuda-tp-3-sevasi"].files] == ["map", "other"]


def test_folder_without_number_uses_file_names(schemes):
    by_id = {s.id: s for s in schemes}
    s = by_id["vadodara-vuda-tp-2-sama-dumad-vemali"]
    assert [f.kind for f in s.files] == ["map", "other"]  # unnumbered F-form joins the scheme
    p1, p2 = by_id["vadodara-vuda-tp-1-padra"], by_id["vadodara-vuda-tp-2-padra"]
    assert [f.url.rsplit("/", 1)[1] for f in p1.files] == [
        "PADARA-T-P-S-NO-01.pdf",
        "PADRA-NO1.pdf",
    ]
    assert [f.url.rsplit("/", 1)[1] for f in p2.files] == [
        "PADARA-T-P-S-NO-02.pdf",
        "PADRA-NO2.pdf",
    ]
    assert [f.title for f in p1.files] == ["Map (PADARA-T-P-S-NO-01)", "Map (PADRA-NO1)"]


def test_scheme_on_two_pages_is_merged(schemes):
    s = next(s for s in schemes if s.id == "vadodara-vuda-tp-2-sevasi")
    assert s.status == "final"
    assert s.source_page_url == FINAL_URL
    assert [(f.kind, f.title) for f in s.files] == [
        ("map", "Map"),
        ("other", "F-Form"),
        ("map", "Map (preliminary)"),
        ("other", "F-Form (preliminary)"),
    ]


def test_urls_absolute_and_encoded(schemes):
    for s in schemes:
        for f in s.files:
            assert f.url.startswith(BASE + "TPSchemeVuda/")
            assert " " not in f.url
    koyali = next(s for s in schemes if s.id == "vadodara-vuda-tp-42-koyali")
    assert koyali.files[1].url.endswith("TPS-42-KOYALI-f-form%20-final-06-10-2020.pdf")


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_page("<html><body><p>Under maintenance</p></body></html>", FINAL_URL)


def test_failed_page_fails_whole_source():
    pages = dict(HTML)
    del pages[FINAL_URL]
    with pytest.raises(RuntimeError):
        VadodaraVUDA(FakeClient(pages)).discover()  # type: ignore[arg-type]


def test_implausibly_few_schemes_raises():
    page = "<p><a href='TPSchemeVuda/final/bhayali-tp-1/B.pdf'>B</a></p>"
    with pytest.raises(ScraperError, match="only 1 schemes"):
        VadodaraVUDA(FakeClient(dict.fromkeys(PAGES, page))).discover()  # type: ignore[arg-type]
