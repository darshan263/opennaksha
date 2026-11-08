from opennaksha.diff import Discovered, merge
from opennaksha.files import FileState
from opennaksha.models import Overlay

from .helpers import T0, T1, T2, scheme

URL = "https://example.test/tp57.pdf"


def found(s, shas: dict[str, str] | None = None) -> Discovered:
    shas = shas or {}
    return Discovered(s, {u: FileState(sha256=h, size_bytes=10) for u, h in shas.items()})


def first_run():
    records, changes = merge({}, [found(scheme("57"), {URL: "aaa"})], {"surat-smc"}, [], T0)
    return records


def test_new_scheme():
    records, changes = merge({}, [found(scheme("57"), {URL: "aaa"})], {"surat-smc"}, [], T0)
    r = records["surat-tp-57"]
    assert changes.new == ["surat-tp-57"]
    assert r.first_seen == r.last_changed == r.last_checked == T0
    assert r.files[0].sha256 == "aaa"
    assert r.files[0].first_seen == T0
    assert not r.files[0].superseded


def test_second_identical_run_has_no_changes():
    prev = first_run()
    records, changes = merge(prev, [found(scheme("57"), {URL: "aaa"})], {"surat-smc"}, [], T1)
    assert not changes.has_data_changes
    r = records["surat-tp-57"]
    assert r.last_changed == T0
    assert r.last_checked == T1
    assert len(r.files) == 1


def test_changed_map_file_supersedes_old_entry():
    prev = first_run()
    records, changes = merge(prev, [found(scheme("57"), {URL: "bbb"})], {"surat-smc"}, [], T1)
    r = records["surat-tp-57"]
    assert [c.model_dump() for c in changes.changed] == [
        {"id": "surat-tp-57", "what": ["map_file"]}
    ]
    assert [(f.sha256, f.superseded) for f in r.files] == [("aaa", True), ("bbb", False)]
    assert r.files[1].first_seen == T1
    assert r.last_changed == T1


def test_unhashed_file_getting_a_hash_is_not_a_change():
    records, _ = merge({}, [found(scheme("57"))], {"surat-smc"}, [], T0)  # --no-download
    records, changes = merge(records, [found(scheme("57"), {URL: "aaa"})], {"surat-smc"}, [], T1)
    assert not changes.has_data_changes
    assert records["surat-tp-57"].files[0].sha256 == "aaa"


def test_new_file_and_dropped_file():
    prev = first_run()
    other = "https://example.test/book57.pdf"
    s = scheme("57", files=[("scheme_book", other)])
    records, changes = merge(prev, [found(s, {other: "ccc"})], {"surat-smc"}, [], T1)
    r = records["surat-tp-57"]
    assert changes.changed[0].what == ["map_file", "new_file"]
    assert [(f.url, f.superseded) for f in r.files] == [(URL, True), (other, False)]


def test_status_and_name_change():
    prev = first_run()
    s = scheme("57", status="final", name_en="Renamed")
    _, changes = merge(prev, [found(s, {URL: "aaa"})], {"surat-smc"}, [], T1)
    assert changes.changed[0].what == ["name", "status"]


def test_removed_from_source_is_kept_and_flagged():
    prev = first_run()
    records, changes = merge(prev, [found(scheme("58"))], {"surat-smc"}, [], T1)
    assert changes.removed_from_source == ["surat-tp-57"]
    r = records["surat-tp-57"]
    assert r.removed_from_source
    assert r.last_changed == T1
    # still removed next time: not reported again
    records, changes = merge(records, [found(scheme("58"))], {"surat-smc"}, [], T2)
    assert changes.removed_from_source == []
    assert records["surat-tp-57"].removed_from_source


def test_scheme_coming_back_clears_flag():
    prev = first_run()
    records, _ = merge(prev, [found(scheme("58"))], {"surat-smc"}, [], T1)
    records, changes = merge(records, [found(scheme("57"), {URL: "aaa"})], {"surat-smc"}, [], T2)
    assert not records["surat-tp-57"].removed_from_source
    assert {c.id for c in changes.changed} == {"surat-tp-57"}


def test_failed_source_keeps_previous_data_unchanged():
    prev = first_run()
    records, changes = merge(prev, [], set(), ["surat-smc"], T1)
    assert records["surat-tp-57"] == prev["surat-tp-57"]
    assert changes.failed_sources == ["surat-smc"]
    assert not changes.has_data_changes


def test_other_sources_untouched_when_one_city_runs():
    prev = first_run()
    s = scheme("1", city="rajkot", authority="RMC", files=[])
    records, changes = merge(prev, [found(s)], {"rajkot-rmc"}, [], T1)
    assert records["surat-tp-57"] == prev["surat-tp-57"]
    assert changes.new == ["rajkot-tp-1"]


def test_overlay_becomes_outdated_when_map_changes():
    prev = first_run()
    prev["surat-tp-57"].overlay = Overlay(
        status="done", url="overlays/surat-tp-57.png", source_sha256="aaa"
    )
    records, _ = merge(prev, [found(scheme("57"), {URL: "aaa"})], {"surat-smc"}, [], T1)
    assert records["surat-tp-57"].overlay.status == "done"
    records, _ = merge(records, [found(scheme("57"), {URL: "bbb"})], {"surat-smc"}, [], T2)
    assert records["surat-tp-57"].overlay.status == "outdated"


def test_duplicate_listings_are_merged():
    a = scheme("57", files=[("map", URL)])
    b = scheme("57", files=[("notification", "https://example.test/n57.pdf")])
    records, changes = merge({}, [found(a), found(b)], {"surat-smc"}, [], T0)
    assert changes.new == ["surat-tp-57"]
    assert len(records["surat-tp-57"].files) == 2
