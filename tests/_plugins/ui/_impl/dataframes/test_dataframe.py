from __future__ import annotations

from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.dataframes.dataframe import (
    ColumnNotFound,
    GetColumnValuesArgs,
    GetColumnValuesResponse,
)

HAS_DEPS = (
    DependencyManager.has_pandas()
    and DependencyManager.has_numpy()
    and DependencyManager.has_polars()
)

if HAS_DEPS:
    import pandas as pd
    import polars as pl


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]}),
        pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]}),
    ],
)
def test_dataframe(
    df: Any,
) -> None:
    subject = ui.dataframe(df)

    assert subject.value is df
    assert subject._component_args["columns"] == [
        ["A", "integer"],
        ["B", "string"],
    ]
    assert subject.get_column_values(
        GetColumnValuesArgs(column="A")
    ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)
    assert subject.get_column_values(
        GetColumnValuesArgs(column="B")
    ) == GetColumnValuesResponse(values=["a"], too_many_values=False)

    with pytest.raises(ColumnNotFound):
        subject.get_column_values(GetColumnValuesArgs(column="idk"))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame({1: [1, 2, 3], 2: ["a", "a", "a"]}),
    ],
)
def test_dataframe_numeric_columns(
    df: Any,
) -> None:
    subject = ui.dataframe(df)

    assert subject.value is df
    assert subject._component_args["columns"] == [
        [1, "integer"],
        [2, "string"],
    ]

    assert subject.get_column_values(
        GetColumnValuesArgs(column=1)
    ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)

    with pytest.raises(ColumnNotFound):
        subject.get_column_values(GetColumnValuesArgs(column="idk"))
    with pytest.raises(ColumnNotFound):
        subject.get_column_values(GetColumnValuesArgs(column="1"))
