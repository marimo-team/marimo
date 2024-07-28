from __future__ import annotations

import pytest

from marimo._plugins.ui._impl.tables.df_protocol_table import (
    DataFrameProtocolTableManager,
)
from marimo._plugins.ui._impl.tables.format import (
    format_column,
    format_row,
    format_value,
)
from marimo._plugins.ui._impl.tables.types import is_dataframe_like


class Fake:
    def __getattr__(self, _):
        return ...


class FakeReturningCallable:
    def __getattr__(self, _):
        return lambda: ...


class Real:
    def __dataframe__(self):
        return ...


def test_is_dataframe_like():
    # Primitives
    assert is_dataframe_like(1) is False
    assert is_dataframe_like("1") is False
    assert is_dataframe_like([]) is False
    assert is_dataframe_like({}) is False
    assert is_dataframe_like(()) is False

    assert is_dataframe_like(Fake()) is False
    assert is_dataframe_like(FakeReturningCallable()) is False
    assert is_dataframe_like(Real()) is True


def test_df_protocol_manager_throws():
    with pytest.raises(ValueError):
        DataFrameProtocolTableManager(Real())


def test_format_value():
    # Test with string formatter
    format_mapping = {"col1": "{:.2f}"}
    assert format_value("col1", 123.456, format_mapping) == "123.46"

    # Test with callable formatter
    format_mapping = {"col1": lambda x: f"${x:.2f}"}
    assert format_value("col1", 123.456, format_mapping) == "$123.46"

    # Test with no formatter
    format_mapping = {}
    assert format_value("col1", 123.456, format_mapping) == 123.456

    # Test with non-existent column
    format_mapping = {"col2": "{:.2f}"}
    assert format_value("col1", 123.456, format_mapping) == 123.456

    # Test with None value
    format_mapping = {"col1": "{:.2f}"}
    assert format_value("col1", None, format_mapping) is None

    # Test with empty string formatter
    format_mapping = {"col1": ""}
    assert format_value("col1", 123.456, format_mapping) == ""

    # Test with complex callable formatter
    format_mapping = {"col1": lambda x: f"{x:.2f} units"}
    assert format_value("col1", 123.456, format_mapping) == "123.46 units"


def test_format_row():
    # Test with string formatter
    format_mapping = {"col1": "{:.2f}", "col2": "{:.1f}"}
    row = {"col1": 123.456, "col2": 78.9}
    expected = {"col1": "123.46", "col2": "78.9"}
    assert format_row(row, format_mapping) == expected

    # Test with callable formatter
    format_mapping = {
        "col1": lambda x: f"${x:.2f}",
        "col2": lambda x: f"{x:.1f}%",
    }
    row = {"col1": 123.456, "col2": 78.9}
    expected = {"col1": "$123.46", "col2": "78.9%"}
    assert format_row(row, format_mapping) == expected

    # Test with mixed formatter
    format_mapping = {"col1": "{:.2f}", "col2": lambda x: f"{x:.1f}%"}
    row = {"col1": 123.456, "col2": 78.9}
    expected = {"col1": "123.46", "col2": "78.9%"}
    assert format_row(row, format_mapping) == expected

    # Test with no formatter
    format_mapping = {}
    row = {"col1": 123.456, "col2": 78.9}
    expected = {"col1": 123.456, "col2": 78.9}
    assert format_row(row, format_mapping) == expected

    # Test with missing column in row
    format_mapping = {"col1": "{:.2f}", "col3": "{:.1f}"}
    row = {"col1": 123.456, "col2": 78.9}
    expected = {"col1": "123.46", "col2": 78.9}
    assert format_row(row, format_mapping) == expected

    # Test with None value in row
    format_mapping = {"col1": "{:.2f}", "col2": "{:.1f}"}
    row = {"col1": None, "col2": 78.9}
    expected = {"col1": None, "col2": "78.9"}
    assert format_row(row, format_mapping) == expected


def test_format_column():
    # Test with string formatter
    format_mapping = {"col1": "{:.2f}"}
    values = [123.456, 78.9]
    expected = ["123.46", "78.90"]
    assert format_column("col1", values, format_mapping) == expected

    # Test with callable formatter
    format_mapping = {"col1": lambda x: f"${x:.2f}"}
    values = [123.456, 78.9]
    expected = ["$123.46", "$78.90"]
    assert format_column("col1", values, format_mapping) == expected

    # Test with no formatter
    format_mapping = {}
    values = [123.456, 78.9]
    expected = [123.456, 78.9]
    assert format_column("col1", values, format_mapping) == expected

    # Test with non-existent column
    format_mapping = {"col2": "{:.2f}"}
    values = [123.456, 78.9]
    expected = [123.456, 78.9]
    assert format_column("col1", values, format_mapping) == expected

    # Test with None value in column
    format_mapping = {"col1": "{:.2f}"}
    values = [123.456, None]
    expected = ["123.46", None]
    assert format_column("col1", values, format_mapping) == expected

    # Test with empty list
    format_mapping = {"col1": "{:.2f}"}
    values = []
    expected = []
    assert format_column("col1", values, format_mapping) == expected
