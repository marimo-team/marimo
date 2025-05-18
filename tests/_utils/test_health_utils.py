from __future__ import annotations

from marimo._utils.health import (
    _get_versions,
    get_chrome_version,
    get_node_version,
    get_optional_modules_list,
    get_python_version,
    get_required_modules_list,
)


def test_get_node_version_exists():
    get_node_version()


def test_get_required_modules_list():
    assert isinstance(get_required_modules_list(), dict)


def test_get_optional_modules_list():
    assert isinstance(get_optional_modules_list(), dict)


def test_get_versions():
    assert isinstance(_get_versions(list(), False), dict)


def test_get_chrome_version():
    get_chrome_version()


def test_get_python_version():
    assert isinstance(get_python_version(), str)
