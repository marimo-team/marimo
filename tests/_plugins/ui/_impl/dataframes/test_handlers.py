# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, cast
from unittest.mock import Mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.dataframes.transforms.apply import (
    TransformsContainer,
    _apply_transforms,
    get_handler_for_dataframe,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    AggregateTransform,
    ColumnConversionTransform,
    Condition,
    DataFrameType,
    ExpandDictTransform,
    ExplodeColumnsTransform,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnTransform,
    SampleRowsTransform,
    SelectColumnsTransform,
    ShuffleRowsTransform,
    SortColumnTransform,
    Transform,
    Transformations,
    TransformType,
)

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.polars.has()
    and DependencyManager.ibis.has()
)

if HAS_DEPS:
    import ibis
    import numpy as np
    import pandas as pd
    import polars as pl
    import polars.testing as pl_testing
else:
    pd = Mock()
    pl = Mock()
    np = Mock()
    ibis = Mock()


def apply(df: DataFrameType, transform: Transform) -> DataFrameType:
    handler = get_handler_for_dataframe(df)
    return _apply_transforms(
        df, handler, Transformations(transforms=[transform])
    )


def assert_frame_equal(df1: DataFrameType, df2: DataFrameType) -> None:
    if isinstance(df1, pd.DataFrame) and isinstance(df2, pd.DataFrame):
        # Remove index to compare
        df1 = df1.reset_index(drop=True)
        df2 = df2.reset_index(drop=True)
        pd.testing.assert_frame_equal(df1, df2)
        return
    if isinstance(df1, pl.DataFrame) and isinstance(df2, pl.DataFrame):
        pl_testing.assert_frame_equal(df1, df2)
        return
    if isinstance(df1, ibis.Expr) and isinstance(df2, ibis.Expr):
        pl_testing.assert_frame_equal(df1.to_polars(), df2.to_polars())
        return
    pytest.fail("DataFrames are not of the same type")


def assert_frame_not_equal(df1: DataFrameType, df2: DataFrameType) -> None:
    with pytest.raises(AssertionError):
        assert_frame_equal(df1, df2)


def df_size(df: DataFrameType) -> int:
    if isinstance(df, pd.DataFrame):
        return df.size
    if isinstance(df, pl.DataFrame):
        return df.shape[0]
    if isinstance(df, ibis.Table):
        return df.count().execute()
    raise ValueError("Unsupported dataframe type")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestTransformHandler:
    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": ["1", "2", "3"]}),
                pd.DataFrame({"A": [1, 2, 3]}),
            ),
            (
                pl.DataFrame({"A": ["1", "2", "3"]}),
                pl.DataFrame({"A": [1, 2, 3]}),
            ),
            (
                ibis.memtable({"A": ["1", "2", "3"]}),
                ibis.memtable({"A": [1, 2, 3]}),
            ),
        ],
    )
    def test_handle_column_conversion_string_to_int(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = ColumnConversionTransform(
            type=TransformType.COLUMN_CONVERSION,
            column_id="A",
            data_type="int64",
            errors="raise",
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1.1, 2.2, 3.3]}),
                pd.DataFrame({"A": ["1.1", "2.2", "3.3"]}),
            ),
            (
                pl.DataFrame({"A": [1.1, 2.2, 3.3]}),
                pl.DataFrame({"A": ["1.1", "2.2", "3.3"]}),
            ),
            (
                ibis.memtable({"A": [1.1, 2.2, 3.3]}),
                ibis.memtable({"A": ["1.1", "2.2", "3.3"]}),
            ),
        ],
    )
    def test_handle_column_conversion_float_to_string(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = ColumnConversionTransform(
            type=TransformType.COLUMN_CONVERSION,
            column_id="A",
            data_type="str",
            errors="raise",
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": ["1", "2", "3", "a"]}),
                pd.DataFrame({"A": ["1", "2", "3", "a"]}),
            ),
            (
                pl.DataFrame({"A": ["1", "2", "3", "a"]}),
                pl.DataFrame({"A": [1, 2, 3, None]}),
            ),
            (
                ibis.memtable({"A": ["1", "2", "3", "a"]}),
                ibis.memtable({"A": ["1", "2", "3", "a"]}),
            ),
        ],
    )
    def test_handle_column_conversion_ignore_errors(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = ColumnConversionTransform(
            type=TransformType.COLUMN_CONVERSION,
            column_id="A",
            data_type="int64",
            errors="ignore",
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3]}),
                pd.DataFrame({"B": [1, 2, 3]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3]}),
                pl.DataFrame({"B": [1, 2, 3]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3]}),
                ibis.memtable({"B": [1, 2, 3]}),
            ),
        ],
    )
    def test_handle_rename_column(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = RenameColumnTransform(
            type=TransformType.RENAME_COLUMN, column_id="A", new_column_id="B"
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected_asc", "expected_desc"),
        [
            (
                pd.DataFrame({"A": [3, 1, 2]}),
                pd.DataFrame({"A": [1, 2, 3]}),
                pd.DataFrame({"A": [3, 2, 1]}),
            ),
            (
                pl.DataFrame({"A": [3, 1, 2]}),
                pl.DataFrame({"A": [1, 2, 3]}),
                pl.DataFrame({"A": [3, 2, 1]}),
            ),
            (
                ibis.memtable({"A": [3, 1, 2]}),
                ibis.memtable({"A": [1, 2, 3]}),
                ibis.memtable({"A": [3, 2, 1]}),
            ),
        ],
    )
    def test_handle_sort_column(
        df: DataFrameType,
        expected_asc: DataFrameType,
        expected_desc: DataFrameType,
    ) -> None:
        transform = SortColumnTransform(
            type=TransformType.SORT_COLUMN,
            column_id="A",
            ascending=True,
            na_position="last",
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected_asc)

        transform = SortColumnTransform(
            type=TransformType.SORT_COLUMN,
            column_id="A",
            ascending=False,
            na_position="last",
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected_desc)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3]}),
                pd.DataFrame({"A": [2, 3]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3]}),
                pl.DataFrame({"A": [2, 3]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3]}),
                ibis.memtable({"A": [2, 3]}),
            ),
        ],
    )
    def test_handle_filter_rows_1(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator=">=", value=2)],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    def test_handle_filter_rows_string_na() -> None:
        for operator in ["contains", "starts_with", "ends_with", "regex"]:
            df = pd.DataFrame({"A": ["foo", "bar", None]})
            transform = FilterRowsTransform(
                type=TransformType.FILTER_ROWS,
                operation="keep_rows",
                where=[
                    Condition(
                        column_id="A",
                        operator=cast(Any, operator),
                        value="foo",
                    )
                ],
            )
            result = apply(df, transform)
            assert_frame_equal(result, pd.DataFrame({"A": ["foo"]}))

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [2], "B": [5]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame({"A": [2], "B": [5]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A": [2], "B": [5]}),
            ),
        ],
    )
    def test_handle_filter_rows_2(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="B", operator="!=", value=5)],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3, 4, 5]}),
                pd.DataFrame({"A": [1, 2, 3]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3, 4, 5]}),
                pl.DataFrame({"A": [1, 2, 3]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3, 4, 5]}),
                ibis.memtable({"A": [1, 2, 3]}),
            ),
        ],
    )
    def test_handle_filter_rows_3(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="<", value=4)],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3]}),
                pd.DataFrame({"A": [1, 3]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3]}),
                pl.DataFrame({"A": [1, 3]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3]}),
                ibis.memtable({"A": [1, 3]}),
            ),
        ],
    )
    def test_handle_filter_rows_4(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="A", operator="==", value=2)],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [2, 3], "B": [5, 6]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame({"A": [2, 3], "B": [5, 6]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A": [2, 3], "B": [5, 6]}),
            ),
        ],
    )
    def test_handle_filter_rows_5(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="B", operator=">=", value=5)],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [3], "B": [6]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame({"A": [3], "B": [6]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A": [3], "B": [6]}),
            ),
        ],
    )
    def test_handle_filter_rows_6(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="B", operator="<", value=6)],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}),
                pd.DataFrame({"A": [3, 4, 5], "B": [3, 2, 1]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}),
                pl.DataFrame({"A": [3, 4, 5], "B": [3, 2, 1]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}),
                ibis.memtable({"A": [3, 4, 5], "B": [3, 2, 1]}),
            ),
        ],
    )
    def test_handle_filter_rows_multiple_conditions_1(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(column_id="A", operator=">=", value=3),
                Condition(column_id="B", operator="<=", value=3),
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}),
                pd.DataFrame({"A": [1, 3, 4, 5], "B": [5, 3, 2, 1]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}),
                pl.DataFrame({"A": [1, 3, 4, 5], "B": [5, 3, 2, 1]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}),
                ibis.memtable({"A": [1, 3, 4, 5], "B": [5, 3, 2, 1]}),
            ),
        ],
    )
    def test_handle_filter_rows_multiple_conditions_2(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[
                Condition(column_id="A", operator="==", value=2),
                Condition(column_id="B", operator="==", value=4),
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [True, False, True, False]}),
                pd.DataFrame({"A": [True, True]}),
            ),
            (
                pl.DataFrame({"A": [True, False, True, False]}),
                pl.DataFrame({"A": [True, True]}),
            ),
            (
                ibis.memtable({"A": [True, False, True, False]}),
                ibis.memtable({"A": [True, True]}),
            ),
        ],
    )
    def test_handle_filter_rows_boolean(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="is_true")],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="A", operator="is_false")],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3]}),
                KeyError,
            ),
            (
                pl.DataFrame({"A": [1, 2, 3]}),
                pl.exceptions.ColumnNotFoundError,
            ),
            (
                ibis.memtable({"A": [1, 2, 3]}),
                ibis.common.exceptions.IbisTypeError,
            ),
        ],
    )
    def test_handle_filter_rows_unknown_column(
        df: DataFrameType, expected: Exception
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="B", operator=">=", value=2)],
        )
        with pytest.raises(expected):
            apply(df, transform)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({1: [1, 2, 3], 2: [4, 5, 6]}),
                pd.DataFrame({1: [2, 3], 2: [5, 6]}),
            ),
            (
                pl.DataFrame({"1": [1, 2, 3], "2": [4, 5, 6]}),
                pl.DataFrame({"1": [2, 3], "2": [5, 6]}),
            ),
            (
                ibis.memtable({"1": [1, 2, 3], "2": [4, 5, 6]}),
                ibis.memtable({"1": [2, 3], "2": [5, 6]}),
            ),
        ],
    )
    def test_handle_filter_rows_number_columns(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id=1, operator=">=", value=2)],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": ["foo", "foo", "bar"], "B": [1, 2, 3]}),
                pd.DataFrame({"B": [3, 3]}),
            ),
            (
                pd.DataFrame(
                    {"A": ["foo", "foo", "bar", "bar"], "B": [1, 2, 3, 4]}
                ),
                pd.DataFrame({"B": [7, 3]}),
            ),
            (
                pl.DataFrame({"A": ["foo", "foo", "bar"], "B": [1, 2, 4]}),
                pl.DataFrame({"A": ["foo", "bar"], "B_sum": [3, 4]}),
            ),
            (
                pl.DataFrame(
                    {"A": ["foo", "foo", "bar", "bar"], "B": [1, 2, 3, 4]}
                ),
                pl.DataFrame({"A": ["foo", "bar"], "B_sum": [3, 7]}),
            ),
            (
                ibis.memtable({"A": ["foo", "foo", "bar"], "B": [1, 2, 4]}),
                ibis.memtable({"A": ["foo", "bar"], "B_sum": [3, 4]}),
            ),
            (
                ibis.memtable(
                    {"A": ["foo", "foo", "bar", "bar"], "B": [1, 2, 3, 4]}
                ),
                ibis.memtable({"A": ["foo", "bar"], "B_sum": [3, 7]}),
            ),
        ],
    )
    def test_handle_group_by(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = GroupByTransform(
            type=TransformType.GROUP_BY,
            column_ids=["A"],
            drop_na=False,
            aggregation="sum",
        )
        result = apply(df, transform)
        if not isinstance(result, pd.DataFrame):
            order_by_a = SortColumnTransform(
                type=TransformType.SORT_COLUMN,
                column_id="A",
                ascending=False,
                na_position="last",
            )
            result = apply(result, order_by_a)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [6], "B": [15]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame(
                    {
                        "A_sum": [6],
                        "B_sum": [15],
                    }
                ),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A_sum": [6], "B_sum": [15]}),
            ),
        ],
    )
    def test_handle_aggregate_sum(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = AggregateTransform(
            type=TransformType.AGGREGATE,
            column_ids=["A", "B"],
            aggregations=["sum"],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [1, 3], "B": [4, 6]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame(
                    {
                        "A_min": [1],
                        "B_min": [4],
                        "A_max": [3],
                        "B_max": [6],
                    }
                ),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable(
                    {
                        "A_min": [1],
                        "B_min": [4],
                        "A_max": [3],
                        "B_max": [6],
                    }
                ),
            ),
        ],
    )
    def test_handle_aggregate_min_max(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = AggregateTransform(
            type=TransformType.AGGREGATE,
            column_ids=["A", "B"],
            aggregations=["min", "max"],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [1, 2, 3]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame({"A": [1, 2, 3]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A": [1, 2, 3]}),
            ),
        ],
    )
    def test_handle_select_columns_single(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = SelectColumnsTransform(
            type=TransformType.SELECT_COLUMNS, column_ids=["A"]
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
            ),
        ],
    )
    def test_handle_select_columns_multiple(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = SelectColumnsTransform(
            type=TransformType.SELECT_COLUMNS, column_ids=["A", "B"]
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [2, 3, 1], "B": [5, 6, 4]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame({"A": [2, 3, 1], "B": [5, 6, 4]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A": [2, 3, 1], "B": [5, 6, 4]}),
            ),
        ],
    )
    def test_shuffle_rows(df: DataFrameType, expected: DataFrameType) -> None:
        transform = ShuffleRowsTransform(
            type=TransformType.SHUFFLE_ROWS, seed=42
        )
        result = apply(df, transform)
        assert df_size(result) == df_size(expected)
        assert "A" in result
        assert "B" in result

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pd.DataFrame({"A": [1, 3], "B": [4, 6]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
                pl.DataFrame({"A": [1, 3], "B": [4, 6]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 5, 6]}),
                ibis.memtable({"A": [1, 3], "B": [4, 6]}),
            ),
        ],
    )
    def test_sample_rows(df: DataFrameType, expected: DataFrameType) -> None:
        transform = SampleRowsTransform(
            type=TransformType.SAMPLE_ROWS, n=2, seed=42, replace=False
        )
        result = apply(df, transform)
        assert df_size(result) == df_size(expected)
        assert "A" in result.columns
        assert "B" in result.columns

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        [
            pd.DataFrame(
                {
                    "A": [[0, 1, 2], ["foo"], [], [3, 4]],
                    "B": [1, 1, 1, 1],
                    "C": [["a", "b", "c"], [np.nan], [], ["d", "e"]],
                }
            ),
            pl.DataFrame(
                {
                    "A": [[0, 1, 2], ["foo"], [], [3, 4]],
                    "B": [1, 1, 1, 1],
                    "C": [["a", "b", "c"], [np.nan], [], ["d", "e"]],
                },
            ),
            ibis.memtable(
                {
                    "A": [[0, 1, 2], [], [], [3, 4]],
                    "B": [1, 1, 1, 1],
                    "C": [["a", "b", "c"], [np.nan], [], ["d", "e"]],
                }
            ),
        ],
    )
    def test_explode_columns(df: DataFrameType) -> None:
        import ibis

        transform = ExplodeColumnsTransform(
            type=TransformType.EXPLODE_COLUMNS, column_ids=["A", "C"]
        )
        result = apply(df, transform)
        if isinstance(result, ibis.Table):
            assert_frame_equal(result, df.unnest("A").unnest("C"))
        else:
            assert_frame_equal(result, df.explode(["A", "C"]))

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            (
                pd.DataFrame({"A": [{"foo": 1, "bar": "hello"}], "B": [1]}),
                pd.DataFrame({"B": [1], "foo": [1], "bar": ["hello"]}),
            ),
            (
                pl.DataFrame({"A": [{"foo": 1, "bar": "hello"}], "B": [1]}),
                pl.DataFrame({"B": [1], "foo": [1], "bar": ["hello"]}),
            ),
            (
                ibis.memtable({"A": [{"foo": 1, "bar": "hello"}], "B": [1]}),
                ibis.memtable({"B": [1], "foo": [1], "bar": ["hello"]}),
            ),
        ],
    )
    def test_expand_dict(df: DataFrameType, expected: DataFrameType) -> None:
        transform = ExpandDictTransform(
            type=TransformType.EXPAND_DICT, column_id="A"
        )
        result = apply(df, transform)
        assert_frame_equal(
            # Sort the columns because the order is not guaranteed
            expected[sorted(expected.columns)],
            result[sorted(result.columns)],
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected", "expected2"),
        [
            (
                pd.DataFrame({"A": [1, 2, 3], "B": [4, 6, 5]}),
                pd.DataFrame({"A": [3, 2], "B": [5, 6]}),
                pd.DataFrame({"A": [2], "B": [6]}),
            ),
            (
                pl.DataFrame({"A": [1, 2, 3], "B": [4, 6, 5]}),
                pl.DataFrame({"A": [3, 2], "B": [5, 6]}),
                pl.DataFrame({"A": [2], "B": [6]}),
            ),
            (
                ibis.memtable({"A": [1, 2, 3], "B": [4, 6, 5]}),
                ibis.memtable({"A": [3, 2], "B": [5, 6]}),
                ibis.memtable({"A": [2], "B": [6]}),
            ),
        ],
    )
    def test_transforms_container(
        df: DataFrameType, expected: DataFrameType, expected2: DataFrameType
    ) -> None:
        # Create a TransformsContainer object
        container = TransformsContainer(df, get_handler_for_dataframe(df))

        # Define some transformations
        sort_transform = SortColumnTransform(
            type=TransformType.SORT_COLUMN,
            column_id="B",
            ascending=True,
            na_position="last",
        )
        filter_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator=">=", value=2)],
        )
        transformations = Transformations([sort_transform, filter_transform])
        # Verify the next transformation
        assert container._is_superset(transformations) is False
        assert (
            container._get_next_transformations(transformations)
            == transformations
        )

        # Apply the transformations
        result = container.apply(transformations)

        # Get the transformed dataframe
        # Check that the transformations were applied correctly
        assert_frame_equal(result, expected)

        # Reapply transforms by adding a new one
        filter_again_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[Condition(column_id="B", operator="==", value=5)],
        )
        transformations = Transformations(
            [sort_transform, filter_transform, filter_again_transform]
        )
        # Verify the next transformation
        assert container._is_superset(transformations) is True
        assert container._get_next_transformations(
            transformations
        ) == Transformations([filter_again_transform])
        result = container.apply(
            transformations,
        )
        # Check that the transformations were applied correctly
        assert_frame_equal(result, expected2)

        transformations = Transformations([sort_transform, filter_transform])
        # Verify the next transformation
        assert container._is_superset(transformations) is False
        assert (
            container._get_next_transformations(transformations)
            == transformations
        )
        # Reapply by removing the last transform
        result = container.apply(
            transformations,
        )
        # Check that the transformations were applied correctly
        assert_frame_equal(result, expected)
