# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from marimo._plugins import ui
from marimo._plugins.ui._impl.table import SearchTableArgs, SortArgs
from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager
from marimo._plugins.ui._impl.utils.dataframe import TableData
from marimo._runtime.runtime import Kernel


@pytest.fixture
def dtm():
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


def test_sort_1d_list_of_strings(dtm: DefaultTableManager):
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


def test_sort_1d_list_of_integers(dtm: DefaultTableManager):
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


def test_sort_list_of_dicts(dtm: DefaultTableManager):
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


def test_sort_dict_of_lists(dtm: DefaultTableManager):
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


def test_sort_dict_of_tuples(dtm: DefaultTableManager):
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


def test_value():
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    data = _normalize_data(data)
    table = ui.table(data)
    assert list(table.value) == []


def test_value_with_selection():
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    data = _normalize_data(data)
    table = ui.table(data)
    assert list(table._convert_value(["0", "2"])) == [
        {"value": "banana"},
        {"value": "cherry"},
    ]


def test_value_with_sorting_then_selection():
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    data = _normalize_data(data)
    table = ui.table(data)

    table.search(SearchTableArgs(sort=SortArgs("value", descending=True)))
    assert list(table._convert_value(["0"])) == [
        {"value": "elderberry"},
    ]

    table.search(SearchTableArgs(sort=SortArgs("value", descending=False)))
    assert list(table._convert_value(["0"])) == [
        {"value": "apple"},
    ]


def test_value_with_search_then_selection():
    data = ["banana", "apple", "cherry", "date", "elderberry"]
    data = _normalize_data(data)
    table = ui.table(data)

    table.search(SearchTableArgs(query="apple"))
    assert list(table._convert_value(["0"])) == [
        {"value": "apple"},
    ]

    table.search(SearchTableArgs(query="banana"))
    assert list(table._convert_value(["0"])) == [
        {"value": "banana"},
    ]

    # empty search
    table.search(SearchTableArgs())
    assert list(table._convert_value(["2"])) == [{"value": "cherry"}]


def test_table_with_too_many_columns_fails():
    data = {str(i): [1] for i in range(101)}
    with pytest.raises(ValueError) as e:
        ui.table(data)

    assert "greater than the maximum allowed columns" in str(e)


def test_table_with_too_many_rows_gets_clamped():
    data = {"a": list(range(20_002))}
    table = ui.table(data)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["has-more"] is True
    assert table._component_args["total-rows"] == 20_002
    assert len(table._component_args["data"]) == 20_000


def test_table_with_too_many_rows_custom_clamp():
    data = {"a": list(range(20_002))}
    table = ui.table(data, _internal_row_limit=30)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["has-more"] is True
    assert table._component_args["total-rows"] == 20_002
    assert len(table._component_args["data"]) == 30


def test_table_with_too_many_rows_custom_clamp_and_total():
    data = {"a": list(range(40))}
    table = ui.table(data, _internal_row_limit=30, _internal_total_rows=300)
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["has-more"] is True
    assert table._component_args["total-rows"] == 300
    assert len(table._component_args["data"]) == 30


def test_table_with_too_many_rows_unknown_total():
    data = {"a": list(range(40))}
    table = ui.table(
        data, _internal_row_limit=30, _internal_total_rows="too_many"
    )
    assert table._component_args["pagination"] is True
    assert table._component_args["page-size"] == 10
    assert table._component_args["has-more"] is True
    assert table._component_args["total-rows"] == "too_many"
    assert len(table._component_args["data"]) == 30
