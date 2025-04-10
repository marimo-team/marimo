# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from typing import Any

import narwhals.stable.v1 as nw
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.data_editor import (
    DataEdits,
    apply_edits,
)

data_editor = ui.data_editor

HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_initialization():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = data_editor(data=data, label="Test Editor")
    assert editor._data == data
    assert editor._edits == {"edits": []}
    assert editor._component_args["pagination"] is True
    assert editor._component_args["page-size"] == 50
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
def test_data_editor_with_too_many_rows():
    data = [{"A": i} for i in range(1001)]
    with pytest.raises(ValueError) as excinfo:
        data_editor(data=data)
    assert "Data editor supports a maximum of 1000 rows" in str(excinfo.value)


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
            "datetime": datetime.datetime(2023, 1, 1, 12, 0),
            "date": datetime.date(2023, 3, 15),
            "duration": datetime.timedelta(days=2, seconds=13500),
            "list": [7, 8, 9],
        },
        {
            "int": 4,
            "float": 4.5,
            "str": "updated2",
            "bool": True,
            "datetime": datetime.datetime(2023, 1, 1, 12, 0),
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
def test_data_editor_with_custom_pagination():
    data = [{"A": i} for i in range(100)]
    editor = data_editor(data=data, pagination=False, page_size=25)
    assert editor._component_args["pagination"] is False
    assert editor._component_args["page-size"] == 25


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_with_too_large_pagesize():
    data = [{"A": i} for i in range(300)]
    with pytest.raises(ValueError):
        _ = data_editor(data=data, page_size=201)


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
