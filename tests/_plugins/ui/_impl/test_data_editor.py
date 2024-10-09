# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.data_editor import (
    DataEdits,
    apply_edits,
)


def test_data_editor_initialization():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = ui.data_editor(data=data, label="Test Editor")
    assert editor._data == data
    assert editor._edits == {"edits": []}
    assert editor._component_args["pagination"] is True
    assert editor._component_args["page-size"] == 50


def test_data_editor_with_column_oriented_data():
    data = {"A": [1, 2, 3], "B": ["a", "b", "c"]}
    editor = ui.data_editor(data=data)
    assert editor._data == data


def test_data_editor_with_too_many_rows():
    data = [{"A": i} for i in range(1001)]
    with pytest.raises(ValueError) as excinfo:
        ui.data_editor(data=data)
    assert "Data editor supports a maximum of 1000 rows" in str(excinfo.value)


def test_apply_edits_row_oriented():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    edits = {"edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]}
    result = apply_edits(data, edits)
    assert result == [
        {"A": 1, "B": "a"},
        {"A": 2, "B": "x"},
        {"A": 3, "B": "c"},
    ]


def test_apply_edits_column_oriented():
    data = {"A": [1, 2, 3], "B": ["a", "b", "c"]}
    edits = {"edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]}
    result = apply_edits(data, edits)
    assert result == {"A": [1, 2, 3], "B": ["a", "x", "c"]}


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


def test_data_editor_value_property():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = ui.data_editor(data=data)
    assert editor.data == data


def test_data_editor_convert_value():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = ui.data_editor(data=data)
    edits: DataEdits = {
        "edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]
    }
    result = editor._convert_value(edits)
    assert result == [
        {"A": 1, "B": "a"},
        {"A": 2, "B": "x"},
        {"A": 3, "B": "c"},
    ]


def test_data_editor_hash():
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor1 = ui.data_editor(data=data)
    editor2 = ui.data_editor(data=data)
    assert hash(editor1) != hash(editor2)


@pytest.mark.skipif(
    not DependencyManager.pandas.has(), reason="Pandas not installed"
)
def test_data_editor_with_pandas_dataframe():
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
    editor = ui.data_editor(data=df)
    assert isinstance(editor.data, pd.DataFrame)
    assert df.equals(editor.data)


@pytest.mark.skipif(
    not DependencyManager.polars.has(), reason="Polars not installed"
)
def test_data_editor_with_polars_dataframe():
    import polars as pl

    df = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
    editor = ui.data_editor(data=df)
    assert isinstance(editor.data, pl.DataFrame)
    assert df.equals(editor.data)


def test_data_editor_with_custom_pagination():
    data = [{"A": i} for i in range(100)]
    editor = ui.data_editor(data=data, pagination=False, page_size=25)
    assert editor._component_args["pagination"] is False
    assert editor._component_args["page-size"] == 25


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

    editor = ui.data_editor(data=data, on_change=on_change)
    editor._update({"edits": [{"rowIdx": 1, "columnId": "B", "value": "x"}]})
    assert callback_called
