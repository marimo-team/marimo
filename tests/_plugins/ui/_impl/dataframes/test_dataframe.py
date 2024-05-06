from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.dataframes.dataframe import (
    ColumnNotFound,
    GetColumnValuesArgs,
    GetColumnValuesResponse,
)

HAS_DEPS = DependencyManager.has_pandas()

if HAS_DEPS:
    import numpy as np
    import pandas as pd


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_dataframe() -> None:
    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    subject = ui.dataframe(df)

    assert subject.value is df
    assert subject._component_args["columns"] == [
        ["A", np.dtype("int64")],
        ["B", np.dtype("O")],
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
def test_dataframe_numeric_columns() -> None:
    df = pd.DataFrame({1: [1, 2, 3], 2: ["a", "a", "a"]})

    subject = ui.dataframe(df)

    assert subject.value is df
    assert subject._component_args["columns"] == [
        [1, np.dtype("int64")],
        [2, np.dtype("O")],
    ]

    assert subject.get_column_values(
        GetColumnValuesArgs(column=1)
    ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)

    with pytest.raises(ColumnNotFound):
        subject.get_column_values(GetColumnValuesArgs(column="idk"))
    with pytest.raises(ColumnNotFound):
        subject.get_column_values(GetColumnValuesArgs(column="1"))
