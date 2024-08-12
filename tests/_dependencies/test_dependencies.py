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
