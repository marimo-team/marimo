# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

from marimo._cli.envinfo import (
    get_system_info,
)
from marimo._utils.diagnostics import abbreviate_home


def test_get_node_version() -> None:
    system_info = get_system_info()
    assert "Binaries" in system_info
    assert "Node" in system_info["Binaries"]
    node_version = system_info["Binaries"]["Node"]

    assert node_version is None or isinstance(node_version, str)


def test_get_package_versions() -> None:
    system_info = get_system_info()
    assert "Dependencies" in system_info
    package_versions = system_info["Dependencies"]

    assert isinstance(package_versions, dict)
    assert "click" in package_versions
    assert "starlette" in package_versions
    assert "pymdown-extensions" in package_versions
    assert package_versions["pymdown-extensions"] != "missing"


def test_get_system_info() -> None:
    system_info = get_system_info()
    assert isinstance(system_info, dict)
    assert "marimo" in system_info
    assert "OS" in system_info
    assert "OS Version" in system_info
    assert "Python Version" in system_info
    assert "Binaries" in system_info
    assert "Dependencies" in system_info
    assert "Experimental Flags" in system_info


def test_abbreviate_home() -> None:
    assert (
        abbreviate_home(
            "/Users/example/.venv/lib/python3.12/site-packages/marimo",
            home=Path("/Users/example"),
        )
        == "~/.venv/lib/python3.12/site-packages/marimo"
    )


def test_abbreviate_home_does_not_touch_other_paths() -> None:
    assert (
        abbreviate_home(
            "/nix/store/marimo",
            home=Path("/Users/example"),
        )
        == "/nix/store/marimo"
    )


def test_abbreviate_home_when_home_undeterminable(monkeypatch) -> None:
    def raise_runtime_error() -> Path:
        raise RuntimeError("Could not determine home directory")

    monkeypatch.setattr(Path, "home", raise_runtime_error)
    assert abbreviate_home("/some/path/marimo") == "/some/path/marimo"


def test_get_system_info_can_redact_location() -> None:
    raw = get_system_info(redact_home=False)
    redacted = get_system_info(redact_home=True)
    assert raw.keys() == redacted.keys()
    assert redacted["location"] == abbreviate_home(raw["location"])
