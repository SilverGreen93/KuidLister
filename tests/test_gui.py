"""Tests for kuidlister.gui: the version limit of the checkbox and the result
of the List button.

These need a QApplication, so they run headless (QT_QPA_PLATFORM=offscreen in
the CI workflows).  The listing itself is covered by test_kuids.py; here it is
only about the widgets around it -- what the spin box holds, how it clamps to
0..127, and what the buttons do with the Append and Copy checkboxes.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent, QDragEnterEvent, QDragMoveEvent
from PyQt6.QtWidgets import QApplication
from kuidlister.gui import (
    DEFAULT_APPEND,
    DEFAULT_COPY,
    DEFAULT_UPTO,
    INPUT_PLACEHOLDER,
    KuidListerWindow,
)
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
    win.chk_append.setChecked(DEFAULT_APPEND)
    win.chk_copy.setChecked(DEFAULT_COPY)
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

def test_the_button_lists_and_copies_when_copy_is_on(window, monkeypatch):
    # The real system clipboard is shared with the rest of the desktop and is
    # flaky to read back inside a test run (Qt commits it from the event loop,
    # and pytest holds the Windows clipboard itself), so capture what the app
    # hands to the clipboard instead of round-tripping through the OS.
    copied: list[str] = []
    monkeypatch.setattr(
        QApplication.clipboard(), "setText", lambda text: copied.append(text)
    )
    window.chk_copy.setChecked(True)
    window.input.setPlainText("<kuid:1234:12345> again <kuid:1234:12345>")

    window.on_list()

    assert window.output.toPlainText() == "<kuid:1234:12345>"
    assert copied == ["<kuid:1234:12345>"]
    assert window.status.text().startswith("Listed 1 KUIDs in")


def test_the_button_lists_without_copying_when_copy_is_off(window, monkeypatch):
    """Copy off: the result is shown but nothing reaches the clipboard."""
    copied: list[str] = []
    monkeypatch.setattr(
        QApplication.clipboard(), "setText", lambda text: copied.append(text)
    )
    window.chk_copy.setChecked(False)
    window.input.setPlainText("<kuid:1234:12345>")

    window.on_list()

    assert window.output.toPlainText() == "<kuid:1234:12345>"  # still listed
    assert copied == []  # ... but never copied


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


# ---------------------------------------------------------------------------
# the Paste button with its Append checkbox
# ---------------------------------------------------------------------------

class _FakeClipboard:
    """Stand in for the system clipboard so a paste test needs no real one."""

    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


def _paste(window, monkeypatch, clip_text):
    monkeypatch.setattr("kuidlister.gui.QApplication.clipboard", lambda: _FakeClipboard(clip_text))
    window.btn_paste.click()


def test_the_checkboxes_start_at_their_defaults(window):
    assert window.chk_append.isChecked() is DEFAULT_APPEND
    assert window.chk_copy.isChecked() is DEFAULT_COPY


def test_the_input_hints_with_a_placeholder(window):
    """The prompt lives in the box as placeholder text, not a separate label."""
    assert window.input.placeholderText() == INPUT_PLACEHOLDER
    # the placeholder only shows while empty; typing hides it as normal
    window.input.setPlainText("<kuid:1:2>")
    assert "Paste copied KUIDs" not in window.input.toPlainText()


def test_paste_appends_when_append_is_on(window, monkeypatch):
    window.chk_append.setChecked(True)
    window.input.setPlainText("<kuid:1:1>")

    _paste(window, monkeypatch, "<kuid:2:2>")

    assert window.input.toPlainText() == "<kuid:1:1>\n<kuid:2:2>"


def test_paste_replaces_when_append_is_off(window, monkeypatch):
    window.chk_append.setChecked(False)
    window.input.setPlainText("<kuid:1:1>")

    _paste(window, monkeypatch, "<kuid:2:2>")

    assert window.input.toPlainText() == "<kuid:2:2>"


def test_a_dropped_file_replaces_when_append_is_off(window, tmp_path):
    """The Append checkbox also governs drops, not just pastes."""
    window.chk_append.setChecked(False)
    window.input.setPlainText("<kuid:1:1>")
    file = tmp_path / "more.txt"
    file.write_text("<kuid:2:2>", encoding="utf-8")

    _drop(window, _mime_for([str(file)]))

    assert window.input.toPlainText() == "<kuid:2:2>"


# ---------------------------------------------------------------------------
# dragging an external file onto the window loads it into the input box
# ---------------------------------------------------------------------------

def _mime_for(paths):
    """A QMimeData carrying local-file URLs, as a real file drop would."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    return mime


def _mid(window) -> QPointF:
    """The centre of the window as a QPointF (the events need float points)."""
    c = window.rect().center()
    return QPointF(c.x(), c.y())


def _drop(window, mime):
    """Run the window's dropEvent with a synthetic event over its centre.

    The event does not own its QMimeData, so keep a reference to it alive for
    the whole call; letting it be collected mid-event crashes Qt.
    """
    event = QDropEvent(
        _mid(window),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    try:
        window.dropEvent(event)
    finally:
        del mime  # outlived the event, safe to release now
    return event


def test_dropping_a_file_loads_its_contents(window, tmp_path):
    file = tmp_path / "kuids.txt"
    file.write_text("<kuid:1234:12345> and <kuid:6:7>", encoding="utf-8")

    _drop(window, _mime_for([str(file)]))

    assert window.input.toPlainText() == "<kuid:1234:12345> and <kuid:6:7>"
    assert "kuids.txt" in window.status.text()


def test_a_dropped_file_appends_to_existing_input(window, tmp_path):
    """With Append on (the default), a drop adds to what is already there."""
    window.chk_append.setChecked(True)
    window.input.setPlainText("<kuid:1:1>")
    file = tmp_path / "more.txt"
    file.write_text("<kuid:2:2>", encoding="utf-8")

    _drop(window, _mime_for([str(file)]))

    assert window.input.toPlainText() == "<kuid:1:1>\n<kuid:2:2>"


def test_dropping_several_files_loads_them_all(window, tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("<kuid:1:1>", encoding="utf-8")
    b.write_text("<kuid:2:2>", encoding="utf-8")

    _drop(window, _mime_for([str(a), str(b)]))

    assert window.input.toPlainText() == "<kuid:1:1>\n<kuid:2:2>"
    assert "2 files" in window.status.text()


def test_a_non_utf8_file_still_loads(tmp_path, app):
    """Undecodable bytes are replaced rather than losing the whole file."""
    window = KuidListerWindow()
    file = tmp_path / "cp1252.txt"
    file.write_bytes(b"<kuid:1:2> caf\xe9")  # \xe9 is invalid UTF-8

    _drop(window, _mime_for([str(file)]))

    loaded = window.input.toPlainText()
    assert "<kuid:1:2>" in loaded
    assert "\ufffd" in loaded  # the bad byte became the replacement char


def test_a_missing_file_is_reported_and_adds_nothing(window):
    """A local-file URL for a path that is not there cannot be read."""
    missing = str(Path(tempfile.gettempdir()) / "kuidlister-does-not-exist.txt")

    _drop(window, _mime_for([missing]))

    assert window.input.toPlainText() == ""
    assert "could not read" in window.status.text().lower()


def test_a_drag_with_no_files_is_refused(window):
    """Text or a web URL is not a file we can read, so the drop is ignored."""
    mime = QMimeData()
    mime.setText("<kuid:1:2>")

    enter = QDragEnterEvent(
        _mid(window), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    window.dragEnterEvent(enter)
    assert not enter.isAccepted()

    drop = QDropEvent(
        _mid(window), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    window.dropEvent(drop)
    del mime  # the events borrow it; keep it alive until they are done
    assert window.input.toPlainText() == ""


def test_a_drag_carrying_a_file_is_accepted(window, tmp_path):
    file = tmp_path / "kuids.txt"
    file.write_text("<kuid:1:2>", encoding="utf-8")

    enter_mime = _mime_for([str(file)])
    enter = QDragEnterEvent(
        _mid(window), Qt.DropAction.CopyAction, enter_mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    window.dragEnterEvent(enter)
    assert enter.isAccepted()

    move_mime = _mime_for([str(file)])
    move = QDragMoveEvent(
        _mid(window), Qt.DropAction.CopyAction, move_mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    window.dragMoveEvent(move)
    assert move.isAccepted()
    del enter_mime, move_mime


def test_the_text_boxes_refuse_url_drops(window, tmp_path):
    """The boxes must not swallow a file drop themselves.

    A plain QPlainTextEdit accepts url data and inserts the file path as text,
    which is exactly what beat the window handler when a file was dropped on the
    input box.  canInsertFromMimeData returning False for urls makes the widget
    ignore the drag so it falls through to KuidListerWindow.dropEvent instead.
    """
    file = tmp_path / "kuids.txt"
    file.write_text("<kuid:1:2>", encoding="utf-8")

    mime = _mime_for([str(file)])
    assert not window.input.canInsertFromMimeData(mime)
    assert not window.output.canInsertFromMimeData(mime)
    del mime


def test_the_text_boxes_still_accept_plain_text_drops(window):
    """Refusing urls must not break the normal internal text drag/select."""
    mime = QMimeData()
    mime.setText("<kuid:5:5>")

    assert window.input.canInsertFromMimeData(mime)
    del mime


def test_a_drop_on_the_input_box_is_read_by_the_window(window, tmp_path):
    """End-to-end for the reported bug: drop on the input box loads contents.

    The box refuses the url (previous test), so the window's handler runs and
    reads the file -- the input ends up with the contents, never the path.
    """
    file = tmp_path / "kuids.txt"
    file.write_text("<kuid:1234:12345>", encoding="utf-8")

    mime = _mime_for([str(file)])
    assert not window.input.canInsertFromMimeData(mime)  # box declines it
    _drop(window, mime)  # ... so the window reads it

    text = window.input.toPlainText()
    assert text == "<kuid:1234:12345>"
    assert str(file) not in text

