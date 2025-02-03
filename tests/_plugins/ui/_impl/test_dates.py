# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime

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
