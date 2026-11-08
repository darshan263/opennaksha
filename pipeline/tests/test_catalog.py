import json

from opennaksha.catalog import MAX_RUNS, append_run, load_previous, scheme_sort_key, write_catalog
from opennaksha.diff import Discovered, merge
from opennaksha.models import ChangesFile, RunChanges, StatusFile

from .helpers import T0, T1, scheme


def build(nos):
    records, run = merge({}, [Discovered(scheme(n)) for n in nos], {"surat-smc"}, [], T0)
    return records, run


def test_write_and_load_roundtrip(tmp_path):
    records, run = build(["10", "2", "2A"])
    changes = append_run(ChangesFile(), run)
    index = write_catalog(tmp_path, records, changes, StatusFile(), T0)
    assert index.cities[0].id == "surat" and index.cities[0].name_gu == "સુરત"
    assert index.cities[0].scheme_count == 3

    raw = (tmp_path / "catalog" / "cities" / "surat.json").read_text(encoding="utf-8")
    assert "\n" not in raw and ": " not in raw  # compact
    data = json.loads(raw)
    assert [s["scheme_no"] for s in data["schemes"]] == ["2", "2A", "10"]
    assert data["schemes"][0]["first_seen"] == "2026-11-01T02:00:00Z"

    prev = load_previous(tmp_path)
    assert not prev.is_first_run
    assert prev.schemes == records
    assert prev.changes.runs[0].new == ["surat-tp-10", "surat-tp-2", "surat-tp-2a"]


def test_missing_previous_is_first_run(tmp_path):
    assert load_previous(tmp_path).is_first_run
    assert load_previous(None).is_first_run


def test_append_run_skips_empty_and_caps_length():
    changes = ChangesFile()
    assert append_run(changes, RunChanges(run_at=T1)).runs == []
    for _ in range(MAX_RUNS + 5):
        changes = append_run(changes, RunChanges(run_at=T1, new=["x"]))
    assert len(changes.runs) == MAX_RUNS


def test_removed_schemes_not_counted_in_index():
    records, _ = build(["1", "2"])
    records, _ = merge(records, [Discovered(scheme("1"))], {"surat-smc"}, [], T1)
    index = write_catalog_tmp(records)
    assert index.cities[0].scheme_count == 1


def write_catalog_tmp(records):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        return write_catalog(Path(d), records, ChangesFile(), StatusFile(), T1)


def test_sort_key_orders_types_then_numbers():
    records, _ = build(["3", "21", "100"])
    keys = sorted(records.values(), key=scheme_sort_key)
    assert [s.scheme_no for s in keys] == ["3", "21", "100"]
