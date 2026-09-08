# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from copy import deepcopy
from typing import Any, cast
from unittest.mock import Mock

import narwhals.stable.v2 as nw
import pytest

from marimo._data.models import DataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.data_editor import (
    DataEdits,
    _convert_value,
    apply_edits,
)
from tests._data.mocks import create_dataframes

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
    assert editor._component_args["editable-columns"] == "all"
    assert editor._component_args["column-sizing-mode"] == "auto"


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_editable_columns():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = data_editor(data=data, editable_columns=["A"])
    assert editor._component_args["editable-columns"] == ["A"]
    assert editor._data == data
    assert editor._edits == {"edits": []}

    with pytest.raises(ValueError, match="Column C is not in the data"):
        data_editor(data=data, editable_columns=["C"])


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


def test_data_editor_appends_to_scalar_list():
    editor = data_editor([1, 2])
    edits: DataEdits = {
        "edits": [{"rowIdx": 2, "columnId": "value", "value": "3"}]
    }

    assert editor._convert_value(edits) == [1, 2, 3]


def test_data_editor_appends_to_empty_scalar_list():
    editor = data_editor([])
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": "value", "value": "x"}]
    }

    assert editor._convert_value(edits) == ["x"]


@pytest.mark.parametrize(
    ("data", "expected_columns"),
    [([], ["value"]), ({"A": []}, ["A"])],
)
def test_data_editor_exposes_columns_for_empty_data(data, expected_columns):
    editor = data_editor(data)

    assert editor._component_args["column-names"] == expected_columns
    assert editor._component_args["field-types"] is None


def test_data_editor_preserves_numeric_string_column_order():
    editor = data_editor([{"10": "x", "2": "y"}])
    edits: DataEdits = {"edits": [{"columnIdx": 0, "type": "remove"}]}

    assert editor._component_args["column-names"] == ["10", "2"]
    assert editor._convert_value(edits) == [{"2": "y"}]


def test_data_editor_edits_heterogeneous_scalar_list():
    editor = data_editor([1, "a"])
    edits: DataEdits = {
        "edits": [{"rowIdx": 1, "columnId": "value", "value": "b"}]
    }

    assert editor._convert_value(edits) == [1, "b"]


def test_data_editor_appends_to_heterogeneous_scalar_list():
    editor = data_editor([1, "a"])
    edits: DataEdits = {
        "edits": [{"rowIdx": 2, "columnId": "value", "value": "b"}]
    }

    assert editor._convert_value(edits) == [1, "a", "b"]


def test_data_editor_uses_inferred_type_for_null_scalar():
    editor = data_editor([None, 7])
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": "value", "value": "8"}]
    }

    assert editor._convert_value(edits) == [8, 7]


@pytest.mark.parametrize(
    ("data", "column", "expected"),
    [
        ([1, 1.5, 2], "value", [3.5, 1.5, 2]),
        (
            [{"A": 1}, {"A": 1.5}, {"A": 2}],
            "A",
            [{"A": 3.5}, {"A": 1.5}, {"A": 2}],
        ),
        ({"A": [1, 1.5, 2]}, "A", {"A": [3.5, 1.5, 2]}),
    ],
)
def test_apply_edits_preserves_untyped_numeric_precision(
    data: Any, column: str, expected: Any
):
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": column, "value": 3.5}]
    }

    assert apply_edits(data, edits) == expected


def test_data_editor_promotes_scalar_list_when_adding_column():
    editor = data_editor([1, 2])
    edits: DataEdits = {
        "edits": [
            {"columnIdx": 1, "type": "insert", "newName": "B"},
            {"rowIdx": 0, "columnId": "B", "value": "x"},
        ]
    }

    assert editor._convert_value(edits) == [
        {"value": 1, "B": "x"},
        {"value": 2, "B": None},
    ]


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


def test_apply_edits_converts_every_cell_in_appended_row():
    data = [{"A": 1, "B": 2.5}]
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 1, "columnId": "A", "value": "2"},
            {"rowIdx": 1, "columnId": "B", "value": "3.5"},
        ]
    }

    assert apply_edits(data, edits) == [
        {"A": 1, "B": 2.5},
        {"A": 2, "B": 3.5},
    ]


def test_apply_edits_tracks_appended_rows_after_removal():
    data = [{"A": 1}]
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 2, "columnId": "A", "value": "3"},
            {"rowIdx": 0, "type": "remove"},
            {"rowIdx": 1, "columnId": "A", "value": "4"},
        ]
    }

    assert apply_edits(data, edits) == [{"A": None}, {"A": 4}]


def test_apply_edits_appends_to_empty_row_oriented_data():
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 0, "columnId": "A", "value": "x"},
            {"rowIdx": 0, "columnId": "B", "value": 1},
        ]
    }

    assert apply_edits([], edits) == [{"A": "x", "B": 1}]


def test_apply_edits_backfills_columns_discovered_in_later_rows():
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 0, "columnId": "A", "value": "a"},
            {"rowIdx": 1, "columnId": "B", "value": "b"},
        ]
    }

    assert apply_edits([], edits) == [
        {"A": "a", "B": None},
        {"A": None, "B": "b"},
    ]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([], [{"A": 1, "B": None}]),
        ({}, {"A": [1], "B": [None]}),
    ],
)
def test_apply_edits_appends_schema_to_empty_data(data, expected):
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": "A", "value": "1"}]
    }
    schema = nw.Schema({"A": nw.Int64(), "B": nw.String()})

    assert apply_edits(data, edits, schema) == expected


def test_apply_edits_extends_row_oriented_data_to_index():
    edits: DataEdits = {
        "edits": [{"rowIdx": 2, "columnId": "A", "value": "x"}]
    }

    assert apply_edits([], edits) == [
        {"A": None},
        {"A": None},
        {"A": "x"},
    ]


def test_apply_edits_ignores_negative_row_index():
    data = [{"A": 1}]
    edits: DataEdits = {"edits": [{"rowIdx": -1, "columnId": "A", "value": 2}]}

    assert apply_edits(data, edits) == [{"A": 1}]


def test_apply_edits_logs_unknown_edit(monkeypatch: pytest.MonkeyPatch):
    edits = cast(DataEdits, {"edits": [{"type": "unknown"}]})
    log_never = Mock()
    monkeypatch.setattr(
        "marimo._plugins.ui._impl.data_editor.log_never", log_never
    )

    assert apply_edits([], edits) == []
    log_never.assert_called_once_with({"type": "unknown"})


def test_data_editor_replays_add_after_removing_all_rows():
    editor = data_editor([{"A": 1, "B": "a"}])
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 0, "type": "remove"},
            {"rowIdx": 0, "columnId": "A", "value": "2"},
            {"rowIdx": 0, "columnId": "B", "value": "b"},
        ]
    }

    assert editor._convert_value(edits) == [{"A": 2, "B": "b"}]


def test_apply_edits_uses_inferred_column_type_for_conversion():
    data = [{"A": None}, {"A": 7}]
    editor = data_editor(data)
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 0, "type": "remove"},
            {"rowIdx": 0, "columnId": "A", "value": "8"},
        ]
    }

    assert editor._convert_value(edits) == [{"A": 8}]


def test_apply_edits_preserves_row_column_order_with_schema():
    data = [{"B": "x", "A": 1}]
    schema = nw.Schema({"A": nw.Int64(), "B": nw.String()})
    edits: DataEdits = {"edits": [{"columnIdx": 0, "type": "remove"}]}

    assert apply_edits(data, edits, schema) == [{"A": 1}]


@pytest.mark.parametrize(
    ("data", "expected"),
    [([], [{"C": 7}]), ({}, {"C": [7]})],
)
def test_apply_edits_tracks_schema_rename_without_rows(data, expected):
    schema = nw.Schema({"A": nw.Int64()})
    edits: DataEdits = {
        "edits": [
            {"columnIdx": 0, "type": "rename", "newName": "C"},
            {"rowIdx": 0, "columnId": "C", "value": "7"},
        ]
    }

    assert apply_edits(data, edits, schema) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [([], [{"A": "007"}]), ({}, {"A": ["007"]})],
)
def test_apply_edits_drops_schema_for_reused_column_name(data, expected):
    schema = nw.Schema({"A": nw.Int64()})
    edits: DataEdits = {
        "edits": [
            {"columnIdx": 0, "type": "remove"},
            {"columnIdx": 0, "type": "insert", "newName": "A"},
            {"rowIdx": 0, "columnId": "A", "value": "007"},
        ]
    }

    assert apply_edits(data, edits, schema) == expected


@pytest.mark.parametrize(
    ("data_type", "value", "expected"),
    [
        ("number", "3.5", 3.5),
        ("boolean", False, False),
        (
            "datetime",
            "2026-08-26T10:30:00",
            datetime.datetime(2026, 8, 26, 10, 30),
        ),
    ],
)
def test_apply_edits_uses_inserted_column_type(
    data_type: DataType, value: Any, expected: Any
):
    data = [{"A": 1}]
    edits: DataEdits = {
        "edits": [
            {
                "columnIdx": 1,
                "type": "insert",
                "newName": "B",
                "dataType": data_type,
            },
            {"rowIdx": 0, "columnId": "B", "value": value},
        ]
    }

    assert apply_edits(data, edits) == [{"A": 1, "B": expected}]


def test_apply_edits_tracks_column_changes_without_rows():
    data = [{"A": 1, "B": "a"}]
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 0, "type": "remove"},
            {"columnIdx": 1, "type": "insert", "newName": "C"},
            {"columnIdx": 0, "type": "remove"},
            {"columnIdx": 0, "type": "rename", "newName": "D"},
            {"rowIdx": 0, "columnId": "D", "value": "x"},
            {"rowIdx": 0, "columnId": "B", "value": "b"},
        ]
    }

    assert apply_edits(data, edits) == [{"D": "x", "B": "b"}]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            [{"A": 1, "B": "x"}, {"A": 2, "B": "y"}],
            [
                {"C": None, "D": None, "B": None},
                {"C": None, "D": "v", "B": None},
                {"C": 7, "D": None, "B": None},
            ],
        ),
        (
            {"A": [1, 2], "B": ["x", "y"]},
            {
                "C": [None, None, 7],
                "D": [None, "v", None],
                "B": [None, None, None],
            },
        ),
    ],
)
def test_apply_edits_replays_mixed_edits_across_orientations(data, expected):
    edits: DataEdits = {
        "edits": [
            {"rowIdx": 0, "type": "remove"},
            {"rowIdx": 0, "type": "remove"},
            {"columnIdx": 0, "type": "rename", "newName": "C"},
            {"columnIdx": 1, "type": "insert", "newName": "D"},
            {"rowIdx": 2, "columnId": "C", "value": "7"},
            {"rowIdx": 1, "columnId": "D", "value": "v"},
        ]
    }
    schema = nw.Schema({"A": nw.Int64(), "B": nw.String()})

    assert apply_edits(data, edits, schema) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([{"A": 1}, {"A": 2}], [{"C": None}, {"C": "x"}]),
        ({"A": [1, 2]}, {"C": [None, "x"]}),
    ],
)
def test_apply_edits_preserves_rows_without_columns(data, expected):
    edits: DataEdits = {
        "edits": [
            {"columnIdx": 0, "type": "remove"},
            {"columnIdx": 0, "type": "insert", "newName": "C"},
            {"rowIdx": 1, "columnId": "C", "value": "x"},
        ]
    }

    assert apply_edits(data, edits) == expected


def test_apply_edits_extends_every_column_to_new_row():
    data = {"A": [1], "B": ["x"]}
    edits: DataEdits = {
        "edits": [{"rowIdx": 2, "columnId": "A", "value": "3"}]
    }

    assert apply_edits(data, edits) == {
        "A": [1, None, 3],
        "B": ["x", None, None],
    }


def test_apply_edits_preserves_sparse_row_shape():
    data = [{"A": 1}, {"B": 2}]
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": "A", "value": "3"}]
    }

    assert apply_edits(data, edits) == [{"A": 3}, {"B": 2}]


def test_invalid_edit_does_not_normalize_column_lengths():
    data = {"A": [1], "B": []}
    edits: DataEdits = {"edits": [{"columnIdx": 2, "type": "remove"}]}

    with pytest.raises(ValueError, match="Column index 2 is out of bounds"):
        apply_edits(data, edits)

    assert data == {"A": [1], "B": []}


def test_remove_column_preserves_rows_in_ragged_data():
    data = {"A": [1, 2, 3], "B": ["x"]}
    edits: DataEdits = {"edits": [{"columnIdx": 0, "type": "remove"}]}

    assert apply_edits(data, edits) == {"B": ["x", None, None]}


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
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
@pytest.mark.parametrize("value", ["invalid", 3.5])
def test_apply_edits_dataframe_rejects_invalid_typed_value(value):
    import pandas as pd

    data = pd.DataFrame({"A": [1, 2]})
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": "A", "value": value}]
    }

    result = apply_edits(data, edits)

    assert result["A"].tolist() == [1, 2]
    assert result["A"].dtype == data["A"].dtype


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
@pytest.mark.parametrize("dtype", ["int8", "uint8", "float16"])
def test_apply_edits_dataframe_small_width_numeric_preserves_dtype(dtype):
    # Editing a cell must not coerce a narrow numeric column to object/string.
    import pandas as pd

    df = pd.DataFrame({"A": pd.array([1, 2, 3], dtype=dtype)})
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": "A", "value": "5"}]
    }
    result = apply_edits(df.copy(), edits)
    assert pd.api.types.is_numeric_dtype(result["A"])
    assert result["A"].tolist() == [5, 2, 3]


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_apply_edits_dataframe_polars_int8_preserves_dtype():
    import polars as pl

    df = pl.DataFrame({"A": pl.Series([1, 2, 3], dtype=pl.Int8)})
    edits: DataEdits = {
        "edits": [{"rowIdx": 0, "columnId": "A", "value": "5"}]
    }
    result = apply_edits(df.clone(), edits)
    # The column stays integer (not coerced to String) even though the
    # column-oriented round-trip widens the exact type to Int64.
    assert result["A"].dtype.is_integer()
    assert result["A"].to_list() == [5, 2, 3]


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


@pytest.mark.parametrize(
    "df",
    # data_editor uses narwhals with eager_only=True, so it only supports
    # eager dataframe backends (pandas, polars, pyarrow), not lazy/relation
    # types like Ibis and DuckDB.
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]},
        exclude=["lazy-polars", "ibis", "duckdb"],
    ),
)
def test_data_editor_supports_dataframe_backends(df: Any) -> None:
    editor = data_editor(data=df)
    assert type(editor.data) is type(df)
    # An applied edit should round-trip back to the same native type.
    edits: DataEdits = {
        "edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]
    }
    result = editor._convert_value(edits)
    assert type(result) is type(df)


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

    @pytest.mark.parametrize(
        ("dtype", "value", "expected"),
        [
            (nw.Int8, "42", 42),
            (nw.UInt8, "42", 42),
            (nw.Int128, "42", 42),
            (nw.UInt128, "42", 42),
            # Float16 where narwhals exposes it, else any float width.
            (getattr(nw, "Float16", nw.Float32), "3.5", 3.5),
        ],
    )
    def test_convert_value_covers_narrow_numeric_widths(
        self, dtype, value, expected
    ):
        result = _convert_value(value, None, dtype)
        assert result == expected
        assert isinstance(result, type(expected))

    def test_convert_value_unknown_dtype_coerces_from_original(self):
        """An Unknown dtype (e.g. pandas float16) must not stringify.

        narwhals reports some pandas extension dtypes as nw.Unknown; the
        conversion should fall back to the original value's type instead of
        coercing the column to object/string.
        """
        result = _convert_value("5.5", 1.0, nw.Unknown)
        assert result == 5.5
        assert isinstance(result, float)

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
        result = _convert_value("invalid", 42, None)
        assert result == "invalid"

    def test_convert_value_value_error_handling_with_dtype(self):
        """Test error handling when conversion fails with dtype."""
        result = _convert_value("invalid", 42, nw.Int64)
        assert result == 42

    @pytest.mark.parametrize("dtype", [None, nw.Int64])
    def test_convert_value_preserves_large_integers(self, dtype):
        result = _convert_value("9007199254740993", 1, dtype)
        assert result == 9007199254740993

    def test_convert_value_does_not_round_large_untyped_fraction(self):
        result = _convert_value("9007199254740993.1", 1, None)
        assert result == "9007199254740993.1"

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
