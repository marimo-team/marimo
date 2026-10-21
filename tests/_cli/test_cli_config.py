# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, cast

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot

from marimo import _loggers
from marimo._cli.config import commands
from marimo._cli.config.utils import format_config_with_sources
from marimo._config.config import PartialMarimoConfig
from marimo._config.manager import MarimoConfigManager, UserConfigStore
from marimo._config.provenance import ConfigLayer, ConfigSource
from marimo._config.resolver import resolve_config_with_sources
from marimo._utils.platform import is_windows

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
def test_config_show() -> None:
    p = subprocess.run(
        ["marimo", "config", "show"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    output = p.stdout.decode()
    assert "Effective configuration (sources shown in comments)" in output
    assert "[formatting]" in output


def test_config_describe() -> None:
    p = subprocess.run(
        ["marimo", "config", "describe"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()


def test_config_show_source_comments_are_valid_toml() -> None:
    import tomlkit

    values = cast(
        PartialMarimoConfig,
        {
            "display": {"theme": "dark", "custom_css": ["styles.css"]},
            "keymap": {"overrides": {}},
            "file_browser": {"folders": [{"path": "/data", "name": "Data"}]},
        },
    )
    resolved = resolve_config_with_sources(
        [
            ConfigLayer(
                values, ConfigSource("project", "/project/pyproject.toml")
            )
        ]
    )
    output = format_config_with_sources(resolved)
    assert output == snapshot(
        """\
[display]
custom_css = ["styles.css"] # project: /project/pyproject.toml
theme = "dark" # project: /project/pyproject.toml

[[file_browser.folders]] # project: /project/pyproject.toml
name = "Data"
path = "/data"

[keymap.overrides] # project: /project/pyproject.toml"""
    )
    assert tomlkit.parse(output).unwrap() == values


def test_config_show_includes_notebook_sources_and_does_not_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_path = tmp_path / "marimo.toml"
    contents = (
        '[display]\ntheme = "dark"\n[ai.open_ai]\napi_key = "private-key"\n'
    )
    user_path.write_text(contents)
    notebook = tmp_path / "app.py"
    notebook.write_text(
        '# /// script\n# [tool.marimo.runtime]\n# on_cell_change = "lazy"\n# ///\n'
    )
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(user_path))
    from marimo._config.manager import ScriptConfigReader

    def manager(*, current_path: str) -> MarimoConfigManager:
        assert current_path == str(notebook)
        return MarimoConfigManager(user, ScriptConfigReader(current_path))

    monkeypatch.setattr(commands, "get_default_config_manager", manager)
    result = CliRunner().invoke(commands.config, ["show", str(notebook)])
    assert result.exit_code == 0, result.output
    assert f'theme = "dark" # user: {user_path}' in result.output
    assert f'on_cell_change = "lazy" # script: {notebook}' in result.output
    assert 'api_key = "********"' in result.output
    assert "private-key" not in result.output
    assert user_path.read_text() == contents


def test_config_show_warns_about_malformed_project_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_path = tmp_path / "marimo.toml"
    user_path.write_text("")
    project = tmp_path / "pyproject.toml"
    project.write_text("[tool.marimo.display\n")
    user = UserConfigStore()
    monkeypatch.setattr(user, "get_config_path", lambda: str(user_path))
    from marimo._config.manager import PyprojectConfigReader

    monkeypatch.setattr(
        commands,
        "get_default_config_manager",
        lambda **_: MarimoConfigManager(
            user, PyprojectConfigReader(str(tmp_path))
        ),
    )
    with _loggers.capture_output() as (_, _, records):
        result = CliRunner().invoke(commands.config, ["show"])
    assert result.exit_code == 0, result.output
    assert len(records) == 1
    assert str(project) in records[0].getMessage()
    assert "Project settings were ignored" in records[0].getMessage()
    assert 'theme = "light" # default' in result.output
