from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import Dependency, DependencyManager


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
