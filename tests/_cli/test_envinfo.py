# Copyright 2024 Marimo. All rights reserved.
from marimo._cli.envinfo import (
    get_system_info,
)


def test_get_node_version() -> None:
    system_info = get_system_info()
    assert "Binaries" in system_info
    assert "Node" in system_info["Binaries"]
    node_version = system_info["Binaries"]["Node"]

    assert node_version is None or isinstance(node_version, str)


def test_get_pip_list() -> None:
    system_info = get_system_info()
    assert "Requirements" in system_info
    pip_list = system_info["Requirements"]

    assert isinstance(pip_list, dict)
    assert "click" in pip_list
    assert "starlette" in pip_list


def test_get_system_info() -> None:
    system_info = get_system_info()
    assert isinstance(system_info, dict)
    assert "marimo" in system_info
    assert "OS" in system_info
    assert "OS Version" in system_info
    assert "Python Version" in system_info
    assert "Binaries" in system_info
    assert "Requirements" in system_info
