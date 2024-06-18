from __future__ import annotations

import unittest
from datetime import date
from typing import Any, Dict

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager

HAS_DEPS = DependencyManager.has_pandas()


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
        limited_manager = self.manager.limit(1)
        expected_data = [
            {"name": "Alice", "age": 30, "birth_year": date(1994, 5, 24)},
        ]
        assert limited_manager.data == expected_data

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
        limited_manager = self.manager.limit(1)
        expected_data = {
            "name": ["Alice"],
            "age": [30],
            "birth_year": [date(1994, 5, 24)],
        }
        assert limited_manager.data == expected_data

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
