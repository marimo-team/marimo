from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import (
    Dependency,
    DependencyManager,
    _version_check,
)


def test_dependencies() -> None:
    # Only testing 2 random dependencies
    if DependencyManager.altair.has():
        import altair

        assert altair is not None
        DependencyManager.altair.require("for testing")

    if DependencyManager.pandas.has():
        import pandas

        assert pandas is not None
        DependencyManager.pandas.require("for testing")


def test_without_dependencies() -> None:
    missing = Dependency("missing")
    assert missing is not None
    assert not missing.has()

    with pytest.raises(ModuleNotFoundError) as excinfo:
        missing.require("for testing")

    assert "for testing" in str(excinfo.value)


@pytest.mark.skipif(
    not DependencyManager.altair.has(),
    reason="altair is not installed",
)
def test_versions():
    assert (
        DependencyManager.altair.require_version(
            min_version="0.0.0", max_version="6.0.0"
        )
        is None
    )

    with pytest.raises(RuntimeError) as excinfo:
        DependencyManager.altair.require_version(min_version="6.0.0")

    version = DependencyManager.altair.get_version()
    assert (
        str(excinfo.value)
        == f"Mismatched version of altair: expected >=6.0.0, got {version}"
    )

    # Override version
    assert (
        DependencyManager.altair.has_at_version(
            min_version="0.0.0", max_version="6.0.0"
        )
        is True
    )
    assert (
        DependencyManager.altair.has_at_version(min_version="7.0.0") is False
    )

    with pytest.raises(RuntimeError) as excinfo:
        DependencyManager.altair.require_at_version(
            why="for testing", min_version="6.0.0"
        )

    assert "Mismatched version of test: expected >=2.0.0, got 1.0.0"

    assert (
        DependencyManager.altair.require_at_version(
            why="for testing", min_version="2.0.0"
        )
        is None
    )


def test_version_check():
    # within range
    assert (
        _version_check(pkg="test", v="1.0.0", min_v="0.0.0", max_v="2.0.0")
        is True
    )
    assert (
        _version_check(pkg="test", v="1.0.0", min_v="1.0.0", max_v="2.0.0")
        is True
    )

    # outside range
    assert (
        _version_check(pkg="test", v="0.4.0", min_v="1.0.0", max_v="2.0.0")
        is False
    )
    assert (
        _version_check(pkg="test", v="2.0.0", min_v="1.0.0", max_v="2.0.0")
        is False
    )

    # does not raise
    assert (
        _version_check(
            pkg="test",
            v="1.0.0",
            min_v="1.0.0",
            max_v="2.0.0",
            raise_error=True,
        )
        is True
    )
    assert (
        _version_check(
            pkg="test",
            v="1.5.0",
            min_v="1.0.0",
            max_v="2.0.0",
            raise_error=True,
        )
        is True
    )

    # too low
    with pytest.raises(RuntimeError) as excinfo:
        _version_check(
            pkg="test",
            v="1.0.0",
            min_v="2.0.0",
            max_v="3.0.0",
            raise_error=True,
        )

    assert (
        str(excinfo.value)
        == "Mismatched version of test: expected >=2.0.0, got 1.0.0"
    )

    with pytest.raises(RuntimeError) as excinfo:
        _version_check(
            pkg="test",
            v="3.0.0",
            min_v="2.0.0",
            max_v="3.0.0",
            raise_error=True,
        )

    # too high
    assert (
        str(excinfo.value)
        == "Mismatched version of test: expected <3.0.0, got 3.0.0"
    )
