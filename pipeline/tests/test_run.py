from opennaksha.run import main


def test_cli_runs(capsys):
    assert main(["--city", "surat", "--no-download"]) == 0
    assert "surat" in capsys.readouterr().out
