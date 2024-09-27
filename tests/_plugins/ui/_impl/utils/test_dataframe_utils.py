# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.utils import get_table_manager

HAS_PANDAS = DependencyManager.pandas.has()
HAS_NARWHALS = DependencyManager.narwhals.has()


def _get_row_headers(
    data: Any,
) -> list[str]:
    manager = get_table_manager(data)
    return manager.get_row_headers()


@pytest.mark.skipif(
    not HAS_PANDAS, reason="optional dependencies not installed"
)
def test_get_row_headers_pandas() -> None:
    import pandas as pd

    # Test with pandas DataFrame
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    df.index.name = "Index"
    assert _get_row_headers(df) == ["Index"]

    # Test with MultiIndex
    arrays = [
        ["foo", "bar", "baz"],
        ["one", "two", "three"],
    ]
    df_multi = pd.DataFrame({"A": range(3)}, index=arrays)
    assert _get_row_headers(df_multi) == ["", ""]

    # Test with RangeIndex
    df_range = pd.DataFrame({"A": range(3)})
    assert _get_row_headers(df_range) == []

    # Test with categorical Index
    df_cat = pd.DataFrame({"A": range(3)})
    df_cat.index = pd.CategoricalIndex(["a", "b", "c"])
    assert _get_row_headers(df_cat) == [""]

    # Test with named categorical Index
    df_cat = pd.DataFrame({"A": range(3)})
    df_cat.index = pd.CategoricalIndex(["a", "b", "c"], name="Colors")
    assert _get_row_headers(df_cat) == ["Colors"]


def test_get_row_headers_list() -> None:
    # Test with non-DataFrame input
    assert _get_row_headers([1, 2, 3]) == []


@pytest.mark.skipif(
    not HAS_PANDAS or not HAS_NARWHALS,
    reason="optional dependencies not installed",
)
def test_get_table_manager() -> None:
    import narwhals as nw
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    assert get_table_manager(df) is not None
    assert get_table_manager(pl.from_pandas(df)) is not None
    assert get_table_manager(pa.table(df)) is not None

    # Test with narwhals DataFrame
    assert get_table_manager(nw.from_native(df)) is not None
    assert get_table_manager(nw.from_native(pa.table(df))) is not None
    assert get_table_manager(nw.from_native(pl.from_pandas(df))) is not None
