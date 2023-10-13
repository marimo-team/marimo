# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import pandas as pd

from marimo._plugins.ui._impl.altair_chart import (
    ChartSelection,
    _filter_dataframe,
)


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
    point_selection: ChartSelection = {
        "signal_channel_1": {"vlPoint": [1], "field": ["value1", "value2"]}
    }
    # Filter the DataFrame with the point selection
    assert len(_filter_dataframe(df, point_selection)) == 2

    # Define an interval selection
    interval_selection: ChartSelection = {
        "signal_channel_2": {"field_2": [1, 3]}
    }
    # Filter the DataFrame with the interval selection
    assert len(_filter_dataframe(df, interval_selection)) == 3

    # Define an interval selection with multiple fields
    multi_field_selection: ChartSelection = {
        "signal_channel_1": {"field_2": [1, 3], "field_3": [30, 40]}
    }
    # Filter the DataFrame with the multi-field selection
    assert len(_filter_dataframe(df, multi_field_selection)) == 1

    # Define an interval selection with multiple fields
    interval_and_point_selection: ChartSelection = {
        "signal_channel_1": {"field_2": [1, 3], "field_3": [20, 40]},
        "signal_channel_2": {"vlPoint": [1], "color": ["red"]},
    }
    # Filter the DataFrame with the multi-field selection
    assert len(_filter_dataframe(df, interval_and_point_selection)) == 1
