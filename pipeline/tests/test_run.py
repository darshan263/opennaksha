import json

from opennaksha.run import build_parser, run
from opennaksha.scrapers.base import BaseScraper

from .helpers import FakeFiles, mock_client, scheme

FILES = {
    "https://example.test/tp1.pdf": b"%PDF one",
    "https://example.test/tp2.pdf": b"%PDF two",
}


class FakeSurat(BaseScraper):
    city_id = "surat"
    authority = "SMC"
    schemes = [scheme("1"), scheme("2")]
    fail = False

    def discover(self):
        if FakeSurat.fail:
            raise RuntimeError("site down")
        return list(FakeSurat.schemes)


def args(tmp_path, out, prev=None, *extra):
    argv = ["--output", str(tmp_path / out), "--points-dir", str(tmp_path / "nopoints")]
    if prev:
        argv += ["--previous", str(tmp_path / prev)]
    return build_parser().parse_args(argv + list(extra))


def test_run_twice_second_run_has_zero_changes(tmp_path):
    fake = FakeFiles(dict(FILES))
    FakeSurat.fail = False
    with mock_client(fake) as client:
        r1 = run(args(tmp_path, "out1"), [FakeSurat], client)
        assert r1.first_run and r1.should_commit
        assert r1.new == ["surat-smc-tp-1", "surat-smc-tp-2"]
        r2 = run(args(tmp_path, "out2", "out1"), [FakeSurat], client)
    assert (r2.new, r2.changed, r2.removed_from_source) == ([], [], [])
    assert not r2.should_commit
    assert len(fake.gets) == 2  # files hashed once; second run used HEAD only
    index = json.loads((tmp_path / "out2/catalog/index.json").read_text(encoding="utf-8"))
    assert index["cities"][0]["scheme_count"] == 2


def test_failed_source_keeps_data_and_counts_failures(tmp_path):
    fake = FakeFiles(dict(FILES))
    FakeSurat.fail = False
    with mock_client(fake) as client:
        run(args(tmp_path, "o0"), [FakeSurat], client)
        FakeSurat.fail = True
        prev = "o0"
        for i in range(1, 4):
            r = run(args(tmp_path, f"o{i}", prev), [FakeSurat], client)
            prev = f"o{i}"
            assert "surat-smc" in r.failed_sources
            assert r.should_commit  # failure count must be persisted
        assert r.failing_sources == {"surat-smc": 3}
        city = json.loads((tmp_path / "o3/catalog/cities/surat.json").read_text(encoding="utf-8"))
        assert len(city["schemes"]) == 2
        assert not any(s["removed_from_source"] for s in city["schemes"])

        FakeSurat.fail = False
        r = run(args(tmp_path, "o4", "o3"), [FakeSurat], client)
    assert r.recovered_sources == ["surat-smc"] and r.failing_sources == {}


def test_changed_file_reported(tmp_path):
    fake = FakeFiles(dict(FILES))
    FakeSurat.fail = False
    with mock_client(fake) as client:
        run(args(tmp_path, "a"), [FakeSurat], client)
        fake.files["https://example.test/tp1.pdf"] = b"%PDF one, revised"
        r = run(args(tmp_path, "b", "a"), [FakeSurat], client)
    assert r.changed == [{"id": "surat-smc-tp-1", "what": ["map_file"]}]
    assert r.commit_message.endswith("0 new, 1 changed")
    changes = json.loads((tmp_path / "b/catalog/changes.json").read_text(encoding="utf-8"))
    assert len(changes["runs"]) == 2


def test_cli_without_scrapers(tmp_path, capsys):
    from opennaksha.run import main

    assert main(["--output", str(tmp_path / "o"), "--city", "nowhere", "--no-download"]) == 0
    assert "no enabled scrapers" in capsys.readouterr().out


class FakeAMC(FakeSurat):
    city_id = "ahmedabad"
    authority = "AMC"
    schemes = [scheme("9", city="ahmedabad", authority="AMC", files=[])]
    fail = False

    def discover(self):
        if FakeAMC.fail:
            raise RuntimeError("blocked")
        return list(FakeAMC.schemes)


def test_skipped_source_keeps_data_without_failure(tmp_path, monkeypatch):
    fake = FakeFiles(dict(FILES))
    FakeSurat.fail = FakeAMC.fail = False
    with mock_client(fake) as client:
        run(args(tmp_path, "a"), [FakeSurat, FakeAMC], client)
        FakeAMC.fail = True  # would fail if it ran
        monkeypatch.setenv("OPENNAKSHA_SKIP_SOURCES", "ahmedabad-amc")
        r = run(args(tmp_path, "b", "a"), [FakeSurat, FakeAMC], client)
        assert r.skipped_sources == ["ahmedabad-amc"]
        assert r.failed_sources == {} and not r.should_commit
        city = json.loads(
            (tmp_path / "b/catalog/cities/ahmedabad.json").read_text(encoding="utf-8")
        )
        assert [s["id"] for s in city["schemes"]] == ["ahmedabad-amc-tp-9"]
        assert not city["schemes"][0]["removed_from_source"]
        # --source runs just that source; the other source's data is untouched
        monkeypatch.delenv("OPENNAKSHA_SKIP_SOURCES")
        FakeAMC.fail = False
        r = run(args(tmp_path, "c", "b", "--source", "ahmedabad-amc"), [FakeSurat, FakeAMC], client)
    assert r.succeeded_sources == ["ahmedabad-amc"]
    assert r.scheme_count == 3


class FakeSuratDP(BaseScraper):
    city_id = "surat"
    authority = "SMC"
    scheme_types = frozenset({"DP"})

    def discover(self):
        s = scheme("2035", files=[])
        return [s.model_copy(update={"scheme_type": "DP"})]


def test_scrapers_of_one_authority_only_manage_their_own_types(tmp_path):
    fake = FakeFiles(dict(FILES))
    FakeSurat.fail = False
    assert FakeSuratDP.source_id() == "surat-smc-dp"
    with mock_client(fake) as client:
        run(args(tmp_path, "a"), [FakeSurat, FakeSuratDP], client)
        # Only the TP scraper runs: the DP record must not be marked removed.
        r = run(args(tmp_path, "b", "a"), [FakeSurat], client)
    assert r.removed_from_source == []
    city = json.loads((tmp_path / "b/catalog/cities/surat.json").read_text(encoding="utf-8"))
    dp = [s for s in city["schemes"] if s["scheme_type"] == "DP"]
    assert len(dp) == 1 and not dp[0]["removed_from_source"]


def test_scraper_returning_foreign_records_fails(tmp_path):
    class Bad(FakeSurat):
        def discover(self):
            return [scheme("1", city="rajkot", authority="RMC")]

    with mock_client(FakeFiles({})) as client:
        r = run(args(tmp_path, "x"), [Bad], client)
    assert "surat-smc" in r.failed_sources
