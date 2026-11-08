import pytest

from opennaksha.ids import make_scheme_id, slug


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("surat", "SMC", "TP", "1", "Laldarwaja"), "surat-smc-tp-1-laldarwaja"),
        (("surat", "SMC", "TP", "1", "Udhna-Majura"), "surat-smc-tp-1-udhna-majura"),
        (("Surat", "smc", "tp", " 57 ", None), "surat-smc-tp-57"),
        (("ahmedabad", "AMC", "TP", "152/G", "Ghatlodia"), "ahmedabad-amc-tp-152-g-ghatlodia"),
        (("ahmedabad", "AMC", "TP", "35_1", "Sola"), "ahmedabad-amc-tp-35-1-sola"),
        (("vadodara", "VUDA", "DP", "2031 rev 1", ""), "vadodara-vuda-dp-2031-rev-1"),
        (("surat", "SUDA", "TP", "62-A", "Kosad – Amroli"), "surat-suda-tp-62-a-kosad-amroli"),
    ],
)
def test_make_scheme_id(args, expected):
    assert make_scheme_id(*args) == expected


def test_gujarati_only_area_is_dropped():
    assert make_scheme_id("surat", "SMC", "TP", "5", "પાંડેસરા") == "surat-smc-tp-5"


def test_slug():
    assert slug("  T.P.S. (Vesu)  ") == "t-p-s-vesu"


def test_rejects_unknown_type():
    with pytest.raises(ValueError):
        make_scheme_id("surat", "SMC", "XYZ", "1")


def test_rejects_empty_scheme_no():
    with pytest.raises(ValueError):
        make_scheme_id("surat", "SMC", "TP", "  ")
