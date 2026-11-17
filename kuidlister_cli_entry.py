"""PyInstaller entry point for the CLI exe (KuidListerCli.exe).

Built with --console so stdin/stdout are attached to the terminal by default,
which is all this app does: kuids in on stdin, the filtered list out.
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    # when run from the source tree without installing, make src/ importable
    _src = Path(__file__).resolve().parent / "src"
    if _src.is_dir() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

    from kuidlister.cli import main

    sys.exit(main())
