from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from opennaksha.scrapers.base import ScraperError
from opennaksha.scrapers.surat_suda_dp import (
    DP1986_URL,
    DP2004_URL,
    INDEX_URL,
    SHEETS_URL,
    VARIATIONS_URL,
    SuratSUDADP,
    parse_dp2035,
    parse_old_dp,
    parse_sanction_notification,
    parse_variations,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "suda"
PAGES = {
    INDEX_URL: (FIXTURES / "dp_index.html").read_text(encoding="utf-8"),
    SHEETS_URL: (FIXTURES / "dp2035_sheets.html").read_text(encoding="utf-8"),
    VARIATIONS_URL: (FIXTURES / "dp2035_variations.html").read_text(encoding="utf-8"),
    DP2004_URL: (FIXTURES / "dp2004_sheets.html").read_text(encoding="utf-8"),
    DP1986_URL: (FIXTURES / "dp1986_sheets.html").read_text(encoding="utf-8"),
}
UPLOADS = "https://www.sudaonline.org/wp-content/uploads/"


class FakeClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.fetched: list[str] = []

    def get_text(self, url: str) -> str:
        self.fetched.append(url)
        if url not in self.pages:
            raise RuntimeError(f"HTTP 503 for {url}")
        return self.pages[url]


@pytest.fixture(scope="module")
def schemes():
    client = FakeClient(PAGES)
    found = SuratSUDADP(client).discover()  # type: ignore[arg-type]
    assert sorted(client.fetched) == sorted(PAGES)
    return found


@pytest.fixture(scope="module")
def by_no(schemes):
    return {s.scheme_no: s for s in schemes}


def test_scraper_identity():
    assert SuratSUDADP.source_id() == "surat-suda-dp"
    assert SuratSUDADP.owner_keys() == {"surat-suda:DP"}


def test_counts_and_statuses(schemes):
    # 1 sanctioned DP-2035 + 11 variation groups + DP 2004 + DP 1986 (docs/sources.md §10.1)
    assert len(schemes) == 14
    assert Counter(s.status for s in schemes) == {"final": 1, "draft": 11, "unknown": 2}
    assert all(
        s.city_id == "surat" and s.authority == "SUDA" and s.scheme_type == "DP" for s in schemes
    )


def test_ids_unique(schemes):
    assert len({s.id for s in schemes}) == len(schemes)


def test_urls_absolute_without_spaces(schemes):
    for s in schemes:
        assert s.files, s.id
        assert len({f.url for f in s.files}) == len(s.files), s.id
        for f in s.files:
            assert f.url.startswith(UPLOADS), f.url
            assert " " not in f.url


def test_dp2035_record(by_no):
    s = by_no["2035"]
    assert s.id == "surat-suda-dp-2035-suda-area"
    assert s.name_en == "SUDA area"
    assert s.status == "final"
    assert s.status_label == "Sanctioned 08-10-2020 (corrigendum 09-11-2020)"
    assert s.status_date == date(2020, 10, 8)
    assert s.source_page_url == SHEETS_URL
    # index map + BASE MAP + 45 sheets + sanction notification
    assert len(s.files) == 48
    maps = [f for f in s.files if f.kind == "map"]
    assert len(maps) == 47
    assert [f.title for f in maps[:5]] == ["Index map", "Base map", "Sheet A", "Sheet B", "Sheet C"]
    assert maps[-1].title == "Sheet Z"
    assert maps[0].url == UPLOADS + "2020/11/INDAX-MAP.jpg"
    assert maps[1].url == UPLOADS + "2020/11/BASE-MAP.jpg"
    assert maps[2].url == UPLOADS + "2020/11/A.jpg"
    assert "Sheet C1" in {f.title for f in maps}
    notif = s.files[-1]
    assert notif.kind == "notification"
    assert notif.url == (
        UPLOADS + "2020/11/SANCTION-MODIFICATION-DP-2035-NOTIFICATION-DT-08-10-2020-"
        "CORRIGENDUM-DT-09-11-2020.pdf"
    )


def test_dp2035_without_notification_link():
    # The notification is only attached when it is actually linked; no URL is constructed.
    index = PAGES[INDEX_URL].replace("SANCTION", "Something")
    assert parse_sanction_notification(index) is None
    s = parse_dp2035(PAGES[SHEETS_URL], None)
    assert len(s.files) == 47
    assert all(f.kind == "map" for f in s.files)


def test_variation_records(by_no):
    var = [s for no, s in by_no.items() if no.startswith("2035-var-")]
    assert len(var) == 11
    assert all(s.status == "draft" for s in var)
    assert sum(len(s.files) for s in var) == 33
    assert sorted(s.scheme_no for s in var) == [
        "2035-var-2024-07-09",
        "2035-var-2024-08-09",
        # groups 3 and 4 share 30/10/2024 → group number appended
        "2035-var-2024-10-30-3",
        "2035-var-2024-10-30-4",
        "2035-var-2025-02-21",
        "2035-var-2025-03-20",
        "2035-var-2025-05-06",
        "2035-var-2025-05-19",
        "2035-var-2025-06-09",
        # group 10 has two dates; the first one is used
        "2035-var-2025-09-11",
        "2035-var-2026-02-27",
    ]
    for s in var:
        assert s.status_date is not None
        assert s.scheme_no.startswith(f"2035-var-{s.status_date.isoformat()}")
        assert any(f.kind == "map" for f in s.files), s.scheme_no
        assert any(f.kind == "notification" for f in s.files), s.scheme_no


def test_first_variation_group(by_no):
    s = by_no["2035-var-2024-07-09"]
    assert s.id == "surat-suda-dp-2035-var-2024-07-09"
    assert s.name_en is None
    assert s.name_gu == "સોનારી(SMC), અબ્રામા(SMC), ખરવાસા, બોણંદ, ગોથાણ(SMC), ભરથાણા-કોસાડ(SMC)"
    assert s.status_label is not None
    assert s.status_label.startswith("સુડાની મંજુર વિકાસ યોજના – ૨૦૩૫")
    assert "૦૯/૦૭/૨૦૨૪" in s.status_label
    assert [(f.kind, f.title) for f in s.files] == [
        ("notification", "રાજ્ય-પત્રમાં પ્રસિદ્ધિની વિગત"),
        ("notification", "જાહેરનામાં ક્રમાંક: GH/V/113 of 2024/UDUHD/DVP/e-file/18/2024/2673/L"),
        ("map", "જાહેરનામાંને સંલગ્ન નકશા"),
    ]
    assert s.files[2].url == UPLOADS + "2024/08/3.-Maps.pdf"


def test_variation_group_8_sheet_ranges(by_no):
    s = by_no["2035-var-2025-05-19"]
    assert s.name_gu is None
    assert s.name_en == "Sheets 2-22"
    assert s.id == "surat-suda-dp-2035-var-2025-05-19-sheets-2-22"
    maps = [f for f in s.files if f.kind == "map"]
    assert [f.title for f in maps] == ["શીટ નંબર ૨ થી ૮", "શીટ નંબર ૯ થી ૧૫", "શીટ નંબર ૧૬ થી ૨૨"]
    assert maps[0].url == UPLOADS + "2025/05/3.Sheet-No-2-to-8.pdf"
    assert len(s.files) == 5  # the link-less "maps" header row is skipped


def test_variation_group_10_duplicate_labels(by_no):
    s = by_no["2035-var-2025-09-11"]
    titles = [f.title for f in s.files]
    assert titles[:2] == ["રાજ્ય-પત્રમાં પ્રસિદ્ધિની વિગત (1)", "રાજ્ય-પત્રમાં પ્રસિદ્ધિની વિગત (2)"]
    assert len(set(titles)) == len(titles)


def test_old_dps_keep_case_sensitive_urls(by_no):
    dp2004, dp1986 = by_no["2004"], by_no["1986"]
    for s in (dp2004, dp1986):
        assert s.name_en == "SUDA area"
        assert s.status == "unknown"
        assert s.status_label == "Earlier development plan (superseded; low resolution)"
        assert all(f.kind == "map" for f in s.files)
    assert len(dp2004.files) == 27
    assert len(dp1986.files) == 20
    assert dp2004.id == "surat-suda-dp-2004-suda-area"
    assert (dp2004.files[0].title, dp2004.files[0].url) == (
        "Sheet Landuse",
        UPLOADS + "2013/08/landuse.jpg",
    )
    assert (dp2004.files[1].title, dp2004.files[1].url) == ("Sheet A", UPLOADS + "2013/08/a.jpg")
    assert (dp1986.files[0].title, dp1986.files[0].url) == ("Sheet A", UPLOADS + "2013/08/A.jpg")
    q = next(f for f in dp1986.files if f.title == "Sheet Q")
    assert q.url == UPLOADS + "2013/08/Q-1986.jpg"


def test_drafts_not_scraped(schemes):
    urls = {f.url for s in schemes for f in s.files}
    assert not any(f"/{folder}/" in u for u in urls for folder in ("2016/05", "2017/04", "2019/02"))


@pytest.mark.parametrize("missing", list(PAGES))
def test_failed_page_fails_whole_source(missing):
    pages = {u: h for u, h in PAGES.items() if u != missing}
    with pytest.raises(RuntimeError, match="503"):
        SuratSUDADP(FakeClient(pages)).discover()  # type: ignore[arg-type]


MAINTENANCE = "<html><body><p>Under maintenance</p></body></html>"


def test_layout_change_raises():
    with pytest.raises(ScraperError):
        parse_dp2035(MAINTENANCE)
    with pytest.raises(ScraperError):
        parse_variations(MAINTENANCE)
    with pytest.raises(ScraperError):
        parse_old_dp(MAINTENANCE, DP2004_URL, "2004")
    with pytest.raises(ScraperError):
        parse_sanction_notification(MAINTENANCE)


def test_layout_change_fails_discover():
    pages = dict(PAGES)
    pages[DP1986_URL] = pages[DP1986_URL].replace("gallery-item", "something-else")
    with pytest.raises(ScraperError, match="gallery items"):
        SuratSUDADP(FakeClient(pages)).discover()  # type: ignore[arg-type]


def _gallery(n: int) -> str:
    items = "".join(
        f"<dl class='gallery-item'><dt class='gallery-icon'><a href='/wp-content/uploads/{i}.jpg'>"
        f"</a></dt><dd class='gallery-caption'>{i}</dd></dl>"
        for i in range(n)
    )
    return f"<div class='entry-content'><div class='gallery'>{items}</div></div>"


def test_implausibly_few_sheets_raises():
    with pytest.raises(ScraperError, match="only 3 gallery items"):
        parse_old_dp(_gallery(3), DP2004_URL, "2004")
    with pytest.raises(ScraperError, match="only 10 gallery items"):
        parse_dp2035(_gallery(10))
    assert len(parse_old_dp(_gallery(20), DP2004_URL, "2004").files) == 20


def test_too_few_variation_groups_raises():
    html = PAGES[VARIATIONS_URL]
    cut = html.index("(૪) સુડાની")
    head = html[: html.rindex("<hr", 0, cut)] + "</div></body></html>"
    with pytest.raises(ScraperError, match="only 3 variation groups"):
        parse_variations(head)


def test_variation_group_without_table_raises():
    html = PAGES[VARIATIONS_URL].replace("<table", "<div", 1)
    with pytest.raises(ScraperError, match="without header or table"):
        parse_variations(html)
