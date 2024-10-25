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
from tests._data.mocks import create_dataframes

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.numpy.has()
    and DependencyManager.polars.has()
)

HAS_IBIS = DependencyManager.ibis.has()
HAS_POLARS = DependencyManager.polars.has()

if HAS_DEPS:
    import pandas as pd
    import polars as pl
else:
    pd = Mock()
    pl = Mock()


def df_length(df: Any) -> int:
    if isinstance(df, pd.DataFrame):
        return len(df)
    if isinstance(df, pl.DataFrame):
        return len(df)
    if hasattr(df, "count"):
        return df.count().execute()
    return len(df)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestDataframes:
    @staticmethod
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {"A": [1, 2, 3], "B": ["a", "a", "a"]},
            exclude=["pyarrow", "duckdb"],
        ),
    )
    def test_dataframe(
        df: Any,
    ) -> None:
        subject = ui.dataframe(df)

        assert subject.value is df
        assert (
            subject._component_args["columns"]
            == [
                ["A", "integer", "i64"],
                ["B", "string", "str"],
            ]
            or subject._component_args["columns"]
            == [
                ["A", "integer", "int64"],
                ["B", "string", "object"],
            ]
            or subject._component_args["columns"]
            == [
                ["A", "integer", "int64"],
                ["B", "string", "string"],
            ]
        )
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
        # Only pandas supports numeric column names
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
        create_dataframes(
            {"1": [1, 2, 3], "2": ["a", "a", "a"]},
            exclude=["pyarrow", "duckdb"],
        ),
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
            *create_dataframes(
                {"A": [], "B": []}, exclude=["pyarrow", "duckdb"]
            ),  # Empty DataFrame
            *create_dataframes(
                {"A": [1], "B": ["a"]}, exclude=["pyarrow", "duckdb"]
            ),  # Single row DataFrame
            *create_dataframes(
                {
                    "A": range(1, 1001),
                    "B": [f"value_{i}" for i in range(1, 1001)],
                },
                exclude=["pyarrow", "duckdb"],
            ),  # Large DataFrame
        ],
    )
    def test_dataframe_edge_cases(df: Any) -> None:
        subject = ui.dataframe(df)

        assert subject.value is df
        assert len(subject._component_args["columns"]) == 2

        result = subject.get_dataframe(EmptyArgs())
        assert result.total_rows == df_length(df)

        # Test get_column_values for empty and large DataFrames
        if df_length(df) == 0:
            assert subject.get_column_values(
                GetColumnValuesArgs(column="A")
            ) == GetColumnValuesResponse(values=[], too_many_values=False)
        elif df_length(df) >= 1000:
            response = subject.get_column_values(
                GetColumnValuesArgs(column="A")
            )
            assert response.too_many_values is True
            assert len(response.values) == 0

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {"A": range(100), "B": ["a"] * 100}, exclude=["pyarrow", "duckdb"]
        ),
    )
    def test_dataframe_with_custom_page_size(df: Any) -> None:
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
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {"A": range(1000), "B": ["a"] * 1000},
            exclude=["pyarrow", "duckdb"],
        ),
    )
    def test_dataframe_with_limit(df: Any) -> None:
        subject = ui.dataframe(df, limit=100)

        result = subject.get_dataframe(EmptyArgs())
        assert result.total_rows == 100

        search_result = subject.search(
            SearchTableArgs(page_size=10, page_number=0)
        )
        assert search_result.total_rows == 100

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {"A": [1, 2, 3], "B": ["a", "b", "c"]},
            exclude=["pyarrow", "duckdb"],
        ),
    )
    def test_dataframe_error_handling(df: Any) -> None:
        subject = ui.dataframe(df)

        # Test ColumnNotFound error
        with pytest.raises(ColumnNotFound):
            subject.get_column_values(GetColumnValuesArgs(column="C"))


@pytest.mark.skipif(
    not HAS_IBIS or not HAS_POLARS,
    reason="optional dependencies not installed",
)
def test_ibis_with_polars_backend() -> None:
    import ibis

    import marimo as mo

    prev_backend = ibis.get_backend()
    ibis.set_backend("polars")

    data = {
        "a": [1, 2, 3],
        "b": [22.5, 23.0, 21.5],
    }
    memtable = ibis.memtable(data)
    dataframe = mo.ui.dataframe(memtable)
    assert dataframe is not None
    assert dataframe.get_dataframe(EmptyArgs()).total_rows == 3
    assert dataframe.get_dataframe(EmptyArgs()).sql_code is None
    ibis.set_backend(prev_backend)
