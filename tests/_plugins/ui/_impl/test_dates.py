# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from typing import cast

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui

HAS_PANDAS = DependencyManager.pandas.has()


def test_date() -> None:
    date = ui.date()
    today = date.value
    assert today == datetime.date.today()

    date._update("2024-01-01")
    assert date.value == datetime.date(2024, 1, 1)

    date = ui.date(value="2024-01-01")
    assert date.value == datetime.date(2024, 1, 1)

    date = ui.date(value="2024-01-01")
    date._update("2024-01-02")
    assert date.value == datetime.date(2024, 1, 2)


def test_datetime() -> None:
    # Test default initialization
    dt = ui.datetime()
    now = datetime.datetime.now()
    assert dt.value
    assert dt.value.date() == now.date()
    assert dt.value.hour == now.hour
    assert dt.value.minute == now.minute

    # Test initialization with a specific value
    dt = ui.datetime(value="2024-01-01T12:30")
    assert dt.value == datetime.datetime(2024, 1, 1, 12, 30)
    # Test initialization with a specific value
    dt = ui.datetime(value="2024-01-01T12")
    assert dt.value == datetime.datetime(2024, 1, 1, 12)
    dt = ui.datetime(value="2024-01-01")
    assert dt.value == datetime.datetime(2024, 1, 1)

    # Test updating the value
    dt._update("2024-02-15T08:45")
    assert dt.value == datetime.datetime(2024, 2, 15, 8, 45)

    # Test with start and stop
    dt = ui.datetime(
        value="2024-01-15T10:00",
        start="2024-01-01T00:00",
        stop="2024-12-31T23:59",
    )
    assert dt.value == datetime.datetime(2024, 1, 15, 10, 0)
    assert dt.start == datetime.datetime(2024, 1, 1, 0, 0)
    assert dt.stop == datetime.datetime(2024, 12, 31, 23, 59)


def test_datetime_min_max_iso_format() -> None:
    """Test that datetime.min and datetime.max are formatted correctly with ISO 8601.

    This test addresses issue #6700 where datetime.min was formatted as
    "1-01-01T00:00:00" instead of "0001-01-01T00:00:00" in some Docker
    environments, causing frontend parsing errors.
    """
    # Test with datetime.min
    dt = ui.datetime()
    start_arg: str = cast(str, dt._args.args.get("start"))
    stop_arg: str = cast(str, dt._args.args.get("stop"))

    # Verify that start and stop are properly formatted ISO 8601 strings
    # with 4-digit years (not single digit years like "1-01-01")
    assert start_arg is not None
    assert stop_arg is not None
    assert start_arg.startswith("0001-"), (
        f"Expected start to begin with '0001-', got: {start_arg}"
    )
    assert stop_arg.startswith("9999-"), (
        f"Expected stop to begin with '9999-', got: {stop_arg}"
    )

    # Verify exact format for datetime.min
    assert start_arg == "0001-01-01T00:00:00"

    # Test with explicit datetime.min and datetime.max
    dt_explicit = ui.datetime(
        start=datetime.datetime.min,
        stop=datetime.datetime.max,
    )
    start_explicit = dt_explicit._args.args.get("start")
    stop_explicit = dt_explicit._args.args.get("stop")

    assert start_explicit == "0001-01-01T00:00:00"
    assert stop_explicit == "9999-12-31T23:59:59"


def test_date_range() -> None:
    # Test default initialization
    dr = ui.date_range()
    today = datetime.date.today()
    assert dr.value == (today, today)

    # Test initialization with specific values
    dr = ui.date_range(value=("2024-01-01", "2024-01-31"))
    assert dr.value == (datetime.date(2024, 1, 1), datetime.date(2024, 1, 31))

    # Test updating the value
    dr._update(("2024-02-01", "2024-02-29"))
    assert dr.value == (datetime.date(2024, 2, 1), datetime.date(2024, 2, 29))

    # Test with start and stop
    dr = ui.date_range(
        start="2024-01-01",
        stop="2024-12-31",
    )
    assert dr.start == datetime.date(2024, 1, 1)
    assert dr.stop == datetime.date(2024, 12, 31)
    assert dr.value == (dr.start, dr.stop)

    # Test with start, stop and value
    dr = ui.date_range(
        value=("2024-03-01", "2024-03-15"),
        start="2024-01-01",
        stop="2024-12-31",
    )
    assert dr.value == (datetime.date(2024, 3, 1), datetime.date(2024, 3, 15))
    assert dr.start == datetime.date(2024, 1, 1)
    assert dr.stop == datetime.date(2024, 12, 31)

    # Test invalid range (start date after end date)
    with pytest.raises(ValueError):
        ui.date_range(value=("2024-02-01", "2024-01-01"))


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_date_from_dataframe() -> None:
    import pandas as pd

    df = pd.DataFrame(
        {"A": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]}
    )
    date = ui.date.from_series(
        df["A"], value=datetime.date(2024, 1, 2), label="Custom label"
    )
    assert date.value == datetime.date(2024, 1, 2)
    assert date.start == datetime.date(2024, 1, 1)
    assert date.stop == datetime.date(2024, 1, 2)
    assert date._args.label == "Custom label"


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_datetime_from_dataframe() -> None:
    import pandas as pd

    # Test from_series for datetime
    df_datetime = pd.DataFrame(
        {
            "B": [
                pd.Timestamp("2024-01-01 10:00"),
                pd.Timestamp("2024-01-02 14:30"),
            ]
        }
    )
    datetime_ui = ui.datetime.from_series(
        df_datetime["B"], value=datetime.datetime(2024, 1, 2, 14, 30)
    )
    assert datetime_ui.value == datetime.datetime(2024, 1, 2, 14, 30)
    assert datetime_ui.start == datetime.datetime(2024, 1, 1, 10, 0)
    assert datetime_ui.stop == datetime.datetime(2024, 1, 2, 14, 30)


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_date_range_from_dataframe() -> None:
    import pandas as pd

    # Test from_series for date_range
    df_date_range = pd.DataFrame(
        {"C": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31")]}
    )
    date_range_ui = ui.date_range.from_series(
        df_date_range["C"],
        value=(datetime.date(2024, 1, 15), datetime.date(2024, 1, 20)),
    )
    assert date_range_ui.value == (
        datetime.date(2024, 1, 15),
        datetime.date(2024, 1, 20),
    )
    assert date_range_ui.start == datetime.date(2024, 1, 1)
    assert date_range_ui.stop == datetime.date(2024, 1, 31)


def test_datetime_precision_default() -> None:
    """Test that datetime precision defaults to 'minute'."""
    dt = ui.datetime(value="2024-01-01T12:30:45")

    # Check that precision is set to "minute" by default in the args
    precision = dt._args.args.get("precision")
    assert precision == "minute"


def test_datetime_precision_validation() -> None:
    """Test that datetime precision validation raises ValueError for invalid values."""
    # Valid precisions should work
    dt_hour = ui.datetime(value="2024-01-01T12:30:45", precision="hour")
    assert dt_hour._args.args.get("precision") == "hour"

    dt_minute = ui.datetime(value="2024-01-01T12:30:45", precision="minute")
    assert dt_minute._args.args.get("precision") == "minute"

    dt_second = ui.datetime(value="2024-01-01T12:30:45", precision="second")
    assert dt_second._args.args.get("precision") == "second"

    # Invalid precision should raise ValueError
    with pytest.raises(ValueError, match="precision must be"):
        ui.datetime(value="2024-01-01T12:30:45", precision="millisecond")  # type: ignore[arg-type]


def test_date_slider_basic() -> None:
    # Test default initialization
    ds = ui.date_slider(
        start=datetime.date(2024, 1, 1),
        stop=datetime.date(2024, 1, 31),
    )
    assert ds.value == (datetime.date(2024, 1, 1), datetime.date(2024, 1, 31))
    assert ds.start == datetime.date(2024, 1, 1)
    assert ds.stop == datetime.date(2024, 1, 31)
    assert ds.step == datetime.timedelta(days=1)

    # Test initialization with specific values
    ds = ui.date_slider(
        start=datetime.date(2024, 1, 1),
        stop=datetime.date(2024, 1, 31),
        value=(datetime.date(2024, 1, 10), datetime.date(2024, 1, 20)),
    )
    assert ds.value == (datetime.date(2024, 1, 10), datetime.date(2024, 1, 20))

    # Test updating the value
    ds._update(["2024-01-05", "2024-01-25"])
    assert ds.value == (datetime.date(2024, 1, 5), datetime.date(2024, 1, 25))


def test_date_slider_with_step() -> None:
    # Test with weekly step
    ds = ui.date_slider(
        start=datetime.date(2024, 1, 1),
        stop=datetime.date(2024, 1, 31),
        step=datetime.timedelta(days=7),
    )
    assert ds.step == datetime.timedelta(days=7)
    # Value should snap to nearest step
    assert ds.value == (datetime.date(2024, 1, 1), datetime.date(2024, 1, 29))

    # Test value snapping to closest step
    ds = ui.date_slider(
        start=datetime.date(2024, 1, 1),
        stop=datetime.date(2024, 1, 31),
        step=datetime.timedelta(days=7),
        value=(datetime.date(2024, 1, 10), datetime.date(2024, 1, 20)),
    )
    # Closest steps to Jan 10 is Jan 8, closest to Jan 20 is Jan 22
    assert ds.value == (datetime.date(2024, 1, 8), datetime.date(2024, 1, 22))


def test_date_slider_with_strings() -> None:
    # Test initialization with string dates
    ds = ui.date_slider(
        start="2024-01-01",
        stop="2024-01-31",
        value=("2024-01-10", "2024-01-20"),
    )
    assert ds.value == (datetime.date(2024, 1, 10), datetime.date(2024, 1, 20))
    assert ds.start == datetime.date(2024, 1, 1)
    assert ds.stop == datetime.date(2024, 1, 31)


def test_date_slider_invalid_bounds() -> None:
    # Test stop before start
    with pytest.raises(ValueError, match="stop date.*must be greater"):
        ui.date_slider(
            start=datetime.date(2024, 1, 31),
            stop=datetime.date(2024, 1, 1),
        )

    # Test negative step
    with pytest.raises(ValueError, match="step.*must be a positive"):
        ui.date_slider(
            start=datetime.date(2024, 1, 1),
            stop=datetime.date(2024, 1, 31),
            step=datetime.timedelta(days=-1),
        )

    # Test value out of bounds
    with pytest.raises(ValueError, match="default value.*must be within"):
        ui.date_slider(
            start=datetime.date(2024, 1, 10),
            stop=datetime.date(2024, 1, 20),
            value=(datetime.date(2024, 1, 1), datetime.date(2024, 1, 15)),
        )

    # Test first date after second date
    with pytest.raises(ValueError, match="first date.*must not be greater"):
        ui.date_slider(
            start=datetime.date(2024, 1, 1),
            stop=datetime.date(2024, 1, 31),
            value=(datetime.date(2024, 1, 20), datetime.date(2024, 1, 10)),
        )


def test_date_slider_properties() -> None:
    ds = ui.date_slider(
        start=datetime.date(2024, 1, 1),
        stop=datetime.date(2024, 12, 31),
        step=datetime.timedelta(weeks=1),
    )
    assert ds.start == datetime.date(2024, 1, 1)
    assert ds.stop == datetime.date(2024, 12, 31)
    assert ds.step == datetime.timedelta(weeks=1)


def test_date_slider_args() -> None:
    # Test that args are properly set for frontend
    ds = ui.date_slider(
        start=datetime.date(2024, 1, 1),
        stop=datetime.date(2024, 1, 31),
        step=datetime.timedelta(days=2),
        debounce=True,
        orientation="vertical",
        show_value=True,
        full_width=True,
        disabled=True,
        label="Select dates",
    )
    args = ds._args.args
    assert args["debounce"] is True
    assert args["orientation"] == "vertical"
    assert args["show-value"] is True
    assert args["full-width"] is True
    assert args["disabled"] is True
    assert ds._args.label == "Select dates"
    # Check that steps are generated
    assert "steps" in args
    assert isinstance(args["steps"], list)
    assert len(args["steps"]) > 0


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
def test_date_slider_from_dataframe() -> None:
    import pandas as pd

    # Test from_series for date_slider
    df = pd.DataFrame(
        {"D": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31")]}
    )
    date_slider_ui = ui.date_slider.from_series(
        df["D"],
        step=datetime.timedelta(days=7),
        value=(datetime.date(2024, 1, 8), datetime.date(2024, 1, 22)),
    )
    assert date_slider_ui.value == (
        datetime.date(2024, 1, 8),
        datetime.date(2024, 1, 22),
    )
    assert date_slider_ui.start == datetime.date(2024, 1, 1)
    assert date_slider_ui.stop == datetime.date(2024, 1, 31)
    assert date_slider_ui.step == datetime.timedelta(days=7)
