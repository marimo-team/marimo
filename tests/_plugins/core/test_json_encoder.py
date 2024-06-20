# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.core.json_encoder import WebComponentEncoder

HAS_DEPS = DependencyManager.has_pandas() and DependencyManager.has_altair()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_numpy_encoding() -> None:
    import numpy as np

    arr = np.array([1, 2, 3])
    encoded = json.dumps(arr, cls=WebComponentEncoder)
    assert encoded == '"[1, 2, 3]"'

    dt64 = np.datetime64("2021-01-01T12:00:00")
    encoded_dt64 = json.dumps(dt64, cls=WebComponentEncoder)
    assert encoded_dt64 == '"2021-01-01T12:00:00"'

    dt64_arr = np.array([dt64, dt64])
    encoded_dt64_arr = json.dumps(dt64_arr, cls=WebComponentEncoder)
    assert encoded_dt64_arr == '["2021-01-01T12:00:00", "2021-01-01T12:00:00"]'

    complex_arr = np.array([1 + 2j, 3 + 4j])
    encoded_complex_arr = json.dumps(complex_arr, cls=WebComponentEncoder)
    assert encoded_complex_arr == '["(1+2j)", "(3+4j)"]'


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_pandas_encoding() -> None:
    import pandas as pd

    # DF
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    encoded = json.dumps(df, cls=WebComponentEncoder)
    assert encoded == '[{"a": 1, "b": 3}, {"a": 2, "b": 4}]'

    # Series
    series = pd.Series([1, 2, 3])
    encoded_series = json.dumps(series, cls=WebComponentEncoder)
    assert encoded_series == "[1, 2, 3]"

    # Timestamp
    timestamp = pd.Timestamp("2021-01-01T12:00:00")
    encoded_timestamp = json.dumps(timestamp, cls=WebComponentEncoder)
    assert encoded_timestamp == '"2021-01-01 12:00:00"'

    # DatetimeTZDtype
    datetime_with_tz = pd.Series(
        pd.date_range("2021-01-01", periods=3, tz="UTC")
    )
    encoded_datetime_with_tz = json.dumps(
        datetime_with_tz, cls=WebComponentEncoder
    )
    assert '"2021-01-01 00:00:00+00:00"' in encoded_datetime_with_tz

    # Categorical
    cat = pd.Categorical(["test", "train", "test", "train"])
    encoded_cat = json.dumps(cat, cls=WebComponentEncoder)
    assert encoded_cat == '["test", "train", "test", "train"]'

    # Interval
    interval = pd.Interval(left=0, right=5)
    encoded_interval = json.dumps(interval, cls=WebComponentEncoder)
    assert encoded_interval == '"(0, 5]"'

    # Timedelta
    timedelta = pd.Timedelta("1 days")
    encoded_timedelta = json.dumps(timedelta, cls=WebComponentEncoder)
    assert encoded_timedelta == '"1 days 00:00:00"'

    timedelta_arr = pd.to_timedelta(["1 days", "2 days", "3 days"])
    encoded_timedelta_arr = json.dumps(timedelta_arr, cls=WebComponentEncoder)
    assert encoded_timedelta_arr == "\"['1 days', '2 days', '3 days']\""

    # Catch-all
    other = pd.Series(["a", "b", "c"])
    encoded_other = json.dumps(other, cls=WebComponentEncoder)
    assert encoded_other == '["a", "b", "c"]'


@dataclass
class MockMIMEObject:
    def _mime_(self) -> tuple[str, str]:
        return "text/plain", "data"


def test_mime_encoding() -> None:
    mime_obj = MockMIMEObject()
    encoded = json.dumps(mime_obj, cls=WebComponentEncoder)
    assert encoded == '{"mimetype": "text/plain", "data": "data"}'


@dataclass
class MockDataclass:
    a: int
    b: str


def test_dataclass_encoding() -> None:
    dataclass_obj = MockDataclass(1, "hello")
    encoded = json.dumps(dataclass_obj, cls=WebComponentEncoder)
    assert encoded == '{"a": 1, "b": "hello"}'


def test_bytes_encoding() -> None:
    bytes_obj = b"hello"
    encoded = json.dumps(bytes_obj, cls=WebComponentEncoder)
    assert encoded == '"hello"'


def test_set_encoding() -> None:
    set_obj = set(["a", "b"])
    encoded = json.dumps(set_obj, cls=WebComponentEncoder)
    assert encoded == '["a", "b"]' or encoded == '["b", "a"]'
    empty_set = set()
    encoded_empty = json.dumps(empty_set, cls=WebComponentEncoder)
    assert encoded_empty == "[]"
    number_set = set([1, 2])
    encoded_number = json.dumps(number_set, cls=WebComponentEncoder)
    assert encoded_number == "[1, 2]" or encoded_number == "[2, 1]"


def test_null_encoding() -> None:
    null = None
    encoded = json.dumps(null, cls=WebComponentEncoder)
    assert encoded == "null"


def test_inf_encoding() -> None:
    inf = float("inf")
    encoded = json.dumps(inf, cls=WebComponentEncoder)
    assert encoded == "Infinity"


def test_nan_encoding() -> None:
    nan = float("nan")
    encoded = json.dumps(nan, cls=WebComponentEncoder)
    assert encoded == "NaN"


def test_empty_encoding() -> None:
    empty = ""
    encoded = json.dumps(empty, cls=WebComponentEncoder)
    assert encoded == '""'
    empty_list = []
    encoded_list = json.dumps(empty_list, cls=WebComponentEncoder)
    assert encoded_list == "[]"
    empty_dict = {}
    encoded_dict = json.dumps(empty_dict, cls=WebComponentEncoder)
    assert encoded_dict == "{}"
    empty_tuple = ()
    encoded_tuple = json.dumps(empty_tuple, cls=WebComponentEncoder)
    assert encoded_tuple == "[]"
    empty_nested = [[], [], []]
    encoded_nested = json.dumps(empty_nested, cls=WebComponentEncoder)
    assert encoded_nested == "[[], [], []]"
