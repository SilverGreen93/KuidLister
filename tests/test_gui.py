"""Tests for kuidlister.gui: the version limit of the checkbox and the result
of the List & Copy button.

These need a QApplication, so they run headless (QT_QPA_PLATFORM=offscreen in
the CI workflows).  The listing itself is covered by test_kuids.py; here it is
only about the widgets around it -- what the spin box holds, how it clamps to
0..127, and what the button does with the value.
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from kuidlister.gui import DEFAULT_UPTO, KuidListerWindow
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
# the "Generate asset versions up to" spin box: 0..127 only
# ---------------------------------------------------------------------------

def test_the_field_starts_at_the_default_with_the_checkbox_off(window):
    assert window.spin_upto.value() == DEFAULT_UPTO
    assert not window.spin_upto.isEnabled()
    assert window._upto() is None


def test_ticking_the_box_enables_the_field(window):
    window.chk_versions.setChecked(True)
    assert window.spin_upto.isEnabled()
    assert window._upto() == DEFAULT_UPTO


@pytest.mark.parametrize("value", [0, 1, 12, 127])
def test_a_valid_limit_is_taken_as_is(window, value):
    window.chk_versions.setChecked(True)
    window.spin_upto.setValue(value)
    assert window._upto() == value


@pytest.mark.parametrize(
    "typed, clamped", [(128, 127), (999, 127), (-1, 0), (-128, 0)]
)
def test_the_spin_box_clamps_to_its_range(window, typed, clamped):
    """It can never hold a number outside 0..127.

    A QSpinBox clamps to its range on every edit, so the old VersionValidator
    and its warning dialog are gone: an out-of-range value simply cannot exist.
    """
    window.chk_versions.setChecked(True)
    window.spin_upto.setValue(typed)
    assert window.spin_upto.value() == clamped
    assert window._upto() == clamped


def test_the_range_is_zero_to_the_maximum(window):
    assert (window.spin_upto.minimum(), window.spin_upto.maximum()) == (0, MAX_VERSION)


def test_the_steppers_move_within_the_range(window):
    """The up/down buttons step by one and stop at the ends."""
    window.spin_upto.setValue(5)
    window.spin_upto.stepUp()
    assert window.spin_upto.value() == 6
    window.spin_upto.setValue(0)
    window.spin_upto.stepDown()
    assert window.spin_upto.value() == 0
    window.spin_upto.setValue(MAX_VERSION)
    window.spin_upto.stepUp()
    assert window.spin_upto.value() == MAX_VERSION


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
    window.spin_upto.setValue(2)

    window.on_list()

    assert window.output.toPlainText() == (
        "<kuid:1234:12345>,<kuid2:1234:12345:1>,<kuid2:1234:12345:2>"
    )


def test_the_reported_time_covers_the_whole_listing(window, monkeypatch):
    """The status time is the whole listing, not just the number crunching.

    Putting a large result in the output box costs far more than building it, so
    the timer has to run until the listing is really finished -- otherwise a big
    paste reports a few milliseconds when it took much longer.  The fake render
    stands in for that cost; the reported time must include it.
    """

    def slow_set_plain_text(_text):
        time.sleep(0.05)  # ~50 ms of "rendering"

    monkeypatch.setattr(window.output, "setPlainText", slow_set_plain_text)
    window.input.setPlainText("<kuid:1234:12345>")

    window.on_list()

    reported = int(window.status.text().split(" in ")[1].split(" ms")[0])
    assert reported >= 50, window.status.text()


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
    window.spin_upto.setValue(MAX_VERSION)

    window.on_list()

    tokens = window.output.toPlainText().split(",")
    assert len(tokens) == MAX_VERSION + 1
    assert tokens[0] == "<kuid:1234:12345>"
    assert not any(token.endswith(":0>") for token in tokens)


def test_clear_empties_the_input(window):
    window.input.setPlainText("<kuid:1:2>")
    window.btn_clear.click()
    assert window.input.toPlainText() == ""
