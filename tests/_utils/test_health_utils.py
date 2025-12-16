from __future__ import annotations

from marimo._utils.health import (
    _get_versions,
    get_chrome_version,
    get_container_resources,
    get_node_version,
    get_optional_modules_list,
    get_python_version,
    get_required_modules_list,
    has_cgroup_limits,
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


def test_has_cgroup_limits():
    """Test that has_cgroup_limits returns a tuple of bools and doesn't crash"""
    memory_limit, cpu_limit = has_cgroup_limits()
    assert isinstance(memory_limit, bool)
    assert isinstance(cpu_limit, bool)


def test_get_container_resources():
    """Test that get_container_resources returns None or a dict and doesn't crash"""
    result = get_container_resources()
    assert result is None or isinstance(result, dict)
    if isinstance(result, dict):
        # If we happen to be in a container, verify structure
        if "memory" in result:
            assert "total" in result["memory"]
            assert "used" in result["memory"]
