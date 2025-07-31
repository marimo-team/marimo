from __future__ import annotations

from typing import Any

import narwhals.stable.v1 as nw
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager
from marimo._plugins.ui._impl.tables.selection import (
    INDEX_COLUMN_NAME,
    add_selection_column,
    remove_selection_column,
)

try:
    import pandas as pd
    import polars as pl
    import pyarrow as pa
except ImportError:
    pl = None
    pd = None
    pa = None

BACKENDS = [pl, pd, pa]

HAS_DEPS = (
    DependencyManager.polars.has()
    and DependencyManager.pandas.has()
    and DependencyManager.pyarrow.has()
)


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_selection_with_index_column(backend: Any):
    # Create test data with index column
    data = nw.from_dict(
        {
            INDEX_COLUMN_NAME: [0, 1, 2],
            "name": ["Alice", "Bob", "Charlie"],
            "age": [30, 25, 35],
        },
        backend=backend,
    )
    manager = NarwhalsTableManager(data)

    # Test selection using index column
    selected = manager.select_rows([0, 2])
    result = selected.data.to_dict(as_series=False)
    assert result[INDEX_COLUMN_NAME] == [0, 2]
    assert result["name"] == ["Alice", "Charlie"]
    assert result["age"] == [30, 35]


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_selection_with_index_column_and_sort(backend: Any):
    # Create test data with index column
    data = nw.from_dict(
        {
            INDEX_COLUMN_NAME: [0, 1, 2],
            "name": ["Alice", "Bob", "Charlie"],
            "age": [30, 25, 35],
        },
        backend=backend,
    )
    manager = NarwhalsTableManager(data)

    # Sort and select
    sorted_data = manager.sort_values(by="age", descending=True)
    selected = sorted_data.select_rows([0, 2])
    result = selected.data.to_dict(as_series=False)
    assert result[INDEX_COLUMN_NAME] == [2, 0]  # Original indices preserved
    assert result["name"] == ["Charlie", "Alice"]
    assert result["age"] == [35, 30]


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_selection_with_index_column_and_search(backend: Any):
    # Create test data with index column
    data = nw.from_dict(
        {
            INDEX_COLUMN_NAME: [0, 1, 2],
            "name": ["Alice", "Bob", "Charlie"],
            "age": [30, 25, 35],
        },
        backend=backend,
    )
    manager = NarwhalsTableManager(data)

    # Search and select
    searched = manager.search("ali")
    selected = searched.select_rows([0])
    result = selected.data.to_dict(as_series=False)
    assert result[INDEX_COLUMN_NAME] == [0]
    assert result["name"] == ["Alice"]
    assert result["age"] == [30]


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_selection_with_index_column_empty(backend: Any):
    # Create test data with index column
    data = nw.from_dict(
        {INDEX_COLUMN_NAME: [0, 1], "name": ["Alice", "Bob"], "age": [30, 25]},
        backend=backend,
    )
    manager = NarwhalsTableManager(data)

    # Test empty selection
    selected = manager.select_rows([])
    result = selected.data.to_dict(as_series=False)
    assert result[INDEX_COLUMN_NAME] == []
    assert result["name"] == []
    assert result["age"] == []


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_selection_without_index_column(backend: Any):
    # Create test data without index column
    data = nw.from_dict(
        {"name": ["Alice", "Bob", "Charlie"], "age": [30, 25, 35]},
        backend=backend,
    )
    manager = NarwhalsTableManager(data)

    # Test selection falls back to positional indexing
    selected = manager.select_rows([0, 2])
    result = selected.data.to_dict(as_series=False)
    assert "name" in result
    assert result["name"] == ["Alice", "Charlie"]
    assert result["age"] == [30, 35]


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_selection_with_index_column_take(backend: Any):
    # Create test data with index column
    data = nw.from_dict(
        {
            INDEX_COLUMN_NAME: [0, 1, 2, 3, 4],
            "name": ["Alice", "Bob", "Charlie", "Dave", "Eve"],
            "age": [30, 25, 35, 28, 22],
        },
        backend=backend,
    )
    manager = NarwhalsTableManager(data)

    # Test take operation preserves index column
    taken = manager.take(2, 1)  # Take 2 rows starting from index 1
    result = taken.data.to_dict(as_series=False)
    assert result[INDEX_COLUMN_NAME] == [1, 2]
    assert result["name"] == ["Bob", "Charlie"]
    assert result["age"] == [25, 35]


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_add_selection_to_dataframe(backend: Any):
    data = nw.from_dict(
        {"name": ["Alice", "Bob", "Charlie"], "age": [30, 25, 35]},
        backend=backend,
    )
    with_selection, has_stable_row_id = add_selection_column(data.to_native())

    assert has_stable_row_id is True

    # Convert back to Narwhals to assert
    nw_df = nw.from_native(with_selection)
    assert nw_df.columns == [INDEX_COLUMN_NAME, "name", "age"]
    assert nw_df[INDEX_COLUMN_NAME].to_list() == [0, 1, 2]


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_add_selection_to_dataframe_already_has_index(backend: Any):
    data = nw.from_dict(
        {
            INDEX_COLUMN_NAME: [0, 1, 2],
            "name": ["Alice", "Bob", "Charlie"],
            "age": [30, 25, 35],
        },
        backend=backend,
    )
    with_selection, has_stable_row_id = add_selection_column(data.to_native())

    assert has_stable_row_id is True

    # Convert back to Narwhals to assert
    nw_df = nw.from_native(with_selection)
    assert nw_df.columns == [INDEX_COLUMN_NAME, "name", "age"]
    assert nw_df[INDEX_COLUMN_NAME].to_list() == [0, 1, 2]


@pytest.mark.skipif(not HAS_DEPS, reason="Deps not installed")
@pytest.mark.parametrize("backend", BACKENDS)
def test_remove_selection_column(backend: Any):
    data = nw.from_dict(
        {"name": ["Alice", "Bob", "Charlie"], "age": [30, 25, 35]},
        backend=backend,
    )
    with_selection, has_stable_row_id = add_selection_column(data.to_native())
    assert has_stable_row_id is True

    without_selection = remove_selection_column(with_selection)
    nw_df = nw.from_native(without_selection)
    assert nw_df.columns == ["name", "age"]

    # Remove again
    without_selection = remove_selection_column(without_selection)
    nw_df = nw.from_native(without_selection)
    assert nw_df.columns == ["name", "age"]
