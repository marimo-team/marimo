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
        assert subject._get_column_values(
            GetColumnValuesArgs(column="A")
        ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)
        assert subject._get_column_values(
            GetColumnValuesArgs(column="B")
        ) == GetColumnValuesResponse(values=["a"], too_many_values=False)

        with pytest.raises(ColumnNotFound):
            subject._get_column_values(GetColumnValuesArgs(column="idk"))

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

        assert subject._get_column_values(
            GetColumnValuesArgs(column=1)
        ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)

        with pytest.raises(ColumnNotFound):
            subject._get_column_values(GetColumnValuesArgs(column="idk"))
        with pytest.raises(ColumnNotFound):
            subject._get_column_values(GetColumnValuesArgs(column="1"))

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
        result = subject._get_dataframe(EmptyArgs())
        assert result.total_rows == 3
        assert (
            result.url
            == "data:application/json;base64,W3siMSI6MSwiMiI6ImEifV0="
        )
        # search
        search_result = subject._search(
            SearchTableArgs(page_size=1, page_number=0)
        )
        assert search_result.total_rows == 3
        assert search_result.data == result.url

        # size 2
        subject = ui.dataframe(df, page_size=2)
        result = subject._get_dataframe(EmptyArgs())
        assert result.total_rows == 3
        assert (
            result.url
            == "data:application/json;base64,W3siMSI6MSwiMiI6ImEifSx7IjEiOjIsIjIiOiJhIn1d"
        )

        # search
        search_result = subject._search(
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

        result = subject._get_dataframe(EmptyArgs())
        assert result.total_rows == df_length(df)

        # Test _get_column_values for empty and large DataFrames
        if df_length(df) == 0:
            assert subject._get_column_values(
                GetColumnValuesArgs(column="A")
            ) == GetColumnValuesResponse(values=[], too_many_values=False)
        elif df_length(df) >= 1000:
            response = subject._get_column_values(
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

        result = subject._get_dataframe(EmptyArgs())
        assert result.total_rows == 100

        search_result = subject._search(
            SearchTableArgs(page_size=10, page_number=0)
        )
        assert search_result.total_rows == 100
        assert search_result.data == result.url

    @staticmethod
    def test_dataframe_too_large_page_size() -> None:
        df = pd.DataFrame({"A": range(300)})
        with pytest.raises(ValueError) as e:
            _ = ui.dataframe(df, page_size=201)
        assert "limited to 200 rows" in str(e.value)

    @staticmethod
    def test_dataframe_with_non_string_column_names() -> None:
        df = pd.DataFrame(
            {0: [1, 2, 3], 1.5: ["a", "b", "c"], "2": [True, False, True]}
        )
        subject = ui.dataframe(df)

        assert subject.value is df
        assert len(subject._component_args["columns"]) == 3

        # Test that we can get column values for non-string column names
        assert subject._get_column_values(
            GetColumnValuesArgs(column=0)
        ) == GetColumnValuesResponse(values=[1, 2, 3], too_many_values=False)
        assert subject._get_column_values(
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

        result = subject._get_dataframe(EmptyArgs())
        assert result.total_rows == 100

        search_result = subject._search(
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
            subject._get_column_values(GetColumnValuesArgs(column="C"))

    @staticmethod
    @pytest.mark.skipif(not HAS_POLARS, reason="Polars not installed")
    def test_polars_groupby_alias() -> None:
        """Test that group by operations use original column names correctly."""
        import polars as pl

        # Create a test dataframe with age and group columns
        df = pl.DataFrame(
            {
                "group": ["a", "a", "b", "b"],
                "age": [10, 20, 30, 40],
            }
        )
        # Test the transformation directly using TransformsContainer
        from marimo._plugins.ui._impl.dataframes.transforms.apply import (
            TransformsContainer,
            get_handler_for_dataframe,
        )
        from marimo._plugins.ui._impl.dataframes.transforms.types import (
            GroupByTransform,
            Transformations,
            TransformType,
        )

        handler = get_handler_for_dataframe(df)
        transform_container = TransformsContainer(df, handler)

        # Create and apply the transformation
        transform = GroupByTransform(
            type=TransformType.GROUP_BY,
            column_ids=["group"],
            drop_na=True,
            aggregation="max",
        )
        transformations = Transformations([transform])
        transformed_df = transform_container.apply(transformations)

        # Verify the transformed DataFrame
        assert isinstance(transformed_df, pl.DataFrame)
        assert "group" in transformed_df.columns
        assert "age_max" in transformed_df.columns
        assert transformed_df.shape == (2, 2)
        assert transformed_df["age_max"].to_list() == [
            20,
            40,
        ]  # max age for each group

        # The resulting frame should have correct column names and values
        # Convert to dict and verify values
        result_dict = {
            col: transformed_df[col].to_list()
            for col in transformed_df.columns
        }
        assert result_dict == {
            "group": ["a", "b"],
            "age_max": [20, 40],
        }

        # Verify the generated code uses original column names
        from marimo._plugins.ui._impl.dataframes.transforms.print_code import (
            python_print_polars,
        )

        code = python_print_polars(
            "df",
            ["group", "age"],
            transform,
        )
        # Code should reference original "age" column, not "age_max"
        assert 'pl.col("age")' in code
        assert 'alias("age_max")' in code
        assert 'pl.col("group")' in code  # Original column name in group by

    @staticmethod
    @pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
    def test_ibis_groupby_alias() -> None:
        """Test that group by operations use original column names correctly."""
        import ibis
        import polars as pl

        # Create a test dataframe with age and group columns
        df = pl.DataFrame(
            {
                "group": ["a", "a", "b", "b"],
                "age": [10, 20, 30, 40],
            }
        )

        # from Polars to Ibis
        df = ibis.memtable(df)

        # Test the transformation directly using TransformsContainer
        from marimo._plugins.ui._impl.dataframes.transforms.apply import (
            TransformsContainer,
            get_handler_for_dataframe,
        )
        from marimo._plugins.ui._impl.dataframes.transforms.types import (
            GroupByTransform,
            SortColumnTransform,
            Transformations,
            TransformType,
        )

        handler = get_handler_for_dataframe(df)
        transform_container = TransformsContainer(df, handler)

        # Create and apply the group_by transformation
        transform_grp = GroupByTransform(
            type=TransformType.GROUP_BY,
            column_ids=["group"],
            drop_na=True,
            aggregation="max",
        )

        # Create and apply the sort transformation
        # result should be ordered
        transform_sort = SortColumnTransform(
            type=TransformType.SORT_COLUMN,
            column_id="age_max",
            ascending=True,
            na_position="first",
        )

        transformations = Transformations([transform_grp, transform_sort])
        transformed_df = transform_container.apply(transformations)

        # from Ibis to Polars
        transformed_df = transformed_df.to_polars()

        # Verify the transformed DataFrame
        assert isinstance(transformed_df, pl.DataFrame)
        assert "group" in transformed_df.columns
        assert "age_max" in transformed_df.columns
        assert transformed_df.shape == (2, 2)
        assert transformed_df["age_max"].to_list() == [
            20,
            40,
        ]  # max age for each group

        # The resulting frame should have correct column names and values
        # Convert to dict and verify values
        result_dict = {
            col: transformed_df[col].to_list()
            for col in transformed_df.columns
        }
        assert result_dict == {
            "group": ["a", "b"],
            "age_max": [20, 40],
        }

        # Verify the generated code uses original column names
        from marimo._plugins.ui._impl.dataframes.transforms.print_code import (
            python_print_ibis,
        )

        code = python_print_ibis(
            "df",
            ["group", "age"],
            transform_grp,
        )
        assert (
            'df.group_by(["group"]).aggregate(**{"age_max" : df["age"].max()})'
            in code
        )


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
    assert dataframe._get_dataframe(EmptyArgs()).total_rows == 3
    assert dataframe._get_dataframe(EmptyArgs()).sql_code is None
    ibis.set_backend(prev_backend)


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_dataframe_with_int_column_names():
    import warnings

    import pandas as pd

    data = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=[0, 1, 2])
    with warnings.catch_warnings(record=True) as w:
        dataframe = ui.dataframe(data)
        # Check that warnings were made
        assert len(w) > 0
        assert "DataFrame has integer column names" in str(w[0].message)

    assert dataframe.value is not None
