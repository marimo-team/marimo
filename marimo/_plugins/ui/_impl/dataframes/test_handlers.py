# Copyright 2023 Marimo. All rights reserved.
import pandas as pd

from marimo._plugins.ui._impl.dataframes.handlers import (
    apply_transforms,
)
from marimo._plugins.ui._impl.dataframes.transforms import (
    AggregateTransform,
    ColumnConversionTransform,
    Condition,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnsTransform,
    SortColumnTransform,
    Transform,
    Transformations,
)


def apply(df: pd.DataFrame, transform: Transform) -> pd.DataFrame:
    return apply_transforms(df, Transformations(transforms=[transform]))


def test_handle_column_conversion():
    # 1 string to int
    df = pd.DataFrame({"A": ["1", "2", "3"]})
    transform = ColumnConversionTransform(
        type="column_conversion", column_id="A", data_type=int, errors="raise"
    )
    result = apply(df, transform)
    assert result["A"].dtype == int
    # 2 float to string
    df = pd.DataFrame({"A": [1.1, 2.2, 3.3]})
    transform = ColumnConversionTransform(
        type="column_conversion", column_id="A", data_type=str, errors="raise"
    )
    result = apply(df, transform)
    assert result["A"].dtype == object
    assert result["A"].tolist() == ["1.1", "2.2", "3.3"]
    # 3 with errors
    df = pd.DataFrame({"A": ["1", "2", "3", "a"]})
    transform = ColumnConversionTransform(
        type="column_conversion", column_id="A", data_type=int, errors="ignore"
    )
    result = apply(df, transform)
    assert result["A"].dtype == object
    assert result["A"].tolist() == ["1", "2", "3", "a"]


def test_handle_rename_column():
    df = pd.DataFrame({"A": [1, 2, 3]})
    transform = RenameColumnsTransform(
        type="rename_column", column_id="A", new_column_id="B"
    )
    result = apply(df, transform)
    assert "B" in result.columns
    assert "A" not in result.columns

    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    transform = RenameColumnsTransform(
        type="rename_column", column_id="B", new_column_id="C"
    )
    result = apply(df, transform)
    assert "C" in result.columns
    assert "B" not in result.columns


def test_handle_sort_column():
    df = pd.DataFrame({"A": [3, 2, 1]})
    transform = SortColumnTransform(
        type="sort_column", column_id="A", ascending=True, na_position="last"
    )
    result = apply(df, transform)
    assert result["A"].tolist() == [1, 2, 3]

    df = pd.DataFrame({"A": [3, 2, 1], "B": [1, 3, 2]})
    transform = SortColumnTransform(
        type="sort_column", column_id="B", ascending=False, na_position="last"
    )
    result = apply(df, transform)
    assert result["B"].tolist() == [3, 2, 1]


def test_handle_filter_rows_1():
    df = pd.DataFrame({"A": [1, 2, 3]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="keep_rows",
        where=[Condition(column_id="A", operator=">=", value=2)],
    )
    result = apply(df, transform)
    assert result["A"].tolist() == [2, 3]


def test_handle_filter_rows_2():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="remove_rows",
        where=[Condition(column_id="B", operator="!=", value=5)],
    )
    result = apply(df, transform)
    assert result["B"].tolist() == [5]


def test_handle_filter_rows_3():
    df = pd.DataFrame({"A": [1, 2, 3, 4, 5]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="keep_rows",
        where=[Condition(column_id="A", operator="<", value=4)],
    )
    result = apply(df, transform)
    assert result["A"].tolist() == [1, 2, 3]


def test_handle_filter_rows_4():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="remove_rows",
        where=[Condition(column_id="A", operator="==", value=2)],
    )
    result = apply(df, transform)
    assert result["A"].tolist() == [1, 3]


def test_handle_filter_rows_5():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="keep_rows",
        where=[Condition(column_id="B", operator=">=", value=5)],
    )
    result = apply(df, transform)
    assert result["B"].tolist() == [5, 6]


def test_handle_filter_rows_6():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="remove_rows",
        where=[Condition(column_id="B", operator="<", value=6)],
    )
    result = apply(df, transform)
    assert result["B"].tolist() == [6]


def test_handle_filter_rows_multiple_conditions_1():
    df = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="keep_rows",
        where=[
            Condition(column_id="A", operator=">=", value=3),
            Condition(column_id="B", operator="<=", value=3),
        ],
    )
    result = apply(df, transform)
    assert result["A"].tolist() == [3, 4, 5]
    assert result["B"].tolist() == [3, 2, 1]


def test_handle_filter_rows_multiple_conditions_2():
    df = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [5, 4, 3, 2, 1]})
    transform = FilterRowsTransform(
        type="filter_rows",
        operation="remove_rows",
        where=[
            Condition(column_id="A", operator="==", value=2),
            Condition(column_id="B", operator="==", value=4),
        ],
    )
    result = apply(df, transform)
    assert result["A"].tolist() == [1, 3, 4, 5]
    assert result["B"].tolist() == [5, 3, 2, 1]


def test_handle_group_by():
    df = pd.DataFrame({"A": ["foo", "foo", "bar"], "B": [1, 2, 3]})
    transform = GroupByTransform(
        type="group_by", column_ids=["A"], drop_na=False, aggregation="sum"
    )
    result = apply(df, transform)
    assert result["B"].tolist() == [3, 3]

    df = pd.DataFrame({"A": ["foo", "foo", "bar", "bar"], "B": [1, 2, 3, 4]})
    transform = GroupByTransform(
        type="group_by", column_ids=["A"], drop_na=False, aggregation="mean"
    )
    result = apply(df, transform)
    assert set(result["B"].tolist()) == set([1.5, 3.5])


def test_handle_aggregate():
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    transform = AggregateTransform(
        type="aggregate", column_ids=["A", "B"], aggregations=["sum"]
    )
    result = apply(df, transform)
    assert result["A"]["sum"] == 6
    assert result["B"]["sum"] == 15

    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    transform = AggregateTransform(
        type="aggregate", column_ids=["A", "B"], aggregations=["min", "max"]
    )
    result = apply(df, transform)
    assert result["A"]["min"] == 1
    assert result["A"]["max"] == 3
    assert result["B"]["min"] == 4
    assert result["B"]["max"] == 6
