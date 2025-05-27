# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.dataframes.transforms.types import Condition
from marimo._plugins.ui._impl.table import (
    DEFAULT_MAX_COLUMNS,
    MAX_COLUMNS_NOT_PROVIDED,
    CalculateTopKRowsArgs,
    CalculateTopKRowsResponse,
    DownloadAsArgs,
    SearchTableArgs,
    SortArgs,
    get_default_table_page_size,
)
from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager
from marimo._plugins.ui._impl.tables.selection import INDEX_COLUMN_NAME
from marimo._plugins.ui._impl.tables.table_manager import TableCell
from marimo._plugins.ui._impl.utils.dataframe import TableData
from marimo._runtime.functions import EmptyArgs
from marimo._runtime.runtime import Kernel
from marimo._utils.data_uri import from_data_uri
from marimo._utils.platform import is_windows
from tests._data.mocks import create_dataframes

if TYPE_CHECKING:
    import pandas as pd


@pytest.fixture
def dtm() -> None:
    return DefaultTableManager([])


def _normalize_data(data: Any) -> list[dict[str, Any]]:
    return DefaultTableManager._normalize_data(data)


def test_normalize_data(executing_kernel: Kernel) -> None:
    # unused, except for the side effect of giving the kernel an execution
    # context
    del executing_kernel

    # Create kernel and give the execution context an existing cell
    data: TableData

    # Test with list of integers
    data = [1, 2, 3]
    result = _normalize_data(data)
    assert result == [
        {"value": 1},
        {"value": 2},
        {"value": 3},
    ]

    # Test with list of strings
    data = ["a", "b", "c"]
    result = _normalize_data(data)
    assert result == [
        {"value": "a"},
        {"value": "b"},
        {"value": "c"},
    ]

    # Test with list of dictionaries
    data = [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]
    result = _normalize_data(data)
    assert result == [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]

    # Dictionary with list of integers
    data = {"key": [1, 2, 3]}
    result = _normalize_data(data)
    assert result == [
        {"key": 1},
        {"key": 2},
        {"key": 3},
    ]

    # Dictionary with tuple of integers
    data = {"key": (1, 2, 3)}
    result = _normalize_data(data)
    assert result == [
        {"key": 1},
        {"key": 2},
        {"key": 3},
    ]

    # Test with empty list
    data = []
    result = _normalize_data(data)
    assert result == []

    # Test with invalid data type
    data2: Any = "invalid data type"
    with pytest.raises(ValueError) as e:
        _normalize_data(data2)
    assert str(e.value) == "data must be a list or tuple or a dict of lists."

    # Test with invalid data structure
    data3: Any = [set([1, 2, 3])]
    with pytest.raises(ValueError) as e:
        _normalize_data(data3)
    assert (
        str(e.value) == "data must be a sequence of JSON-serializable types, "
        "or a sequence of dicts."
    )


def test_sort_1d_list_of_strings(dtm: DefaultTableManager) -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="value", descending=False).data
    expected_data = [
        {"value": "apple"},
        {"value": "banana"},
        {"value": "cherry"},
        {"value": "date"},
        {"value": "elderberry"},
    ]
    assert sorted_data == expected_data


def test_sort_1d_list_of_integers(dtm: DefaultTableManager) -> None:
    data = [42, 17, 23, 99, 8]
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="value", descending=False).data
    expected_data = [
        {"value": 8},
        {"value": 17},
        {"value": 23},
        {"value": 42},
        {"value": 99},
    ]
    assert sorted_data == expected_data


def test_sort_list_of_dicts(dtm: DefaultTableManager) -> None:
    data = [
        {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
        {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
        {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
        {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
    ]
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="age", descending=True).data

    with pytest.raises(KeyError):
        _res = dtm.sort_values(by="missing_column", descending=True).data

    expected_data = [
        {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
        {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
        {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
        {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
    ]
    assert sorted_data == expected_data


def test_sort_dict_of_lists(dtm: DefaultTableManager) -> None:
    data = {
        "company": [
            "Company A",
            "Company B",
            "Company C",
            "Company D",
            "Company E",
        ],
        "type": ["Tech", "Finance", "Health", "Tech", "Finance"],
        "net_worth": [1000, 2000, 1500, 1800, 1700],
    }
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="net_worth", descending=False).data

    with pytest.raises(KeyError):
        _res = dtm.sort_values(by="missing_column", descending=True).data

    expected_data = {
        "company": [
            "Company A",
            "Company C",
            "Company E",
            "Company D",
            "Company B",
        ],
        "type": ["Tech", "Health", "Finance", "Tech", "Finance"],
        "net_worth": [1000, 1500, 1700, 1800, 2000],
    }
    assert sorted_data == _normalize_data(expected_data)


def test_sort_dict_of_tuples(dtm: DefaultTableManager) -> None:
    data = {
        "key1": (42, 17, 23),
        "key2": (99, 8, 4),
        "key3": (34, 65, 12),
        "key4": (1, 2, 3),
        "key5": (7, 9, 11),
    }
    dtm.data = _normalize_data(data)
    sorted_data = dtm.sort_values(by="key1", descending=True).data

    with pytest.raises(KeyError):
        _res = dtm.sort_values(by="missing_column", descending=True).data

    expected_data = [
        {"key1": 42, "key2": 99, "key3": 34, "key4": 1, "key5": 7},
        {"key1": 23, "key2": 4, "key3": 12, "key4": 3, "key5": 11},
        {"key1": 17, "key2": 8, "key3": 65, "key4": 2, "key5": 9},
    ]
    assert sorted_data == _normalize_data(expected_data)


def test_value() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)
    assert list(table.value) == []


def test_value_with_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)
    assert list(table._convert_value(["0", "2"])) == [
        "banana",
        "cherry",
    ]


def test_value_with_initial_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data, initial_selection=[0, 2])
    assert table.value == ["banana", "cherry"]


def test_value_does_not_include_index_column() -> None:
    data: list[dict[str, Any]] = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": 35},
    ]
    table = ui.table(data, initial_selection=[0, 2])
    selected_data = table.value
    assert isinstance(selected_data, list)
    assert len(selected_data) == 2
    assert all(isinstance(row, dict) for row in selected_data)
    # Check that INDEX_COLUMN_NAME is not in any of the selected rows
    for row in selected_data:
        assert isinstance(row, dict)
        assert INDEX_COLUMN_NAME not in row
    assert selected_data == [
        {"name": "Alice", "age": 30},
        {"name": "Charlie", "age": 35},
    ]


def test_invalid_initial_selection() -> None:
    data = ["banana", "apple"]
    with pytest.raises(IndexError):
        ui.table(data, initial_selection=[2])

    with pytest.raises(TypeError):
        ui.table(data, initial_selection=["apple"])

    # multiple rows cannot be selected for single selection mode
    with pytest.raises(ValueError):
        ui.table(data, selection="single", initial_selection=[0, 1])


def test_value_with_sorting_then_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)

    table._search(
        SearchTableArgs(
            sort=SortArgs("value", descending=True),
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "elderberry"},
    ]

    table._search(
        SearchTableArgs(
            sort=SortArgs(
                "value",
                descending=False,
            ),
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "apple"},
    ]


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": ["x", "z", "y"]},
        exclude=["ibis", "duckdb", "lazy-polars"],
    ),
)
def test_value_with_sorting_then_selection_dfs(df: Any) -> None:
    import narwhals as nw

    table = ui.table(df)
    table._search(
        SearchTableArgs(
            sort=SortArgs("a", descending=True),
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["0"])
    assert not isinstance(value, nw.DataFrame)
    assert nw.from_native(value)["a"][0] == "x"

    table._search(
        SearchTableArgs(
            sort=SortArgs("a", descending=False),
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["0"])
    assert not isinstance(value, nw.DataFrame)
    assert INDEX_COLUMN_NAME not in value.columns
    assert nw.from_native(value)["a"][0] == "x"


def test_value_with_search_then_selection() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)

    table._search(
        SearchTableArgs(
            query="apple",
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "apple"},
    ]

    table._search(
        SearchTableArgs(
            query="banana",
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["0"])) == [
        {"value": "banana"},
    ]

    # Rows not in the search are not selected
    with pytest.raises(IndexError):
        table._convert_value(["2"])

    # empty search
    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    assert list(table._convert_value(["2"])) == ["cherry"]


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": ["foo", "bar", "baz"]},
        exclude=["ibis", "duckdb", "lazy-polars"],
    ),
)
def test_value_with_search_then_selection_dfs(df: Any) -> None:
    import narwhals as nw

    table = ui.table(df)
    table._search(
        SearchTableArgs(
            query="bar",
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["1"])
    assert not isinstance(value, nw.DataFrame)
    assert INDEX_COLUMN_NAME not in value.columns
    assert nw.from_native(value)["a"][0] == "bar"

    table._search(
        SearchTableArgs(
            query="foo",
            page_size=10,
            page_number=0,
        )
    )
    # Can still select rows not in the search
    value = table._convert_value(["0", "1"])
    assert not isinstance(value, nw.DataFrame)
    assert INDEX_COLUMN_NAME not in value.columns
    assert nw.from_native(value)["a"][0] == "foo"
    assert nw.from_native(value)["a"][1] == "bar"
    # empty search
    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value(["2"])
    assert not isinstance(value, nw.DataFrame)
    assert nw.from_native(value)["a"][0] == "baz"


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": ["foo", "bar", "baz"]},
        exclude=["ibis", "duckdb", "lazy-polars"],
    ),
)
def test_value_with_search_then_cell_selection_dfs(df: Any) -> None:
    import narwhals as nw

    table = ui.table(df, selection="multi-cell")
    table._search(
        SearchTableArgs(
            query="bar",
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value([{"rowId": "1", "columnName": "a"}])
    assert not isinstance(value, nw.DataFrame)
    assert value[0].value == "bar"

    table._search(
        SearchTableArgs(
            query="foo",
            page_size=10,
            page_number=0,
        )
    )
    # Can still select rows not in the search
    value = table._convert_value(
        [{"rowId": 0, "columnName": "a"}, {"rowId": 1, "columnName": "a"}]
    )
    assert not isinstance(value, nw.DataFrame)
    assert value[0].value == "foo"
    assert len(value) == 1

    # empty search
    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    value = table._convert_value([{"rowId": "2", "columnName": "a"}])
    assert not isinstance(value, nw.DataFrame)
    assert value[0].value == "baz"


def test_value_with_selection_then_sorting_dict_of_lists() -> None:
    data = {
        "company": [
            "Company A",
            "Company B",
            "Company C",
            "Company D",
            "Company E",
        ],
        "type": ["Tech", "Finance", "Health", "Tech", "Finance"],
        "net_worth": [1000, 2000, 1500, 1800, 1700],
    }
    table = ui.table(data)

    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    assert table._convert_value(["0", "2"])["company"] == [
        "Company A",
        "Company C",
    ]

    table._search(
        SearchTableArgs(
            sort=SortArgs("net_worth", descending=True),
            page_size=10,
            page_number=0,
        )
    )
    assert table._convert_value(["0", "2"])["company"] == [
        "Company B",
        "Company E",
    ]


def test_value_with_cell_selection_then_sorting_dict_of_lists() -> None:
    data = {
        "company": [
            "Company A",
            "Company B",
            "Company C",
            "Company D",
            "Company E",
        ],
        "type": ["Tech", "Finance", "Health", "Tech", "Finance"],
        "net_worth": [1000, 2000, 1500, 1800, 1700],
    }
    table = ui.table(data, selection="multi-cell")

    table._search(
        SearchTableArgs(
            page_size=10,
            page_number=0,
        )
    )
    assert table._convert_value(
        [
            {"rowId": "0", "columnName": "company"},
            {"rowId": "2", "columnName": "company"},
        ]
    ) == [
        TableCell(row="0", column="company", value="Company A"),
        TableCell(row="2", column="company", value="Company C"),
    ]

    table._search(
        SearchTableArgs(
            sort=SortArgs("net_worth", descending=True),
            page_size=10,
            page_number=0,
        )
    )
    assert table._convert_value(
        [
            {"rowId": "0", "columnName": "company"},
            {"rowId": "2", "columnName": "company"},
        ]
    ) == [
        TableCell(row="0", column="company", value="Company B"),
        TableCell(row="2", column="company", value="Company E"),
    ]


@pytest.mark.parametrize(
    "df", create_dataframes({"a": [1, 2, 3]}, include=["ibis"])
)
def test_value_with_cell_selection_unsupported_for_ibis(df: Any) -> None:
    with pytest.raises(NotImplementedError):
        _table = ui.table(df, selection="multi-cell")


def test_search_sort_nonexistent_columns() -> None:
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    table = ui.table(data)

    # no error raised
    table._search(
        SearchTableArgs(
            sort=SortArgs("missing_column", descending=False),
            page_size=10,
            page_number=0,
        )
    )

    assert table._convert_value(["0"]) == ["banana"]


def test_invalid_index_in_initial_selection() -> None:
    """Test that invalid initial selection raises appropriate errors"""
    with pytest.raises(IndexError):
        ui.table(
            data={"a": [1, 2], "b": [3, 4]},
            initial_selection=[5],  # Invalid index
        )


def test_invalid_initial_cell_selection() -> None:
    """Test that invalid initial selection raises appropriate errors"""
    with pytest.raises(TypeError):
        ui.table(
            data={"a": [1, 2], "b": [3, 4]},
            selection="single-cell",
            initial_selection=[(1, 2, 3)],  # invalid tulple length
        )


def test_initial_row_selection_happy_path() -> None:
    """Test that initial row selection works with valid indices"""
    table = ui.table(
        data={"a": [1, 2, 3], "b": [4, 5, 6]}, initial_selection=[0, 1]
    )
    assert table.value == {"a": [1, 2], "b": [4, 5]}


def test_initial_cell_selection_happy_path() -> None:
    """Test that initial cell selection works with valid coordinates"""
    table = ui.table(
        data={"a": [1, 2, 3], "b": [4, 5, 6]},
        selection="multi-cell",
        initial_selection=[("0", "a"), ("1", "b")],
    )
    assert table.value == [
        TableCell(row="0", column="a", value=1),
        TableCell(row="1", column="b", value=5),
    ]


def test_get_row_ids_dict() -> None:
    data = {
        "id": [1, 2, 3] * 3,
        "fruits": ["banana", "apple", "cherry"] * 3,
        "quantity": [10, 20, 30] * 3,
    }
    table = ui.table(data)

    initial_response = table._get_row_ids(EmptyArgs())
    assert initial_response.all_rows is True
    assert initial_response.row_ids == []
    assert initial_response.error is None

    table._search(
        SearchTableArgs(
            query="cherry",
            page_size=10,
            page_number=0,
        )
    )

    response = table._get_row_ids(EmptyArgs())
    # For dicts, we do not need to find row_id, we just return the index
    assert response.row_ids == [0, 1, 2]
    assert response.all_rows is False
    assert response.error is None


def test_get_row_ids_for_lists() -> None:
    table = ui.table(["apples", "bananas", "bananas", "cherries"])
    initial_response = table._get_row_ids(EmptyArgs())
    assert initial_response.all_rows is True
    assert initial_response.row_ids == []
    assert initial_response.error is None

    table._search(
        SearchTableArgs(
            query="banana",
            page_size=10,
            page_number=0,
        )
    )
    response = table._get_row_ids(EmptyArgs())
    assert response.row_ids == [0, 1]
    assert response.all_rows is False
    assert response.error is None


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "id": [1, 2, 3] * 3,
            "fruits": ["banana", "apple", "cherry"] * 3,
            "quantity": [10, 20, 30] * 3,
        },
        exclude=["ibis", "duckdb", "lazy-polars"],
    ),
)
def test_get_row_ids_with_df(df: any) -> None:
    table = ui.table(df)

    initial_response = table._get_row_ids(EmptyArgs())
    assert initial_response.all_rows is True
    assert initial_response.row_ids == []
    assert initial_response.error is None

    # Test with search
    table._search(
        SearchTableArgs(
            query="cherry",
            page_size=10,
            page_number=0,
        )
    )

    response = table._get_row_ids(EmptyArgs())
    assert response.row_ids == [2, 5, 8]
    assert response.all_rows is False
    assert response.error is None

    # Test with no search
    table._search(
        SearchTableArgs(
            query="",
            page_size=10,
            page_number=0,
        )
    )

    response = table._get_row_ids(EmptyArgs())
    assert response.all_rows is True
    assert response.row_ids == []
    assert response.error is None


def test_table_with_too_many_columns_passes() -> None:
    data = {str(i): [1] for i in range(101)}
    assert ui.table(data) is not None


def test_table_with_too_many_rows_gets_clamped() -> None:
    data = {"a": list(range(20_002))}
    table = ui.table(data)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["total-rows"] == 20_002
    assert len(json.loads(table._component_args["data"])) == 10


def test_table_too_large_pagesize_throws_error() -> None:
    data = {"a": list(range(20_002))}
    with pytest.raises(ValueError) as e:
        _ = ui.table(data, page_size=201)
    assert "limited to 200 rows" in str(e.value)


def test_can_get_second_page() -> None:
    data = {"a": list(range(40))}
    table = ui.table(data)
    result = table._search(
        SearchTableArgs(
            page_size=10,
            page_number=1,
        )
    )
    result_data = json.loads(result.data)
    assert len(result_data) == 10
    assert result_data[0]["a"] == 10
    assert result_data[-1]["a"] == 19


def test_can_get_second_page_with_search() -> None:
    data = {"a": list(range(40))}
    table = ui.table(data)
    result = table._search(
        SearchTableArgs(
            query="2",
            page_size=5,
            page_number=1,
        )
    )
    result_data = json.loads(result.data)
    assert len(result_data) == 5
    assert result_data[0]["a"] == 23
    assert result_data[-1]["a"] == 27


@pytest.mark.parametrize(
    "df",
    create_dataframes({"a": list(range(40))}, include=["ibis"]),
)
def test_can_get_second_page_with_search_df(df: Any) -> None:
    table = ui.table(df)
    result = table._search(
        SearchTableArgs(
            query="2",
            page_size=5,
            page_number=1,
        )
    )
    result_data = json.loads(result.data)
    assert len(result_data) == 5
    assert int(result_data[0]["a"]) == 23
    assert int(result_data[-1]["a"]) == 27


def test_with_no_pagination() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data, pagination=False)
    assert table._component_args["pagination"] is False
    assert table._component_args["page-size"] == 20
    assert table._component_args["total-rows"] == 20
    assert len(json.loads(table._component_args["data"])) == 20


def test_table_with_too_many_rows_and_custom_total() -> None:
    data = {"a": list(range(40))}
    table = ui.table(
        data, _internal_column_charts_row_limit=30, _internal_total_rows=300
    )
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["total-rows"] == 300
    assert len(json.loads(table._component_args["data"])) == 10


def test_table_with_too_many_rows_unknown_total() -> None:
    data = {"a": list(range(40))}
    table = ui.table(
        data,
        _internal_column_charts_row_limit=30,
        _internal_total_rows="too_many",
    )
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["total-rows"] == "too_many"
    assert len(json.loads(table._component_args["data"])) == 10


def test_empty_table() -> None:
    table = ui.table([])
    assert table._component_args["total-rows"] == 0


def test_table_with_too_many_rows_column_summaries_disabled() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data, _internal_summary_row_limit=10)

    summaries_disabled = table._get_column_summaries(EmptyArgs())
    assert summaries_disabled.is_disabled is True

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    summaries_enabled = table._get_column_summaries(EmptyArgs())
    assert summaries_enabled.is_disabled is False


def test_with_too_many_rows_column_charts_disabled() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data, _internal_column_charts_row_limit=10)

    charts_disabled = table._get_column_summaries(EmptyArgs())
    assert charts_disabled.is_disabled is False
    assert charts_disabled.data is None

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    charts_enabled = table._get_column_summaries(EmptyArgs())
    assert charts_enabled.is_disabled is False


@pytest.mark.skipif(is_windows(), reason=r"windows returns \r instead")
def test__get_column_summaries_after_search() -> None:
    data = {"a": list(range(20))}
    table = ui.table(data)

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    summaries_data = from_data_uri(summaries.data)[1].decode("utf-8")
    # Result is csv or json
    assert summaries_data in ["a\n2\n12\n", '[{"a": 2}, {"a": 12}]']
    # We don't have column summaries for non-dataframe data
    assert summaries.stats["a"].min is None
    assert summaries.stats["a"].max is None


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test__get_column_summaries_after_search_df() -> None:
    import pandas as pd

    table = ui.table(pd.DataFrame({"a": list(range(20))}))
    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    assert isinstance(summaries.data, str)
    assert summaries.data.startswith(
        "data:text/plain;base64,"
    ) or summaries.data.startswith(
        "data:application/vnd.apache.arrow.file;base64,"
    )
    assert summaries.stats["a"].min == 0
    assert summaries.stats["a"].max == 19

    # search results are 2 and 12
    table._search(
        SearchTableArgs(
            query="2",
            page_size=10,
            page_number=0,
        )
    )
    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    assert isinstance(summaries.data, str)
    # Result is csv
    assert summaries.data.startswith(
        "data:text/csv;base64,"
    ) or summaries.data.startswith(
        "data:application/vnd.apache.arrow.file;base64,"
    )
    # We don't have column summaries for non-dataframe data
    assert summaries.stats["a"].min == 2
    assert summaries.stats["a"].max == 12
    assert summaries.stats["a"].nulls == 0


def test_show_column_summaries_modes():
    data = {"a": list(range(20))}

    # Test stats-only mode
    table_stats = ui.table(data, show_column_summaries="stats")
    summaries_stats = table_stats._get_column_summaries(EmptyArgs())
    assert summaries_stats.is_disabled is False
    assert summaries_stats.data is None
    assert len(summaries_stats.stats) > 0

    # Test chart-only mode
    table_chart = ui.table(data, show_column_summaries="chart")
    summaries_chart = table_chart._get_column_summaries(EmptyArgs())
    assert summaries_chart.is_disabled is False
    assert summaries_chart.data is not None
    assert len(summaries_chart.stats) == 0

    # Test default mode (both stats and chart)
    table_both = ui.table(data, show_column_summaries=True)
    summaries_both = table_both._get_column_summaries(EmptyArgs())
    assert summaries_both.is_disabled is False
    assert summaries_both.data is not None
    assert len(summaries_both.stats) > 0

    # Test disabled mode
    table_disabled = ui.table(data, show_column_summaries=False)
    summaries_disabled = table_disabled._get_column_summaries(EmptyArgs())
    assert summaries_disabled.is_disabled is False
    assert summaries_disabled.data is None
    assert len(summaries_disabled.stats) == 0

    # Test Default behavior
    table_default = ui.table(data)
    summaries_default = table_default._get_column_summaries(EmptyArgs())
    assert summaries_default.is_disabled is False
    assert summaries_default.data is not None
    assert len(summaries_default.stats) > 0


def test_table_with_frozen_columns() -> None:
    data = {
        "a": list(range(20)),
        "b": list(range(20)),
        "c": list(range(20)),
        "d": list(range(20)),
        "e": list(range(20)),
    }
    table = ui.table(
        data, freeze_columns_left=["a", "b"], freeze_columns_right=["d", "e"]
    )
    assert table._component_args["freeze-columns-left"] == ["a", "b"]
    assert table._component_args["freeze-columns-right"] == ["d", "e"]


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_table_with_filtered_columns_pandas() -> None:
    import pandas as pd

    table = ui.table(pd.DataFrame({"a": [1, 2, 3], "b": ["abc", "def", None]}))
    result = table._search(
        SearchTableArgs(
            filters=[Condition(column_id="b", operator="contains", value="f")],
            page_size=10,
            page_number=0,
        )
    )
    assert result.total_rows == 1


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_table_with_filtered_columns_polars() -> None:
    import polars as pl

    table = ui.table(pl.DataFrame({"a": [1, 2, 3], "b": ["abc", "def", None]}))
    result = table._search(
        SearchTableArgs(
            filters=[Condition(column_id="b", operator="contains", value="a")],
            page_size=10,
            page_number=0,
        )
    )

    assert result.total_rows == 1


def test_show_column_summaries_default():
    # Test default behavior (True for < 40 columns, False otherwise)
    small_data = {"col" + str(i): range(5) for i in range(39)}
    table_small = ui.table(small_data)
    assert table_small._show_column_summaries is True
    assert table_small._component_args["show-column-summaries"] is True

    large_data = {"col" + str(i): range(5) for i in range(41)}
    table_large = ui.table(large_data)
    assert table_large._show_column_summaries is False
    assert table_large._component_args["show-column-summaries"] is False

    # explicitly set to True
    table_true = ui.table(large_data, show_column_summaries=True)
    assert table_true._show_column_summaries is True
    assert table_true._component_args["show-column-summaries"] is True


def test_data_with_rich_components():
    data = {
        "a": [1, 2],
        "b": [ui.text("foo"), ui.slider(start=0, stop=10)],
    }
    table = ui.table(data)
    assert isinstance(table._component_args["data"], str)
    assert isinstance(
        json.loads(table._component_args["data"]),
        list,
    )


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "a": [1, 2],
            "b": [ui.text("foo"), ui.slider(start=0, stop=10)],
        },
        include=["polars", "pandas"],
    ),
)
def test_data_with_rich_components_in_data_frames(df: Any) -> None:
    table = ui.table(df)
    assert isinstance(table._component_args["data"], str)
    assert isinstance(
        json.loads(table._component_args["data"]),
        list,
    )


def test_show_column_summaries_explicit():
    # Test explicit setting of show_column_summaries
    data = {"a": [1, 2, 3], "b": [4, 5, 6]}
    table_true = ui.table(data, show_column_summaries=True)
    assert table_true._show_column_summaries is True
    assert table_true._component_args["show-column-summaries"] is True

    table_false = ui.table(data, show_column_summaries=False)
    assert table_false._show_column_summaries is False
    assert table_false._component_args["show-column-summaries"] is False


def test_show_column_summaries_disabled():
    # Test when show_column_summaries is explicitly set to False
    table = ui.table(
        {"a": [1, 2, 3], "b": [4, 5, 6]}, show_column_summaries=False
    )

    summaries = table._get_column_summaries(EmptyArgs())
    assert summaries.is_disabled is False
    assert summaries.data is None
    assert len(summaries.stats) == 0


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_show_download():
    import pandas as pd

    data = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    table_default = ui.table(data)
    assert table_default._component_args["show-download"] is True

    table_true = ui.table(data, show_download=True)
    assert table_true._component_args["show-download"] is True

    table_false = ui.table(data, show_download=False)
    assert table_false._component_args["show-download"] is False


DOWNLOAD_FORMATS = ["csv", "json", "parquet"]


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_download_as_pandas() -> None:
    """Test downloading table data as different formats with pandas DataFrame."""
    import pandas as pd
    from pandas.testing import assert_frame_equal

    data = pd.DataFrame({"cities": ["Newark", "New York", "Los Angeles"]})
    table = ui.table(data)

    def download_and_convert(
        format_type: str, table_instance: ui.table
    ) -> pd.DataFrame:
        """Helper to download and convert table data to DataFrame."""
        download_str = table_instance._download_as(
            DownloadAsArgs(format=format_type)
        )
        return _convert_data_bytes_to_pandas_df(download_str, format_type)

    # Test base downloads (full data)
    for format_type in DOWNLOAD_FORMATS:
        downloaded_df = download_and_convert(format_type, table)
        assert_frame_equal(data, downloaded_df)

    # Test downloads with search filter
    table._search(SearchTableArgs(query="New", page_size=10, page_number=0))
    for format_type in DOWNLOAD_FORMATS:
        filtered_df = download_and_convert(format_type, table)
        assert len(filtered_df) == 2
        assert all(filtered_df["cities"].isin(["Newark", "New York"]))

    # Test downloads with selection (includes search from before)
    table._convert_value(["1"])
    for format_type in DOWNLOAD_FORMATS:
        selected_df = download_and_convert(format_type, table)
        assert len(selected_df) == 1
        assert selected_df["cities"].iloc[0] == "New York"


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_download_as_polars() -> None:
    """Test downloading table data as different formats with polars DataFrame."""
    import polars as pl
    from polars.testing import assert_frame_equal

    data = pl.DataFrame({"cities": ["Newark", "New York", "Los Angeles"]})
    table = ui.table(data)

    def download_and_convert(
        format_type: str, table_instance: ui.table
    ) -> pl.DataFrame:
        """Helper to download and convert table data to DataFrame."""
        download_str = table_instance._download_as(
            DownloadAsArgs(format=format_type)
        )
        data_bytes = from_data_uri(download_str)[1]

        if format_type == "json":
            return pl.read_json(data_bytes)
        if format_type == "parquet":
            return pl.read_parquet(data_bytes)
        if format_type == "csv":
            return pl.read_csv(data_bytes)
        raise ValueError(f"Unsupported format: {format_type}")

    # Test base downloads (full data)
    for format_type in DOWNLOAD_FORMATS:
        downloaded_df = download_and_convert(format_type, table)
        assert_frame_equal(data, downloaded_df)

    # Test downloads with search filter
    table._search(SearchTableArgs(query="New", page_size=10, page_number=0))
    for format_type in DOWNLOAD_FORMATS:
        filtered_df = download_and_convert(format_type, table)
        assert len(filtered_df) == 2
        assert all(filtered_df["cities"].is_in(["Newark", "New York"]))

    # Test downloads with selection (includes search from before)
    table._convert_value(["1"])
    for format_type in DOWNLOAD_FORMATS:
        selected_df = download_and_convert(format_type, table)
        assert len(selected_df) == 1
        assert selected_df["cities"][0] == "New York"


def test_download_as_for_unsupported_cell_selection() -> None:
    for selection in ["single-cell", "multi-cell"]:
        table = ui.table(data=[], selection=selection)
        with pytest.raises(NotImplementedError):
            table._download_as(DownloadAsArgs(format="csv"))


@pytest.mark.skipif(
    not DependencyManager.pandas.has() or not DependencyManager.polars.has(),
    reason="Pandas or Polars not installed",
)
def test_download_as_for_supported_cell_selection() -> None:
    # Assert that download works for other selection types
    for selection in ["single", "multi", None]:
        table = ui.table(data=[], selection=selection)
        table._download_as(DownloadAsArgs(format="csv"))


@pytest.mark.skipif(
    not DependencyManager.polars.has(),
    reason="Polars not installed",
)
@pytest.mark.parametrize(
    "fmt",
    ["csv", "json", "parquet"],
)
def test_download_as_for_dataframes(fmt: str) -> None:
    import polars as pl

    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    table = ui.table(df)
    table._download_as(DownloadAsArgs(format=fmt))


def test_pagination_behavior() -> None:
    # Test with default page_size=10
    data = {"a": list(range(8))}
    table = ui.table(data)
    assert table._component_args["pagination"] is False
    assert table._component_args["page-size"] == 10
    assert len(json.loads(table._component_args["data"])) == 8

    # Test with custom page_size=5 and data <= page_size
    data = {"a": list(range(5))}
    table = ui.table(data, page_size=5)
    assert table._component_args["pagination"] is False
    assert table._component_args["page-size"] == 5
    assert len(json.loads(table._component_args["data"])) == 5

    # Test with custom page_size=5 and data > page_size
    data = {"a": list(range(8))}
    table = ui.table(data, page_size=5)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 5
    assert len(json.loads(table._component_args["data"])) == 5

    # Test with explicit pagination=True
    data = {"a": list(range(5))}
    table = ui.table(data, pagination=True, page_size=5)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 5
    assert len(json.loads(table._component_args["data"])) == 5


def test_column_clamping():
    # Create data with many columns
    data = {f"col{i}": [1, 2, 3] for i in range(100)}

    # Test default max_columns
    table = ui.table(data)
    assert len(table._manager.get_column_names()) == 100
    assert table._component_args["total-columns"] == 100
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
    assert len(json.loads(table._component_args["data"])[0].keys()) == 50
    assert table._component_args["field-types"] is None

    # Test custom max_columns
    table = ui.table(data, max_columns=20)
    assert len(table._manager.get_column_names()) == 100
    assert table._component_args["total-columns"] == 100
    assert table._component_args["max-columns"] == 20
    assert len(json.loads(table._component_args["data"])[0].keys()) == 20
    assert table._component_args["field-types"] is None

    # Test no clamping
    table = ui.table(data, max_columns=None)
    assert len(table._manager.get_column_names()) == 100
    assert table._component_args["total-columns"] == 100
    assert table._component_args["max-columns"] == "all"
    assert len(json.loads(table._component_args["data"])[0].keys()) == 100
    assert table._component_args["field-types"] is None


def test_column_clamping_with_small_data():
    data = {f"col{i}": [1, 2, 3] for i in range(10)}

    # Should not clamp when under max_columns
    table = ui.table(data)
    assert len(table._manager.get_column_names()) == 10
    assert table._component_args["total-columns"] == 10
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
    assert len(json.loads(table._component_args["data"])[0].keys()) == 10
    assert table._component_args["field-types"] is None


def test_search_clamping_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(100)}
    table = ui.table(data, max_columns=20)

    # Perform a search
    search_args = SearchTableArgs(page_size=10, page_number=0, query="1")
    response = table._search(search_args)

    # Check that the search result is clamped
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 20

    # Check that selection is not clamped
    table._selected_manager = table._searched_manager.select_rows([0])
    selected_data = table._selected_manager.data
    assert len(selected_data) == 100


def test_search_no_clamping_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(100)}
    table = ui.table(data, max_columns=None)

    # Perform a search
    search_args = SearchTableArgs(page_size=10, page_number=0, query="1")
    response = table._search(search_args)

    # Check that the search result is not clamped
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 100

    # Check that selection is not clamped
    table._selected_manager = table._searched_manager.select_rows([0])
    selected_data = table._selected_manager.data
    assert len(selected_data) == 100


def test_search_clamp_max_columns_in_search():
    data = {f"col{i}": [1, 2, 3] for i in range(100)}
    table = ui.table(data, max_columns=20)

    response = table._search(
        SearchTableArgs(page_size=10, page_number=0, query="1", max_columns=1)
    )
    result_data = json.loads(response.data)
    # Only 1 column is shown
    assert len(result_data[0].keys()) == 1

    response = table._search(
        SearchTableArgs(page_size=10, page_number=0, query="1", max_columns=30)
    )
    result_data = json.loads(response.data)
    # Show 30 columns
    assert len(result_data[0].keys()) == 30


def test_column_clamping_with_exact_max_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(50)}
    table = ui.table(data, max_columns=50)

    # Check that the table is not clamped
    assert len(table._manager.get_column_names()) == 50
    assert table._component_args["total-columns"] == 50
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
    assert len(json.loads(table._component_args["data"])[0].keys()) == 50
    assert table._component_args["field-types"] is None


def test_column_clamping_with_more_than_max_columns():
    data = {f"col{i}": [1, 2, 3] for i in range(60)}
    table = ui.table(data, max_columns=50)

    # Check that the table is clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
    assert len(json.loads(table._component_args["data"])[0].keys()) == 50
    assert table._component_args["field-types"] is None


def test_column_clamping_with_no_columns():
    table = ui.table([], max_columns=50)

    # Check that the table handles no columns gracefully
    assert len(table._manager.get_column_names()) == 1
    assert table._component_args["total-columns"] == 1
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
    assert len(json.loads(table._component_args["data"])) == 0
    assert table._component_args["field-types"] is None


def test_column_clamping_with_single_column():
    data = {"col1": [1, 2, 3]}
    table = ui.table(data, max_columns=50)

    # Check that the table handles a single column gracefully
    assert len(table._manager.get_column_names()) == 1
    assert table._component_args["total-columns"] == 1
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
    assert len(json.loads(table._component_args["data"])[0].keys()) == 1
    assert table._component_args["field-types"] is None


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_column_clamping_with_polars():
    import polars as pl

    data = pl.DataFrame({f"col{i}": [1, 2, 3] for i in range(60)})
    table = ui.table(data)

    # Check that the table is clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
    json_data = json.loads(table._component_args["data"])
    headers = json_data[0].keys()
    assert len(headers) == 50  # 50 columns
    # Field types are not clamped
    assert len(table._component_args["field-types"]) == 60

    table = ui.table(data, max_columns=40)

    # Check that the table is clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    assert table._component_args["max-columns"] == 40
    json_data = json.loads(table._component_args["data"])
    headers = json_data[0].keys()
    assert len(headers) == 40  # 40 columns
    # Field types aren't clamped
    assert len(table._component_args["field-types"]) == 60

    table = ui.table(data, max_columns=None)

    # Check that the table is not clamped
    assert len(table._manager.get_column_names()) == 60
    assert table._component_args["total-columns"] == 60
    assert table._component_args["max-columns"] == "all"
    json_data = json.loads(table._component_args["data"])
    headers = json_data[0].keys()

    assert len(headers) == 61  # 60 columns + 1 selection column
    assert len(table._component_args["field-types"]) == 60


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_dataframe_with_int_column_names():
    import warnings

    import pandas as pd

    data = pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=[0, 1, 2])
    with warnings.catch_warnings(record=True) as w:
        table = ui.table(data)
        # Check that warnings were made
        assert len(w) > 0
        assert "DataFrame has integer column names" in str(w[0].message)

    # Check that the table handles integer column names correctly
    assert table._manager.get_column_names() == [0, 1, 2]
    assert table._component_args["total-columns"] == 3
    assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS


def test_cell_initial_style():
    def always_green(_row, _col, _value):
        return {"backgroundColor": "green"}

    table = ui.table([1, 2, 3], style_cell=always_green)
    assert "cell-styles" in table._args.args
    cell_styles = table._args.args["cell-styles"]
    assert len(cell_styles) == 3
    assert "1" in cell_styles
    assert "value" in cell_styles["1"]
    assert "backgroundColor" in cell_styles["1"]["value"]
    assert "green" == cell_styles["1"]["value"]["backgroundColor"]


def test_cell_style_of_next_page():
    def always_green(_row, _col, _value):
        return {"backgroundColor": "green"}

    data = [
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6},
        {"a": 7, "b": 8},
    ]

    table = ui.table(data, page_size=2, style_cell=always_green)
    last_page = table._search(SearchTableArgs(page_size=2, page_number=1))
    cell_styles = last_page.cell_styles
    assert len(cell_styles) == 2
    assert "2" in cell_styles
    assert "a" in cell_styles["2"]
    assert "backgroundColor" in cell_styles["2"]["a"]
    assert "green" in cell_styles["2"]["a"]["backgroundColor"]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_cell_search_df_styles():
    def always_green(_row, _col, _value):
        return {"backgroundColor": "green"}

    import polars as pl

    data = ["apples", "apples", "bananas", "bananas", "carrots", "carrots"]

    table = ui.table(pl.DataFrame(data), style_cell=always_green)
    page = table._search(
        SearchTableArgs(page_size=2, page_number=0, query="carrot")
    )
    assert page.cell_styles == {
        "4": {"column_0": {"backgroundColor": "green"}},
        "5": {"column_0": {"backgroundColor": "green"}},
    }


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
@pytest.mark.xfail(reason="Sorted rows are not supported for styling yet")
def test_cell_search_df_styles_sorted():
    def always_green(_row, _col, _value):
        return {"backgroundColor": "green"}

    import polars as pl

    data = ["apples", "apples", "bananas", "bananas", "carrots", "carrots"]
    table = ui.table(pl.DataFrame(data), style_cell=always_green)
    page = table._search(
        SearchTableArgs(
            page_size=2,
            page_number=0,
            query="",
            sort=SortArgs(by="column_0", descending=True),
        )
    )
    # Sorted rows have reverse order of row_ids
    assert page.cell_styles == {
        "4": {"column_0": {"backgroundColor": "green"}},
        "5": {"column_0": {"backgroundColor": "green"}},
    }


@pytest.mark.skipif(
    not DependencyManager.pandas.has(),
    reason="Pandas not installed, only pandas has multi-col idx",
)
def test_json_multi_col_idx_table() -> None:
    import pandas as pd

    cols = pd.MultiIndex.from_arrays(
        [["basic_amt"] * 2, ["NSW", "QLD"]], names=[None, "Faculty"]
    )
    idx = pd.Index(["All", "Full"])
    data = pd.DataFrame([(1, 1), (0, 1)], index=idx, columns=cols)
    table = ui.table(data)

    json_data = json.loads(table._component_args["data"])
    assert json_data == [
        {
            "": "All",
            INDEX_COLUMN_NAME: 0,
            "basic_amt,NSW": 1,
            "basic_amt,QLD": 1,
        },
        {
            "": "Full",
            INDEX_COLUMN_NAME: 1,
            "basic_amt,NSW": 0,
            "basic_amt,QLD": 1,
        },
    ]

    # If col name looks like a tuple
    df = pd.DataFrame(
        {
            "('basic_amt', 'NSW')": [1],
            "('basic_amt', 'QLD')": [2],
        }
    )
    table = ui.table(df)
    json_data = json.loads(table._component_args["data"])
    assert json_data == [
        {
            INDEX_COLUMN_NAME: 0,
            "('basic_amt', 'NSW')": 1,
            "('basic_amt', 'QLD')": 2,
        }
    ]


# Test for lazy dataframes
@pytest.mark.skipif(
    not DependencyManager.polars.has(),
    reason="Polars not installed",
)
def test_lazy_dataframe() -> None:
    import warnings

    # Capture warnings that might be raised during lazy dataframe operations
    with warnings.catch_warnings(record=True) as recorded_warnings:
        import polars as pl

        num_rows = 21

        # Create a large dataframe that would trigger lazy loading
        large_df = pl.LazyFrame(
            {"col1": range(1000), "col2": [f"value_{i}" for i in range(1000)]}
        )

        # Create table with _internal_lazy=True to simulate lazy loading
        table = ui.table.lazy(large_df, page_size=num_rows)

        # Verify the lazy flag is set
        assert table._lazy is True

        # Check that the banner text indicates lazy loading
        assert (
            table._get_banner_text()
            == f"Previewing only the first {num_rows} rows."
        )

        # Verify the component args are set
        assert table._component_args["lazy"] is True
        assert table._component_args["total-rows"] == "too_many"
        assert table._component_args["page-size"] == num_rows
        assert table._component_args["pagination"] is False
        assert table._component_args["data"] == []
        assert table._component_args["total-columns"] == 0
        assert table._component_args["max-columns"] == DEFAULT_MAX_COLUMNS
        assert table._component_args["field-types"] is None

        # Verify that search response indicates "too_many" for total_rows
        # but returns the preview rows
        search_args = SearchTableArgs(page_size=num_rows, page_number=0)
        search_response = table._search(search_args)
        assert search_response.total_rows == "too_many"

        # Check that only the preview rows are returned
        json_data = json.loads(search_response.data)
        assert len(json_data) == num_rows

    # Warning comes from search
    assert len(recorded_warnings) == 0

    # Select rows
    value = table._convert_value([])
    assert value is None


@pytest.mark.skipif(
    not DependencyManager.polars.has(),
    reason="Polars not installed",
)
def test_lazy_dataframe_with_non_lazy_dataframe():
    import polars as pl

    # Create a Polars LazyFrame
    df = pl.DataFrame(
        {"col1": range(1000), "col2": [f"value_{i}" for i in range(1000)]}
    )
    with pytest.raises(ValueError):
        table = ui.table.lazy(df)


@pytest.mark.skipif(
    DependencyManager.altair.has(),
    reason="If altair is installed, it will trigger to_marimo_arrow()",
)
def test_get_data_url_no_deps() -> None:
    table = ui.table([1, 2, 3])
    response = table._get_data_url({})
    assert response.data_url.startswith("data:application/json;base64,")
    data = json.loads(from_data_uri(response.data_url)[1])
    assert data == [{"value": 1}, {"value": 2}, {"value": 3}]
    assert response.format == "json"


@pytest.mark.skipif(
    not DependencyManager.altair.has(), reason="Altair not installed"
)
def test_get_data_url_with_altair() -> None:
    table = ui.table([1, 2, 3])
    response = table._get_data_url({})
    assert response.data_url.startswith("data:text/csv;base64,")
    assert response.format == "csv"


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_get_data_url_values() -> None:
    table = ui.table([1, 2, 3])
    response = table._get_data_url({})
    initial_data_url = response.data_url
    assert initial_data_url.startswith("data:text/csv;base64,")
    assert response.format == "csv"

    import pandas as pd
    from pandas.testing import assert_frame_equal

    df = _convert_data_bytes_to_pandas_df(response.data_url, response.format)
    expected_df = pd.DataFrame({0: [1, 2, 3]})
    assert_frame_equal(df, expected_df)

    # Test search
    table._search(SearchTableArgs(query="2", page_size=3, page_number=0))
    response = table._get_data_url({})

    df = _convert_data_bytes_to_pandas_df(response.data_url, response.format)
    expected_df = pd.DataFrame({"value": [2]})
    assert_frame_equal(df, expected_df)


def test_default_table_page_size():
    assert get_default_table_page_size() == 10


def test_calculate_top_k_rows():
    table = ui.table({"A": [1, 3, 3, None, None]})
    result = table._calculate_top_k_rows(
        CalculateTopKRowsArgs(column="A", k=10)
    )
    assert result == CalculateTopKRowsResponse(
        data=[(3, 2), (None, 2), (1, 1)],
    )


def _convert_data_bytes_to_pandas_df(
    data: str, data_format: str
) -> pd.DataFrame:
    import io

    import pandas as pd

    data_bytes = from_data_uri(data)[1]

    if data_format == "csv":
        df = pd.read_csv(io.BytesIO(data_bytes))
        # Convert column names to integers if they represent integers
        df.columns = pd.Index(
            [
                int(col) if isinstance(col, str) and col.isdigit() else col
                for col in df.columns
            ]
        )
        return df
    elif data_format == "json":
        return pd.read_json(io.BytesIO(data_bytes))
    elif data_format == "parquet":
        return pd.read_parquet(io.BytesIO(data_bytes))
    else:
        raise ValueError(f"Unsupported data_format: {data_format}")


def test_max_columns_not_provided():
    # Create data with many columns
    data = {f"col{i}": [1, 2, 3] for i in range(100)}
    table = ui.table(data)

    # Test default behavior (should use DEFAULT_MAX_COLUMNS=50)
    search_args = SearchTableArgs(
        page_size=10, page_number=0, max_columns=MAX_COLUMNS_NOT_PROVIDED
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 50

    # Test when not set (uses MAX_COLUMNS_NOT_PROVIDED as the default)
    search_args = SearchTableArgs(page_size=10, page_number=0)
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 50

    # Test with explicit max_columns
    search_args = SearchTableArgs(page_size=10, page_number=0, max_columns=20)
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 20

    # Test with max_columns=None (show all columns)
    search_args = SearchTableArgs(
        page_size=10, page_number=0, max_columns=None
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 100


def test_max_columns_not_provided_with_sort():
    # Create data with many columns
    data = {f"col{i}": [1, 2, 3] for i in range(100)}
    table = ui.table(data)

    # Test sort with default max_columns
    search_args = SearchTableArgs(
        page_size=10,
        page_number=0,
        sort=SortArgs(by="col0", descending=True),
        max_columns=MAX_COLUMNS_NOT_PROVIDED,
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 50

    # Test sort with explicit max_columns
    search_args = SearchTableArgs(
        page_size=10,
        page_number=0,
        sort=SortArgs(by="col0", descending=True),
        max_columns=20,
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 20

    # Test sort with max_columns=None
    search_args = SearchTableArgs(
        page_size=10,
        page_number=0,
        sort=SortArgs(by="col0", descending=True),
        max_columns=None,
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 100


@pytest.mark.skipif(
    not DependencyManager.polars.has(),
    reason="Pandas not installed",
)
def test_max_columns_not_provided_with_filters():
    # Create data with many columns
    import polars as pl

    data = pl.DataFrame({f"col{i}": [1, 2, 3] for i in range(100)})
    table = ui.table(data)

    # Test filters with default max_columns
    search_args = SearchTableArgs(
        page_size=10,
        page_number=0,
        filters=[Condition(column_id="col0", operator="==", value=1)],
        max_columns=MAX_COLUMNS_NOT_PROVIDED,
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 50

    # Test filters with explicit max_columns
    search_args = SearchTableArgs(
        page_size=10,
        page_number=0,
        filters=[Condition(column_id="col0", operator="==", value=1)],
        max_columns=20,
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 20

    # Test filters with max_columns=None
    search_args = SearchTableArgs(
        page_size=10,
        page_number=0,
        filters=[Condition(column_id="col0", operator="==", value=1)],
        max_columns=None,
    )
    response = table._search(search_args)
    result_data = json.loads(response.data)
    assert len(result_data[0].keys()) == 101  # +1 for marimo_row_id
