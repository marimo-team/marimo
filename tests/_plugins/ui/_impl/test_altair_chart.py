# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import json
import sys
from unittest.mock import Mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl import altair_chart
from marimo._plugins.ui._impl.altair_chart import (
    ChartDataType,
    ChartSelection,
    _filter_dataframe,
    _has_geoshape,
    _parse_spec,
)
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.polars.has()
    and DependencyManager.altair.has()
    # altair produces different output on windows
    and sys.platform != "win32"
)

if HAS_DEPS:
    import pandas as pd
    import polars as pl
else:
    pd = Mock()
    pl = Mock()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestAltairChart:
    @staticmethod
    @pytest.mark.parametrize(
        "df",
        [
            pd.DataFrame(
                {
                    "field": ["value1", "value2", "value3", "value4"],
                    "color": ["red", "red", "blue", "blue"],
                    "field_2": [1, 2, 3, 4],
                    "field_3": [10, 20, 30, 40],
                }
            ),
            pl.DataFrame(
                {
                    "field": ["value1", "value2", "value3", "value4"],
                    "color": ["red", "red", "blue", "blue"],
                    "field_2": [1, 2, 3, 4],
                    "field_3": [10, 20, 30, 40],
                }
            ),
        ],
    )
    def test_filter_dataframe(df: ChartDataType) -> None:
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
        first, second = _filter_dataframe(df, point_selection)["field"]
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
    @pytest.mark.parametrize(
        "df",
        [
            pd.DataFrame(
                {
                    "field": ["value1", "value2", "value3", "value4"],
                    "date_column": pd.to_datetime(
                        [
                            "2019-12-29",
                            "2020-01-01",
                            "2020-01-08",
                            "2020-01-10",
                        ]
                    ),
                }
            ),
            pl.DataFrame(
                {
                    "field": ["value1", "value2", "value3", "value4"],
                    "date_column": [
                        datetime.date(2019, 12, 29),
                        datetime.date(2020, 1, 1),
                        datetime.date(2020, 1, 8),
                        datetime.date(2020, 1, 10),
                    ],
                }
            ),
        ],
    )
    def test_filter_dataframe_with_dates(
        df: ChartDataType,
    ) -> None:  # Check that the date column is a datetime64[ns] column
        assert (
            df["date_column"].dtype == "datetime64[ns]"
            or str(df["date_column"].dtype) == "Date"
        )

        # Define an interval selection
        interval_selection: ChartSelection = {
            "signal_channel_2": {
                "date_column": [
                    # Vega passes back milliseconds since epoch
                    1577000000000,  # Sunday, December 22, 2019 7:33:20 AM
                    1578009600000,  # Friday, January 3, 2020 12:00:00 AM
                ]
            }
        }
        # Filter the DataFrame with the interval selection
        assert len(_filter_dataframe(df, interval_selection)) == 2
        first, second = _filter_dataframe(df, interval_selection)["field"]
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

    @staticmethod
    def test_large_chart() -> None:
        import altair as alt

        # smoke test; this shouldn't error, even though it's larger than
        # altair's default of 5000 data points.
        df = pd.DataFrame({"a": [10000], "b": [10000]})
        altair_chart.altair_chart(
            alt.Chart(df).mark_circle().encode(x="a", y="b")
        )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_can_add_altair_chart() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    unwrapped = (
        alt.Chart(data).mark_point().encode(x="values:Q").properties(width=200)
    )
    chart1 = altair_chart.altair_chart(unwrapped)
    chart2 = altair_chart.altair_chart(
        alt.Chart(data).mark_bar().encode(x="values:Q")
    )

    assert chart1 + chart2 is not None
    assert chart2 + chart1 is not None
    assert chart2 + unwrapped is not None
    with pytest.raises(ValueError):
        assert unwrapped + chart2


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_can_or_altair_chart() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    unwrapped = (
        alt.Chart(data).mark_point().encode(x="values:Q").properties(width=200)
    )
    chart1 = altair_chart.altair_chart(unwrapped)
    chart2 = altair_chart.altair_chart(
        alt.Chart(data).mark_bar().encode(x="values:Q")
    )

    assert chart1 | chart2 is not None
    assert chart2 | chart1 is not None
    assert chart2 | unwrapped is not None
    with pytest.raises(ValueError):
        assert unwrapped + chart2


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_can_and_altair_chart() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    unwrapped = (
        alt.Chart(data).mark_point().encode(x="values:Q").properties(width=200)
    )
    chart1 = altair_chart.altair_chart(unwrapped)
    chart2 = altair_chart.altair_chart(
        alt.Chart(data).mark_bar().encode(x="values:Q")
    )

    assert chart1 & chart2 is not None
    assert chart2 & chart1 is not None
    assert chart2 & unwrapped is not None
    with pytest.raises(ValueError):
        assert unwrapped + chart2


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_does_not_modify_original() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    alt1 = (
        alt.Chart(data).mark_point().encode(x="values:Q").properties(width=200)
    )
    alt2 = alt.Chart(data).mark_bar().encode(x="values:Q").properties()
    combined1 = alt1 | alt2
    combined2 = altair_chart.altair_chart(alt1) | altair_chart.altair_chart(
        alt2
    )

    assert combined1 == combined2._chart


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_dataframe() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    chart = altair_chart.altair_chart(
        alt.Chart(data).mark_point().encode(x="values:Q")
    )
    assert chart.dataframe == data


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_dataframe_csv() -> None:
    import altair as alt
    import pandas as pd
    import polars as pl

    data = "https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/stocks.csv"
    chart = altair_chart.altair_chart(
        alt.Chart(data).mark_point().encode(x="values:Q")
    )
    assert isinstance(chart.dataframe, (pd.DataFrame, pl.DataFrame))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_dataframe_json() -> None:
    import altair as alt
    import pandas as pd
    import polars as pl

    data = (
        "https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/barley.json"
    )
    chart = altair_chart.altair_chart(
        alt.Chart(data).mark_point().encode(x="values:Q")
    )
    assert isinstance(chart.dataframe, (pd.DataFrame, pl.DataFrame))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_parse_spec_url() -> None:
    import altair as alt

    data = "https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/stocks.csv"
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    snapshot("parse_spec_url.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_parse_spec_pandas() -> None:
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"values": [1, 2, 3]})
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    snapshot("parse_spec_pandas.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_parse_spec_narwhal() -> None:
    import altair as alt
    import narwhals.stable.v1 as nw

    data = nw.from_native(pd.DataFrame({"values": [1, 2, 3]}))
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    snapshot("parse_spec_narwhal.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(
    not HAS_DEPS or not DependencyManager.geopandas.has(),
    reason="optional dependencies not installed",
)
def test_parse_spec_geopandas() -> None:
    import altair as alt
    import geopandas as gpd

    data = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    # take top 3 countries with largest population
    data = data.sort_values(by="pop_est", ascending=False).head(3)
    chart = (
        alt.Chart(data)
        .mark_geoshape()
        .encode(shape="geometry", color="pop_est:Q")
    )
    spec = _parse_spec(chart)
    snapshot("parse_spec_geopandas.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_has_geoshape() -> None:
    import altair as alt

    chart_with_geoshape = alt.Chart().mark_geoshape()
    assert _has_geoshape(chart_with_geoshape) is True

    chart_with_geoshape = alt.Chart().mark_geoshape(stroke="black")
    assert _has_geoshape(chart_with_geoshape) is True

    chart_without_geoshape = alt.Chart().mark_bar()
    assert _has_geoshape(chart_without_geoshape) is False


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_no_selection_pandas() -> None:
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"values": [1, 2, 3]})
    chart = altair_chart.altair_chart(
        alt.Chart(data).mark_point().encode(x="values:Q")
    )
    assert isinstance(chart._value, pd.DataFrame)
    assert len(chart._value) == 0
    selected_value = chart._convert_value({})
    assert isinstance(selected_value, pd.DataFrame)
    selected_value = chart._convert_value(None)
    assert isinstance(selected_value, pd.DataFrame)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_no_selection_polars() -> None:
    import altair as alt
    import polars as pl

    data = pl.DataFrame({"values": [1, 2, 3]})
    chart = altair_chart.altair_chart(
        alt.Chart(data).mark_point().encode(x="values:Q")
    )
    assert isinstance(chart._value, pl.DataFrame)
    assert len(chart._value) == 0
    selected_value = chart._convert_value({})
    assert isinstance(selected_value, pl.DataFrame)
    selected_value = chart._convert_value(None)
    assert isinstance(selected_value, pl.DataFrame)
