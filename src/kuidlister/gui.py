"""PyQt6 GUI for Kuid Lister.

A fixed-size portrait window, laid out top to bottom like the original form:
the label asking for pasted content, Append paste / Clear, the input box, the
List & Copy button next to the "Generate asset versions up to" checkbox and
its number, the read-only result box, the status line and the copyright/GitHub
footer.

All the work happens in :mod:`kuidlister.kuids`; this module only moves text
between the widgets and reports how long it took.  The original drove its
progress bar with three ``Application.DoEvents()`` loops; parsing is fast enough
that no progress reporting is needed, so the listing runs straight through.
"""

from __future__ import annotations

import sys
import time
import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QIntValidator, QValidator
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .kuids import (
    MAX_VERSION,
    dedupe,
    expand_versions,
    extract_kuids,
    format_token,
    join,
    split_kuid,
)

__all__ = ["KuidListerWindow", "VersionValidator", "run_gui"]

APP_TITLE = f"Kuid Lister {__version__}"
GITHUB_URL = "https://github.com/SilverGreen93/KuidLister"
ICON_FILE = "kuidlister.ico"
DEFAULT_UPTO = 10


class VersionValidator(QIntValidator):
    """A 0..MAX_VERSION field that never ends up holding a bad number.

    QIntValidator alone is not enough: it calls "128" and "999" *intermediate*
    (a longer edit of them could still be in range), so the widget happily keeps
    such a value and a List & Copy would run with a limit above 127.  Anything
    that is not strictly in range is refused here instead, which is what the
    original's TextBox3 TextChanged handler did when it popped up its warning.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, MAX_VERSION, parent)

    def validate(self, input_str: str, input_pos: int):  # type: ignore[override]
        state, text, position = super().validate(input_str, input_pos)
        if state == QValidator.State.Intermediate:
            return QValidator.State.Invalid, text, position
        if state == QValidator.State.Acceptable and not 0 <= int(text) <= MAX_VERSION:
            return QValidator.State.Invalid, text, position
        return state, text, position


def _window_icon() -> QIcon | None:
    """The app icon, if it can be found next to the code or in the bundle.

    Setting it on the application as well as the window is what puts it in the
    Windows taskbar; --icon alone only stamps the exe file on disk.
    """
    if getattr(sys, "frozen", False):  # running under PyInstaller
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / ICON_FILE
    else:
        base = Path(__file__).resolve().parent.parent.parent / "assets" / ICON_FILE
    return QIcon(str(base)) if base.is_file() else None


class KuidListerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._running = False
        self._build()

    # -- layout -------------------------------------------------------------
    def _build(self) -> None:
        self.setWindowTitle(APP_TITLE)
        icon = _window_icon()
        if icon:
            self.setWindowIcon(icon)
        self.setFixedSize(470, 481)  # the original's ClientSize minus its progress bar

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(6)

        outer.addWidget(QLabel("Paste KUIDs copied from Content Manager here:"))

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        self.btn_paste = QPushButton("Append paste")
        self.btn_clear = QPushButton("Clear")
        for button in (self.btn_paste, self.btn_clear):
            button.setMinimumSize(128, 30)
        buttons.addWidget(self.btn_paste)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_clear)
        outer.addLayout(buttons)

        self.input = QPlainTextEdit()
        outer.addWidget(self.input, 1)

        options = QHBoxLayout()
        options.setSpacing(4)
        self.btn_list = QPushButton("List & Copy")
        self.btn_list.setMinimumSize(128, 30)
        self.chk_versions = QCheckBox("Generate asset versions up to:")
        self.edit_upto = QLineEdit(str(DEFAULT_UPTO))
        # the original validated on every keystroke and complained; a validator
        # simply refuses anything outside the range instead -- including the
        # "128"/"999" QIntValidator would have let stand as intermediate
        self.edit_upto.setValidator(VersionValidator(self))
        self.edit_upto.setFixedWidth(48)
        self.chk_versions.toggled.connect(self.edit_upto.setEnabled)
        self.edit_upto.setEnabled(self.chk_versions.isChecked())
        options.addWidget(self.btn_list)
        options.addStretch(1)
        options.addWidget(self.chk_versions)
        options.addWidget(self.edit_upto)
        outer.addLayout(options)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        outer.addWidget(self.output, 1)

        self.status = QLabel("Ready.")
        outer.addWidget(self.status)

        footer = QHBoxLayout()
        label = QLabel("\u00a9 2024 SilverGreen93")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link = QLabel(f'<a href="{GITHUB_URL}">{GITHUB_URL}</a>')
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link.setOpenExternalLinks(False)
        link.linkActivated.connect(lambda: webbrowser.open(GITHUB_URL))
        footer.addWidget(label, 1)
        footer.addWidget(link, 2)
        outer.addLayout(footer)

        self.btn_paste.clicked.connect(self.on_append_paste)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_list.clicked.connect(self.on_list)

    # -- actions ------------------------------------------------------------
    def on_append_paste(self) -> None:
        """Add the clipboard to the end of the input, as Append paste did."""
        text = QApplication.clipboard().text()
        if text:
            self.input.appendPlainText(text)

    def on_clear(self) -> None:
        self.input.clear()

    def on_list(self) -> None:
        """List the kuids, copy the result and report how long it took."""
        if self._running:
            return
        upto = self._upto()
        if upto is _INVALID_UPTO:
            return  # the version limit was refused, nothing to do

        self._running = True
        started = time.perf_counter()
        try:
            text = self.input.toPlainText()

            # find and dedupe, then rebuild each kuid -- with its versions when
            # asked for.  The listing is a single straight pass: parsing is fast
            # enough that no progress reporting (or event-loop turn) is needed.
            unique = dedupe(extract_kuids(text))
            if upto is None:
                tokens = [format_token(kuid) for kuid in unique]
            else:
                pairs: dict[tuple[int, int], str] = {}
                for kuid in unique:
                    pairs.setdefault(split_kuid(kuid), kuid)
                tokens = expand_versions(list(pairs.values()), upto)

            result = join(tokens)
            self.output.setPlainText(result)

            # the original selected and copied the result for you
            if result:
                QApplication.clipboard().setText(result)

            # measure only now, so the time covers everything up to a finished
            # listing -- putting the big result in the output box (a quarter
            # megabyte here) and copying it cost more than the computation did
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self.status.setText(f"Listed {len(tokens)} KUIDs in {elapsed_ms:.0f} ms.")
        finally:
            self._running = False

    def _upto(self) -> int | None:
        """The version limit of the checkbox, or None when it is off.

        :data:`_INVALID_UPTO` when the number is out of range -- the same
        complaint the original raised in TextBox3's TextChanged handler.
        """
        if not self.chk_versions.isChecked():
            return None
        value = int(self.edit_upto.text() or str(DEFAULT_UPTO))
        if not 0 <= value <= MAX_VERSION:
            QMessageBox.warning(
                self, "Invalid version", "Versions above 127 or below 0 are invalid!"
            )
            return _INVALID_UPTO
        return value


# sentinel for a refused version limit, distinct from the checkbox being off
_INVALID_UPTO = object()


def run_gui() -> int:
    """Launch the GUI. Returns the process exit code."""
    app = QApplication(sys.argv[:1])
    icon = _window_icon()
    if icon:
        app.setWindowIcon(icon)
    window = KuidListerWindow()
    window.show()
    return app.exec()


def main() -> int:
    """Entry point for the ``kuidlister-gui`` script."""
    return run_gui()


if __name__ == "__main__":
    sys.exit(run_gui())
