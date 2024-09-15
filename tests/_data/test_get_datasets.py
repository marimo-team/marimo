from __future__ import annotations

import pytest

from marimo._data.get_datasets import has_updates_to_datasource
from marimo._dependencies.dependencies import DependencyManager

HAS_DEPS = DependencyManager.duckdb.has()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_has_updates_to_datasource() -> None:
    assert has_updates_to_datasource("hello") is False
    assert has_updates_to_datasource("ATTACH 'marimo.db'") is True
    assert has_updates_to_datasource("DETACH marimo") is True
    assert has_updates_to_datasource("CREATE TABLE cars (name TEXT)") is True
