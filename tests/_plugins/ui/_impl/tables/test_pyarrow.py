from __future__ import annotations

import datetime
import unittest

import pytest

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.pyarrow_table import (
    PyArrowTableManagerFactory,
)

HAS_DEPS = DependencyManager.has_pyarrow()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPyArrowTableManagerFactory(unittest.TestCase):
    def setUp(self) -> None:
        import pyarrow as pa

        self.factory = PyArrowTableManagerFactory()
        self.data = pa.table(
            {  # type: ignore
                # Integer
                "A": [1, 2, 3],
                # String
                "B": ["aaa", "b", "c"],
                # Float
                "C": [1.0, 2.0, 3.0],
                # Boolean
                "D": [True, False, True],
                # DateTime
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
            }
        )
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        assert self.factory.package_name() == "pyarrow"

    def test_to_csv(self) -> None:
        assert isinstance(self.manager.to_csv(), bytes)

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data.take(indices)
        assert selected_manager.data == expected_data

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.num_rows == 0

    def test_select_columns(self) -> None:
        columns = ["A"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = self.data.select(columns)
        assert selected_manager.data == expected_data

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import pyarrow as pa

        expected_field_types = {
            "A": ("integer", "int64"),
            "B": ("string", "string"),
            "C": ("number", "double"),
            "D": ("boolean", "bool"),
            "E": ("date", "timestamp[us]"),
        }
        assert self.manager.get_field_types() == expected_field_types

        complex_data = pa.table(
            {
                "A": [1, 2, 3],
                "B": ["aaa", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [None, None, None],
            }  # type: ignore
        )
        expected_field_types = {
            "A": ("integer", "int64"),
            "B": ("string", "string"),
            "C": ("number", "double"),
            "D": ("boolean", "bool"),
            "E": ("unknown", "null"),
        }
        assert (
            self.factory.create()(complex_data).get_field_types()
            == expected_field_types
        )

    def test_limit(self) -> None:
        limited_manager = self.manager.limit(1)
        expected_data = self.data.take([0])
        assert limited_manager.data == expected_data

    def test_limit_more_than_num_rows(self) -> None:
        limited_manager = self.manager.limit(500)
        assert limited_manager.data == self.data

    def test_summary_integer(self) -> None:
        column = "A"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=3,
            min=1,
            max=3,
            mean=2.0,
        )

    def test_summary_string(self) -> None:
        column = "B"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=3,
        )

    def test_summary_number(self) -> None:
        column = "C"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            min=1.0,
            max=3.0,
            mean=2.0,
        )

    def test_summary_boolean(self) -> None:
        column = "D"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            true=2,
            false=1,
        )

    def test_summary_date(self) -> None:
        column = "E"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            min=datetime.datetime(2021, 1, 1, 0, 0),
            max=datetime.datetime(2021, 1, 3, 0, 0),
        )

    def test_sort_values(self) -> None:
        sorted_df = self.manager.sort_values("A", descending=True).data
        expected_df = self.data.sort_by([("A", "descending")])
        assert sorted_df.equals(expected_df)

    def test_get_unique_column_values(self) -> None:
        column = "B"
        unique_values = self.manager.get_unique_column_values(column)
        assert unique_values == ["aaa", "b", "c"]

    def test_search(self) -> None:
        manager = self.factory.create()(self.data)
        assert manager.search("aaa").get_num_rows() == 1
        assert manager.search("true").get_num_rows() == 2
        assert manager.search("baz").get_num_rows() == 0

    def test_apply_formatting(self) -> None:
        import pyarrow as pa

        from marimo._plugins.ui._impl.tables.format import FormatMapping

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
        }
        print(self.manager.data)
        formatted_data = self.manager.apply_formatting(format_mapping)
        expected_data = pa.table(
            {
                "A": [2, 4, 6],
                "B": ["AAA", "B", "C"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
            }
        )
        assert formatted_data.equals(expected_data)

    def test_apply_formatting_with_empty_table(self) -> None:
        import pyarrow as pa

        from marimo._plugins.ui._impl.tables.format import FormatMapping

        empty_data = pa.table({})
        manager = self.factory.create()(empty_data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = manager.apply_formatting(format_mapping)
        assert formatted_data.equals(empty_data)

    def test_apply_formatting_partial(self) -> None:
        import pyarrow as pa

        from marimo._plugins.ui._impl.tables.format import FormatMapping

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = self.manager.apply_formatting(format_mapping)
        expected_data = pa.table(
            {
                "A": [2, 4, 6],
                "B": ["aaa", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
            }
        )
        assert formatted_data.equals(expected_data)

    def test_apply_formatting_empty(self) -> None:
        from marimo._plugins.ui._impl.tables.format import FormatMapping

        format_mapping: FormatMapping = {}

        formatted_data = self.manager.apply_formatting(format_mapping)
        assert formatted_data.equals(self.data)

    def test_apply_formatting_invalid_column(self) -> None:
        from marimo._plugins.ui._impl.tables.format import FormatMapping

        format_mapping: FormatMapping = {
            "Z": lambda x: x * 2,
        }

        formatted_data = self.manager.apply_formatting(format_mapping)
        assert formatted_data.equals(self.data)
