# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import dataclasses
import json
from collections import namedtuple
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._plugins.core.json_encoder import WebComponentEncoder

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.altair.has()
    and DependencyManager.polars.has()
)


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
    assert encoded_timestamp == '"2021-01-01T12:00:00"'

    # DatetimeTZDtype
    datetime_with_tz = pd.Series(
        pd.date_range("2021-01-01", periods=3, tz="UTC")
    )
    encoded_datetime_with_tz = json.dumps(
        datetime_with_tz, cls=WebComponentEncoder
    )
    assert '"2021-01-01T00:00:00+00:00"' in encoded_datetime_with_tz

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
    assert encoded_timedelta_arr == '["1 days", "2 days", "3 days"]'

    # Catch-all
    other = pd.Series(["a", "b", "c"])
    encoded_other = json.dumps(other, cls=WebComponentEncoder)
    assert encoded_other == '["a", "b", "c"]'


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_polars_encoding() -> None:
    import polars as pl

    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    encoded = json.dumps(df, cls=WebComponentEncoder)
    assert encoded == '{"a": [1, 2], "b": [3, 4]}'

    series = pl.Series([1, 2, 3])
    encoded_series = json.dumps(series, cls=WebComponentEncoder)
    assert encoded_series == "[1, 2, 3]"


@dataclass
class MockMIMEObject:
    def _mime_(self) -> tuple[str, str]:
        return "text/plain", "data"


def test_mime_encoding() -> None:
    mime_obj = MockMIMEObject()
    encoded = json.dumps(mime_obj, cls=WebComponentEncoder)
    assert encoded == '{"mimetype": "text/plain", "data": "data"}'


def test_list_mime_encoding() -> None:
    mime_obj = [MockMIMEObject(), MockMIMEObject()]
    encoded = json.dumps(mime_obj, cls=WebComponentEncoder)
    assert (
        encoded
        == '[{"mimetype": "text/plain", "data": "data"}, {"mimetype": "text/plain", "data": "data"}]'  # noqa: E501
    )


def test_dict_mime_encoding() -> None:
    mime_obj = {"key": MockMIMEObject()}
    encoded = json.dumps(mime_obj, cls=WebComponentEncoder)
    assert encoded == '{"key": {"mimetype": "text/plain", "data": "data"}}'


def test_nested_mime_encoding() -> None:
    mime_obj = {"key": [MockMIMEObject(), MockMIMEObject()]}
    encoded = json.dumps(mime_obj, cls=WebComponentEncoder)
    assert (
        encoded
        == '{"key": [{"mimetype": "text/plain", "data": "data"}, {"mimetype": "text/plain", "data": "data"}]}'  # noqa: E501
    )


@dataclass
class MockDataclass:
    a: int
    b: str
    items: Optional[list[Any]] = None
    other_items: Optional[dict[str, Any]] = None


class Button(MIME):
    def _mime_(self) -> tuple[str, str]:
        return "text/html", "<button>Click me!</button>"


def test_dataclass_encoding() -> None:
    dataclass_obj = MockDataclass(1, "hello")
    encoded = json.dumps(dataclass_obj, cls=WebComponentEncoder)
    assert (
        encoded == '{"a": 1, "b": "hello", "items": null, "other_items": null}'
    )


def test_dataclass_with_list_encoding() -> None:
    dataclass_obj = MockDataclass(
        1, "hello", items=[1, "2", MockMIMEObject(), Button()]
    )
    # as dict
    assert dataclasses.asdict(dataclass_obj) == {
        "a": 1,
        "b": "hello",
        "items": [1, "2", {}, {}],  # asdict will convert to empty dictionaries
        "other_items": None,
    }

    # But our encoder handles nested dataclasses back through the encoder
    encoded = json.dumps(dataclass_obj, cls=WebComponentEncoder)
    assert (
        encoded
        == '{"a": 1, "b": "hello", "items": [1, "2", {"mimetype": "text/plain", "data": "data"}, {"mimetype": "text/html", "data": "<button>Click me!</button>"}], "other_items": null}'  # noqa: E501
    )


def test_dataclass_with_dict_encoding() -> None:
    dataclass_obj = MockDataclass(
        1, "hello", other_items={"key": MockMIMEObject()}
    )
    encoded = json.dumps(dataclass_obj, cls=WebComponentEncoder)
    assert (
        encoded
        == '{"a": 1, "b": "hello", "items": null, "other_items": {"key": {"mimetype": "text/plain", "data": "data"}}}'  # noqa: E501
    )


def test_dict_encoding() -> None:
    dict_obj = {"key": "value"}
    encoded = json.dumps(dict_obj, cls=WebComponentEncoder)
    assert encoded == '{"key": "value"}'


def test_bytes_encoding() -> None:
    bytes_obj = b"hello"
    encoded = json.dumps(bytes_obj, cls=WebComponentEncoder)
    assert encoded == '"hello"'


def test_memoryview_encoding() -> None:
    bytes_obj = b"hello"
    memview = memoryview(bytes_obj)
    encoded = json.dumps(memview, cls=WebComponentEncoder)
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


def test_tuple_encoding() -> None:
    tuple_obj = ("a", "b")
    encoded = json.dumps(tuple_obj, cls=WebComponentEncoder)
    assert encoded == '["a", "b"]'
    empty_tuple = ()
    encoded_empty = json.dumps(empty_tuple, cls=WebComponentEncoder)
    assert encoded_empty == "[]"


def test_frozen_set_encoding() -> None:
    frozen_set_obj = frozenset(["a", "b"])
    encoded = json.dumps(frozen_set_obj, cls=WebComponentEncoder)
    assert encoded == '["a", "b"]' or encoded == '["b", "a"]'
    empty_frozen_set = frozenset()
    encoded_empty = json.dumps(empty_frozen_set, cls=WebComponentEncoder)
    assert encoded_empty == "[]"
    number_frozen_set = frozenset([1, 2])
    encoded_number = json.dumps(number_frozen_set, cls=WebComponentEncoder)
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


def test_complex_number_encoding() -> None:
    complex_num = 3 + 4j
    encoded = json.dumps(complex_num, cls=WebComponentEncoder)
    assert encoded == '"(3+4j)"'


def test_custom_class_encoding() -> None:
    @dataclass
    class CustomClass:
        name: str
        value: int

    custom_obj = CustomClass(name="test", value=42)
    encoded = json.dumps(custom_obj, cls=WebComponentEncoder)
    assert encoded == '{"name": "test", "value": 42}'


def test_nested_structure_encoding() -> None:
    nested_structure = {
        "list": [1, 2, 3],
        "dict": {"a": 1, "b": 2},
        "tuple": (4, 5, 6),
        "set": {7, 8, 9},
    }
    encoded = json.dumps(nested_structure, cls=WebComponentEncoder)
    decoded = json.loads(encoded)
    assert decoded["list"] == [1, 2, 3]
    assert decoded["dict"] == {"a": 1, "b": 2}
    assert decoded["tuple"] == [4, 5, 6]  # Tuples are converted to lists
    assert set(decoded["set"]) == {7, 8, 9}


def test_date_time_encoding() -> None:
    import datetime

    date_obj = datetime.date(2023, 1, 1)
    time_obj = datetime.time(12, 30, 45)
    datetime_obj = datetime.datetime(2023, 1, 1, 12, 30, 45)

    encoded_date = json.dumps(date_obj, cls=WebComponentEncoder)
    encoded_time = json.dumps(time_obj, cls=WebComponentEncoder)
    encoded_datetime = json.dumps(datetime_obj, cls=WebComponentEncoder)

    assert encoded_date == '"2023-01-01"'
    assert encoded_time == '"12:30:45"'
    assert encoded_datetime == '"2023-01-01T12:30:45"'


def test_timedelta_encoding() -> None:
    import datetime

    timedelta_obj = datetime.timedelta(days=1, seconds=2, microseconds=3)
    encoded = json.dumps(timedelta_obj, cls=WebComponentEncoder)
    assert encoded == '"1 day, 0:00:02.000003"'


def test_enum_encoding() -> None:
    from enum import Enum

    class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3

    encoded = json.dumps(Color.RED, cls=WebComponentEncoder)
    assert encoded == '"RED"'


def test_uuid_encoding() -> None:
    import uuid

    uuid_obj = uuid.uuid4()
    encoded = json.dumps(uuid_obj, cls=WebComponentEncoder)
    assert encoded == f'"{str(uuid_obj)}"'


def test_circular_reference_encoding():
    circular_dict = {}
    circular_dict["self"] = circular_dict
    with pytest.raises(ValueError):
        json.dumps(circular_dict, cls=WebComponentEncoder)


def test_custom_object_with_dict():
    class CustomObject:
        def __init__(self):
            self.attr = "value"

    obj = CustomObject()
    encoded = json.dumps(obj, cls=WebComponentEncoder)
    assert encoded == '{"attr": "value"}'


def test_object_with_slots():
    class SlottedObject:
        __slots__ = ["x", "y"]

        def __init__(self, x, y):
            self.x = x
            self.y = y

    obj = SlottedObject(1, 2)
    encoded = json.dumps(obj, cls=WebComponentEncoder)
    assert encoded == '{"x": 1, "y": 2}'


def test_named_tuple_encoding():
    Point = namedtuple("Point", ["x", "y"])
    p = Point(1, 2)
    encoded = json.dumps(p, cls=WebComponentEncoder)
    assert encoded == "[1, 2]"


def test_complex_nested_structure():
    complex_obj = {
        "list": [1, {"a": 2}, (3, 4)],
        "dict": {"b": [5, 6], "c": {"d": 7}},
        "set": {8, 9, 10},
        "tuple": (11, [12, 13], {"e": 14}),
    }
    encoded = json.dumps(complex_obj, cls=WebComponentEncoder)
    decoded = json.loads(encoded)
    assert decoded["list"] == [1, {"a": 2}, [3, 4]]
    assert decoded["dict"] == {"b": [5, 6], "c": {"d": 7}}
    assert set(decoded["set"]) == {8, 9, 10}
    assert decoded["tuple"] == [11, [12, 13], {"e": 14}]


def test_png_encoding() -> None:
    purple_square = "b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x14\x00\x00\x00\x14\x08\x02\x00\x00\x00\x02\xeb\x8aZ\x00\x00\x00\tpHYs\x00\x00.#\x00\x00.#\x01x\xa5?v\x00\x00\x00\x1dIDAT8\xcbc\xac\x11\xa9g \x1701P\x00F5\x8fj\x1e\xd5<\xaa\x99r\xcd\x00m\xba\x017\xd3\x00\xdf\xcb\x00\x00\x00\x00IEND\xaeB`\x82'"  # noqa: E501
    encoded = json.dumps(purple_square, cls=WebComponentEncoder)
    assert isinstance(encoded, str)


def test_range_encoding() -> None:
    r = range(10)
    encoded = json.dumps(r, cls=WebComponentEncoder)
    assert encoded == "[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]"


def test_error_encoding() -> None:
    from marimo._messaging.errors import MultipleDefinitionError
    from marimo._types.ids import CellId_t

    error_obj = MultipleDefinitionError(
        "This is a custom error", (CellId_t("test"), CellId_t("test2"))
    )
    encoded = json.dumps(error_obj, cls=WebComponentEncoder)
    assert (
        encoded
        == '{"name": "This is a custom error", "cells": ["test", "test2"], "type": "multiple-defs"}'
    )


def test_invalid_class() -> None:
    class InvalidClass: ...

    invalid_obj = InvalidClass()
    invalid_obj.__slots__ = None

    encoded = json.dumps(invalid_obj, cls=WebComponentEncoder)
    assert encoded == '{"__slots__": null}'


def test_empty_slots() -> None:
    class ExClass:
        __slots__ = []

        # With a property (as sanity check)
        @property
        def one(self):
            return 1

    obj = ExClass()

    encoded = json.dumps(obj, cls=WebComponentEncoder)
    assert encoded == "{}"


def test_decimal_encoding() -> None:
    from decimal import Decimal

    decimal_obj = Decimal("123.45")
    encoded = json.dumps(decimal_obj, cls=WebComponentEncoder)
    assert encoded == "123.45"
