# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import pandas as pd

from marimo._plugins.ui._impl.vega import _filter_dataframe, _to_dataframe


def test_to_data_frame() -> None:
    # Test with URL data source
    vega_spec_url = {
        "data": {
            "url": "https://raw.githubusercontent.com/vega/vega/main/docs/data/cars.json"
        }
    }
    df_url = _to_dataframe(vega_spec_url)
    assert isinstance(df_url, pd.DataFrame)
    assert not df_url.empty

    # Test with inline list data source
    vega_spec_values = {
        "data": {
            "values": [
                {"column1": "value1", "column2": "value2"},
                {"column1": "value3", "column2": "value4"},
            ]
        }
    }
    df_values = _to_dataframe(vega_spec_values)
    assert isinstance(df_values, pd.DataFrame)
    assert not df_values.empty
    assert len(df_values) == 2
    assert list(df_values.columns) == ["column1", "column2"]

    # Test with named data source
    vega_spec_values = {
        "data": {"name": "named_data_source"},
        "datasets": {
            "named_data_source": [
                {"column1": "value1", "column2": "value2"},
                {"column1": "value3", "column2": "value4"},
            ]
        },
    }
    df_values = _to_dataframe(vega_spec_values)
    assert isinstance(df_values, pd.DataFrame)
    assert not df_values.empty
    assert len(df_values) == 2
    assert list(df_values.columns) == ["column1", "column2"]

    # Test with unsupported data source
    vega_spec_unsupported = {"data": {"name": "named_data_source"}}
    try:
        _to_dataframe(vega_spec_unsupported)
        raise AssertionError("Expected ValueError was not raised")
    except ValueError:
        pass


def test_filter_dataframe() -> None:
    df = pd.DataFrame(
        {
            "field": ["value1", "value2", "value3", "value4"],
            "color": ["red", "red", "blue", "blue"],
            "field_2": [1, 2, 3, 4],
            "field_3": [10, 20, 30, 40],
        }
    )

    # Define a point selection
    point_selection = {
        "signal_channel_1": {"vlPoint": True, "field": ["value1", "value2"]}
    }
    # Filter the DataFrame with the point selection
    assert len(_filter_dataframe(df, point_selection)) == 2

    # Define an interval selection
    interval_selection = {"signal_channel_2": {"field_2": [1, 3]}}
    # Filter the DataFrame with the interval selection
    assert len(_filter_dataframe(df, interval_selection)) == 3

    # Define an interval selection with multiple fields
    multi_field_selection = {
        "signal_channel_1": {"field_2": [1, 3], "field_3": [30, 40]}
    }
    # Filter the DataFrame with the multi-field selection
    assert len(_filter_dataframe(df, multi_field_selection)) == 1

    # Define an interval selection with multiple fields
    interval_and_point_selection = {
        "signal_channel_1": {"field_2": [1, 3], "field_3": [20, 40]},
        "signal_channel_2": {"vlPoint": True, "color": ["red"]},
    }
    # Filter the DataFrame with the multi-field selection
    assert len(_filter_dataframe(df, interval_and_point_selection)) == 1
