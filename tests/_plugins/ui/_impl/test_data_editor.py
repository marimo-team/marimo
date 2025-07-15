# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from copy import deepcopy
from typing import Any

import narwhals.stable.v1 as nw
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.data_editor import (
    DataEdits,
    _convert_value,
    apply_edits,
)

data_editor = ui.data_editor

HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()


def assert_data_equals_with_order(actual, expected):
    """Helper function to test both values and column ordering."""
    # Test that the data has the same values
    assert actual == expected

    # Test that the column order is preserved
    if isinstance(actual, list) and actual and isinstance(actual[0], dict):
        # Row-oriented data
        actual_keys = list(actual[0].keys())
        expected_keys = list(expected[0].keys())
        assert actual_keys == expected_keys, (
            f"Column order mismatch: {actual_keys} != {expected_keys}"
        )
    elif isinstance(actual, dict) and actual:
        # Column-oriented data
        actual_keys = list(actual.keys())
        expected_keys = list(expected.keys())
        assert actual_keys == expected_keys, (
            f"Column order mismatch: {actual_keys} != {expected_keys}"
        )


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_initialization():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = data_editor(data=data, label="Test Editor")
    assert editor._data == data
    assert editor._edits == {"edits": []}
    assert editor._component_args["column-sizing-mode"] == "auto"


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_with_column_oriented_data():
    data = {"A": [1, 2, 3], "B": ["a", "b", "c"]}
    editor = data_editor(data=data)
    assert editor._data == data


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_row_oriented():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    edits = {"edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]}
    result = apply_edits(data, edits)
    assert result == [
        {"A": 1, "B": "a"},
        {"A": 2, "B": "x"},
        {"A": 3, "B": "c"},
    ]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_column_oriented():
    data = {"A": [1, 2, 3], "B": ["a", "b", "c"]}
    edits = {"edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]}
    result = apply_edits(data, edits)
    assert result == {"A": [1, 2, 3], "B": ["a", "x", "c"]}


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_new_row():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}]
    edits = {"edits": [{"rowIdx": 2, "columnId": "A", "value": 3}]}
    result = apply_edits(data, edits)
    assert result == [
        {"A": 1, "B": "a"},
        {"A": 2, "B": "b"},
        {"A": 3, "B": None},
    ]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_ints_floats():
    data = [{"A": 1, "B": 2.5}, {"A": 3, "B": 4.7}]
    edits = {
        "edits": [
            {"rowIdx": 0, "columnId": "A", "value": "2"},
            {"rowIdx": 1, "columnId": "B", "value": "5.8"},
        ]
    }
    result = apply_edits(data, edits)
    assert result == [{"A": 2, "B": 2.5}, {"A": 3, "B": 5.8}]

    # With dtypes
    result = apply_edits(
        data, edits, schema=nw.Schema({"A": nw.Float32(), "B": nw.Float32()})
    )
    assert result == [{"A": 2.0, "B": 2.5}, {"A": 3.0, "B": 5.8}]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_booleans():
    data = [{"A": True, "B": False}, {"A": False, "B": True}]
    edits = {
        "edits": [
            {"rowIdx": 0, "columnId": "A", "value": False},
            {"rowIdx": 1, "columnId": "B", "value": False},
        ]
    }
    result = apply_edits(data, edits)
    assert result == [{"A": False, "B": False}, {"A": False, "B": False}]

    # With dtypes
    result = apply_edits(
        data, edits, schema=nw.Schema({"A": nw.Boolean(), "B": nw.Boolean()})
    )
    assert result == [{"A": False, "B": False}, {"A": False, "B": False}]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_dates():
    data = [
        {"date": datetime.date(2023, 1, 1)},
        {"date": datetime.date(2023, 2, 1)},
    ]
    edits = {
        "edits": [
            {"rowIdx": 0, "columnId": "date", "value": "2023-03-15"},
            {"rowIdx": 1, "columnId": "date", "value": "2023-04-20"},
        ]
    }
    result = apply_edits(data, edits)
    assert result == [
        {"date": datetime.date(2023, 3, 15)},
        {"date": datetime.date(2023, 4, 20)},
    ]

    # With dtypes
    result = apply_edits(data, edits, schema=nw.Schema({"date": nw.Date()}))
    assert result == [
        {"date": datetime.date(2023, 3, 15)},
        {"date": datetime.date(2023, 4, 20)},
    ]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_lists():
    data = [{"list": [1, 2, 3]}, {"list": [4, 5, 6]}]
    edits = {
        "edits": [
            {"rowIdx": 0, "columnId": "list", "value": "[1, 2, 3, 4]"},
            {"rowIdx": 1, "columnId": "list", "value": "7,8"},
        ]
    }
    result = apply_edits(data, edits)
    assert result == [{"list": [1, 2, 3, 4]}, {"list": [7, 8]}]

    # With dtypes
    result = apply_edits(
        data, edits, schema=nw.Schema({"list": nw.List(nw.Int64())})
    )
    assert result == [{"list": [1, 2, 3, 4]}, {"list": [7, 8]}]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_various_datatypes():
    data = [
        {
            "int": 1,
            "float": 1.5,
            "str": "hello",
            "bool": True,
            "datetime": datetime.datetime(2023, 1, 1, 12, 0),
            "date": datetime.date(2023, 1, 1),
            "duration": datetime.timedelta(days=1, hours=2, minutes=30),
            "list": [1, 2, 3],
        },
        {
            "int": 2,
            "float": 2.5,
            "str": "world",
            "bool": False,
            "datetime": datetime.datetime(2023, 2, 1, 12, 0),
            "date": datetime.date(2023, 2, 1),
            "duration": datetime.timedelta(days=2, hours=4, minutes=45),
            "list": [4, 5, 6],
        },
    ]
    edits = {
        "edits": [
            {"rowIdx": 0, "columnId": "int", "value": "3"},
            {"rowIdx": 0, "columnId": "float", "value": "3.14"},
            {"rowIdx": 0, "columnId": "str", "value": "updated"},
            {"rowIdx": 0, "columnId": "bool", "value": False},
            {
                "rowIdx": 0,
                "columnId": "datetime",
                "value": "2023-03-15T15:30:00",
            },
            {"rowIdx": 0, "columnId": "date", "value": "2023-03-15"},
            {"rowIdx": 0, "columnId": "duration", "value": "186300000000"},
            {"rowIdx": 0, "columnId": "list", "value": "[7, 8, 9]"},
            {"rowIdx": 1, "columnId": "int", "value": "4"},
            {"rowIdx": 1, "columnId": "float", "value": "4.5"},
            {"rowIdx": 1, "columnId": "str", "value": "updated2"},
            {"rowIdx": 1, "columnId": "bool", "value": True},
            {
                "rowIdx": 1,
                "columnId": "datetime",
                "value": "2023-04-20T10:00:00",
            },
            {"rowIdx": 1, "columnId": "date", "value": "2023-04-20"},
            {"rowIdx": 1, "columnId": "duration", "value": 186300000000},
            {"rowIdx": 1, "columnId": "list", "value": "10,11,12"},
        ]
    }
    result = apply_edits(data, edits)
    assert result == [
        {
            "int": 3,
            "float": 3.14,
            "str": "updated",
            "bool": False,
            "datetime": datetime.datetime(2023, 3, 15, 15, 30),
            "date": datetime.date(2023, 3, 15),
            "duration": datetime.timedelta(days=2, seconds=13500),
            "list": [7, 8, 9],
        },
        {
            "int": 4,
            "float": 4.5,
            "str": "updated2",
            "bool": True,
            "datetime": datetime.datetime(2023, 4, 20, 10, 0),
            "date": datetime.date(2023, 4, 20),
            "duration": datetime.timedelta(days=2, seconds=13500),
            "list": [10, 11, 12],
        },
    ]

    # Test with explicit dtypes
    dtypes = nw.Schema(
        {
            "int": nw.Int64(),
            "float": nw.Float64(),
            "str": nw.String(),
            "bool": nw.Boolean(),
            "datetime": nw.Datetime(),
            "date": nw.Date(),
            "duration": nw.Duration(),
            "list": nw.List(nw.Int64()),
        }
    )
    result_with_dtypes = apply_edits(data, edits, schema=dtypes)
    assert result_with_dtypes == result


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_edge_cases():
    data = [
        {
            "empty_to_value": None,
            "value_to_empty": "hello",
            "zero_length_list": [],
        },
        {
            "empty_to_value": None,
            "value_to_empty": "world",
            "zero_length_list": [],
        },
    ]
    edits = {
        "edits": [
            {"rowIdx": 0, "columnId": "empty_to_value", "value": "filled"},
            {"rowIdx": 1, "columnId": "value_to_empty", "value": ""},
            {"rowIdx": 0, "columnId": "zero_length_list", "value": "[1]"},
            {"rowIdx": 1, "columnId": "zero_length_list", "value": "[]"},
        ]
    }
    result = apply_edits(data, edits)
    assert result == [
        {
            "empty_to_value": "filled",
            "value_to_empty": "hello",
            "zero_length_list": [1],
        },
        {"empty_to_value": None, "value_to_empty": "", "zero_length_list": []},
    ]


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_apply_edits_dataframe():
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
    edits: DataEdits = {
        "edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]
    }
    result = apply_edits(df, edits)
    assert pd.DataFrame({"A": [1, 2, 3], "B": ["a", "x", "c"]}).equals(result)


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_value_property():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = data_editor(data=data)
    assert editor.data == data


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_convert_value():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = data_editor(data=data)
    edits: DataEdits = {
        "edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]
    }
    result = editor._convert_value(edits)
    assert result == [
        {"A": 1, "B": "a"},
        {"A": 2, "B": "x"},
        {"A": 3, "B": "c"},
    ]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_hash():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor1 = data_editor(data=data)
    editor2 = data_editor(data=data)
    assert hash(editor1) != hash(editor2)


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_data_editor_with_pandas_dataframe():
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
    editor = data_editor(data=df)
    assert isinstance(editor.data, pd.DataFrame)
    assert df.equals(editor.data)


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_with_polars_dataframe():
    import polars as pl

    df = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
    editor = data_editor(data=df)
    assert isinstance(editor.data, pl.DataFrame)
    assert df.equals(editor.data)


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_on_change_callback():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    callback_called = False

    def on_change(new_data: Any):
        nonlocal callback_called
        callback_called = True
        assert new_data == [
            {"A": 1, "B": "a"},
            {"A": 2, "B": "x"},
            {"A": 3, "B": "c"},
        ]

    editor = data_editor(data=data, on_change=on_change)
    editor._update({"edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]})
    assert callback_called


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
class TestBulkEditsRowOrientedData:
    """Test bulk edits for row-oriented data."""

    def test_remove_start_row(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"rowIdx": 0, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = [{"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        assert_data_equals_with_order(result, expected)

    def test_remove_middle_row(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"rowIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = [{"A": 1, "B": "a"}, {"A": 3, "B": "c"}]
        assert_data_equals_with_order(result, expected)

    def test_remove_end_row(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"rowIdx": 2, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}]
        assert_data_equals_with_order(result, expected)

    def test_remove_invalid_row(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"rowIdx": 3, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert result == [
            {"A": 1, "B": "a"},
            {"A": 2, "B": "b"},
            {"A": 3, "B": "c"},
        ]

    def test_remove_multiple_rows(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {
            "edits": [
                {"rowIdx": 0, "type": "remove"},
                {"rowIdx": 1, "type": "remove"},
            ]
        }
        result = apply_edits(data, edits)
        expected = [{"A": 2, "B": "b"}]
        assert_data_equals_with_order(result, expected)

    def test_remove_then_edit(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {
            "edits": [
                {"rowIdx": 0, "type": "remove"},
                {"rowIdx": 0, "columnId": "B", "value": "x"},
            ]
        }
        result = apply_edits(data, edits)
        expected = [{"A": 2, "B": "x"}, {"A": 3, "B": "c"}]
        assert_data_equals_with_order(result, expected)

    def test_remove_first_column(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"columnIdx": 0, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = [{"B": "a"}, {"B": "b"}, {"B": "c"}]
        assert_data_equals_with_order(result, expected)

    def test_remove_middle_column(self):
        data = [
            {"A": 1, "B": "a", "C": "x"},
            {"A": 2, "B": "b", "C": "y"},
            {"A": 3, "B": "c", "C": "z"},
        ]
        edits = {"edits": [{"columnIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = [
            {"A": 1, "C": "x"},
            {"A": 2, "C": "y"},
            {"A": 3, "C": "z"},
        ]
        assert_data_equals_with_order(result, expected)

    def test_remove_last_column(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"columnIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = [{"A": 1}, {"A": 2}, {"A": 3}]
        assert_data_equals_with_order(result, expected)

    def test_add_column_start(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"columnIdx": 0, "type": "insert", "newName": "C"}]}
        result = apply_edits(data, edits)
        expected = [
            {"C": None, "A": 1, "B": "a"},
            {"C": None, "A": 2, "B": "b"},
            {"C": None, "A": 3, "B": "c"},
        ]
        assert_data_equals_with_order(result, expected)

    def test_add_column_middle(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"columnIdx": 1, "type": "insert", "newName": "C"}]}
        result = apply_edits(data, edits)
        expected = [
            {"A": 1, "C": None, "B": "a"},
            {"A": 2, "C": None, "B": "b"},
            {"A": 3, "C": None, "B": "c"},
        ]
        assert_data_equals_with_order(result, expected)

    def test_add_column_end(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"columnIdx": 2, "type": "insert", "newName": "C"}]}
        result = apply_edits(data, edits)
        expected = [
            {"A": 1, "B": "a", "C": None},
            {"A": 2, "B": "b", "C": None},
            {"A": 3, "B": "c", "C": None},
        ]
        assert_data_equals_with_order(result, expected)

    def test_add_column_fails(self):
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
        edits = {"edits": [{"columnIdx": 3, "type": "insert"}]}

        with pytest.raises(
            ValueError, match="New column name is required for insert"
        ):
            apply_edits(data, edits)

    def test_rename_column_start(self):
        data = [
            {"A": 1, "B": "a", "C": "x", "D": "w"},
            {"A": 2, "B": "b", "C": "y", "D": "v"},
            {"A": 3, "B": "c", "C": "z", "D": "u"},
        ]
        edits = {"edits": [{"columnIdx": 0, "type": "rename", "newName": "X"}]}
        result = apply_edits(data, edits)
        expected = [
            {"X": 1, "B": "a", "C": "x", "D": "w"},
            {"X": 2, "B": "b", "C": "y", "D": "v"},
            {"X": 3, "B": "c", "C": "z", "D": "u"},
        ]
        assert_data_equals_with_order(result, expected)

    def test_rename_column_middle(self):
        data = [
            {"A": 1, "B": "a", "C": "x", "D": "w"},
            {"A": 2, "B": "b", "C": "y", "D": "v"},
            {"A": 3, "B": "c", "C": "z", "D": "u"},
        ]
        edits = {"edits": [{"columnIdx": 1, "type": "rename", "newName": "X"}]}
        result = apply_edits(data, edits)
        expected = [
            {"A": 1, "X": "a", "C": "x", "D": "w"},
            {"A": 2, "X": "b", "C": "y", "D": "v"},
            {"A": 3, "X": "c", "C": "z", "D": "u"},
        ]
        assert_data_equals_with_order(result, expected)

    def test_rename_column_end(self):
        data = [
            {"A": 1, "B": "a", "C": "x", "D": "w"},
            {"A": 2, "B": "b", "C": "y", "D": "v"},
            {"A": 3, "B": "c", "C": "z", "D": "u"},
        ]
        edits = {"edits": [{"columnIdx": 3, "type": "rename", "newName": "X"}]}
        result = apply_edits(data, edits)
        expected = [
            {"A": 1, "B": "a", "C": "x", "X": "w"},
            {"A": 2, "B": "b", "C": "y", "X": "v"},
            {"A": 3, "B": "c", "C": "z", "X": "u"},
        ]
        assert_data_equals_with_order(result, expected)


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
class TestBulkEditsColumnOrientedData:
    """Test bulk edits for column-oriented data."""

    def test_remove_start_row(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {"edits": [{"rowIdx": 0, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = {"A": [2, 3], "B": ["b", "c"], "C": [5, 6]}
        assert_data_equals_with_order(result, expected)

    def test_remove_middle_row(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {"edits": [{"rowIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = {"A": [1, 3], "B": ["a", "c"], "C": [4, 6]}
        assert_data_equals_with_order(result, expected)

    def test_remove_end_row(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {"edits": [{"rowIdx": 2, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = {"A": [1, 2], "B": ["a", "b"], "C": [4, 5]}
        assert_data_equals_with_order(result, expected)

    def test_remove_invalid_row(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [
                {"rowIdx": 3, "type": "remove"},
                {"rowIdx": -1, "type": "remove"},
            ]
        }
        result = apply_edits(data, edits)
        expected = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        assert_data_equals_with_order(result, expected)

    def test_remove_then_edit(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [
                {"rowIdx": 0, "type": "remove"},
                {"rowIdx": 0, "columnId": "B", "value": "x"},
            ]
        }
        result = apply_edits(data, edits)
        expected = {"A": [2, 3], "B": ["x", "c"], "C": [5, 6]}
        assert_data_equals_with_order(result, expected)

    def test_remove_multiple_rows(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [
                {"rowIdx": 0, "type": "remove"},
                {"rowIdx": 1, "type": "remove"},
            ]
        }
        result = apply_edits(data, edits)
        expected = {"A": [2], "B": ["b"], "C": [5]}
        assert_data_equals_with_order(result, expected)

    def test_rename_column(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [{"columnIdx": 0, "type": "rename", "newName": "D"}]
        }
        result = apply_edits(data, edits)
        expected = {"D": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        assert_data_equals_with_order(result, expected)

    def test_remove_column_middle(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {"edits": [{"columnIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = {"A": [1, 2, 3], "C": [4, 5, 6]}
        assert_data_equals_with_order(result, expected)

    def test_remove_column_end(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {"edits": [{"columnIdx": 2, "type": "remove"}]}
        result = apply_edits(data, edits)
        expected = {"A": [1, 2, 3], "B": ["a", "b", "c"]}
        assert_data_equals_with_order(result, expected)

    def test_insert_column_start(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [{"columnIdx": 0, "type": "insert", "newName": "D"}]
        }
        result = apply_edits(data, edits)
        expected = {
            "D": [None, None, None],
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
            "C": [4, 5, 6],
        }
        assert_data_equals_with_order(result, expected)

    def test_insert_column_middle(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [{"columnIdx": 1, "type": "insert", "newName": "D"}]
        }
        result = apply_edits(deepcopy(data), edits)
        expected = {
            "A": [1, 2, 3],
            "D": [None, None, None],
            "B": ["a", "b", "c"],
            "C": [4, 5, 6],
        }
        assert_data_equals_with_order(result, expected)

        edits = {"edits": [{"columnIdx": 2, "type": "insert", "newName": "D"}]}
        result = apply_edits(deepcopy(data), edits)
        expected = {
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
            "D": [None, None, None],
            "C": [4, 5, 6],
        }
        assert_data_equals_with_order(result, expected)

    def test_insert_column_end(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [{"columnIdx": 3, "type": "insert", "newName": "D"}]
        }
        result = apply_edits(data, edits)
        expected = {
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
            "C": [4, 5, 6],
            "D": [None, None, None],
        }
        assert_data_equals_with_order(result, expected)

    def test_mixed_edits(self):
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        edits: DataEdits = {
            "edits": [
                {"columnIdx": 1, "type": "insert", "newName": "D"},
                {"rowIdx": 0, "type": "remove"},
            ]
        }
        result = apply_edits(data, edits)
        expected = {
            "A": [2, 3],
            "D": [None, None],
            "B": ["b", "c"],
            "C": [5, 6],
        }
        assert_data_equals_with_order(result, expected)


@pytest.mark.skipif(
    not DependencyManager.pandas.has() and not DependencyManager.polars.has(),
    reason="Pandas or Polars not installed",
)
class TestBulkEditsDataframe:
    """Test bulk edits for dataframe data."""

    def test_remove_start_row(self):
        import pandas as pd
        import polars as pl

        data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {"edits": [{"rowIdx": 0, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert pd.DataFrame({"A": [2, 3], "B": ["b", "c"]}).equals(result)

        data = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {"edits": [{"rowIdx": 0, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert pl.DataFrame({"A": [2, 3], "B": ["b", "c"]}).equals(result)

    def test_remove_middle_row(self):
        import pandas as pd
        import polars as pl

        data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {"edits": [{"rowIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert pd.DataFrame({"A": [1, 3], "B": ["a", "c"]}).equals(result)

        data = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {"edits": [{"rowIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert pl.DataFrame({"A": [1, 3], "B": ["a", "c"]}).equals(result)

    def test_remove_end_row(self):
        import pandas as pd
        import polars as pl

        data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {"edits": [{"rowIdx": 2, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert pd.DataFrame({"A": [1, 2], "B": ["a", "b"]}).equals(result)

        data = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {"edits": [{"rowIdx": 2, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert pl.DataFrame({"A": [1, 2], "B": ["a", "b"]}).equals(result)

    def test_insert_column_start(self):
        import pandas as pd

        data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {
            "edits": [{"columnIdx": 0, "type": "insert", "newName": "D"}]
        }
        result = apply_edits(data, edits)
        assert pd.DataFrame(
            {"D": [None, None, None], "A": [1, 2, 3], "B": ["a", "b", "c"]}
        ).equals(result)

    def test_insert_column_middle(self):
        import pandas as pd

        data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {
            "edits": [{"columnIdx": 1, "type": "insert", "newName": "D"}]
        }
        result = apply_edits(data, edits)
        assert pd.DataFrame(
            {"A": [1, 2, 3], "D": [None, None, None], "B": ["a", "b", "c"]}
        ).equals(result)

    def test_insert_column_end(self):
        import pandas as pd

        data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {
            "edits": [{"columnIdx": 2, "type": "insert", "newName": "D"}]
        }
        result = apply_edits(data, edits)
        assert pd.DataFrame(
            {"A": [1, 2, 3], "B": ["a", "b", "c"], "D": [None, None, None]}
        ).equals(result)

    def test_rename_column(self):
        import pandas as pd

        data = pd.DataFrame(
            {"A": [1, 2, 3], "B": ["a", "b", "c"], "C": [4, 5, 6]}
        )
        edits: DataEdits = {
            "edits": [{"columnIdx": 1, "type": "rename", "newName": "D"}]
        }
        result = apply_edits(data, edits)
        assert pd.DataFrame(
            {"A": [1, 2, 3], "D": ["a", "b", "c"], "C": [4, 5, 6]}
        ).equals(result)

    def test_remove_column(self):
        import pandas as pd

        data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        edits: DataEdits = {"edits": [{"columnIdx": 1, "type": "remove"}]}
        result = apply_edits(data, edits)
        assert pd.DataFrame({"A": [1, 2, 3]}).equals(result)


class TestConvertValue:
    """Test the _convert_value function directly."""

    def test_convert_value_with_dtype_datetime(self):
        """Test datetime conversion with dtype."""
        result = _convert_value("2023-03-15T10:30:00", None, nw.Datetime)
        assert result == datetime.datetime(2023, 3, 15, 10, 30, 0)

    def test_convert_value_with_dtype_date(self):
        """Test date conversion with dtype."""
        result = _convert_value("2023-03-15", None, nw.Date)
        assert result == datetime.date(2023, 3, 15)

    def test_convert_value_with_dtype_duration(self):
        """Test duration conversion with dtype."""
        result = _convert_value("186300000000", None, nw.Duration)
        assert result == datetime.timedelta(days=2, seconds=13500)

    def test_convert_value_with_dtype_float32(self):
        """Test Float32 conversion with dtype."""
        result = _convert_value("3.14", None, nw.Float32)
        assert result == 3.14
        assert isinstance(result, float)

    def test_convert_value_with_dtype_float64(self):
        """Test Float64 conversion with dtype."""
        result = _convert_value("3.14", None, nw.Float64)
        assert result == 3.14
        assert isinstance(result, float)

    def test_convert_value_with_dtype_int16(self):
        """Test Int16 conversion with dtype."""
        result = _convert_value("42", None, nw.Int16)
        assert result == 42
        assert isinstance(result, int)

    def test_convert_value_with_dtype_int32(self):
        """Test Int32 conversion with dtype."""
        result = _convert_value("42", None, nw.Int32)
        assert result == 42
        assert isinstance(result, int)

    def test_convert_value_with_dtype_int64(self):
        """Test Int64 conversion with dtype."""
        result = _convert_value("42", None, nw.Int64)
        assert result == 42
        assert isinstance(result, int)

    def test_convert_value_with_dtype_uint16(self):
        """Test UInt16 conversion with dtype."""
        result = _convert_value("42", None, nw.UInt16)
        assert result == 42
        assert isinstance(result, int)

    def test_convert_value_with_dtype_uint32(self):
        """Test UInt32 conversion with dtype."""
        result = _convert_value("42", None, nw.UInt32)
        assert result == 42
        assert isinstance(result, int)

    def test_convert_value_with_dtype_uint64(self):
        """Test UInt64 conversion with dtype."""
        result = _convert_value("42", None, nw.UInt64)
        assert result == 42
        assert isinstance(result, int)

    def test_convert_value_with_dtype_string(self):
        """Test String conversion with dtype."""
        result = _convert_value(42, None, nw.String)
        assert result == "42"
        assert isinstance(result, str)

    def test_convert_value_with_dtype_enum(self):
        """Test Enum conversion with dtype."""
        result = _convert_value(42, None, nw.Enum)
        assert result == "42"
        assert isinstance(result, str)

    def test_convert_value_with_dtype_categorical(self):
        """Test Categorical conversion with dtype."""
        result = _convert_value(42, None, nw.Categorical)
        assert result == "42"
        assert isinstance(result, str)

    def test_convert_value_with_dtype_boolean(self):
        """Test Boolean conversion with dtype."""
        result = _convert_value(True, None, nw.Boolean)
        assert result is True
        assert isinstance(result, bool)

        result = _convert_value(False, None, nw.Boolean)
        assert result is False
        assert isinstance(result, bool)

        result = _convert_value(1, None, nw.Boolean)
        assert result is True

        result = _convert_value(0, None, nw.Boolean)
        assert result is False

    def test_convert_value_with_dtype_list_string_parsable(self):
        """Test List conversion with dtype - string that can be parsed as list."""
        result = _convert_value("[1, 2, 3]", None, nw.List)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_convert_value_with_dtype_list_string_comma_separated(self):
        """Test List conversion with dtype - comma-separated string."""
        result = _convert_value("1,2,3", None, nw.List)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_convert_value_with_dtype_list_already_list(self):
        """Test List conversion with dtype - value is already a list."""
        result = _convert_value([1, 2, 3], None, nw.List)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_convert_value_with_dtype_list_wrap_single_value(self):
        """Test List conversion with dtype - wrap single value in list."""
        result = _convert_value(42, None, nw.List)
        assert result == [42]
        assert isinstance(result, list)

    def test_convert_value_with_dtype_none_value(self):
        """Test conversion with dtype when value is None."""
        result = _convert_value(None, None, nw.String)
        assert result is None

    def test_convert_value_with_unsupported_dtype(self):
        """Test conversion with unsupported dtype."""
        result = _convert_value("test", None, "unsupported_dtype")
        assert result == "test"
        assert isinstance(result, str)

    def test_convert_value_without_dtype_original_none(self):
        """Test conversion without dtype when original_value is None."""
        result = _convert_value("test", None, None)
        assert result == "test"

    def test_convert_value_without_dtype_value_none(self):
        """Test conversion without dtype when value is None."""
        result = _convert_value(None, "original", None)
        assert result is None

    def test_convert_value_without_dtype_int_conversion(self):
        """Test conversion without dtype - int type conversion."""
        result = _convert_value("42", 10, None)
        assert result == 42
        assert isinstance(result, int)

    def test_convert_value_without_dtype_float_conversion(self):
        """Test conversion without dtype - float type conversion."""
        result = _convert_value("3.14", 1.0, None)
        assert result == 3.14
        assert isinstance(result, float)

    def test_convert_value_without_dtype_string_conversion(self):
        """Test conversion without dtype - string type conversion."""
        result = _convert_value(42, "original", None)
        assert result == "42"
        assert isinstance(result, str)

    def test_convert_value_without_dtype_date_conversion(self):
        """Test conversion without dtype - date type conversion."""
        original = datetime.date(2023, 1, 1)
        result = _convert_value("2023-03-15", original, None)
        assert result == datetime.date(2023, 3, 15)
        assert isinstance(result, datetime.date)

    def test_convert_value_without_dtype_datetime_conversion(self):
        """Test conversion without dtype - datetime type conversion."""
        original = datetime.datetime(2023, 1, 1, 12, 0)
        result = _convert_value("2023-03-15T10:30:00", original, None)
        assert result == datetime.datetime(2023, 3, 15, 10, 30, 0)
        assert isinstance(result, datetime.datetime)

    def test_convert_value_without_dtype_timedelta_conversion(self):
        """Test conversion without dtype - timedelta type conversion."""
        original = datetime.timedelta(days=1)
        result = _convert_value("186300000000", original, None)
        assert result == datetime.timedelta(days=2, seconds=13500)
        assert isinstance(result, datetime.timedelta)

    def test_convert_value_without_dtype_list_string_parsable(self):
        """Test conversion without dtype - list from parsable string."""
        original = [1, 2, 3]
        result = _convert_value("[4, 5, 6]", original, None)
        assert result == [4, 5, 6]
        assert isinstance(result, list)

    def test_convert_value_without_dtype_list_string_comma_separated(self):
        """Test conversion without dtype - list from comma-separated string."""
        original = [1, 2, 3]
        result = _convert_value("4,5,6", original, None)
        assert result == [4, 5, 6]
        assert isinstance(result, list)

    def test_convert_value_without_dtype_list_already_list(self):
        """Test conversion without dtype - list when value is already list."""
        original = [1, 2, 3]
        result = _convert_value([4, 5, 6], original, None)
        assert result == [4, 5, 6]
        assert isinstance(result, list)

    def test_convert_value_without_dtype_list_wrap_single_value(self):
        """Test conversion without dtype - wrap single value in list."""
        original = [1, 2, 3]
        result = _convert_value(42, original, None)
        assert result == [42]
        assert isinstance(result, list)

    def test_convert_value_without_dtype_other_types(self):
        """Test conversion without dtype - other types return value as-is."""
        original = {"key": "value"}
        result = _convert_value("new_value", original, None)
        assert result == "new_value"

    def test_convert_value_value_error_handling(self):
        """Test error handling when conversion fails."""
        # This should fail to convert "invalid" to int
        result = _convert_value("invalid", 42, None)
        # Should return original value when conversion fails
        assert result == 42

    def test_convert_value_value_error_handling_with_dtype(self):
        """Test error handling when conversion fails with dtype."""
        # This should fail to convert "invalid" to int
        result = _convert_value("invalid", 42, nw.Int64)
        # Should return original value when conversion fails
        assert result == 42

    def test_convert_value_list_parsing_error(self):
        """Test list parsing error handling."""
        # This should fail to parse as a list
        result = _convert_value("invalid[list", [1, 2, 3], nw.List)
        # Should split by comma as fallback
        assert result == ["invalid[list"]

    def test_convert_value_list_parsing_error_without_dtype(self):
        """Test list parsing error handling without dtype."""
        # This should fail to parse as a list
        result = _convert_value("invalid[list", [1, 2, 3], None)
        # Should split by comma as fallback
        assert result == ["invalid[list"]
