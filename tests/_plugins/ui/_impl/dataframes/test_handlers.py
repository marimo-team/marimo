# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from datetime import date
from typing import Any, Optional, cast

import narwhals.stable.v2 as nw
import pytest

from marimo._plugins.ui._impl.dataframes.transforms.apply import (
    TransformsContainer,
    apply_transforms_to_df,
)
from marimo._plugins.ui._impl.dataframes.transforms.handlers import (
    NarwhalsTransformHandler,
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
    UniqueTransform,
)
from marimo._plugins.ui._impl.tables.narwhals_table import (
    NAN_VALUE,
    NEGATIVE_INF,
    POSITIVE_INF,
)
from marimo._utils.narwhals_utils import is_narwhals_lazyframe, make_lazy
from tests._data.mocks import create_dataframes

pytest.importorskip("ibis")
pd = pytest.importorskip("pandas")
pytest.importorskip("polars")
pytest.importorskip("pyarrow")


def apply(df: DataFrameType, transform: Transform) -> DataFrameType:
    return apply_transforms_to_df(df, transform)


def create_test_dataframes(
    data: dict[str, list[Any]],
    *,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    strict: bool = True,
) -> list[DataFrameType]:
    """Create test dataframes including ibis if available."""
    return create_dataframes(
        data,
        include=include or ["pandas", "polars", "pyarrow", "ibis"],
        exclude=exclude,
        strict=strict,
    )


def collect_df(df: DataFrameType) -> nw.DataFrame[Any]:
    nw_df = nw.from_native(df)
    if is_narwhals_lazyframe(nw_df):
        nw_df = nw_df.collect()
    return nw_df


def assert_frame_equal(a: DataFrameType, b: DataFrameType) -> None:
    nw_a = collect_df(a)
    nw_b = collect_df(b)
    assert type(a) is type(b)
    assert nw_a.to_dict(as_series=False) == nw_b.to_dict(as_series=False)


def assert_frame_equal_with_nans(a: DataFrameType, b: DataFrameType) -> None:
    """
    Assert two dataframes are equal, treating NaNs in the same locations as equal.
    """
    import math

    nw_a = collect_df(a)
    nw_b = collect_df(b)

    dict_a = nw_a.to_dict(as_series=False)
    dict_b = nw_b.to_dict(as_series=False)

    assert dict_a.keys() == dict_b.keys(), "DataFrame columns do not match."

    for col in dict_a:
        values_a = dict_a[col]
        values_b = dict_b[col]
        assert len(values_a) == len(values_b), (
            f"Length mismatch in column {col}"
        )
        for idx, (val_a, val_b) in enumerate(zip(values_a, values_b)):
            both_nan = (
                isinstance(val_a, float)
                and isinstance(val_b, float)
                and math.isnan(val_a)
                and math.isnan(val_b)
            )
            if not (val_a == val_b or both_nan):
                raise AssertionError(
                    f"DataFrame values differ at column '{col}', row {idx}: {val_a} != {val_b}"
                )


def assert_frame_not_equal(df1: DataFrameType, df2: DataFrameType) -> None:
    with pytest.raises(AssertionError):
        assert_frame_equal(df1, df2)


def df_size(df: DataFrameType) -> int:
    nw_df = collect_df(df)
    return nw_df.shape[0]


class TestTransformHandler:
    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes({"A": ["1", "2", "3"]}),
                create_test_dataframes({"A": [1, 2, 3]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1.1, 2.2, 3.3]}),
                create_test_dataframes({"A": ["1.1", "2.2", "3.3"]}),
            )
        ),
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
    @pytest.mark.skip(
        reason="Column conversion with errors='ignore' not fully supported in narwhals"
    )
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes({"A": ["1", "2", "3", "a"]}),
                create_test_dataframes({"A": [1, 2, 3, None]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3]}),
                create_test_dataframes({"B": [1, 2, 3]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [3, 1, 2]}),
                create_test_dataframes({"A": [1, 2, 3]}),
                create_test_dataframes({"A": [3, 2, 1]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3]}),
                create_test_dataframes({"A": [2, 3]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [2], "B": [5]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3, 4, 5]}),
                create_test_dataframes({"A": [1, 2, 3]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3]}),
                create_test_dataframes({"A": [1, 3]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [2, 3], "B": [5, 6]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [3], "B": [6]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes(
                    {"date": [date(2001, 1, 1), date(2001, 1, 2)]},
                    exclude=["pandas"],
                ),
                create_test_dataframes(
                    {"date": [date(2001, 1, 1)]}, exclude=["pandas"]
                ),
            )
        ),
    )
    def test_handle_filter_rows_date(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="date", operator="==", value=date(2001, 1, 1)
                )
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [1, 2], "B": [4, 5]}),
            )
        ),
    )
    def test_filter_rows_in_operator(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="in", value=[1, 2])],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            *zip(
                create_test_dataframes(
                    {"date": [date(2001, 1, 1), date(2001, 1, 2)]},
                    exclude=["polars"],
                ),
                create_test_dataframes(
                    {"date": [date(2001, 1, 1)]}, exclude=["polars"]
                ),
            ),
        ],
    )
    def test_filter_rows_in_dates(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="date",
                    operator="in",
                    value=["2001-01-01"],  # Backend will receive as string
                ),
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"A": [[1, 2], [3, 4]]}, exclude=["pyarrow"]
                ),
                create_test_dataframes({"A": [[1, 2]]}, exclude=["pyarrow"]),
            )
        ),
    )
    def test_filter_rows_in_operator_nested_list(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="in", value=[[1, 2]])],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"A": [{"a": 1, "b": 2}, {"a": 3, "b": 4}]},
                    exclude=["ibis", "pyarrow"],
                ),
                create_test_dataframes(
                    {"A": [{"a": 1, "b": 2}]}, exclude=["ibis", "pyarrow"]
                ),
            )
        ),
    )
    def test_filter_rows_in_operator_dicts(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="A", operator="in", value=[{"a": 1, "b": 2}]
                )
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.xfail(
        reason="Filtering dicts with None values is not yet supported"
    )
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"A": [{"a": 1, "b": None}, {"a": 3, "b": 4}]},
                ),
                create_test_dataframes(
                    {"A": [{"a": 1, "b": None}]},
                ),
            )
        ),
    )
    def test_filter_rows_in_operator_dicts_with_nulls(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="A", operator="in", value=[{"a": 1, "b": None}]
                )
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            *zip(
                create_test_dataframes(
                    {"A": [1, 2, None], "B": [4, 5, 6]}, exclude=["pandas"]
                ),
                create_test_dataframes(
                    {"A": [None], "B": [6]}, exclude=["pandas"]
                ),
            ),
        ],
    )
    def test_filter_rows_in_operator_null_rows(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="in", value=[None])],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [3], "B": [6]}),
            )
        ),
    )
    def test_filter_rows_not_in_operator(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="not_in", value=[1, 2])],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"A": ["foo", "bar", "baz"], "B": [1, 2, 3]}
                ),
                create_test_dataframes({"A": ["baz"], "B": [3]}),
            )
        ),
    )
    def test_filter_rows_not_in_operator_strings(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="A", operator="not_in", value=["foo", "bar"]
                )
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            *zip(
                create_test_dataframes(
                    {"A": [1, 2, 3, None], "B": [4, 5, 6, 7]},
                    exclude=["ibis"],
                ),
                create_test_dataframes({"A": [3], "B": [6]}, exclude=["ibis"]),
            ),
        ],
    )
    def test_filter_rows_not_in_operator_with_nulls(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        # not_in with None in value should exclude rows where A is 1, 2, or null
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(column_id="A", operator="not_in", value=[1, 2, None])
            ],
        )
        result = apply(df, transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            *zip(
                create_test_dataframes(
                    {"A": [1, 2, 3, None], "B": [4, 5, 6, 7]},
                    exclude=["ibis"],
                ),
                create_test_dataframes(
                    {"A": [3, None], "B": [6, 7]}, exclude=["ibis"]
                ),
            ),
        ],
    )
    def test_filter_rows_not_in_operator_keep_nulls(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        # not_in WITHOUT None in value should keep null rows (only exclude 1 and 2)
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[Condition(column_id="A", operator="not_in", value=[1, 2])],
        )
        result = apply(df, transform)
        if nw.dependencies.is_pandas_dataframe(result):
            assert_frame_equal_with_nans(result, expected)
        else:
            assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}
                ),
                create_test_dataframes({"A": [3, 4, 5], "B": [3, 2, 1]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes(
                    {"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]}
                ),
                create_test_dataframes({"A": [1, 3, 4, 5], "B": [5, 3, 2, 1]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [True, False, True, False]}),
                create_test_dataframes({"A": [True, True]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3]}),
                [KeyError],
            )
        ),
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
            *zip(
                create_test_dataframes(
                    {1: [1, 2, 3], 2: [4, 5, 6]}, include=["pandas"]
                ),
                create_test_dataframes(
                    {1: [2, 3], 2: [5, 6]}, include=["pandas"]
                ),
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
        "df",
        create_test_dataframes({"column_a": ["alpha", "beta", "gamma"]}),
    )
    def test_handle_filter_rows_categorical(df: DataFrameType) -> None:
        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="column_a",
                    operator="equals",
                    value="alpha",
                )
            ],
        )
        result = apply(df, transform)
        assert df_size(result) == 1

        transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="column_a",
                    operator="does_not_equal",
                    value="alpha",
                )
            ],
        )
        result = apply(df, transform)
        assert df_size(result) == 2

        ends_with_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="column_a", operator="ends_with", value="mma"
                )
            ],
        )
        result = apply(df, ends_with_transform)
        assert df_size(result) == 1

        contains_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="column_a", operator="contains", value="mma"
                )
            ],
        )
        result = apply(df, contains_transform)
        assert df_size(result) == 1

        does_not_contain_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="remove_rows",
            where=[
                Condition(
                    column_id="column_a",
                    operator="contains",
                    value="mma",
                )
            ],
        )
        result = apply(df, does_not_contain_transform)
        assert df_size(result) == 2

        starts_with_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="column_a", operator="starts_with", value="alp"
                )
            ],
        )
        result = apply(df, starts_with_transform)
        assert df_size(result) == 1

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        [
            *zip(
                create_test_dataframes(
                    {"A": ["foo", "foo", "bar"], "B": [1, 2, 4]}
                ),
                create_test_dataframes({"A": ["foo", "bar"], "B_sum": [3, 4]}),
            ),
            *zip(
                create_test_dataframes(
                    {"A": ["foo", "foo", "bar", "bar"], "B": [1, 2, 3, 4]},
                ),
                create_test_dataframes({"A": ["foo", "bar"], "B_sum": [3, 7]}),
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
            aggregation_column_ids=[],
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
            *zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A_sum": [6], "B_sum": [15]}),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes(
                    {"A_min": [1], "B_min": [4], "A_max": [3], "B_max": [6]},
                ),
            ),
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [1, 2, 3]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
            )
        ),
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
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
                create_test_dataframes({"A": [2, 3, 1], "B": [5, 6, 4]}),
            )
        ),
    )
    def test_shuffle_rows(df: DataFrameType, expected: DataFrameType) -> None:
        transform = ShuffleRowsTransform(
            type=TransformType.SHUFFLE_ROWS, seed=42
        )
        result = apply(df, transform)
        assert df_size(result) == df_size(expected)
        nw_result = collect_df(result)
        assert "A" in nw_result.columns
        assert "B" in nw_result.columns
        assert type(result) is type(expected)

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        create_test_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}),
    )
    def test_sample_rows(df: DataFrameType) -> None:
        transform = SampleRowsTransform(
            type=TransformType.SAMPLE_ROWS, n=2, seed=42, replace=False
        )
        result = apply(df, transform)
        assert df_size(result) == 2
        nw_result = collect_df(result)
        assert "A" in nw_result.columns
        assert "B" in nw_result.columns
        assert type(result) is type(df)

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        create_test_dataframes(
            {
                "A": [[0, 1, 2], [1], [], [3, 4]],
                "B": [1, 1, 1, 1],
                "C": [["a", "b", "c"], ["foo"], [], ["d", "e"]],
            },
            strict=False,
            exclude=[
                "pandas",
                "ibis",
                "pyarrow",
            ],  # pandas Object dtype and ibis multi-column explode not supported
        ),
    )
    def test_explode_columns(df: DataFrameType) -> None:
        transform = ExplodeColumnsTransform(
            type=TransformType.EXPLODE_COLUMNS, column_ids=["A", "C"]
        )
        result = apply(df, transform)
        nw_result = collect_df(result)
        assert nw_result.columns == ["A", "B", "C"]

    @staticmethod
    @pytest.mark.skip(
        reason="Dict/struct expansion not supported uniformly across backends"
    )
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"A": [{"foo": 1, "bar": "hello"}], "B": [1]}
                ),
                create_test_dataframes(
                    {"B": [1], "foo": [1], "bar": ["hello"]}
                ),
            )
        ),
    )
    def test_expand_dict(df: DataFrameType, expected: DataFrameType) -> None:
        transform = ExpandDictTransform(
            type=TransformType.EXPAND_DICT, column_id="A"
        )
        result = apply(df, transform)
        # Convert to narwhals and select sorted columns
        nw_result = collect_df(result)
        nw_expected = collect_df(expected)
        result_cols = sorted(nw_result.columns)
        expected_cols = sorted(nw_expected.columns)
        assert_frame_equal(
            nw_expected.select(expected_cols),
            nw_result.select(result_cols),
        )

    @staticmethod
    @pytest.mark.parametrize(
        (
            "df",
            "expected_first",
            "expected_last",
            "expected_none",
            "expected_any",
        ),
        [
            *[
                (df, exp_first, exp_last, exp_none, exp_any)
                for df, exp_first, exp_last, exp_none, exp_any in zip(
                    create_test_dataframes(
                        {"A": ["a", "a", "b", "b", "c"], "B": [1, 2, 3, 4, 5]},
                    ),
                    create_test_dataframes(
                        {"A": ["a", "b", "c"], "B": [1, 3, 5]},
                    ),
                    create_test_dataframes(
                        {"A": ["a", "b", "c"], "B": [2, 4, 5]},
                    ),
                    create_test_dataframes(
                        {"A": ["c"], "B": [5]},
                    ),
                    create_test_dataframes(
                        {"A": ["a", "b", "c"], "B": [1, 3, 5]},
                    ),
                )
            ],
        ],
    )
    def test_unique(
        df: DataFrameType,
        expected_first: DataFrameType,
        expected_last: DataFrameType,
        expected_none: DataFrameType,
        expected_any: DataFrameType,
    ) -> None:
        for keep, expected in [
            ("first", expected_first),
            ("last", expected_last),
            ("none", expected_none),
        ]:
            transform = UniqueTransform(
                type=TransformType.UNIQUE, column_ids=["A"], keep=keep
            )
            result = apply(df, transform)
            # Order may not be preserved across backends, sort before comparing
            nw_result = collect_df(result)
            nw_expected = collect_df(expected)
            assert_frame_equal(
                nw_expected.sort("A"),
                nw_result.sort("A"),
            )

        transform = UniqueTransform(
            type=TransformType.UNIQUE, column_ids=["A"], keep="any"
        )
        result = apply(df, transform)
        # For "any" mode, order is not guaranteed, so sort both before comparing
        nw_result = collect_df(result)
        nw_expected = collect_df(expected_any)
        assert_frame_equal(
            nw_expected.sort("A"),
            nw_result.sort("A"),
        )
        assert type(result) is type(df)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected", "expected2"),
        list(
            zip(
                create_test_dataframes({"A": [1, 2, 3], "B": [4, 6, 5]}),
                create_test_dataframes({"A": [3, 2], "B": [5, 6]}),
                create_test_dataframes({"A": [2], "B": [6]}),
            )
        ),
    )
    def test_transforms_container(
        df: DataFrameType, expected: DataFrameType, expected2: DataFrameType
    ) -> None:
        nw_df, undo = make_lazy(df)
        container = TransformsContainer(nw_df, NarwhalsTransformHandler())

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
        assert_frame_equal(undo(result), expected)

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
        assert_frame_equal(undo(result), expected2)

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
        assert_frame_equal(undo(result), expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"date": [date(2001, 1, 1), date(2001, 1, 2)]},
                    exclude=["pyarrow"],
                ),
                create_test_dataframes(
                    {"date": [date(2001, 1, 1)]}, exclude=["pyarrow"]
                ),
            )
        ),
    )
    def test_filter_rows_date(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        eq_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="date",
                    operator="==",
                    value="2001-01-01",
                )
            ],
        )
        result = apply(df, eq_transform)
        assert_frame_equal(result, expected)

        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="date",
                    operator="in",
                    value=["2001-01-01"],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"nulls": [1, 2, 3, None]}, include=["pandas"]
                ),
                create_test_dataframes(
                    {"nulls": [float("nan")]}, include=["pandas"]
                ),
            )
        ),
    )
    def test_filter_rows_nulls_pandas(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="nulls",
                    operator="in",
                    value=[NAN_VALUE],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal_with_nans(result, expected)

    @staticmethod
    @pytest.mark.xfail(
        reason="NaN filtering for object dtypes in pandas aren't implemented"
    )
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"nulls": [1, 2, 3, None, "hello"]}, include=["pandas"]
                ),
                create_test_dataframes(
                    {"nulls": [float("nan")]}, include=["pandas"]
                ),
            )
        ),
    )
    def test_filter_rows_null_pandas_object(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="nulls",
                    operator="in",
                    value=[NAN_VALUE],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"nulls": [1, 2, 3, float("nan")]},
                    exclude=["pandas", "ibis"],  # Ibis serializes nans to None
                    strict=False,
                ),
                create_test_dataframes(
                    {"nulls": [float("nan")]}, exclude=["pandas", "ibis"]
                ),
            )
        ),
    )
    def test_filter_rows_nulls_others(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="nulls",
                    operator="in",
                    value=[NAN_VALUE],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal_with_nans(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"nulls": [1, 2, 3, float("nan"), float("inf")]},
                    strict=False,
                ),
                create_test_dataframes({"nulls": [float("inf")]}),
            )
        ),
    )
    def test_filter_rows_infs(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="nulls",
                    operator="in",
                    value=[POSITIVE_INF],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal_with_nans(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {"nulls": [1, float("nan"), float("inf"), float("-inf")]},
                    strict=False,
                ),
                create_test_dataframes({"nulls": [float("-inf")]}),
            )
        ),
    )
    def test_filter_rows_neg_infs(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="nulls",
                    operator="in",
                    value=[NEGATIVE_INF],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal_with_nans(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {
                        "nulls": [
                            1,
                            float("nan"),
                            float("inf"),
                            float("-inf"),
                            None,
                        ]
                    },
                    include=["pandas"],
                ),
                create_test_dataframes(
                    {"nulls": [float("nan"), float("inf"), None]},
                    include=["pandas"],
                ),
            )
        ),
    )
    def test_filter_rows_infs_and_nulls_pandas(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="nulls",
                    operator="in",
                    value=[NAN_VALUE, POSITIVE_INF, None],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal_with_nans(result, expected)

    @staticmethod
    @pytest.mark.parametrize(
        ("df", "expected"),
        list(
            zip(
                create_test_dataframes(
                    {
                        "nulls": [
                            1,
                            float("nan"),
                            float("inf"),
                            float("-inf"),
                            None,
                        ]
                    },
                    exclude=["pandas", "ibis"],  # Ibis serializes nans to None
                    strict=False,
                ),
                create_test_dataframes(
                    {"nulls": [float("nan"), float("inf"), None]},
                    exclude=["pandas", "ibis"],
                ),
            )
        ),
    )
    def test_filter_rows_infs_and_nulls_others(
        df: DataFrameType, expected: DataFrameType
    ) -> None:
        in_transform = FilterRowsTransform(
            type=TransformType.FILTER_ROWS,
            operation="keep_rows",
            where=[
                Condition(
                    column_id="nulls",
                    operator="in",
                    value=[NAN_VALUE, POSITIVE_INF, None],
                )
            ],
        )
        result = apply(df, in_transform)
        assert_frame_equal_with_nans(result, expected)
