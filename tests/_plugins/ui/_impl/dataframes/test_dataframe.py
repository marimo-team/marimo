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
from marimo._utils.platform import is_windows

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
    @pytest.mark.skipif(
        is_windows(), reason="windows produces different csv output"
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
    @pytest.mark.skipif(
        is_windows(), reason="windows produces different csv output"
    )
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

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        [
            pd.DataFrame({"A": [], "B": []}),  # Empty DataFrame
            pd.DataFrame({"A": [1], "B": ["a"]}),  # Single row DataFrame
            pd.DataFrame(
                {
                    "A": list(range(1, 1001)),
                    "B": [f"value_{i}" for i in range(1, 1001)],
                }
            ),  # Large DataFrame
        ],
    )
    def test_dataframe_edge_cases(df: Any) -> None:
        subject = ui.dataframe(df)

        assert subject.value is df
        assert len(subject._component_args["columns"]) == 2

        result = subject.get_dataframe(EmptyArgs())
        assert result.total_rows == len(df)

        # Test get_column_values for empty and large DataFrames
        if len(df) == 0:
            assert subject.get_column_values(
                GetColumnValuesArgs(column="A")
            ) == GetColumnValuesResponse(values=[], too_many_values=False)
        elif len(df) >= 1000:
            response = subject.get_column_values(
                GetColumnValuesArgs(column="A")
            )
            assert response.too_many_values is True
            assert len(response.values) == 0

    @staticmethod
    def test_dataframe_with_custom_page_size() -> None:
        df = pd.DataFrame({"A": range(100), "B": ["a"] * 100})
        subject = ui.dataframe(df, page_size=10)

        result = subject.get_dataframe(EmptyArgs())
        assert result.total_rows == 100

        search_result = subject.search(
            SearchTableArgs(page_size=10, page_number=0)
        )
        assert search_result.total_rows == 100
        assert search_result.data == result.url

    @staticmethod
    def test_dataframe_with_non_string_column_names() -> None:
        df = pd.DataFrame(
            {0: [1, 2, 3], 1.5: ["a", "b", "c"], "2": [True, False, True]}
        )
        subject = ui.dataframe(df)

        assert subject.value is df
        assert len(subject._component_args["columns"]) == 3

        # Test that we can get column values for non-string column names
        assert subject.get_column_values(
            GetColumnValuesArgs(column=0)
        ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)
        assert subject.get_column_values(
            GetColumnValuesArgs(column=1.5)
        ) == GetColumnValuesResponse(
            values=["a", "b", "c"], too_many_values=False
        )

    @staticmethod
    def test_dataframe_with_limit() -> None:
        df = pd.DataFrame({"A": range(1000), "B": ["a"] * 1000})
        subject = ui.dataframe(df, limit=100)

        result = subject.get_dataframe(EmptyArgs())
        assert result.total_rows == 100

        search_result = subject.search(
            SearchTableArgs(page_size=10, page_number=0)
        )
        assert search_result.total_rows == 100

    @staticmethod
    def test_dataframe_error_handling() -> None:
        df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        subject = ui.dataframe(df)

        # Test ColumnNotFound error
        with pytest.raises(ColumnNotFound):
            subject.get_column_values(GetColumnValuesArgs(column="C"))
