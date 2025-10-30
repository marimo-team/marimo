# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import io
import json
import sys
from contextlib import redirect_stderr
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import narwhals.stable.v2 as nw
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.altair_chart import (
    ChartDataType,
    ChartSelection,
    _filter_dataframe,
    _get_binned_fields,
    _has_binning,
    _has_geoshape,
    _has_legend_param,
    _has_no_nested_hconcat,
    _has_selection_param,
    _parse_spec,
    _update_vconcat_width,
    altair_chart,
)
from marimo._runtime.runtime import Kernel
from marimo._utils.narwhals_utils import is_narwhals_lazyframe
from tests._data.mocks import create_dataframes
from tests.conftest import ExecReqProvider
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame, IntoLazyFrame

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


def get_len(df: IntoDataFrame | IntoLazyFrame) -> int:
    df = nw.from_native(df, pass_through=False)
    if is_narwhals_lazyframe(df):
        return df.collect().shape[0]
    return df.shape[0]


def maybe_collect(df: IntoDataFrame | IntoLazyFrame) -> nw.DataFrame[Any]:
    nw_df = nw.from_native(df, pass_through=False)
    if is_narwhals_lazyframe(nw_df):
        return nw_df.collect()
    return nw_df


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
        ),
    )
    def test_filter_dataframe(df: ChartDataType) -> None:
        # Define a point selection
        point_selection: ChartSelection = {
            "signal_channel_1": {"vlPoint": [1], "field": ["value1", "value2"]}
        }
        # Filter the DataFrame with the point selection
        assert get_len(_filter_dataframe(df, selection=point_selection)) == 2

        # Point selected with a no fields
        point_selection = {
            "select_point": {
                "_vgsid_": [2, 3],  # vega is 1-indexed
                "vlPoint": [""],
            },
        }
        # Filter the DataFrame with the point selection
        filtered_df = _filter_dataframe(df, selection=point_selection)
        assert get_len(filtered_df) == 2
        first, second = maybe_collect(filtered_df)["field"]
        assert str(first) == "value2"
        assert str(second) == "value3"

        # Define an interval selection
        interval_selection: ChartSelection = {
            "signal_channel_2": {"field_2": [1, 3]}
        }
        # Filter the DataFrame with the interval selection
        filtered_df = _filter_dataframe(df, selection=interval_selection)
        assert get_len(filtered_df) == 3

        # Define an interval selection with multiple fields
        multi_field_selection: ChartSelection = {
            "signal_channel_1": {"field_2": [1, 3], "field_3": [30, 40]}
        }
        # Filter the DataFrame with the multi-field selection
        filtered_df = _filter_dataframe(df, selection=multi_field_selection)
        assert get_len(filtered_df) == 1

        # Define an interval selection with multiple fields
        interval_and_point_selection: ChartSelection = {
            "signal_channel_1": {"field_2": [1, 3], "field_3": [20, 40]},
            "signal_channel_2": {"vlPoint": [1], "color": ["red"]},
        }
        # Filter the DataFrame with the multi-field selection
        filtered_df = _filter_dataframe(
            df, selection=interval_and_point_selection
        )
        assert get_len(filtered_df) == 1

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
        filtered_df = _filter_dataframe(df, selection=interval_selection)
        assert get_len(filtered_df) == 2
        first, second = maybe_collect(filtered_df)["field"]
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
        filtered_df = _filter_dataframe(df, selection=interval_selection)
        assert get_len(filtered_df) == 2
        first, second = maybe_collect(filtered_df)["field"]
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
        filtered_df = _filter_dataframe(df, selection=interval_selection)
        assert get_len(filtered_df) == 2
        first, second = maybe_collect(filtered_df)["field"]
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
        filtered_df = _filter_dataframe(df, selection=interval_selection)
        assert get_len(filtered_df) == 2
        first, second = maybe_collect(filtered_df)["field"]
        assert str(first) == "value1"
        assert str(second) == "value2"

    @staticmethod
    @pytest.mark.parametrize(
        "df",
        create_dataframes(
            {
                "field": ["value1", "value2", "value3"],
                "date_column": [
                    datetime.date(2020, 1, 1),
                    datetime.date(2020, 1, 8),
                    datetime.date(2020, 1, 10),
                ],
            },
        ),
    )
    def test_filter_dataframe_with_dates_graceful_error(
        df: ChartDataType,
    ) -> None:
        """Test that invalid date comparisons are handled gracefully."""
        # Try with invalid date strings that can't be parsed
        interval_selection: ChartSelection = {
            "signal_channel": {"date_column": ["invalid_date", "also_invalid"]}
        }
        # Should not raise an error, but skip the filter condition
        # and return the original dataframe
        filtered_df = _filter_dataframe(df, selection=interval_selection)
        # Since the filter failed gracefully, we should get the full dataframe
        assert get_len(filtered_df) == 3

        # Try with mixed valid/invalid values - the coercion should handle it
        interval_selection = {
            "signal_channel": {
                "date_column": [
                    datetime.date(2020, 1, 1).isoformat(),
                    "not_a_valid_date",
                ]
            }
        }
        # The filter should be skipped due to type error
        filtered_df = _filter_dataframe(df, selection=interval_selection)
        assert get_len(filtered_df) == 3

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
        ),
    )
    def test_filter_dataframe_with_datetimes_as_strings(
        df: IntoDataFrame,
    ) -> None:
        assert (
            get_len(
                _filter_dataframe(
                    df,
                    selection={
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
                    selection={
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
                    selection={
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
                    selection={
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
                    selection={
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
                    selection={
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
                    selection={
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
                    selection={
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
                    selection={
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
                    selection={
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

    assert combined1.to_dict() == combined2._chart.to_dict()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_creating_altair_chart_does_not_mutate_original() -> None:
    import altair as alt

    data = {"values": [1, 2, 3]}
    original_chart = alt.Chart(data).mark_point().encode(x="values:Q")

    # Store the original spec
    original_spec = original_chart.to_dict()

    # Create marimo altair_chart wrapper
    _ = altair_chart(original_chart)

    # Verify the original chart hasn't been mutated
    assert original_chart.to_dict() == original_spec


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
    spec["data"] = {"url": "_placeholder_", "format": spec["data"]["format"]}
    snapshot("parse_spec_pandas.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_parse_spec_narwhal() -> None:
    import altair as alt

    data = pd.DataFrame({"values": [1, 2, 3]})
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    # Replace data.url with a placeholder
    spec["data"] = {"url": "_placeholder_", "format": spec["data"]["format"]}
    snapshot("parse_spec_narwhal.txt", json.dumps(spec, indent=2))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_parse_spec_polars() -> None:
    import altair as alt
    import polars as pl

    data = pl.DataFrame({"values": [1, 2, 3]})
    chart = alt.Chart(data).mark_point().encode(x="values:Q")
    spec = _parse_spec(chart)
    # Replace data.url with a placeholder
    spec["data"] = {"url": "_placeholder_", "format": spec["data"]["format"]}
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
def test_get_binned_fields() -> None:
    """Test _get_binned_fields detection for various binning configurations."""
    import altair as alt

    # Case 1: No binning - should return empty dict
    spec_no_binning = _parse_spec(
        alt.Chart(pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]}))
        .mark_point()
        .encode(x="x", y="y")
    )
    binned_fields = _get_binned_fields(spec_no_binning)
    assert binned_fields == {}

    # Case 2: Single field with bin=True
    spec_bin_true = _parse_spec(
        alt.Chart(pd.DataFrame({"values": range(100)}))
        .mark_bar()
        .encode(x=alt.X("values", bin=True), y="count()")
    )
    binned_fields = _get_binned_fields(spec_bin_true)
    assert "values" in binned_fields
    assert binned_fields["values"] is True

    # Case 3: Single field with bin configuration
    spec_bin_config = _parse_spec(
        alt.Chart(pd.DataFrame({"values": range(100)}))
        .mark_bar()
        .encode(x=alt.X("values", bin=alt.Bin(maxbins=20)), y="count()")
    )
    binned_fields = _get_binned_fields(spec_bin_config)
    assert "values" in binned_fields
    assert isinstance(binned_fields["values"], dict)
    assert binned_fields["values"]["maxbins"] == 20

    # Case 4: Bin configuration with step
    spec_bin_step = _parse_spec(
        alt.Chart(pd.DataFrame({"values": range(100)}))
        .mark_bar()
        .encode(x=alt.X("values", bin=alt.Bin(step=10)), y="count()")
    )
    binned_fields = _get_binned_fields(spec_bin_step)
    assert "values" in binned_fields
    assert isinstance(binned_fields["values"], dict)
    assert binned_fields["values"]["step"] == 10

    # Case 5: Multiple binned fields (2D histogram)
    spec_multiple_bins = _parse_spec(
        alt.Chart(pd.DataFrame({"x": range(100), "y": range(100)}))
        .mark_rect()
        .encode(
            x=alt.X("x", bin=True),
            y=alt.Y("y", bin=alt.Bin(maxbins=15)),
            color="count()",
        )
    )
    binned_fields = _get_binned_fields(spec_multiple_bins)
    assert "x" in binned_fields
    assert "y" in binned_fields
    assert binned_fields["x"] is True
    assert isinstance(binned_fields["y"], dict)
    assert binned_fields["y"]["maxbins"] == 15

    # Case 6: Mix of binned and non-binned fields
    spec_mixed = _parse_spec(
        alt.Chart(
            pd.DataFrame(
                {
                    "x": range(100),
                    "y": range(100),
                    "color": ["A"] * 50 + ["B"] * 50,
                }
            )
        )
        .mark_bar()
        .encode(
            x=alt.X("x", bin=True),
            y="count()",
            color="color:N",  # Not binned
        )
    )
    binned_fields = _get_binned_fields(spec_mixed)
    assert "x" in binned_fields
    assert "color" not in binned_fields
    assert binned_fields["x"] is True

    # Case 7: Binned field on y-axis
    spec_y_binned = _parse_spec(
        alt.Chart(pd.DataFrame({"values": range(100)}))
        .mark_bar()
        .encode(x="count()", y=alt.Y("values", bin=True))
    )
    binned_fields = _get_binned_fields(spec_y_binned)
    assert "values" in binned_fields
    assert binned_fields["values"] is True

    # Case 8: Spec with no encoding (should not error)
    spec_no_encoding = {"mark": "point"}
    binned_fields = _get_binned_fields(spec_no_encoding)
    assert binned_fields == {}

    # Case 9: Bin with extent
    spec_bin_extent = _parse_spec(
        alt.Chart(pd.DataFrame({"values": range(100)}))
        .mark_bar()
        .encode(x=alt.X("values", bin=alt.Bin(extent=[0, 50])), y="count()")
    )
    binned_fields = _get_binned_fields(spec_bin_extent)
    assert "values" in binned_fields
    assert isinstance(binned_fields["values"], dict)
    assert binned_fields["values"]["extent"] == [0, 50]


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
        exclude=["lazy-polars"],
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
    # Test that selection is now enabled for binned charts
    assert marimo_chart._component_args["chart-selection"] is not False


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "x": [1, 2, 3, 4],
            "y": [1, 2, 3, 4],
            "category": ["A", "A", "B", "B"],
        },
        exclude=["lazy-polars"],
    ),
)
def test_apply_selection(df: IntoDataFrame):
    import altair as alt

    chart = alt.Chart(df).mark_point().encode(x="x", y="y", color="category")

    marimo_chart = altair_chart(chart)
    marimo_chart._chart_selection = {"signal_channel": {"category": ["A"]}}

    filtered_data = marimo_chart.apply_selection(df)
    assert get_len(filtered_data) == 2
    assert all(maybe_collect(filtered_data)["category"] == "A")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "values": [10, 15, 20, 25, 30, 35, 40, 45],
            "category": ["A", "A", "B", "B", "C", "C", "D", "D"],
        },
    ),
)
def test_filter_dataframe_with_binned_fields(df: ChartDataType) -> None:
    """Test filtering with binned fields using interval selection."""
    # Define binned fields (simulating what would come from _get_binned_fields)
    binned_fields = {"values": True}

    # Interval selection on a binned field - selecting bins from 20 to 30
    # This should include values where 20 <= values < 30
    interval_selection: ChartSelection = {
        "signal_channel": {"values": [20, 30]}
    }
    filtered_df = _filter_dataframe(
        df, selection=interval_selection, binned_fields=binned_fields
    )
    assert get_len(filtered_df) == 2
    collected = maybe_collect(filtered_df)
    assert all(collected["values"] >= 20)
    assert all(collected["values"] < 30)

    # Test with wider range (not including max value)
    wider_selection: ChartSelection = {"signal_channel": {"values": [10, 40]}}
    filtered_df = _filter_dataframe(
        df, selection=wider_selection, binned_fields=binned_fields
    )
    assert get_len(filtered_df) == 6
    collected = maybe_collect(filtered_df)
    assert all(collected["values"] >= 10)
    assert all(collected["values"] < 40)

    # Test boundary values - right boundary is not inclusive for non-last bin
    boundary_selection: ChartSelection = {
        "signal_channel": {"values": [30, 40]}
    }
    filtered_df = _filter_dataframe(
        df, selection=boundary_selection, binned_fields=binned_fields
    )
    assert get_len(filtered_df) == 2
    collected = maybe_collect(filtered_df)
    assert 30 in collected["values"]
    assert 35 in collected["values"]
    assert 40 not in collected["values"]

    # Test last bin - right boundary SHOULD be inclusive
    # When selecting to the max value (45), it should be included
    last_bin_selection: ChartSelection = {
        "signal_channel": {"values": [40, 45]}
    }
    filtered_df = _filter_dataframe(
        df, selection=last_bin_selection, binned_fields=binned_fields
    )
    assert get_len(filtered_df) == 2
    collected = maybe_collect(filtered_df)
    assert 40 in collected["values"]
    assert 45 in collected["values"]  # Last bin includes right boundary


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "values": list(range(0, 100, 10)),
            "id": list(range(10)),
        },
    ),
)
def test_filter_dataframe_binned_with_multiple_selections(
    df: ChartDataType,
) -> None:
    """Test filtering with binned fields and multiple selection channels."""
    binned_fields = {"values": True}

    # Multiple selection channels
    multi_selection: ChartSelection = {
        "signal_channel_1": {"values": [20, 50]},
        "signal_channel_2": {"id": [2, 6]},
    }
    filtered_df = _filter_dataframe(
        df, selection=multi_selection, binned_fields=binned_fields
    )
    # Should have values >= 20 and < 50 AND id >= 2 and < 6
    assert get_len(filtered_df) == 3
    collected = maybe_collect(filtered_df)
    assert all(collected["values"] >= 20)
    assert all(collected["values"] < 50)
    assert all(collected["id"] >= 2)
    assert all(collected["id"] < 6)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "timestamp": [
                datetime.datetime(2020, 1, 1),
                datetime.datetime(2020, 2, 1),
                datetime.datetime(2020, 3, 1),
                datetime.datetime(2020, 4, 1),
                datetime.datetime(2020, 5, 1),
            ],
            "value": [10, 20, 30, 40, 50],
        },
    ),
)
def test_filter_dataframe_binned_dates(df: ChartDataType) -> None:
    """Test filtering with binned date fields."""
    binned_fields = {"timestamp": True}

    # Interval selection on binned date field (not last bin)
    # Vega sends milliseconds since epoch
    start = int(datetime.datetime(2020, 2, 1).timestamp() * 1000)
    end = int(datetime.datetime(2020, 4, 1).timestamp() * 1000)

    interval_selection: ChartSelection = {
        "signal_channel": {"timestamp": [start, end]}
    }
    filtered_df = _filter_dataframe(
        df, selection=interval_selection, binned_fields=binned_fields
    )
    assert get_len(filtered_df) == 2
    collected = maybe_collect(filtered_df)
    timestamps = collected["timestamp"]
    # Should include Feb and Mar, but not Apr (right boundary non-inclusive for non-last bin)
    assert datetime.datetime(2020, 2, 1) in timestamps
    assert datetime.datetime(2020, 3, 1) in timestamps
    assert datetime.datetime(2020, 4, 1) not in timestamps

    # Test last bin - should include the right boundary
    start_last = int(datetime.datetime(2020, 4, 1).timestamp() * 1000)
    end_last = int(datetime.datetime(2020, 5, 1).timestamp() * 1000)

    last_bin_selection: ChartSelection = {
        "signal_channel": {"timestamp": [start_last, end_last]}
    }
    filtered_df = _filter_dataframe(
        df, selection=last_bin_selection, binned_fields=binned_fields
    )
    assert get_len(filtered_df) == 2
    collected = maybe_collect(filtered_df)
    timestamps = collected["timestamp"]
    # Last bin should include May (right boundary inclusive)
    assert datetime.datetime(2020, 4, 1) in timestamps
    assert datetime.datetime(2020, 5, 1) in timestamps


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "values": [5, 10, 15, 20, 25, 30],
            "category": ["A", "A", "B", "B", "C", "C"],
        },
    ),
)
def test_filter_dataframe_binned_with_point_selection(
    df: ChartDataType,
) -> None:
    """Test that point selection works correctly with binned fields."""
    binned_fields = {"values": True}

    # Point selection should still work even with binned fields
    # However, point selections on binned fields should be treated as intervals
    point_selection: ChartSelection = {
        "signal_channel": {
            "vlPoint": [1],
            "values": [10, 20],
        }
    }
    filtered_df = _filter_dataframe(
        df, selection=point_selection, binned_fields=binned_fields
    )
    # With binning, should filter as a range
    assert get_len(filtered_df) == 2
    collected = maybe_collect(filtered_df)
    assert all(collected["values"] >= 10)
    assert all(collected["values"] < 20)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({"values": range(100)}, exclude=["lazy-polars"]),
)
def test_chart_binning_end_to_end(df: IntoDataFrame):
    """Test binning with selection end-to-end through altair_chart."""
    import altair as alt

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(x=alt.X("values", bin=True), y="count()")
    )

    marimo_chart = altair_chart(chart)

    # Simulate a selection from the frontend (bin from 20 to 30, not last bin)
    marimo_chart._chart_selection = {"select_interval": {"values": [20, 30]}}

    # Get filtered data
    filtered = marimo_chart._convert_value(marimo_chart._chart_selection)
    assert get_len(filtered) == 10
    collected = maybe_collect(filtered)
    assert all(collected["values"] >= 20)
    assert all(collected["values"] < 30)

    # Test last bin (should include right boundary)
    marimo_chart._chart_selection = {"select_interval": {"values": [90, 99]}}
    filtered = marimo_chart._convert_value(marimo_chart._chart_selection)
    assert get_len(filtered) == 10
    collected = maybe_collect(filtered)
    assert all(collected["values"] >= 90)
    assert all(collected["values"] <= 99)
    assert 99 in collected["values"]  # Last bin includes max value


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_filter_dataframe_without_binned_fields() -> None:
    """Test that filtering works normally when binned_fields is None."""
    df = pd.DataFrame({"values": [10, 20, 30, 40, 50]})

    # Without binned_fields (default behavior)
    interval_selection: ChartSelection = {
        "signal_channel": {"values": [20, 40]}
    }
    filtered_df = _filter_dataframe(df, selection=interval_selection)
    # Without binning flag, should use inclusive right boundary
    assert get_len(filtered_df) == 3
    collected = maybe_collect(filtered_df)
    assert 20 in collected["values"]
    assert 30 in collected["values"]
    assert 40 in collected["values"]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_value_is_not_available() -> None:
    import altair as alt

    # inline charts
    chart_spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "data": {"values": [{"x": 1, "y": 1}]},
        "mark": "point",
        "encoding": {
            "x": {"field": "x", "type": "quantitative"},
            "y": {"field": "y", "type": "quantitative"},
        },
    }

    marimo_chart = altair_chart(alt.Chart.from_dict(chart_spec))

    # check if calling marimo_chart.value writes to stderr
    with io.StringIO() as buf, redirect_stderr(buf):
        _ = marimo_chart.value
        stderr_output = buf.getvalue()
        assert (
            "Use `.apply_selection(df)` to filter a DataFrame based on the selection."
            in stderr_output
        )


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


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_chart_with_column_encoding_not_full_width() -> None:
    import altair as alt

    from marimo._plugins.ui._impl.altair_chart import maybe_make_full_width

    # Create a chart with column encoding (faceted chart)
    data = pd.DataFrame(
        {
            "x": [1, 2, 3, 4],
            "y": [4, 5, 6, 7],
            "category": ["A", "B", "A", "B"],
        }
    )
    chart = (
        alt.Chart(data)
        .mark_point()
        .encode(x="x:Q", y="y:Q", column="category:N")
    )

    # Test that chart with column encoding is NOT made full width
    result = maybe_make_full_width(chart)
    assert result.width is alt.Undefined

    # Test that chart without column encoding IS made full width
    chart_without_column = (
        alt.Chart(data).mark_point().encode(x="x:Q", y="y:Q")
    )
    result_without_column = maybe_make_full_width(chart_without_column)
    assert result_without_column.width == "container"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_has_no_nested_hconcat() -> None:
    import altair as alt

    # Create simple charts
    chart1 = alt.Chart(pd.DataFrame({"x": [1, 2], "y": [3, 4]})).mark_point()
    chart2 = alt.Chart(pd.DataFrame({"x": [1, 2], "y": [3, 4]})).mark_line()

    # Simple chart has no hconcat
    assert _has_no_nested_hconcat(chart1) is True

    # HConcatChart should return False
    hconcat_chart = alt.hconcat(chart1, chart2)
    assert _has_no_nested_hconcat(hconcat_chart) is False

    # VConcatChart with no nested hconcat should return True
    vconcat_chart = alt.vconcat(chart1, chart2)
    assert _has_no_nested_hconcat(vconcat_chart) is True

    # LayerChart with no nested hconcat should return True
    layer_chart = alt.layer(chart1, chart2)
    assert _has_no_nested_hconcat(layer_chart) is True

    # VConcatChart with nested HConcatChart should return False
    nested_vconcat_with_hconcat = alt.vconcat(hconcat_chart, chart1)
    assert _has_no_nested_hconcat(nested_vconcat_with_hconcat) is False

    # VConcatChart with nested VConcatChart (no hconcat) should return True
    nested_vconcat = alt.vconcat(
        alt.vconcat(chart1, chart2), alt.vconcat(chart1, chart2)
    )
    assert _has_no_nested_hconcat(nested_vconcat) is True

    # LayerChart with simple charts (no hconcat) should return True
    layer_simple = alt.layer(chart1, chart2)
    assert _has_no_nested_hconcat(layer_simple) is True

    # VConcatChart with nested layers (no hconcat) should return True
    vconcat_with_layer = alt.vconcat(chart1, alt.layer(chart1, chart2))
    assert _has_no_nested_hconcat(vconcat_with_layer) is True

    # Deeply nested VConcat with HConcat should return False
    deeply_nested = alt.vconcat(alt.vconcat(chart1, hconcat_chart), chart2)
    assert _has_no_nested_hconcat(deeply_nested) is False


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_autosize_not_applied_with_nested_hconcat() -> None:
    import altair as alt

    # Create simple charts
    data = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    chart1 = alt.Chart(data).mark_point().encode(x="x", y="y")
    chart2 = alt.Chart(data).mark_line().encode(x="x", y="y")

    def get_autosize(chart: dict[str, Any]) -> str | None:
        return chart.get("autosize")

    # Test 1: VConcatChart with nested HConcatChart should NOT have autosize applied
    hconcat_chart = alt.hconcat(chart1, chart2)
    vconcat_with_hconcat = alt.vconcat(hconcat_chart, chart1)

    marimo_chart = altair_chart(vconcat_with_hconcat)
    # The autosize should remain Undefined (not set to "fit-x")
    assert get_autosize(marimo_chart._spec) is None

    # Test 2: Simple VConcatChart (no nested hconcat) SHOULD have autosize applied
    simple_vconcat = alt.vconcat(chart1, chart2)
    marimo_chart_simple = altair_chart(simple_vconcat)
    # The autosize should be set to "fit-x"
    assert get_autosize(marimo_chart_simple._spec) == "fit-x"

    # Test 3: VConcatChart with nested vconcat containing hconcat should NOT have autosize
    nested_with_hconcat = alt.vconcat(
        alt.vconcat(chart1, hconcat_chart), chart2
    )

    marimo_chart_complex = altair_chart(nested_with_hconcat)
    assert get_autosize(marimo_chart_complex._spec) is None

    # Test 4: VConcatChart with explicit autosize should not be overridden
    vconcat_with_autosize = alt.vconcat(chart1, chart2).properties(
        autosize="none"
    )
    marimo_chart_explicit = altair_chart(vconcat_with_autosize)
    # Should keep the explicit autosize value
    assert get_autosize(marimo_chart_explicit._spec) == "none"
