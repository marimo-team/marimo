import unittest
from typing import Any, Dict

from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager


class TestDefaultTable(unittest.TestCase):
    def setUp(self) -> None:
        self.data = [
            {"A": 1, "B": "a"},
            {"A": 2, "B": "b"},
            {"A": 3, "B": "c"},
        ]
        self.manager = DefaultTableManager(self.data)

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = [
            {"A": 1, "B": "a"},
            {"A": 3, "B": "c"},
        ]
        assert selected_manager.data == expected_data

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data == []

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")


class TestColumnarDefaultTable(unittest.TestCase):
    def setUp(self) -> None:
        self.data: Dict[str, Any] = {
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
        }
        self.manager = DefaultTableManager(self.data)

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = {
            "A": [1, 3],
            "B": ["a", "c"],
        }
        assert selected_manager.data == expected_data

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data == {"A": [], "B": []}

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")
