"""Tests for kuidlister.cli: stdin handling, --upto and the exit statuses."""

from __future__ import annotations

import io

import pytest

from kuidlister.cli import main, run_cli
from kuidlister.kuids import MAX_VERSION

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
    assert out.getvalue() == "<kuid:1234:12345>,<kuid2:4321:54321:2>\n"
    assert err.getvalue() == ""


def test_run_cli_with_upto_generates_the_versions():
    out = io.StringIO()
    assert run_cli("<kuid:1234:12345>", upto=2, out=out) is True
    assert out.getvalue() == (
        "<kuid:1234:12345>,<kuid2:1234:12345:1>,<kuid2:1234:12345:2>\n"
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
    assert capsys.readouterr().out == "<kuid:1234:12345>,<kuid2:4321:54321:2>\n"


def test_upto_option_expands_every_kuid(monkeypatch, capsys):
    feed(monkeypatch, SAMPLE)
    assert main(["--upto", "1"]) == 0
    assert capsys.readouterr().out == (
        "<kuid:1234:12345>,<kuid2:1234:12345:1>,"
        "<kuid:4321:54321>,<kuid2:4321:54321:1>\n"
    )


def test_upto_zero_lists_each_asset_once_without_a_zero_version(monkeypatch, capsys):
    feed(monkeypatch, "<kuid:1234:12345>")
    assert main(["--upto", "0"]) == 0
    assert capsys.readouterr().out == "<kuid:1234:12345>\n"


def test_upto_never_writes_an_explicit_zero_version(monkeypatch, capsys):
    feed(monkeypatch, "<kuid:1234:12345>")
    main(["--upto", "3"])
    tokens = capsys.readouterr().out.rstrip("\n").split(",")
    assert tokens[0] == "<kuid:1234:12345>"
    assert not any(token.endswith(":0>") for token in tokens)


def test_repeats_in_the_input_are_listed_once(monkeypatch, capsys):
    feed(monkeypatch, "<kuid:1234:12345> and again <kuid:1234:12345>")
    assert main([]) == 0
    assert capsys.readouterr().out == "<kuid:1234:12345>\n"


def test_repeats_give_one_version_run(monkeypatch, capsys):
    feed(monkeypatch, "<kuid:1:2> <kuid2:1:2:3> <kuid2:1:2:4>")
    assert main(["--upto", "2"]) == 0
    assert capsys.readouterr().out == "<kuid:1:2>,<kuid2:1:2:1>,<kuid2:1:2:2>\n"


def test_negative_kuids_are_listed(monkeypatch, capsys):
    feed(
        monkeypatch,
        "<kuid:-1234:-12345> <kuid:-1234:12345> "
        "<kuid:1234:-12345> <kuid2:1234:-12345:2>",
    )
    assert main([]) == 0
    assert capsys.readouterr().out == (
        "<kuid:-1234:-12345>,<kuid:-1234:12345>,"
        "<kuid:1234:-12345>,<kuid2:1234:-12345:2>\n"
    )


def test_versions_are_kept_without_upto(monkeypatch, capsys):
    """Each kuid keeps its version; only exact repeats collapse."""
    feed(monkeypatch, "<kuid2:1234:12345:3> <kuid2:1234:12345:4>")
    assert main([]) == 0
    assert capsys.readouterr().out == "<kuid2:1234:12345:3>,<kuid2:1234:12345:4>\n"


def test_upto_127_is_the_largest_accepted(monkeypatch, capsys):
    feed(monkeypatch, "<kuid:1234:12345>")
    assert main(["--upto", "127"]) == 0
    assert len(capsys.readouterr().out.rstrip("\n").split(",")) == 128


@pytest.mark.parametrize("limit", ["128", "999", "2147483648"])
def test_a_limit_above_the_maximum_is_refused(monkeypatch, capsys, limit):
    feed(monkeypatch, SAMPLE)
    assert main(["--upto", limit]) == 2
    captured = capsys.readouterr()
    assert "invalid" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize("limit", ["-1", "-128"])
def test_a_negative_limit_is_refused(monkeypatch, capsys, limit):
    """A minus sign parses as a number, so the range check has to catch it."""
    feed(monkeypatch, SAMPLE)
    assert main(["--upto", limit]) == 2
    captured = capsys.readouterr()
    assert "invalid" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize("limit", ["abc", "1.5", "", "10x"])
def test_a_limit_that_is_not_a_number_is_refused(monkeypatch, capsys, limit):
    """argparse rejects it with status 2 and a message on stderr."""
    feed(monkeypatch, SAMPLE)
    with pytest.raises(SystemExit) as exc:
        main(["--upto", limit])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "invalid int value" in captured.err


def test_every_limit_from_zero_to_the_maximum_is_accepted(monkeypatch, capsys):
    """The boundary sweep: 0..127 all list something, nothing in between fails."""
    for limit in range(0, MAX_VERSION + 1):
        feed(monkeypatch, "<kuid:1234:12345>")
        assert main(["--upto", str(limit)]) == 0, f"--upto {limit} was refused"
        capsys.readouterr()


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
