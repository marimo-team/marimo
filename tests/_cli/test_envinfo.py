# Copyright 2023 Marimo. All rights reserved.
from marimo._cli.envinfo import (
    _get_node_version,
    _get_pip_list,
    get_system_info,
)


def test_get_node_version() -> None:
    node_version = _get_node_version()
    assert node_version is None or isinstance(node_version, str)


def test_get_pip_list() -> None:
    pip_list = _get_pip_list()
    assert isinstance(pip_list, dict)
    assert "click" in pip_list
    assert "tornado" in pip_list


def test_get_system_info() -> None:
    system_info = get_system_info()
    assert isinstance(system_info, dict)
    assert "marimo" in system_info
    assert "OS" in system_info
    assert "OS Version" in system_info
    assert "Python Version" in system_info
    assert "Binaries" in system_info
    assert "Requirements" in system_info
