import pytest

from opennaksha.ids import make_scheme_id


@pytest.mark.parametrize(
    ("city", "kind", "no", "expected"),
    [
        ("surat", "TP", "57", "surat-tp-57"),
        ("Surat", "tp", " 57 ", "surat-tp-57"),
        ("ahmedabad", "TP", "12/A", "ahmedabad-tp-12-a"),
        ("vadodara", "DP", "2031 rev 1", "vadodara-dp-2031-rev-1"),
        ("rajkot", "VILLAGE", "Mavdi / Part", "rajkot-village-mavdi-part"),
    ],
)
def test_make_scheme_id(city, kind, no, expected):
    assert make_scheme_id(city, kind, no) == expected


def test_rejects_unknown_type():
    with pytest.raises(ValueError):
        make_scheme_id("surat", "XYZ", "1")


def test_rejects_empty_scheme_no():
    with pytest.raises(ValueError):
        make_scheme_id("surat", "TP", "  ")
