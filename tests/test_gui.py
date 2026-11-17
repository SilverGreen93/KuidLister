"""Tests for kuidlister.gui: the version limit of the checkbox and the result
of the List & Copy button.

These need a QApplication, so they run headless (QT_QPA_PLATFORM=offscreen in
the CI workflows).  The listing itself is covered by test_kuids.py; here it is
only about the widgets around it -- what the number field accepts, what it
refuses, and what it does when a value slips through anyway.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtGui import QValidator
from PyQt6.QtWidgets import QApplication

from kuidlister.gui import DEFAULT_UPTO, _INVALID_UPTO, KuidListerWindow
from kuidlister.kuids import MAX_VERSION


@pytest.fixture(scope="module")
def app():
    """One offscreen QApplication for the whole module."""
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def window(app) -> KuidListerWindow:
    win = KuidListerWindow()
    win.chk_versions.setChecked(False)
    win.input.clear()
    win.output.clear()
    return win


# ---------------------------------------------------------------------------
# the "Generate asset versions up to" number field: 0..127 only
# ---------------------------------------------------------------------------

def test_the_field_starts_at_the_default_with_the_checkbox_off(window):
    assert window.edit_upto.text() == str(DEFAULT_UPTO)
    assert not window.edit_upto.isEnabled()
    assert window._upto() is None


def test_ticking_the_box_enables_the_field(window):
    window.chk_versions.setChecked(True)
    assert window.edit_upto.isEnabled()
    assert window._upto() == DEFAULT_UPTO


@pytest.mark.parametrize("value", ["0", "1", "12", "127"])
def test_a_valid_limit_is_taken_as_typed(window, value):
    window.chk_versions.setChecked(True)
    window.edit_upto.setText(value)
    assert window._upto() == int(value)


@pytest.mark.parametrize("value", ["128", "999", "9999", "-1", "-128", "abc"])
def test_an_out_of_range_limit_is_refused_by_the_validator(window, value):
    """The field will not hold a number outside 0..127.

    QIntValidator on its own calls "128" and "999" *intermediate* -- a longer
    edit of them might still be in range -- so the widget keeps them and a List
    & Copy would run with a limit above 127.  VersionValidator reports Invalid
    for anything not strictly in range instead, the equivalent of the original's
    complaint in TextBox3's TextChanged handler.
    """
    state = window.edit_upto.validator().validate(value, 0)[0]
    assert state == QValidator.State.Invalid


def test_the_field_accepts_the_keystrokes_of_a_valid_limit(window):
    """Every prefix of an in-range limit is acceptable."""
    validator = window.edit_upto.validator()
    for value in ("0", "1", "12", "127"):
        for i in range(1, len(value) + 1):
            state = validator.validate(value[:i], 0)[0]
            assert state == QValidator.State.Acceptable, f"{value[:i]!r} refused"


def test_the_field_still_rejects_a_bare_minus_sign(window):
    """The range starts at zero, so a negative limit cannot be typed."""
    validator = window.edit_upto.validator()
    assert validator.validate("-", 0)[0] == QValidator.State.Invalid


@pytest.mark.parametrize("value", ["128", "999", "127"])
def test_the_button_never_lists_with_an_out_of_range_limit(window, monkeypatch, value):
    """Whatever ends up in the field, a limit above 127 cannot be listed with.

    The validator stops the digits while typing, but text can still reach the
    field another way (paste, or a programmatic set bypasses it), so _upto() is
    what actually guards the listing: an in-range value goes through, anything
    else brings up the warning and leaves the result box empty.
    """
    shown: list[str] = []
    monkeypatch.setattr(
        "kuidlister.gui.QMessageBox.warning",
        lambda _parent, _title, text: shown.append(text),
    )
    window.input.setPlainText("<kuid:1234:12345>")
    window.chk_versions.setChecked(True)
    window.edit_upto.setText(value)

    window.on_list()

    if value == "127":
        assert shown == []
        assert len(window.output.toPlainText().split(",")) == MAX_VERSION + 1
    else:
        assert len(shown) == 1 and "invalid" in shown[0].lower()
        assert window.output.toPlainText() == ""


@pytest.mark.parametrize("value", ["128", "-5"])
def test_a_limit_that_slips_through_is_reported_and_stops_the_list(
    window, monkeypatch, value
):
    """_upto() refuses the value rather than passing it to the listing."""
    shown: list[tuple[str, str]] = []

    def fake_warning(_parent, title, text):
        shown.append((title, text))

    monkeypatch.setattr("kuidlister.gui.QMessageBox.warning", fake_warning)
    window.chk_versions.setChecked(True)
    window.edit_upto.setText(value)

    assert window._upto() is _INVALID_UPTO
    assert len(shown) == 1
    title, text = shown[0]
    assert "version" in title.lower()
    assert "invalid" in text.lower()


def test_the_button_does_nothing_when_the_limit_was_refused(window, monkeypatch):
    """No output and no clipboard write after a refused limit."""
    monkeypatch.setattr("kuidlister.gui.QMessageBox.warning", lambda *a: None)
    copied: list[str] = []
    monkeypatch.setattr(
        QApplication.clipboard(), "setText", lambda text: copied.append(text)
    )
    window.input.setPlainText("<kuid:1234:12345>")
    window.chk_versions.setChecked(True)
    window.edit_upto.setText("999999999999999999999")  # past the validator's int

    window.on_list()

    assert window.output.toPlainText() == ""
    assert window.status.text() == "Ready."
    assert copied == []  # nothing was ever handed to the clipboard


# ---------------------------------------------------------------------------
# the button with a valid limit
# ---------------------------------------------------------------------------

def test_the_button_lists_and_copies_the_result(window, monkeypatch):
    # The real system clipboard is shared with the rest of the desktop and is
    # flaky to read back inside a test run (Qt commits it from the event loop,
    # and pytest holds the Windows clipboard itself), so capture what the app
    # hands to the clipboard instead of round-tripping through the OS.
    copied: list[str] = []
    monkeypatch.setattr(
        QApplication.clipboard(), "setText", lambda text: copied.append(text)
    )
    window.input.setPlainText("<kuid:1234:12345> again <kuid:1234:12345>")

    window.on_list()

    assert window.output.toPlainText() == "<kuid:1234:12345>"
    assert copied == ["<kuid:1234:12345>"]
    assert window.status.text().startswith("Listed 1 KUIDs in")


def test_the_checkbox_generates_one_version_run_per_asset(window):
    """Repeats of one asset give a single 0..n run, starting with the bare kuid."""
    window.input.setPlainText(
        "<kuid:1234:12345> <kuid2:1234:12345:3> <kuid2:1234:12345:4>"
    )
    window.chk_versions.setChecked(True)
    window.edit_upto.setText("2")

    window.on_list()

    assert window.output.toPlainText() == (
        "<kuid:1234:12345>,<kuid2:1234:12345:1>,<kuid2:1234:12345:2>"
    )


def test_the_button_keeps_versions_but_normalises_zero(window):
    """Checkbox off: :3 and :4 stay separate, an explicit :0 becomes the kuid.

    Guards that the GUI shares list_kuids' rules -- it used to format tokens on
    its own and drop every version.
    """
    window.input.setPlainText(
        "<kuid2:1234:12345:3> <kuid2:1234:12345:4> <kuid2:1234:12345:0>"
    )

    window.on_list()

    assert window.output.toPlainText() == (
        "<kuid2:1234:12345:3>,<kuid2:1234:12345:4>,<kuid:1234:12345>"
    )


def test_negative_kuids_survive_the_button(window):
    window.input.setPlainText(
        "<kuid:-1234:-12345> <kuid:-1234:12345> "
        "<kuid:1234:-12345> <kuid2:1234:-12345:2>"
    )

    window.on_list()

    assert window.output.toPlainText() == (
        "<kuid:-1234:-12345>,<kuid:-1234:12345>,"
        "<kuid:1234:-12345>,<kuid2:1234:-12345:2>"
    )


def test_the_maximum_limit_is_usable_from_the_field(window):
    window.input.setPlainText("<kuid:1234:12345>")
    window.chk_versions.setChecked(True)
    window.edit_upto.setText(str(MAX_VERSION))

    window.on_list()

    tokens = window.output.toPlainText().split(",")
    assert len(tokens) == MAX_VERSION + 1
    assert tokens[0] == "<kuid:1234:12345>"
    assert not any(token.endswith(":0>") for token in tokens)


def test_clear_empties_the_input(window):
    window.input.setPlainText("<kuid:1:2>")
    window.btn_clear.click()
    assert window.input.toPlainText() == ""
