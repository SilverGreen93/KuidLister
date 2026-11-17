"""PyInstaller entry point for the GUI exe (KuidLister.exe).

Built with --windowed (GUI subsystem) so double-clicking the exe opens the GUI
without a terminal flash.  Kuid Lister takes no paths on the command line: its
input is pasted into the window.
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    # when run from the source tree without installing, make src/ importable
    _src = Path(__file__).resolve().parent / "src"
    if _src.is_dir() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

    from kuidlister.gui import run_gui

    sys.exit(run_gui())
