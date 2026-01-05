from __future__ import annotations

from marimo._utils.health import (
    _get_versions,
    _has_cgroup_cpu_limit,
    get_cgroup_cpu_percent,
    get_cgroup_mem_stats,
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


def test_has_cgroup_cpu_limits():
    """Test that has_cgroup_limits returns a tuple of bools and doesn't crash"""
    has_cgroup_cpu_limit = _has_cgroup_cpu_limit()
    assert isinstance(has_cgroup_cpu_limit, bool)


def test_get_container_resources():
    """Test that get_container_resources returns None or a dict and doesn't crash"""
    cpu_result = get_cgroup_cpu_percent()
    memory_result = get_cgroup_mem_stats()
    assert cpu_result is None or isinstance(cpu_result, float)
    assert memory_result is None or isinstance(memory_result, dict)
    if isinstance(memory_result, dict):
        # If we happen to be in a container, verify structure
        assert "total" in memory_result
        assert "used" in memory_result
        assert "free" in memory_result
        assert "percent" in memory_result
