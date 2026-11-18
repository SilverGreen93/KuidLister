"""PyQt6 GUI for Kuid Lister.

A fixed-size portrait window, laid out top to bottom like the original form:
the label asking for pasted content, Paste (with an Append checkbox) / Clear,
the input box, the List button next to a Copy checkbox and the "Generate asset
versions up to" checkbox and its number, the read-only result box, the status
line and the copyright/GitHub footer.

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
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
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

__all__ = ["KuidListerWindow", "run_gui"]

APP_TITLE = f"Kuid Lister {__version__}"
GITHUB_URL = "https://github.com/SilverGreen93/KuidLister"
ICON_FILE = "kuidlister.ico"
DEFAULT_UPTO = 10
# the two new option checkboxes start off, matching the old always-append and
# always-copy behaviour so nothing surprises a returning user
DEFAULT_APPEND = True
DEFAULT_COPY = True


class DropForwardEdit(QPlainTextEdit):
    """A text box that lets file drops fall through to the window.

    QPlainTextEdit handles a URL drop itself and inserts the file's path as
    text, which would beat the window's own handler when the drop lands on this
    box.  Refusing url data here makes the widget ignore those drags, so they
    reach :meth:`KuidListerWindow.dropEvent` and the file is read instead.
    Ordinary text drops (dragging a selection inside the app) still work.
    """

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802 (Qt name)
        if source.hasUrls():
            return False
        return super().canInsertFromMimeData(source)


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
        self.btn_paste = QPushButton("Paste")
        self.chk_append = QCheckBox("Append")
        self.chk_append.setChecked(DEFAULT_APPEND)
        self.btn_clear = QPushButton("Clear")
        for button in (self.btn_paste, self.btn_clear):
            button.setMinimumSize(90, 30)
        buttons.addWidget(self.btn_paste)
        buttons.addWidget(self.chk_append)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_clear)
        outer.addLayout(buttons)

        self.input = DropForwardEdit()
        outer.addWidget(self.input, 1)

        options = QHBoxLayout()
        options.setSpacing(4)
        self.btn_list = QPushButton("List")
        self.btn_list.setMinimumSize(90, 30)
        self.chk_copy = QCheckBox("Copy")
        self.chk_copy.setChecked(DEFAULT_COPY)
        self.chk_versions = QCheckBox("Generate asset versions up to:")
        self.spin_upto = QSpinBox()
        # a spin box is clamped to its range, so it can only ever hold a value
        # from 0 to MAX_VERSION -- no separate validator or warning needed, which
        # the old QLineEdit with a VersionValidator had to do by hand
        self.spin_upto.setRange(0, MAX_VERSION)
        self.spin_upto.setValue(DEFAULT_UPTO)
        self.spin_upto.setFixedWidth(64)
        self.chk_versions.toggled.connect(self.spin_upto.setEnabled)
        self.spin_upto.setEnabled(self.chk_versions.isChecked())
        options.addWidget(self.btn_list)
        options.addWidget(self.chk_copy)
        options.addStretch(1)
        options.addWidget(self.chk_versions)
        options.addWidget(self.spin_upto)
        outer.addLayout(options)

        self.output = DropForwardEdit()
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

        self.btn_paste.clicked.connect(self.on_paste)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_list.clicked.connect(self.on_list)

        # accept file drops anywhere on the window; the text boxes are
        # DropForwardEdit so a drop landing on one still reaches us (see there)
        self.setAcceptDrops(True)

    # -- actions ------------------------------------------------------------
    def _insert_into_input(self, text: str) -> None:
        """Put pasted or dropped text in the input.

        The Append checkbox decides whether it is added after what is already
        there or replaces it; with the box off the new text is the whole input.
        """
        if self.chk_append.isChecked():
            self.input.appendPlainText(text)
        else:
            self.input.setPlainText(text)

    def on_paste(self) -> None:
        """Put the clipboard in the input, appending or replacing as set."""
        text = QApplication.clipboard().text()
        if text:
            self._insert_into_input(text)

    def on_clear(self) -> None:
        self.input.clear()

    # -- drag and drop ------------------------------------------------------
    @staticmethod
    def _file_urls(event) -> list[str]:
        """Local file paths carried by a drag, empty if it carries none.

        Only files already on disk count; a URL dragged from a browser or plain
        text is not something we can read, so it is ignored and the drop refused.
        """
        data = event.mimeData()
        if not data.hasUrls():
            return []
        paths: list[str] = []
        for url in data.urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        return paths

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt name)
        """Offer to accept the drag only when it carries at least one file."""
        if self._file_urls(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 (Qt name)
        """Keep accepting while the pointer moves over the window.

        Without this Qt drops the highlight after the first enter and refuses
        the release even though dragEnter accepted it.
        """
        if self._file_urls(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt name)
        """Load every dropped file into the input box."""
        paths = self._file_urls(event)
        if not paths:
            event.ignore()
            return
        loaded = [name for name in (self._load_file(path) for path in paths) if name]
        event.acceptProposedAction()
        if len(loaded) == 1:
            self.status.setText(f"Loaded {loaded[0]}.")
        elif loaded:
            self.status.setText(f"Loaded {len(loaded)} files.")

    def _load_file(self, path: str) -> str:
        """Append one file's contents to the input; return its display name.

        Read as UTF-8 with undecodable bytes replaced rather than raising, since
        CM copy text is usually plain but a stray BOM or code page should not
        lose the rest of the file.  A path that is not a readable file (gone, or
        a folder) reports the problem instead of loading nothing silently.
        """
        name = Path(path).name
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.status.setText(f"Could not read {name}: {exc.strerror}.")
            return ""
        if text:
            self._insert_into_input(text)
        return name

    def on_list(self) -> None:
        """List the kuids, copy the result and report how long it took."""
        if self._running:
            return
        upto = self._upto()

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

            # the Copy checkbox decides whether the list also goes to the
            # clipboard; without it the result is only shown, never copied
            if result and self.chk_copy.isChecked():
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

        The spin box is clamped to 0..MAX_VERSION, so its value always needs a
        version run and can never be out of range -- no warning path like the
        original's TextBox3 TextChanged handler has to exist here.
        """
        if not self.chk_versions.isChecked():
            return None
        return self.spin_upto.value()


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
