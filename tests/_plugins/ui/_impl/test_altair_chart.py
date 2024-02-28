# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.altair_chart import (
    ChartSelection,
    _filter_dataframe,
)
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

HAS_DEPS = DependencyManager.has_pandas() and DependencyManager.has_altair()

if HAS_DEPS:
    import pandas as pd


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestAltairChart:
    @staticmethod
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

        # Point selected with a no fields
        point_selection = {
            "select_point": {
                "_vgsid_": [2, 3],  # vega is 1-indexed
                "vlPoint": [""],
            },
        }
        # Filter the DataFrame with the point selection
        assert len(_filter_dataframe(df, point_selection)) == 2
        first, second = _filter_dataframe(df, point_selection)["field"].values
        assert first == "value2"
        assert second == "value3"

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

    @staticmethod
    def test_filter_dataframe_with_dates() -> None:
        df = pd.DataFrame(
            {
                "field": ["value1", "value2", "value3", "value4"],
                "color": ["red", "red", "blue", "blue"],
                "field_2": [1, 2, 3, 4],
                "field_3": [10, 20, 30, 40],
                "date": pd.to_datetime(
                    ["2020-01-01", "2020-01-03", "2020-01-05", "2020-01-07"]
                ),
            }
        )

        # Check that the date column is a datetime64[ns] column
        assert df["date"].dtype == "datetime64[ns]"

        # Define an interval selection
        interval_selection: ChartSelection = {
            "signal_channel_2": {
                "date": [
                    # Vega passes back milliseconds since epoch
                    1577000000000,  # Sunday, December 22, 2019 7:33:20 AM
                    1578009600000,  # Friday, January 3, 2020 12:00:00 AM
                ]
            }
        }
        # Filter the DataFrame with the interval selection
        assert len(_filter_dataframe(df, interval_selection)) == 2
        first, second = _filter_dataframe(df, interval_selection)[
            "field"
        ].values
        assert first == "value1"
        assert second == "value2"

    @staticmethod
    async def test_altair_settings_when_set(
        k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get(
                    """
                    import altair as alt
                    # Reset
                    alt.data_transformers.enable('default')
                    initial_options = alt.data_transformers.options
                    alt.data_transformers.disable_max_rows()
                    options_1 = alt.data_transformers.options
                    """
                ),
                exec_req.get(
                    """
                    import pandas as pd
                    df = pd.DataFrame({ 'x': [1], 'y': [2]})
                    c = alt.Chart(df).mark_point().encode(x='x', y='y')
                    c
                    """
                ),
                exec_req.get("options_2 = alt.data_transformers.options"),
            ]
        )
        assert k.globals["initial_options"] == {}
        assert k.globals["options_1"] == {"max_rows": None}
        assert k.globals["options_2"] == {"max_rows": None}
