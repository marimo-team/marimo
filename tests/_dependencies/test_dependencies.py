# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import (
    Dependency,
    DependencyManager,
    _version_check,
)
from marimo._dependencies.errors import ManyModulesNotFoundError


def test_dependencies() -> None:
    # Only testing 2 random dependencies
    if DependencyManager.altair.has():
        import altair

        assert altair is not None
        DependencyManager.altair.require("for testing")
        assert DependencyManager.altair.imported()
        assert DependencyManager.imported("altair")

    if DependencyManager.pandas.has():
        import pandas

        assert pandas is not None
        DependencyManager.pandas.require("for testing")
        assert DependencyManager.pandas.imported()
        assert DependencyManager.imported("pandas")


def test_without_dependencies() -> None:
    missing = Dependency("missing")
    assert missing is not None
    assert not missing.has()

    with pytest.raises(ModuleNotFoundError) as excinfo:
        missing.require("for testing")

    assert excinfo.value.name == "missing"

    assert "for testing" in str(excinfo.value)


def test_subpackage_cache_invalidation() -> None:
    """Test that subpackage dependencies properly invalidate importlib cache."""
    # Create a dependency for a missing subpackage
    missing_subpackage = Dependency("google.missing_package")

    with patch("importlib.invalidate_caches") as mock_invalidate:
        with pytest.raises(ModuleNotFoundError) as excinfo:
            missing_subpackage.require("for testing subpackage handling")

        # Verify the behavior
        assert excinfo.value.name == "google.missing_package"
        assert "for testing subpackage handling" in str(excinfo.value)

        # Verify that invalidate_caches was called for subpackage
        mock_invalidate.assert_called_once()

        # Verify that the module was removed from sys.modules
        assert "google.missing_package" not in sys.modules


def test_regular_package_no_cache_invalidation() -> None:
    """Test that regular packages (no dot) don't trigger cache invalidation."""

    # Create a dependency for a missing regular package
    missing_package = Dependency("missing_regular_package")

    with patch("importlib.invalidate_caches") as mock_invalidate:
        with pytest.raises(ModuleNotFoundError) as excinfo:
            missing_package.require("for testing regular package")

        # Verify the behavior
        assert excinfo.value.name == "missing_regular_package"
        assert "for testing regular package" in str(excinfo.value)

        # Verify that invalidate_caches was NOT called for regular package
        mock_invalidate.assert_not_called()


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


def test_has_as_version_when_not_installed():
    missing = Dependency("missing")
    assert missing is not None
    assert missing.has() is False
    assert missing.has_at_version(min_version="2.0.0") is False


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


def test_require_many() -> None:
    """Test that require_many correctly raises ManyModulesNotFoundError."""

    missing1 = Dependency("missing1")
    missing2 = Dependency("missing2")

    # Test with all missing dependencies
    with pytest.raises(ManyModulesNotFoundError) as excinfo:
        DependencyManager.require_many(
            "for testing multiple dependencies",
            missing1,
            missing2,
        )

    assert excinfo.value.package_names == ["missing1", "missing2"]
    assert "for testing multiple dependencies" in str(excinfo.value)

    # Test with some dependencies available (if pandas is installed)
    if DependencyManager.pandas.has():
        with pytest.raises(ManyModulesNotFoundError) as excinfo:
            DependencyManager.require_many(
                "for testing mixed dependencies",
                DependencyManager.pandas,
                missing1,
            )

        assert excinfo.value.package_names == ["missing1"]
        assert "for testing mixed dependencies" in str(excinfo.value)

        # Test with all dependencies available
        result = DependencyManager.require_many(
            "for testing available dependencies", DependencyManager.pandas
        )
        assert result is None
