from __future__ import annotations

import unittest
from datetime import date
from typing import Any, Dict

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager

HAS_DEPS = DependencyManager.pandas.has()


class TestDefaultTable(unittest.TestCase):
    def setUp(self) -> None:
        self.data = [
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
            {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
            {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
            {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
            {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
        ]
        self.manager = DefaultTableManager(self.data)

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = [
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
            {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
        ]
        assert selected_manager.data == expected_data

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data == []

    def test_select_columns(self) -> None:
        columns = ["birth_year"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = [
            {"birth_year": date(1994, 5, 24)},
            {"birth_year": date(1999, 7, 14)},
            {"birth_year": date(1989, 12, 1)},
            {"birth_year": date(1996, 3, 5)},
            {"birth_year": date(2002, 1, 30)},
        ]
        assert selected_manager.data == expected_data

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_limit(self) -> None:
        limited_manager = self.manager.take(1, 0)
        expected_data = [
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        ]
        assert limited_manager.data == expected_data

    def test_take_out_of_bounds(self) -> None:
        # Too large of page
        limited_manager = self.manager.take(10, 0)
        assert limited_manager.data == self.data

        # Too large of page and offset
        limited_manager = self.manager.take(10, 10)
        assert limited_manager.data == []

    def test_sort(self) -> None:
        sorted_data = self.manager.sort_values(by="name", descending=True).data
        expected_data = [
            {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
            {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
            {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
            {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        ]
        assert sorted_data == expected_data
        # reverse sort
        sorted_data = self.manager.sort_values(
            by="name", descending=False
        ).data
        expected_data = [
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
            {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
            {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
            {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
            {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
        ]
        assert sorted_data == expected_data

    def test_sort_single_values(self) -> None:
        manager = DefaultTableManager([1, 3, 2])
        sorted_data = manager.sort_values(by="value", descending=True).data
        expected_data = [{"value": 3}, {"value": 2}, {"value": 1}]
        assert sorted_data == expected_data
        # reverse sort
        sorted_data = manager.sort_values(by="value", descending=False).data
        expected_data = [{"value": 1}, {"value": 2}, {"value": 3}]
        assert sorted_data == expected_data

    def test_mixed_values(self) -> None:
        manager = DefaultTableManager([1, "foo", 2, False])
        sorted_data = manager.sort_values(by="value", descending=True).data
        expected_data = [
            {"value": "foo"},
            {"value": False},
            {"value": 2},
            {"value": 1},
        ]
        assert sorted_data == expected_data
        # reverse sort
        sorted_data = manager.sort_values(by="value", descending=False).data
        expected_data = [
            {"value": 1},
            {"value": 2},
            {"value": False},
            {"value": "foo"},
        ]
        assert sorted_data == expected_data

    def test_search(self) -> None:
        searched_manager = self.manager.search("alice")
        expected_data = [
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        ]
        assert searched_manager.data == expected_data

        searched_manager = self.manager.search("1994")
        expected_data = [
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        ]
        assert searched_manager.data == expected_data

    def test_apply_formatting(self) -> None:
        format_mapping = {
            "name": lambda x: x.upper(),
            "age": lambda x: x + 1,
            "birth_year": lambda x: x.year,
        }
        formatted_manager = self.manager.apply_formatting(format_mapping)
        expected_data = [
            {"name": "ALICE", "age": 31, "birth_year": 1994},
            {"name": "BOB", "age": 26, "birth_year": 1999},
            {"name": "CHARLIE", "age": 36, "birth_year": 1989},
            {"name": "DAVE", "age": 29, "birth_year": 1996},
            {"name": "EVE", "age": 23, "birth_year": 2002},
        ]
        assert formatted_manager == expected_data

    def test_apply_formatting_partial(self) -> None:
        format_mapping = {
            "age": lambda x: x + 1,
        }
        formatted_manager = self.manager.apply_formatting(format_mapping)
        expected_data = [
            {"name": "Alice", "age": 31, "birth_year": date(1994, 5, 24)},
            {"name": "Bob", "age": 26, "birth_year": date(1999, 7, 14)},
            {"name": "Charlie", "age": 36, "birth_year": date(1989, 12, 1)},
            {"name": "Dave", "age": 29, "birth_year": date(1996, 3, 5)},
            {"name": "Eve", "age": 23, "birth_year": date(2002, 1, 30)},
        ]
        assert formatted_manager == expected_data

    def test_apply_formatting_empty(self) -> None:
        format_mapping = {}
        formatted_manager = self.manager.apply_formatting(format_mapping)
        assert formatted_manager == self.data

    def test_apply_formatting_invalid_column(self) -> None:
        format_mapping = {
            "invalid_column": lambda x: x * 2,
        }
        formatted_manager = self.manager.apply_formatting(format_mapping)
        assert formatted_manager == self.data

    def test_apply_formatting_with_nan(self) -> None:
        data_with_nan = self.data.copy()
        data_with_nan[1]["age"] = None
        manager_with_nan = DefaultTableManager(data_with_nan)
        format_mapping = {
            "age": lambda x: x + 1 if x is not None else x,
        }
        formatted_manager = manager_with_nan.apply_formatting(format_mapping)
        expected_data = [
            {"name": "Alice", "age": 31, "birth_year": date(1994, 5, 24)},
            {"name": "Bob", "age": None, "birth_year": date(1999, 7, 14)},
            {"name": "Charlie", "age": 36, "birth_year": date(1989, 12, 1)},
            {"name": "Dave", "age": 29, "birth_year": date(1996, 3, 5)},
            {"name": "Eve", "age": 23, "birth_year": date(2002, 1, 30)},
        ]
        assert formatted_manager == expected_data

    def test_apply_formatting_with_mixed_types(self) -> None:
        data = [
            {"name": "Alice", "value": 1},
            {"name": "Bob", "value": "foo"},
            {"name": "Charlie", "value": 2},
            {"name": "Dave", "value": False},
        ]
        manager = DefaultTableManager(data)
        format_mapping = {
            "value": str,
        }
        formatted_manager = manager.apply_formatting(format_mapping)
        expected_data = [
            {"name": "Alice", "value": "1"},
            {"name": "Bob", "value": "foo"},
            {"name": "Charlie", "value": "2"},
            {"name": "Dave", "value": "False"},
        ]
        assert formatted_manager == expected_data

    def test_apply_formatting_with_complex_data(self) -> None:
        data = [
            {
                "name": "Alice",
                "age": 30,
                "birth_year": date(1994, 5, 24),
                "score": 1.5,
            },
            {
                "name": "Bob",
                "age": 25,
                "birth_year": date(1999, 7, 14),
                "score": 2.5,
            },
            {
                "name": "Charlie",
                "age": 35,
                "birth_year": date(1989, 12, 1),
                "score": 3.5,
            },
        ]
        manager = DefaultTableManager(data)
        format_mapping = {
            "name": lambda x: x.upper(),
            "age": lambda x: x + 1,
            "birth_year": lambda x: x.year,
            "score": lambda x: f"{x:.1f}",
        }
        formatted_manager = manager.apply_formatting(format_mapping)
        expected_data = [
            {"name": "ALICE", "age": 31, "birth_year": 1994, "score": "1.5"},
            {"name": "BOB", "age": 26, "birth_year": 1999, "score": "2.5"},
            {"name": "CHARLIE", "age": 36, "birth_year": 1989, "score": "3.5"},
        ]
        assert formatted_manager == expected_data


class TestColumnarDefaultTable(unittest.TestCase):
    def setUp(self) -> None:
        self.data: Dict[str, Any] = {
            "name": ["Alice", "Bob", "Charlie", "Dave", "Eve"],
            "age": [30, 25, 35, 28, 22],
            "birth_year": [
                date(1994, 5, 24),
                date(1999, 7, 14),
                date(1989, 12, 1),
                date(1996, 3, 5),
                date(2002, 1, 30),
            ],
        }
        self.manager = DefaultTableManager(self.data)

    def test_select_rows(self) -> None:
        indices = [1, 3]
        selected_manager = self.manager.select_rows(indices)
        expected_data = {
            "name": ["Bob", "Dave"],
            "age": [25, 28],
            "birth_year": [
                date(1999, 7, 14),
                date(1996, 3, 5),
            ],
        }
        assert selected_manager.data == expected_data

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data == {
            "name": [],
            "age": [],
            "birth_year": [],
        }

    def test_select_columns(self) -> None:
        columns = ["age"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = {
            "age": [30, 25, 35, 28, 22],
        }
        assert selected_manager.data == expected_data

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        assert self.manager.get_field_types() == {}

    def test_limit(self) -> None:
        limited_manager = self.manager.take(1, 0)
        expected_data = {
            "name": ["Alice"],
            "age": [30],
            "birth_year": [date(1994, 5, 24)],
        }
        assert limited_manager.data == expected_data

    def test_take_out_of_bounds(self) -> None:
        # Too large of page
        limited_manager = self.manager.take(10, 0)
        assert limited_manager.data == self.data

        # Too large of page and offset
        limited_manager = self.manager.take(10, 10)
        assert limited_manager.data["age"] == []
        assert limited_manager.data["name"] == []

    def test_sort(self) -> None:
        sorted_data = self.manager.sort_values(by="name", descending=True).data
        expected_data = [
            {"name": "Eve", "age": 22, "birth_year": date(2002, 1, 30)},
            {"name": "Dave", "age": 28, "birth_year": date(1996, 3, 5)},
            {"name": "Charlie", "age": 35, "birth_year": date(1989, 12, 1)},
            {"name": "Bob", "age": 25, "birth_year": date(1999, 7, 14)},
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        ]
        assert sorted_data == expected_data

    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    def test_get_unique_column_values(self) -> None:
        unique_values = self.manager.get_unique_column_values("age")
        assert unique_values == [22, 25, 28, 30, 35]

    def test_search(self) -> None:
        searched_manager = self.manager.search("alice")
        expected_data = {
            "name": ["Alice"],
            "age": [30],
            "birth_year": [date(1994, 5, 24)],
        }
        assert searched_manager.data == expected_data

        searched_manager = self.manager.search("1994")
        expected_data = {
            "name": ["Alice"],
            "age": [30],
            "birth_year": [date(1994, 5, 24)],
        }
        assert searched_manager.data == expected_data

    def test_apply_formatting(self) -> None:
        format_mapping = {
            "name": lambda x: x.upper(),
            "age": lambda x: x + 1,
            "birth_year": lambda x: x.year,
        }
        formatted_manager = self.manager.apply_formatting(format_mapping)
        expected_data = {
            "name": ["ALICE", "BOB", "CHARLIE", "DAVE", "EVE"],
            "age": [31, 26, 36, 29, 23],
            "birth_year": [1994, 1999, 1989, 1996, 2002],
        }
        assert formatted_manager == expected_data

    def test_apply_formatting_partial(self) -> None:
        format_mapping = {
            "age": lambda x: x + 1,
        }
        formatted_manager = self.manager.apply_formatting(format_mapping)
        expected_data = {
            "name": ["Alice", "Bob", "Charlie", "Dave", "Eve"],
            "age": [31, 26, 36, 29, 23],
            "birth_year": [
                date(1994, 5, 24),
                date(1999, 7, 14),
                date(1989, 12, 1),
                date(1996, 3, 5),
                date(2002, 1, 30),
            ],
        }
        assert formatted_manager == expected_data

    def test_apply_formatting_empty(self) -> None:
        format_mapping = {}
        formatted_manager = self.manager.apply_formatting(format_mapping)
        assert formatted_manager == self.data

    def test_apply_formatting_invalid_column(self) -> None:
        format_mapping = {
            "invalid_column": lambda x: x * 2,
        }
        formatted_manager = self.manager.apply_formatting(format_mapping)
        assert formatted_manager == self.data

    def test_apply_formatting_with_nan(self) -> None:
        data_with_nan = self.data.copy()
        data_with_nan["age"][1] = None
        manager_with_nan = DefaultTableManager(data_with_nan)
        format_mapping = {
            "age": lambda x: x + 1 if x is not None else x,
        }
        formatted_manager = manager_with_nan.apply_formatting(format_mapping)
        expected_data = {
            "name": ["Alice", "Bob", "Charlie", "Dave", "Eve"],
            "age": [31, None, 36, 29, 23],
            "birth_year": [
                date(1994, 5, 24),
                date(1999, 7, 14),
                date(1989, 12, 1),
                date(1996, 3, 5),
                date(2002, 1, 30),
            ],
        }
        assert formatted_manager == expected_data

    def test_apply_formatting_with_mixed_types(self) -> None:
        data = {
            "name": ["Alice", "Bob", "Charlie", "Dave"],
            "value": [1, "foo", 2, False],
        }
        manager = DefaultTableManager(data)
        format_mapping = {
            "value": str,
        }
        formatted_manager = manager.apply_formatting(format_mapping)
        expected_data = {
            "name": ["Alice", "Bob", "Charlie", "Dave"],
            "value": ["1", "foo", "2", "False"],
        }
        assert formatted_manager == expected_data

    def test_apply_formatting_with_complex_data(self) -> None:
        data = {
            "name": ["Alice", "Bob", "Charlie"],
            "age": [30, 25, 35],
            "birth_year": [
                date(1994, 5, 24),
                date(1999, 7, 14),
                date(1989, 12, 1),
            ],
            "score": [1.5, 2.5, 3.5],
        }
        manager = DefaultTableManager(data)
        format_mapping = {
            "name": lambda x: x.upper(),
            "age": lambda x: x + 1,
            "birth_year": lambda x: x.year,
            "score": lambda x: f"{x:.1f}",
        }
        formatted_manager = manager.apply_formatting(format_mapping)
        expected_data = {
            "name": ["ALICE", "BOB", "CHARLIE"],
            "age": [31, 26, 36],
            "birth_year": [1994, 1999, 1989],
            "score": ["1.5", "2.5", "3.5"],
        }
        assert formatted_manager == expected_data

    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    def test_to_csv(self) -> None:
        manager = DefaultTableManager(
            {
                "a": [1, 2],
                "b": [3, 4],
            }
        )
        result = manager.to_csv()
        assert (
            result == b"a,b\n1,3\n2,4\n" or result == b"a,b\r\n1,3\r\n2,4\r\n"
        )

    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    def test_to_json(self) -> None:
        manager = DefaultTableManager(
            {
                "a": [1, 2],
                "b": [3, 4],
            }
        )
        assert manager.to_json() == b'[{"a":1,"b":3},{"a":2,"b":4}]'


class TestDictionaryDefaultTable(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = DefaultTableManager(
            {
                "a": 1,
                "b": 2,
            }
        )

    def test_select_rows(self) -> None:
        selected_manager = self.manager.select_rows([0])
        assert selected_manager.data == [{"key": "a", "value": 1}]

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data == []

    def test_select_columns(self) -> None:
        selected_manager = self.manager.select_columns(["a"])
        assert selected_manager.data == {"a": 1}

    def test_get_rows_headers(self) -> None:
        headers = self.manager.get_row_headers()
        assert headers == []

    def test_limit(self) -> None:
        limited_manager = self.manager.take(1, 0)
        assert limited_manager.data == [{"key": "a", "value": 1}]

    def test_take_out_of_bounds(self) -> None:
        # Too large of page
        limited_manager = self.manager.take(10, 0)
        assert limited_manager.data == [
            {"key": "a", "value": 1},
            {"key": "b", "value": 2},
        ]

        # Too large of page and offset
        limited_manager = self.manager.take(10, 10)
        assert limited_manager.data == []

    def test_sort(self) -> None:
        sorted_manager = self.manager.sort_values(by="value", descending=True)
        expected_data = [{"key": "b", "value": 2}, {"key": "a", "value": 1}]
        assert sorted_manager.data == expected_data

    def test_search(self) -> None:
        searched_manager = self.manager.search("a")
        assert searched_manager.data == [{"key": "a", "value": 1}]

    def test_apply_formatting(self) -> None:
        # Doesn't format when dictionary
        assert self.manager.apply_formatting({"value": lambda x: x + 1}) == {
            "a": 1,
            "b": 2,
        }

        assert DefaultTableManager(self.manager.to_data()).apply_formatting(
            {"value": lambda x: x + 1}
        ) == [
            {"key": "a", "value": 2},
            {"key": "b", "value": 3},
        ]

    def test_apply_formatting_empty(self) -> None:
        formatted_manager = self.manager.apply_formatting({})
        assert formatted_manager == self.manager.data

    def test_apply_formatting_invalid_column(self) -> None:
        formatted_manager = self.manager.apply_formatting(
            {"invalid_column": lambda x: x * 2}
        )
        assert formatted_manager == self.manager.data

    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    def test_to_csv(self) -> None:
        result = self.manager.to_csv()
        assert result == b"key,value\na,1\nb,2\n" or result == (
            b"key,value\r\na,1\r\nb,2\r\n"
        )

    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    def test_to_json(self) -> None:
        assert (
            self.manager.to_json()
            == b'[{"key":"a","value":1},{"key":"b","value":2}]'
        )
