# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import json
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import narwhals.stable.v1 as nw
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.altair_chart import (
    ChartDataType,
    ChartSelection,
    _filter_dataframe,
    _has_binning,
    _has_geoshape,
    _has_legend_param,
    _has_selection_param,
    _parse_spec,
    _update_vconcat_width,
    altair_chart,
)
from marimo._runtime.runtime import Kernel
from tests._data.mocks import NON_EAGER_LIBS, create_dataframes
from tests.conftest import ExecReqProvider
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame

snapshot = snapshotter(__file__)

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.polars.has()
    and DependencyManager.altair.has()
    # altair produces different output on windows
    and sys.platform != "win32"
    # skip 3.9
    and sys.version_info >= (3, 10)
)

if HAS_DEPS:
    import pandas as pd
else:
    pd = Mock()


def get_len(df: IntoDataFrame) -> int:
    return nw.from_native(df).shape[0]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestAltairChart:
    @staticmethod
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {
                "field": ["value1", "value2", "value3", "value4"],
                "color": ["red", "red", "blue", "blue"],
                "field_2": [1, 2, 3, 4],
                "field_3": [10, 20, 30, 40],
            },
            exclude=NON_EAGER_LIBS,
        ),
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
        assert str(first) == "value2"
        assert str(second) == "value3"

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
        create_dataframes(
            {
                "field": ["value1", "value2", "value3", "value4"],
                "date_column": [
                    datetime.date(2019, 12, 29),
                    datetime.date(2020, 1, 1),
                    datetime.date(2020, 1, 8),
                    datetime.date(2020, 1, 10),
                ],
                "date_column_utc": [
                    datetime.datetime(
                        2019, 12, 29, tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime(
                        2020, 1, 1, tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime(
                        2020, 1, 8, tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime(
                        2020, 1, 10, tzinfo=datetime.timezone.utc
                    ),
                ],
                "datetime_column": [
                    datetime.datetime(2019, 12, 29),
                    datetime.datetime(2020, 1, 1),
                    datetime.datetime(2020, 1, 8),
                    datetime.datetime(2020, 1, 10),
                ],
            },
            exclude=NON_EAGER_LIBS,
        ),
    )
    def test_filter_dataframe_with_dates(
        df: ChartDataType,
    ) -> None:
        assert (
            nw.Datetime
            == nw.from_native(df, pass_through=False).schema["datetime_column"]
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
        assert get_len(_filter_dataframe(df, interval_selection)) == 2
        first, second = _filter_dataframe(df, interval_selection)["field"]
        assert str(first) == "value1"
        assert str(second) == "value2"

        # Date interface from isoformat
        interval_selection = {
            "signal_channel_2": {
                "date_column": [
                    datetime.date(2019, 12, 29).isoformat(),
                    datetime.date(2020, 1, 1).isoformat(),
                ]
            }
        }
        assert get_len(_filter_dataframe(df, interval_selection)) == 2
        first, second = _filter_dataframe(df, interval_selection)["field"]
        assert str(first) == "value1"
        assert str(second) == "value2"

        # Date with utc
        interval_selection = {
            "signal_channel_2": {
                "date_column_utc": [
                    datetime.datetime(
                        2019, 12, 29, tzinfo=datetime.timezone.utc
                    ).timestamp()
                    * 1000,
                    datetime.datetime(
                        2020, 1, 1, tzinfo=datetime.timezone.utc
                    ).timestamp()
                    * 1000,
                ]
            }
        }
        assert get_len(_filter_dataframe(df, interval_selection)) == 2
        first, second = _filter_dataframe(df, interval_selection)["field"]
        assert str(first) == "value1"
        assert str(second) == "value2"

        # Define an interval selection with a datetime column
        interval_selection: ChartSelection = {
            "signal_channel_2": {
                "datetime_column": [
                    # Vega passes back milliseconds since epoch
                    1577000000000,  # Sunday, December 22, 2019 7:33:20 AM
                    1578009600000,  # Friday, January 3, 2020 12:00:00 AM
                ]
            }
        }
        # Filter the DataFrame with the interval selection
        assert len(_filter_dataframe(df, interval_selection)) == 2
        first, second = _filter_dataframe(df, interval_selection)["field"]
        assert str(first) == "value1"
        assert str(second) == "value2"

    @staticmethod
    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {
                "datetime_column_utc": [
                    datetime.datetime.fromtimestamp(
                        10000, datetime.timezone.utc
                    ),
                    datetime.datetime.fromtimestamp(
                        20000, datetime.timezone.utc
                    ),
                ],
                "datetime_column": [
                    datetime.datetime(2019, 12, 29),
                    datetime.datetime(2020, 1, 1),
                ],
            },
            exclude=NON_EAGER_LIBS,
        ),
    )
    def test_filter_dataframe_with_datetimes_as_strings(
        df: IntoDataFrame,
    ) -> None:
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_point": {
                            "datetime_column_utc": [
                                datetime.datetime(
                                    1970,
                                    1,
                                    1,
                                    2,
                                    46,
                                    40,
                                    tzinfo=datetime.timezone.utc,
                                ).isoformat()
                            ],
                            "vlPoint": [1],
                        }
                    },
                )
            )
            == 1
        )
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column_utc": [
                                datetime.datetime(
                                    1970,
                                    1,
                                    1,
                                    1,
                                    46,
                                    40,
                                    tzinfo=datetime.timezone.utc,
                                ).isoformat(),
                                datetime.datetime(
                                    1970,
                                    2,
                                    1,
                                    1,
                                    46,
                                    40,
                                    tzinfo=datetime.timezone.utc,
                                ).isoformat(),
                            ]
                        }
                    },
                )
            )
            == 2
        )
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column_utc": [
                                datetime.datetime(
                                    1970,
                                    1,
                                    1,
                                    1,
                                    0,
                                    40,
                                    tzinfo=datetime.timezone.utc,
                                ).isoformat(),
                                datetime.datetime(
                                    1970,
                                    1,
                                    1,
                                    1,
                                    1,
                                    40,
                                    tzinfo=datetime.timezone.utc,
                                ).isoformat(),
                            ]
                        }
                    },
                )
            )
            == 0
        )

        # Non-UTC datetimes
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column": [
                                datetime.datetime(2019, 12, 29).isoformat(),
                                datetime.datetime(2020, 1, 1).isoformat(),
                            ]
                        }
                    },
                )
            )
            == 2
        )

        # Datetimes with timezone given, get remove
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column": [
                                datetime.datetime(
                                    2019, 12, 29, tzinfo=datetime.timezone.utc
                                ).isoformat(),
                                datetime.datetime(
                                    2020, 1, 1, tzinfo=datetime.timezone.utc
                                ).isoformat(),
                            ]
                        }
                    },
                )
            )
            == 2
        )

    @staticmethod
    @pytest.mark.skipif(
        not HAS_DEPS, reason="optional dependencies not installed"
    )
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {
                "datetime_column_utc": [
                    datetime.datetime.fromtimestamp(
                        10000, datetime.timezone.utc
                    ),
                    datetime.datetime.fromtimestamp(
                        20000, datetime.timezone.utc
                    ),
                ],
                "datetime_column": [
                    datetime.datetime.fromtimestamp(10000),
                    datetime.datetime.fromtimestamp(20000),
                ],
            },
            exclude=NON_EAGER_LIBS,
        ),
    )
    def test_filter_dataframe_with_datetimes_as_numbers(
        df: Any,
    ) -> None:
        def to_milliseconds(seconds: int) -> int:
            return int(seconds * 1000)

        milliseconds_since_epoch = to_milliseconds(10000)
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column_utc": [
                                0,
                                milliseconds_since_epoch - 1,
                            ]
                        }
                    },
                )
            )
            == 0
        )
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column_utc": [
                                milliseconds_since_epoch,
                                milliseconds_since_epoch
                                + to_milliseconds(9000),
                            ]
                        }
                    },
                )
            )
            == 1
        )
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column_utc": [
                                milliseconds_since_epoch,
                                milliseconds_since_epoch
                                + to_milliseconds(20000),
                            ]
                        }
                    },
                )
            )
            == 2
        )

        # non-UTC datetimes
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column": [
                                0,
                                datetime.datetime(2020, 1, 1)
                                .now()
                                .timestamp(),
                            ]
                        }
                    },
                )
            )
            == 2
        )

        # Datetimes with timezone given, get remove
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    {
                        "select_interval": {
                            "datetime_column": [
                                datetime.datetime(
                                    2019, 12, 29, tzinfo=datetime.timezone.utc
                                ).isoformat(),
                                datetime.datetime(
                                    2020, 1, 1, tzinfo=datetime.timezone.utc
                                ).isoformat(),
                            ]
                        }
                    },
                )
            )
            == 0
        )

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
        altair_chart(alt.Chart(df).mark_circle().encode(x="a", y="b"))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_can_add_altair_chart() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    unwrapped = (
        alt.Chart(data).mark_point().encode(x="values:Q").properties(width=200)
    )
    chart1 = altair_chart(unwrapped)
    chart2 = altair_chart(alt.Chart(data).mark_bar().encode(x="values:Q"))

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
    chart1 = altair_chart(unwrapped)
    chart2 = altair_chart(alt.Chart(data).mark_bar().encode(x="values:Q"))

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
    chart1 = altair_chart(unwrapped)
    chart2 = altair_chart(alt.Chart(data).mark_bar().encode(x="values:Q"))

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
    combined2 = altair_chart(alt1) | altair_chart(alt2)

    assert combined1 == combined2._chart


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_dataframe() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    chart = altair_chart(alt.Chart(data).mark_point().encode(x="values:Q"))
    assert chart.dataframe == data


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_dataframe_csv() -> None:
    import altair as alt
    import pandas as pd
    import polars as pl

    data = "https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/stocks.csv"
    chart = altair_chart(alt.Chart(data).mark_point().encode(x="values:Q"))
    assert isinstance(chart.dataframe, (pd.DataFrame, pl.DataFrame))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_dataframe_json() -> None:
    import altair as alt
    import pandas as pd
    import polars as pl

    data = (
        "https://cdn.jsdelivr.net/npm/vega-datasets@v1.29.0/data/barley.json"
    )
    chart = altair_chart(alt.Chart(data).mark_point().encode(x="values:Q"))
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
    # Replace data.url with a placeholder
    spec["data"]["url"] = "_placeholder_"
    snapshot("parse_spec_pandas.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_parse_spec_narwhal() -> None:
    import altair as alt

    data = nw.from_native(pd.DataFrame({"values": [1, 2, 3]}))
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    # Replace data.url with a placeholder
    spec["data"]["url"] = "_placeholder_"
    snapshot("parse_spec_narwhal.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_parse_spec_polars() -> None:
    import altair as alt
    import polars as pl

    data = pl.DataFrame({"values": [1, 2, 3]})
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    # Replace data.url with a placeholder
    spec["data"]["url"] = "_placeholder_"
    snapshot("parse_spec_polars.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(
    not HAS_DEPS or not DependencyManager.duckdb.has(),
    reason="optional dependencies not installed",
)
def test_parse_spec_duckdb() -> None:
    import altair as alt
    import duckdb

    data = duckdb.from_df(pd.DataFrame({"values": [1, 2, 3]}))
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    snapshot("parse_spec_duckdb.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(
    not HAS_DEPS or not DependencyManager.geopandas.has(),
    reason="optional dependencies not installed",
)
def test_parse_spec_geopandas() -> None:
    import altair as alt
    import geopandas as gpd

    # Create a simple GeoDataFrame with 3 countries
    data = gpd.GeoDataFrame(
        {
            "name": ["USA", "China", "India"],
            "pop_est": [331002651, 1439323776, 1380004385],
            "geometry": [
                gpd.points_from_xy([x], [y])[0]
                for x, y in [(-95, 37), (105, 35), (77, 20)]
            ],
        }
    )
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

    # Test nested charts
    nested_layer = alt.layer(
        alt.Chart().mark_bar(), alt.Chart().mark_geoshape()
    )
    assert _has_geoshape(nested_layer) is True

    nested_vconcat = alt.vconcat(
        alt.Chart().mark_bar(), alt.Chart().mark_geoshape()
    )
    assert _has_geoshape(nested_vconcat) is True

    nested_hconcat = alt.hconcat(
        alt.Chart().mark_bar(), alt.Chart().mark_geoshape()
    )
    assert _has_geoshape(nested_hconcat) is True

    all_non_geoshape = alt.layer(
        alt.Chart().mark_bar(), alt.Chart().mark_line()
    )
    assert _has_geoshape(all_non_geoshape) is False


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_no_selection_pandas() -> None:
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"values": [1, 2, 3]})
    chart = altair_chart(alt.Chart(data).mark_point().encode(x="values:Q"))
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
    chart = altair_chart(alt.Chart(data).mark_point().encode(x="values:Q"))
    assert isinstance(chart._value, pl.DataFrame)
    assert len(chart._value) == 0
    selected_value = chart._convert_value({})
    assert isinstance(selected_value, pl.DataFrame)
    selected_value = chart._convert_value(None)
    assert isinstance(selected_value, pl.DataFrame)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"x": [1, 2, 3], "y1": [4, 5, 6], "y2": [7, 8, 9]},
        exclude=["ibis", "lazy-polars"],
    ),
)
def test_layered_chart(df: IntoDataFrame):
    import altair as alt

    base = alt.Chart(df).encode(x="x")
    chart1 = base.mark_line().encode(y="y1")
    chart2 = base.mark_line().encode(y="y2")
    layered = alt.layer(chart1, chart2)

    marimo_chart = altair_chart(layered)
    assert isinstance(marimo_chart._chart, alt.LayerChart)
    assert marimo_chart.dataframe is not None


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({"values": range(100)}, exclude=["lazy-polars"]),
)
def test_chart_with_binning(df: IntoDataFrame):
    import altair as alt

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(x=alt.X("values", bin=True), y="count()")
    )

    marimo_chart = altair_chart(chart)
    assert _has_binning(marimo_chart._spec)
    # Test that selection is disabled for binned charts
    assert marimo_chart._component_args["chart-selection"] is False


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "x": [1, 2, 3, 4],
            "y": [1, 2, 3, 4],
            "category": ["A", "A", "B", "B"],
        },
        exclude=["ibis", "pyarrow", "duckdb", "lazy-polars"],
    ),
)
def test_apply_selection(df: IntoDataFrame):
    import altair as alt

    chart = alt.Chart(df).mark_point().encode(x="x", y="y", color="category")

    marimo_chart = altair_chart(chart)
    marimo_chart._chart_selection = {"signal_channel": {"category": ["A"]}}

    filtered_data = marimo_chart.apply_selection(df)
    assert len(filtered_data) == 2
    assert all(filtered_data["category"] == "A")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_chart_with_url_data():
    import altair as alt
    import polars as pl

    url = "https://vega.github.io/vega-datasets/data/cars.json"
    chart = (
        alt.Chart(url)
        .mark_point()
        .encode(x="Horsepower:Q", y="Miles_per_Gallon:Q")
    )

    marimo_chart = altair_chart(chart)
    assert isinstance(marimo_chart.dataframe, pl.DataFrame)
    assert len(marimo_chart.dataframe) > 0


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"x": [1, 2, 3], "y": [4, 5, 6]}, exclude=["lazy-polars"]
    ),
)
def test_chart_operations(df: IntoDataFrame):
    import altair as alt

    chart1 = alt.Chart(df).mark_point().encode(x="x", y="y")
    chart2 = alt.Chart(df).mark_line().encode(x="x", y="y")

    marimo_chart1 = altair_chart(chart1)
    marimo_chart2 = altair_chart(chart2)

    combined_chart = marimo_chart1 + marimo_chart2
    assert isinstance(combined_chart, altair_chart)
    assert isinstance(combined_chart._chart, alt.LayerChart)

    concat_chart = marimo_chart1 | marimo_chart2
    assert isinstance(concat_chart, altair_chart)
    assert isinstance(concat_chart._chart, alt.HConcatChart)

    facet_chart = marimo_chart1 & marimo_chart2
    assert isinstance(facet_chart, altair_chart)
    assert isinstance(facet_chart._chart, alt.VConcatChart)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_has_selection_param() -> None:
    import altair as alt

    # Chart with no selection param
    chart = alt.Chart().mark_point()
    assert _has_selection_param(chart) is False

    # Chart with selection param but bound to input
    chart = (
        alt.Chart()
        .mark_point()
        .add_params(
            alt.selection_point(
                name="my_selection", encodings=["x"], bind="legend"
            )
        )
    )
    assert _has_selection_param(chart) is False

    # Chart with unbound selection param
    chart = (
        alt.Chart()
        .mark_point()
        .add_params(alt.selection_point(name="my_selection"))
    )
    assert chart.params[0].bind is alt.Undefined
    assert _has_selection_param(chart) is True

    # Layer chart
    rule = alt.Chart().mark_rule(strokeDash=[2, 2]).encode(y=alt.datum(2))
    layered = alt.layer(chart, rule)
    assert _has_selection_param(layered) is True

    # Invalid chart
    chart = None
    assert _has_selection_param(chart) is False


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_has_legend_param() -> None:
    import altair as alt

    # Chart with no legend param
    chart = alt.Chart().mark_point()
    assert _has_legend_param(chart) is False

    # Chart with legend binding
    chart = (
        alt.Chart()
        .mark_point()
        .add_params(alt.selection_point(fields=["color"], bind="legend"))
    )
    assert _has_legend_param(chart) is True

    # Layer chart
    rule = alt.Chart().mark_rule(strokeDash=[2, 2]).encode(y=alt.datum(2))
    layered = alt.layer(chart, rule)
    assert _has_legend_param(layered) is True

    # Chart with non-legend binding
    chart = alt.Chart().mark_point().add_params(alt.selection_point())
    assert _has_legend_param(chart) is False

    layered = alt.layer(chart, rule)
    assert _has_legend_param(layered) is False

    # Invalid chart
    chart = None
    assert _has_legend_param(chart) is False


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_update_vconcat_width() -> None:
    import altair as alt

    # Create a simple chart
    chart1 = alt.Chart(pd.DataFrame({"x": [1, 2], "y": [3, 4]})).mark_point()
    chart2 = alt.Chart(pd.DataFrame({"x": [1, 2], "y": [3, 4]})).mark_line()

    # Create a vconcat chart
    vconcat_chart = alt.vconcat(chart1, chart2)

    # Update the width
    updated_chart = _update_vconcat_width(vconcat_chart)

    # Check that the width is set to container for both subcharts
    assert updated_chart.vconcat[0].width == "container"
    assert updated_chart.vconcat[1].width == "container"

    # Test with nested vconcat
    nested_vconcat = alt.vconcat(
        alt.vconcat(chart1, chart2), alt.vconcat(chart1, chart2)
    )

    updated_nested = _update_vconcat_width(nested_vconcat)

    # Check that all nested charts have container width
    assert updated_nested.vconcat[0].vconcat[0].width == "container"
    assert updated_nested.vconcat[0].vconcat[1].width == "container"
    assert updated_nested.vconcat[1].vconcat[0].width == "container"
    assert updated_nested.vconcat[1].vconcat[1].width == "container"

    # Test with layer chart
    layer_chart = alt.layer(chart1, chart2)
    updated_layer = _update_vconcat_width(layer_chart)
    assert updated_layer.layer[0].width == "container"
    assert updated_layer.layer[1].width == "container"

    # Test with hconcat chart
    hconcat_chart = alt.hconcat(chart1, chart2)
    updated_hconcat = _update_vconcat_width(hconcat_chart)
    assert updated_hconcat.hconcat[0].width == "container"
    assert updated_hconcat.hconcat[1].width == "container"
