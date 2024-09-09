from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.dataframes.dataframe import (
    ColumnNotFound,
    GetColumnValuesArgs,
    GetColumnValuesResponse,
)
from marimo._plugins.ui._impl.table import SearchTableArgs
from marimo._runtime.functions import EmptyArgs

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.numpy.has()
    and DependencyManager.polars.has()
)

if HAS_DEPS:
    import pandas as pd
    import polars as pl
else:
    pd = Mock()
    pl = Mock()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestDataframes:
    @staticmethod
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
            ["A", "integer", "i64"],
            ["B", "string", "str"],
        ] or subject._component_args["columns"] == [
            ["A", "integer", "int64"],
            ["B", "string", "object"],
        ]
        assert subject.get_column_values(
            GetColumnValuesArgs(column="A")
        ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)
        assert subject.get_column_values(
            GetColumnValuesArgs(column="B")
        ) == GetColumnValuesResponse(values=["a"], too_many_values=False)

        with pytest.raises(ColumnNotFound):
            subject.get_column_values(GetColumnValuesArgs(column="idk"))

    @staticmethod
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
            [1, "integer", "int64"],
            [2, "string", "object"],
        ]

        assert subject.get_column_values(
            GetColumnValuesArgs(column=1)
        ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)

        with pytest.raises(ColumnNotFound):
            subject.get_column_values(GetColumnValuesArgs(column="idk"))
        with pytest.raises(ColumnNotFound):
            subject.get_column_values(GetColumnValuesArgs(column="1"))

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        [
            pd.DataFrame({1: [1, 2, 3], 2: ["a", "a", "a"]}),
        ],
    )
    def test_dataframe_page_size(
        df: Any,
    ) -> None:
        # size 1
        subject = ui.dataframe(df, page_size=1)
        result = subject.get_dataframe(EmptyArgs())
        assert result.total_rows == 3
        assert result.url == "data:text/csv;base64,MSwyCjEsYQo="

        # search
        search_result = subject.search(
            SearchTableArgs(page_size=1, page_number=0)
        )
        assert search_result.total_rows == 3
        assert search_result.data == result.url

        # size 2
        subject = ui.dataframe(df, page_size=2)
        result = subject.get_dataframe(EmptyArgs())
        assert result.total_rows == 3
        assert result.url == "data:text/csv;base64,MSwyCjEsYQoyLGEK"

        # search
        search_result = subject.search(
            SearchTableArgs(page_size=2, page_number=0)
        )
        assert search_result.total_rows == 3
        assert search_result.data == result.url
