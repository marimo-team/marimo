# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.core.json_encoder import WebComponentEncoder

HAS_DEPS = DependencyManager.has_pandas() and DependencyManager.has_altair()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_numpy_encoding() -> None:
    import numpy as np

    arr = np.array([1, 2, 3])
    encoded = json.dumps(arr, cls=WebComponentEncoder)
    assert encoded == "[1, 2, 3]"

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


class MockMIMEObject:
    def _mime_(self) -> tuple[str, str]:
        return "text/plain", "data"


def test_mime_encoding() -> None:
    mime_obj = MockMIMEObject()
    encoded = json.dumps(mime_obj, cls=WebComponentEncoder)
    assert encoded == '{"mimetype": "text/plain", "data": "data"}'


def test_bytes_encoding() -> None:
    bytes_obj = b"hello"
    encoded = json.dumps(bytes_obj, cls=WebComponentEncoder)
    assert encoded == '"hello"'
