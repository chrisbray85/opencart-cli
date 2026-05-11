"""Smoke tests — no live store needed.

These verify imports, config round-tripping, formatters, and safety guards.
The CI matrix runs these on Python 3.10-3.13 across Linux + macOS.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_app_imports() -> None:
    from opencart_cli.app import app

    assert app.info.name == "opencart"


def test_version_string() -> None:
    from opencart_cli import __version__

    assert __version__.count(".") == 2  # semver


def test_sparkline_basic() -> None:
    from opencart_cli.formatters import sparkline

    s = sparkline([1, 2, 3, 4, 5, 6, 7, 8])
    assert len(s) == 8
    # Range maps to 8 distinct chars from " ▁▂▃▄▅▆▇█"
    assert s[0] in " ▁"  # lowest
    assert s[-1] == "█"  # highest


def test_sparkline_flat_series() -> None:
    from opencart_cli.formatters import sparkline

    s = sparkline([5, 5, 5, 5])
    assert len(s) == 4
    assert len(set(s)) == 1  # all the same char


def test_sparkline_empty() -> None:
    from opencart_cli.formatters import sparkline

    assert sparkline([]) == ""


def test_safe_select_blocks_drop() -> None:
    from opencart_cli.core.operations import safe_select

    class FakeDB:
        def query(self, sql, params=None):
            raise AssertionError("Should not be called")

    with pytest.raises(ValueError, match="Only SELECT"):
        safe_select(FakeDB(), "DROP TABLE oc_product")


def test_safe_select_blocks_insert() -> None:
    from opencart_cli.core.operations import safe_select

    class FakeDB:
        def query(self, sql, params=None):
            raise AssertionError("Should not be called")

    with pytest.raises(ValueError, match="Only SELECT"):
        safe_select(FakeDB(), "INSERT INTO oc_product (model) VALUES ('x')")


def test_safe_select_blocks_ddl_inside_select() -> None:
    from opencart_cli.core.operations import safe_select

    class FakeDB:
        def query(self, sql, params=None):
            raise AssertionError("Should not be called")

    # A SELECT that mentions ALTER as a keyword should be refused
    with pytest.raises(ValueError, match="DDL keywords"):
        safe_select(FakeDB(), "SELECT 1; ALTER TABLE foo DROP bar")


def test_safe_select_allows_select() -> None:
    from opencart_cli.core.operations import safe_select

    class FakeDB:
        def __init__(self):
            self.calls = []

        def query(self, sql, params=None):
            self.calls.append((sql, params))
            return [{"n": 1}]

    db = FakeDB()
    result = safe_select(db, "SELECT 1 AS n")
    assert result == [{"n": 1}]
    assert len(db.calls) == 1


def test_config_round_trip(tmp_path: Path) -> None:
    """Saving and re-loading a config preserves all fields."""
    from opencart_cli.core.config import (
        Config,
        DBConnection,
        OpenCartInstall,
        Profile,
        load_config,
        save_config,
    )

    cfg_path = tmp_path / "config.yaml"
    cfg = Config(default_profile="prod")
    cfg.profiles["prod"] = Profile(
        name="prod",
        description="example",
        read_only=False,
        connection={"type": "ssh", "host": "example.com", "user": "me", "key": "~/.ssh/id"},
        db=DBConnection(user="u", name="n"),
        opencart=OpenCartInstall(root="/srv/oc", version="3.x"),
    )
    cfg.profiles["local"] = Profile(
        name="local",
        description="",
        read_only=False,
        connection={"type": "ddev", "project_path": "/Users/me/Sites/foo"},
        db=DBConnection(user="db", name="db", host="db"),
        opencart=OpenCartInstall(root="/var/www/html", version="auto"),
    )

    save_config(cfg, cfg_path)
    loaded = load_config(cfg_path)
    assert loaded.default_profile == "prod"
    assert set(loaded.profiles) == {"prod", "local"}
    assert loaded.profiles["prod"].connection["host"] == "example.com"
    assert loaded.profiles["local"].connection["type"] == "ddev"
    assert loaded.profiles["local"].db.host == "db"


def test_profile_read_only_auto_for_prod() -> None:
    """Profiles named prod* are auto-readonly even without the flag."""
    from opencart_cli.core.config import DBConnection, OpenCartInstall, Profile

    p = Profile(
        name="prod-uk",
        connection={"type": "ssh", "host": "x", "user": "y"},
        db=DBConnection(user="u", name="n"),
        opencart=OpenCartInstall(root="/x"),
    )
    assert p.is_read_only is True


def test_unknown_connection_type_rejected() -> None:
    from opencart_cli.core.connection import ConnectionFailed, make_connection

    with pytest.raises(ConnectionFailed, match="Unknown connection type"):
        make_connection({"type": "telepathy"})


def test_formatter_emits_json_when_piped(monkeypatch, capsys) -> None:
    """In non-TTY mode, render() falls back to JSON."""
    from opencart_cli.formatters import render

    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    render([{"a": 1, "b": "two"}], fmt="auto")
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed == [{"a": 1, "b": "two"}]


def test_csv_emit(capsys) -> None:
    from opencart_cli.formatters import render

    render([{"id": 1, "name": "x"}, {"id": 2, "name": "y"}], fmt="csv")
    out = capsys.readouterr().out
    assert "id,name" in out
    assert "1,x" in out
