"""Tests for kuidlister.settings: where the file goes and how it survives.

The config directory is chosen per platform; these tests point HOME / APPDATA /
XDG_CONFIG_HOME at a temp dir (via monkeypatch) so nothing touches the real
profile, then check that what was saved comes back on the next load.
"""

from __future__ import annotations

import json

from kuidlister import settings


def _point_at(tmp_path, monkeypatch):
    """Make the config dir resolve to *tmp_path* regardless of platform."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(settings.Path, "home", lambda: tmp_path)


def test_the_file_lives_under_a_named_folder(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    path = settings.settings_path()
    assert path.parent.name == settings.APP_DIR_NAME
    assert path.name == settings.SETTINGS_FILE


def test_round_trip_keeps_every_value(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    values = {"append": False, "copy": True, "versions": True, "upto": 42}

    settings.save(values)
    loaded = settings.load(values)

    assert loaded == values


def test_a_missing_file_gives_the_defaults(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    defaults = {"append": True, "copy": True, "versions": False, "upto": 10}

    assert settings.load(defaults) == defaults


def test_a_corrupt_file_gives_the_defaults(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    settings.settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings.settings_path().write_text("{ not json", encoding="utf-8")
    defaults = {"upto": 10}

    assert settings.load(defaults) == defaults


def test_only_known_keys_are_read(tmp_path, monkeypatch):
    """A hand-edited file cannot add keys or smuggle wrong types."""
    _point_at(tmp_path, monkeypatch)
    settings.settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings.settings_path().write_text(
        json.dumps({"upto": "7", "surprise": "x"}), encoding="utf-8"
    )
    defaults = {"upto": 10}

    loaded = settings.load(defaults)
    assert loaded == {"upto": 7}  # int coerced, unknown key dropped


def test_a_bad_number_falls_back_to_the_default(tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    settings.settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings.settings_path().write_text(
        json.dumps({"upto": "not a number"}), encoding="utf-8"
    )

    assert settings.load({"upto": 10}) == {"upto": 10}
