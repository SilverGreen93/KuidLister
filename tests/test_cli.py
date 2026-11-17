"""Tests for kuidlister.cli: stdin handling, --upto and the exit statuses."""

from __future__ import annotations

import io

import pytest

from kuidlister.cli import main, run_cli

SAMPLE = """Unknown location: <kuid:1234:12345>
Modified: <kuid2:4321:54321:2>"""


def feed(monkeypatch, text: str) -> None:
    """Stand in for the terminal's stdin."""
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


# ---------------------------------------------------------------------------
# run_cli: the listing itself
# ---------------------------------------------------------------------------

def test_run_cli_writes_one_comma_separated_line():
    out, err = io.StringIO(), io.StringIO()
    assert run_cli(SAMPLE, out=out, err=err) is True
    assert out.getvalue() == "<kuid:1234:12345>,<kuid:4321:54321>\n"
    assert err.getvalue() == ""


def test_run_cli_with_upto_generates_the_versions():
    out = io.StringIO()
    assert run_cli("<kuid:1234:12345>", upto=2, out=out) is True
    assert out.getvalue() == (
        "<kuid2:1234:12345:0>,<kuid2:1234:12345:1>,<kuid2:1234:12345:2>\n"
    )


def test_run_cli_reports_input_without_kuids():
    out, err = io.StringIO(), io.StringIO()
    assert run_cli("nothing to list", out=out, err=err) is False
    assert out.getvalue() == ""
    assert "No KUIDs" in err.getvalue()


# ---------------------------------------------------------------------------
# main: stdin, --upto, exit status
# ---------------------------------------------------------------------------

def test_reads_the_kuids_from_stdin(monkeypatch, capsys):
    feed(monkeypatch, SAMPLE)
    assert main([]) == 0
    assert capsys.readouterr().out == "<kuid:1234:12345>,<kuid:4321:54321>\n"


def test_upto_option_expands_every_kuid(monkeypatch, capsys):
    feed(monkeypatch, SAMPLE)
    assert main(["--upto", "1"]) == 0
    assert capsys.readouterr().out == (
        "<kuid2:1234:12345:0>,<kuid2:1234:12345:1>,"
        "<kuid2:4321:54321:0>,<kuid2:4321:54321:1>\n"
    )


def test_upto_zero_is_allowed(monkeypatch, capsys):
    feed(monkeypatch, "<kuid:1234:12345>")
    assert main(["--upto", "0"]) == 0
    assert capsys.readouterr().out == "<kuid2:1234:12345:0>\n"


def test_upto_127_is_the_largest_accepted(monkeypatch, capsys):
    feed(monkeypatch, "<kuid:1234:12345>")
    assert main(["--upto", "127"]) == 0
    assert len(capsys.readouterr().out.rstrip("\n").split(",")) == 128


@pytest.mark.parametrize("limit", ["128", "-1", "1000"])
def test_a_limit_out_of_range_is_refused(monkeypatch, capsys, limit):
    feed(monkeypatch, SAMPLE)
    assert main(["--upto", limit]) == 2
    captured = capsys.readouterr()
    assert "invalid" in captured.err
    assert captured.out == ""


def test_input_without_kuids_exits_one(monkeypatch, capsys):
    feed(monkeypatch, "no kuids in this paste")
    assert main([]) == 1
    captured = capsys.readouterr()
    assert "No KUIDs" in captured.err
    assert captured.out == ""


def test_a_limit_out_of_range_is_reported_even_without_kuids(monkeypatch, capsys):
    """The bad option is the user's mistake and wins over an empty input."""
    feed(monkeypatch, "no kuids in this paste")
    assert main(["--upto", "200"]) == 2
    assert "invalid" in capsys.readouterr().err


def test_help_mentions_upto(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "--upto" in capsys.readouterr().out
