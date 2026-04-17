from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from marimo._utils.health import (
    CGROUP_V1_MEMORY_LIMIT_FILE,
    CGROUP_V1_MEMORY_USAGE_FILE,
    CGROUP_V2_MEMORY_CURRENT_FILE,
    CGROUP_V2_MEMORY_MAX_FILE,
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
    assert isinstance(_get_versions([], False), dict)


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


def _mock_cgroup_files(file_contents: dict[str, str]):
    """Return (exists_side_effect, open_side_effect) for mocking cgroup reads."""

    def exists_side_effect(path: str) -> bool:
        return path in file_contents

    original_open = open

    def open_side_effect(path: str, encoding: str = "utf-8"):
        if path in file_contents:

            class FakeFile(StringIO):
                def __enter__(self):
                    return self

                def __exit__(self, *_args: object):
                    pass

            return FakeFile(file_contents[path])
        return original_open(path, encoding=encoding)

    return exists_side_effect, open_side_effect


def test_cgroup_v1_memory_unlimited_returns_none():
    """cgroup v1 with LONG_MAX-4096 sentinel (typical WSL2) should be
    treated as unlimited and return None."""
    exists_fn, open_fn = _mock_cgroup_files(
        {CGROUP_V1_MEMORY_LIMIT_FILE: "9223372036854771712\n"}
    )
    with (
        patch("os.path.exists", side_effect=exists_fn),
        patch("builtins.open", side_effect=open_fn),
    ):
        assert get_cgroup_mem_stats() is None


def test_cgroup_v1_memory_unlimited_long_max_returns_none():
    """cgroup v1 with exact LONG_MAX (2^63-1) should also return None."""
    exists_fn, open_fn = _mock_cgroup_files(
        {CGROUP_V1_MEMORY_LIMIT_FILE: "9223372036854775807\n"}
    )
    with (
        patch("os.path.exists", side_effect=exists_fn),
        patch("builtins.open", side_effect=open_fn),
    ):
        assert get_cgroup_mem_stats() is None


def test_cgroup_v1_memory_with_real_limit():
    """cgroup v1 with a real 2GB limit should return correct stats."""
    exists_fn, open_fn = _mock_cgroup_files(
        {
            CGROUP_V1_MEMORY_LIMIT_FILE: "2147483648\n",
            CGROUP_V1_MEMORY_USAGE_FILE: "1073741824\n",
        }
    )
    with (
        patch("os.path.exists", side_effect=exists_fn),
        patch("builtins.open", side_effect=open_fn),
    ):
        result = get_cgroup_mem_stats()
        assert result is not None
        assert result["total"] == 2147483648
        assert result["used"] == 1073741824
        assert result["available"] == 1073741824
        assert result["percent"] == 50.0


def test_cgroup_v2_memory_unlimited_returns_none():
    """cgroup v2 with 'max' (no limit) should return None."""
    exists_fn, open_fn = _mock_cgroup_files(
        {
            CGROUP_V2_MEMORY_MAX_FILE: "max\n",
            CGROUP_V2_MEMORY_CURRENT_FILE: "1048576\n",
        }
    )
    with (
        patch("os.path.exists", side_effect=exists_fn),
        patch("builtins.open", side_effect=open_fn),
    ):
        assert get_cgroup_mem_stats() is None
