"""Remember the GUI options between runs.

The three checkboxes (Append, Copy, Generate asset versions) and the "up to"
number are stored as a small JSON file in the platform's config directory:
``%APPDATA%\\KuidLister`` on Windows, ``~/.config/KuidLister`` on Linux
(honouring ``$XDG_CONFIG_HOME``), and ``~/Library/Application Support/KuidLister``
on macOS.  The directory is computed by hand rather than pulled from a
library like platformdirs, to keep the package dependency-free.

Reading is forgiving: a missing, unreadable or malformed file just yields the
defaults, so a fresh install -- or a hand-edited settings.json -- never stops
the app from starting.  Writing creates the directory on demand and stays quiet
about failures; losing the saved options is not worth crashing over.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_DIR_NAME = "KuidLister"
SETTINGS_FILE = "settings.json"

# keys written to / read from the JSON, and the value used when one is absent
KEY_APPEND = "append"
KEY_COPY = "copy"
KEY_VERSIONS = "versions"
KEY_UPTO = "upto"


def config_dir() -> Path:
    """The per-user settings directory for this platform.

    ``%APPDATA%`` (falling back to a folder in the home dir) on Windows,
    ``$XDG_CONFIG_HOME`` or ``~/.config`` on Linux, and the macOS Application
    Support folder elsewhere.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / APP_DIR_NAME


def settings_path() -> Path:
    """Full path of the settings file inside :func:`config_dir`."""
    return config_dir() / SETTINGS_FILE


def load(defaults: dict) -> dict:
    """The saved options merged over *defaults*.

    Only values already named in *defaults* are taken, and bool/int keys are
    coerced to their default's type, so a hand-edited file cannot smuggle in a
    wrong type.  Anything unreadable (no file yet, bad JSON, no permission) is
    ignored and the defaults come back whole.
    """
    settings = dict(defaults)
    try:
        raw = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings
    if not isinstance(raw, dict):
        return settings
    for key, default in defaults.items():
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(default, bool):
            settings[key] = bool(value)
        elif isinstance(default, int):
            try:
                settings[key] = int(value)
            except (TypeError, ValueError):
                settings[key] = default
        else:
            settings[key] = value
    return settings


def save(values: dict) -> None:
    """Write *values* as JSON, creating the directory if needed.

    Failures are swallowed: a read-only or otherwise unwritable config dir
    should not stop the app from closing -- the options simply do not persist.
    """
    try:
        directory = config_dir()
        directory.mkdir(parents=True, exist_ok=True)
        settings_path().write_text(
            json.dumps(values, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


__all__ = [
    "APP_DIR_NAME",
    "SETTINGS_FILE",
    "KEY_APPEND",
    "KEY_COPY",
    "KEY_VERSIONS",
    "KEY_UPTO",
    "config_dir",
    "settings_path",
    "load",
    "save",
]
