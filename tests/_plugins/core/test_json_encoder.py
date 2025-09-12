# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from collections import namedtuple
from dataclasses import dataclass
from typing import Any, Optional

from marimo._messaging.mimetypes import KnownMimeType
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.msgspec_encoder import encode_json_str
from marimo._output.mime import MIME

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.altair.has()
    and DependencyManager.polars.has()
)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_numpy_encoding() -> None:
    import numpy as np

    arr = np.array([1, 2, 3])
    encoded = encode_json_str(arr)
    assert encoded == "[1,2,3]"

    dt64 = np.datetime64("2021-01-01T12:00:00")
    encoded_dt64 = encode_json_str(dt64)
    assert encoded_dt64 == '"2021-01-01T12:00:00"'

    dt64_arr = np.array([dt64, dt64])
    encoded_dt64_arr = encode_json_str(dt64_arr)
    assert encoded_dt64_arr == '["2021-01-01T12:00:00","2021-01-01T12:00:00"]'

    complex_arr = np.array([1 + 2j, 3 + 4j])
    encoded_complex_arr = encode_json_str(complex_arr)
    assert encoded_complex_arr == '["(1+2j)","(3+4j)"]'


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_pandas_encoding() -> None:
    import pandas as pd

    # DF
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    encoded = encode_json_str(df)
    assert encoded == '[{"a":1,"b":3},{"a":2,"b":4}]'

    # Series
    series = pd.Series([1, 2, 3])
    encoded_series = encode_json_str(series)
    assert encoded_series == "[1,2,3]"

    # Timestamp
    timestamp = pd.Timestamp("2021-01-01T12:00:00")
    encoded_timestamp = encode_json_str(timestamp)
    assert encoded_timestamp == '"2021-01-01 12:00:00"'

    # DatetimeTZDtype
    datetime_with_tz = pd.Series(
        pd.date_range("2021-01-01", periods=3, tz="UTC")
    )
    encoded_datetime_with_tz = encode_json_str(datetime_with_tz)
    assert '"2021-01-01 00:00:00+00:00"' in encoded_datetime_with_tz

    # Categorical
    cat = pd.Categorical(["test", "train", "test", "train"])
    encoded_cat = encode_json_str(cat)
    assert encoded_cat == '["test","train","test","train"]'

    # Interval
    interval = pd.Interval(left=0, right=5)
    encoded_interval = encode_json_str(interval)
    assert encoded_interval == '"(0, 5]"'

    # Timedelta
    timedelta = pd.Timedelta("1 days")
    encoded_timedelta = encode_json_str(timedelta)
    assert encoded_timedelta == '"1 days 00:00:00"'

    timedelta_arr = pd.to_timedelta(["1 days", "2 days", "3 days"])
    encoded_timedelta_arr = encode_json_str(timedelta_arr)
    assert encoded_timedelta_arr == '["1 days","2 days","3 days"]'

    # Catch-all
    other = pd.Series(["a", "b", "c"])
    encoded_other = encode_json_str(other)
    assert encoded_other == '["a","b","c"]'


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_polars_encoding() -> None:
    import polars as pl

    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    encoded = encode_json_str(df)
    assert encoded == '{"a":[1,2],"b":[3,4]}'

    series = pl.Series([1, 2, 3])
    encoded_series = encode_json_str(series)
    assert encoded_series == "[1,2,3]"


class MockMIMEObject(MIME):
    def _mime_(self) -> tuple[KnownMimeType, str]:
        return "text/plain", "data"


def test_mime_encoding() -> None:
    mime_obj = MockMIMEObject()
    encoded = encode_json_str(mime_obj)
    assert encoded == '{"mimetype":"text/plain","data":"data"}'


def test_list_mime_encoding() -> None:
    mime_obj = [MockMIMEObject(), MockMIMEObject()]
    encoded = encode_json_str(mime_obj)
    assert (
        encoded
        == '[{"mimetype":"text/plain","data":"data"},{"mimetype":"text/plain","data":"data"}]'  # noqa:E501
    )


def test_dict_mime_encoding() -> None:
    mime_obj = {"key": MockMIMEObject()}
    encoded = encode_json_str(mime_obj)
    assert encoded == '{"key":{"mimetype":"text/plain","data":"data"}}'


def test_nested_mime_encoding() -> None:
    mime_obj = {"key": [MockMIMEObject(), MockMIMEObject()]}
    encoded = encode_json_str(mime_obj)
    assert (
        encoded
        == '{"key":[{"mimetype":"text/plain","data":"data"},{"mimetype":"text/plain","data":"data"}]}'  # noqa:E501
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
    encoded = encode_json_str(dataclass_obj)
    assert encoded == '{"a":1,"b":"hello","items":null,"other_items":null}'


def test_dataclass_with_list_encoding() -> None:
    dataclass_obj = MockDataclass(
        1, "hello", items=[1, "2", MockMIMEObject(), Button()]
    )
    encoded = encode_json_str(dataclass_obj)
    assert (
        encoded
        == '{"a":1,"b":"hello","items":[1,"2",{"mimetype":"text/plain","data":"data"},{"mimetype":"text/html","data":"<button>Click me!</button>"}],"other_items":null}'  # noqa:E501
    )


def test_dataclass_with_dict_encoding() -> None:
    dataclass_obj = MockDataclass(
        1, "hello", other_items={"key": MockMIMEObject()}
    )
    encoded = encode_json_str(dataclass_obj)
    assert (
        encoded
        == '{"a":1,"b":"hello","items":null,"other_items":{"key":{"mimetype":"text/plain","data":"data"}}}'  # noqa:E501
    )


def test_dict_encoding() -> None:
    dict_obj = {"key": "value"}
    encoded = encode_json_str(dict_obj)
    assert encoded == '{"key":"value"}'


def test_bytes_encoding() -> None:
    bytes_obj = b"hello"
    encoded = encode_json_str(bytes_obj)
    assert encoded == '"aGVsbG8="'


def test_memoryview_encoding() -> None:
    bytes_obj = b"hello"
    memview = memoryview(bytes_obj)
    encoded = encode_json_str(memview)
    assert encoded == '"aGVsbG8="'


def test_set_encoding() -> None:
    set_obj = set(["a", "b"])
    encoded = encode_json_str(set_obj)
    assert encoded == '["a","b"]' or encoded == '["b","a"]'
    empty_set = set()
    encoded_empty = encode_json_str(empty_set)
    assert encoded_empty == "[]"
    number_set = set([1, 2])
    encoded_number = encode_json_str(number_set)
    assert encoded_number == "[1,2]" or encoded_number == "[2,1]"


def test_tuple_encoding() -> None:
    tuple_obj = ("a", "b")
    encoded = encode_json_str(tuple_obj)
    assert encoded == '["a","b"]'
    empty_tuple = ()
    encoded_empty = encode_json_str(empty_tuple)
    assert encoded_empty == "[]"


def test_frozen_set_encoding() -> None:
    frozen_set_obj = frozenset(["a", "b"])
    encoded = encode_json_str(frozen_set_obj)
    assert encoded == '["a","b"]' or encoded == '["b","a"]'
    empty_frozen_set = frozenset()
    encoded_empty = encode_json_str(empty_frozen_set)
    assert encoded_empty == "[]"
    number_frozen_set = frozenset([1, 2])
    encoded_number = encode_json_str(number_frozen_set)
    assert encoded_number == "[1,2]" or encoded_number == "[2,1]"


def test_null_encoding() -> None:
    null = None
    encoded = encode_json_str(null)
    assert encoded == "null"


def test_inf_encoding() -> None:
    inf = float("inf")
    encoded = encode_json_str(inf)
    assert encoded == "null"  # msgspec encodes infinity as null


def test_nan_encoding() -> None:
    nan = float("nan")
    encoded = encode_json_str(nan)
    assert encoded == "null"  # msgspec encodes NaN as null


def test_empty_encoding() -> None:
    empty = ""
    encoded = encode_json_str(empty)
    assert encoded == '""'
    empty_list = []
    encoded_list = encode_json_str(empty_list)
    assert encoded_list == "[]"
    empty_dict = {}
    encoded_dict = encode_json_str(empty_dict)
    assert encoded_dict == "{}"
    empty_tuple = ()
    encoded_tuple = encode_json_str(empty_tuple)
    assert encoded_tuple == "[]"
    empty_nested = [[], [], []]
    encoded_nested = encode_json_str(empty_nested)
    assert encoded_nested == "[[],[],[]]"


def test_complex_number_encoding() -> None:
    complex_num = 3 + 4j
    encoded = encode_json_str(complex_num)
    assert encoded == '"(3+4j)"'


def test_custom_class_encoding() -> None:
    @dataclass
    class CustomClass:
        name: str
        value: int

    custom_obj = CustomClass(name="test", value=42)
    encoded = encode_json_str(custom_obj)
    assert encoded == '{"name":"test","value":42}'


def test_nested_structure_encoding() -> None:
    nested_structure = {
        "list": [1, 2, 3],
        "dict": {"a": 1, "b": 2},
        "tuple": (4, 5, 6),
        "set": {7, 8, 9},
    }
    encoded = encode_json_str(nested_structure)
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

    encoded_date = encode_json_str(date_obj)
    encoded_time = encode_json_str(time_obj)
    encoded_datetime = encode_json_str(datetime_obj)

    assert encoded_date == '"2023-01-01"'
    assert encoded_time == '"12:30:45"'
    assert encoded_datetime == '"2023-01-01T12:30:45"'


def test_timedelta_encoding() -> None:
    import datetime

    timedelta_obj = datetime.timedelta(days=1, seconds=2, microseconds=3)
    encoded = encode_json_str(timedelta_obj)
    assert encoded == '"P1DT2.000003S"'


def test_enum_encoding() -> None:
    from enum import Enum

    class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3

    encoded = encode_json_str(Color.RED)
    assert encoded == "1"


def test_str_enum() -> None:
    from enum import StrEnum

    class Color(StrEnum):
        RED = "RED"
        GREEN = "GREEN"
        BLUE = "BLUE"

    encoded = encode_json_str(Color.RED)
    assert encoded == '"RED"'


def test_uuid_encoding() -> None:
    import uuid

    uuid_obj = uuid.uuid4()
    encoded = encode_json_str(uuid_obj)
    assert encoded == f'"{str(uuid_obj)}"'


def test_circular_reference_encoding():
    circular_dict = {}
    circular_dict["self"] = circular_dict
    with pytest.raises(RecursionError):
        encode_json_str(circular_dict)


def test_custom_object_with_dict():
    class CustomObject:
        def __init__(self):
            self.attr = "value"

    obj = CustomObject()
    encoded = encode_json_str(obj)
    assert encoded == '{"attr":"value"}'


def test_object_with_slots():
    class SlottedObject:
        __slots__ = ["x", "y"]

        def __init__(self, x, y):
            self.x = x
            self.y = y

    obj = SlottedObject(1, 2)
    encoded = encode_json_str(obj)
    assert encoded == '{"x":1,"y":2}'


def test_named_tuple_encoding():
    Point = namedtuple("Point", ["x", "y"])
    p = Point(1, 2)
    encoded = encode_json_str(p)
    assert encoded == "[1,2]"


def test_complex_nested_structure():
    complex_obj = {
        "list": [1, {"a": 2}, (3, 4)],
        "dict": {"b": [5, 6], "c": {"d": 7}},
        "set": {8, 9, 10},
        "tuple": (11, [12, 13], {"e": 14}),
    }
    encoded = encode_json_str(complex_obj)
    decoded = json.loads(encoded)
    assert decoded["list"] == [1, {"a": 2}, [3, 4]]
    assert decoded["dict"] == {"b": [5, 6], "c": {"d": 7}}
    assert set(decoded["set"]) == {8, 9, 10}
    assert decoded["tuple"] == [11, [12, 13], {"e": 14}]


def test_png_encoding() -> None:
    purple_square = "b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x14\x00\x00\x00\x14\x08\x02\x00\x00\x00\x02\xeb\x8aZ\x00\x00\x00\tpHYs\x00\x00.#\x00\x00.#\x01x\xa5?v\x00\x00\x00\x1dIDAT8\xcbc\xac\x11\xa9g \x1701P\x00F5\x8fj\x1e\xd5<\xaa\x99r\xcd\x00m\xba\x017\xd3\x00\xdf\xcb\x00\x00\x00\x00IEND\xaeB`\x82'"  # noqa: E501
    encoded = encode_json_str(purple_square)
    assert isinstance(encoded, str)


def test_range_encoding() -> None:
    r = range(10)
    encoded = encode_json_str(r)
    assert encoded == "[0,1,2,3,4,5,6,7,8,9]"


def test_error_encoding() -> None:
    from marimo._messaging.errors import MultipleDefinitionError
    from marimo._types.ids import CellId_t

    error_obj = MultipleDefinitionError(
        "This is a custom error", (CellId_t("test"), CellId_t("test2"))
    )
    encoded = encode_json_str(error_obj)
    assert (
        encoded
        == '{"type":"multiple-defs","name":"This is a custom error","cells":["test","test2"]}'
    )


def test_invalid_class() -> None:
    class InvalidClass: ...

    invalid_obj = InvalidClass()
    invalid_obj.__slots__ = None

    encoded = encode_json_str(invalid_obj)
    assert encoded == '{"__slots__":null}'


def test_empty_slots() -> None:
    class ExClass:
        __slots__ = []

        # With a property (as sanity check)
        @property
        def one(self):
            return 1

    obj = ExClass()

    encoded = encode_json_str(obj)
    assert encoded == "{}"


def test_decimal_encoding() -> None:
    from decimal import Decimal

    decimal_obj = Decimal("123.45")
    encoded = encode_json_str(decimal_obj)
    assert encoded == "123.45"
