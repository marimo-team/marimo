# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.table_manager import FieldTypes
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._plugins.ui._impl.utils.dataframe import (
    DEFAULT_CSV_ENCODING,
    get_default_csv_encoding,
)

HAS_PANDAS = DependencyManager.pandas.has()
HAS_NARWHALS = DependencyManager.narwhals.has()
HAS_POLARS = DependencyManager.polars.has()
HAS_PYARROW = DependencyManager.pyarrow.has()


def _get_row_headers(
    data: Any,
) -> FieldTypes:
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
    assert _get_row_headers(df) == [("Index", ("integer", "int64"))]

    # Test with MultiIndex
    arrays = [
        ["foo", "bar", "baz"],
        ["one", "two", "three"],
    ]
    df_multi = pd.DataFrame({"A": range(3)}, index=arrays)
    assert _get_row_headers(df_multi) in [
        # pandas 2.x
        [("", ("string", "object")), ("", ("string", "object"))],
        # pandas 3.x (StringDtype default)
        [("", ("string", "str")), ("", ("string", "str"))],
    ]

    # Test with RangeIndex
    df_range = pd.DataFrame({"A": range(3)})
    assert _get_row_headers(df_range) == []

    # Test with categorical Index
    df_cat = pd.DataFrame({"A": range(3)})
    df_cat.index = pd.CategoricalIndex(["a", "b", "c"])
    assert _get_row_headers(df_cat) == [("", ("string", "category"))]

    # Test with named categorical Index
    df_cat = pd.DataFrame({"A": range(3)})
    df_cat.index = pd.CategoricalIndex(["a", "b", "c"], name="Colors")
    assert _get_row_headers(df_cat) == [("Colors", ("string", "category"))]


def test_get_row_headers_list() -> None:
    # Test with non-DataFrame input
    assert _get_row_headers([1, 2, 3]) == []


@pytest.mark.skipif(
    not HAS_PANDAS or not HAS_NARWHALS or not HAS_POLARS or not HAS_PYARROW,
    reason="optional dependencies not installed",
)
def test_get_table_manager() -> None:
    import narwhals.stable.v2 as nw
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


def test_get_default_csv_encoding():
    assert get_default_csv_encoding() == DEFAULT_CSV_ENCODING


def test_union_tolerates_string_type_aliases() -> None:
    """Verify that Union[] handles string-valued type aliases (narwhals compat).

    In narwhals <2.9.0 (e.g. 2.6.0, shipped in Pyodide), types like
    IntoDataFrame are plain strings at runtime:
        IntoDataFrame: TypeAlias = "NativeDataFrame"

    The X | Y syntax raises TypeError when one operand is a string, while
    Union[X, Y] gracefully wraps it in a ForwardRef.  This test guards
    against regressions if someone converts Union[] back to X | Y in the
    affected module-level type aliases.

    See: https://github.com/marimo-team/marimo/issues/9152
    """
    from typing import Any, ForwardRef, Union

    fake_into_df = "NativeDataFrame"  # simulates narwhals 2.6.0

    # Union[] works with string operands
    result = Union[dict[Any, Any], fake_into_df]  # type: ignore[valid-type]
    args = result.__args__
    assert dict[Any, Any] in args
    assert ForwardRef("NativeDataFrame") in args

    # X | Y fails with string operands — this is the bug we're guarding against
    with pytest.raises(TypeError, match="unsupported operand type"):
        dict[Any, Any] | fake_into_df  # type: ignore[operator]
