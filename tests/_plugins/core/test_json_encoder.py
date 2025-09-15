# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import collections
import datetime
import fractions
import json
import pathlib
import sys
import uuid
from collections import namedtuple
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.msgspec_encoder import encode_json_str
from marimo._output.mime import MIME
from marimo._utils.platform import is_windows

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

    # Additional numpy types
    td64 = np.timedelta64(1, "D")
    encoded = encode_json_str(td64)
    assert encoded == '"1 days"'

    bool_val = np.bool_(True)
    encoded = encode_json_str(bool_val)
    assert encoded == "true"

    bytes_val = np.bytes_(b"hello")
    encoded = encode_json_str(bytes_val)
    assert encoded == "\"b'hello'\""

    str_val = np.str_("hello")
    encoded = encode_json_str(str_val)
    assert encoded == '"hello"'


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

    # Additional pandas types
    period = pd.Period("2021-01", freq="M")
    encoded = encode_json_str(period)
    assert encoded == '"2021-01"'

    # DatetimeIndex
    dt_index = pd.date_range("2021-01-01", periods=3, freq="D")
    encoded = encode_json_str(dt_index)
    result = json.loads(encoded)
    assert len(result) == 3
    assert "2021-01-01" in result[0]

    # MultiIndex
    multi_index = pd.MultiIndex.from_tuples([("A", 1), ("B", 2)])
    encoded = encode_json_str(multi_index)
    result = json.loads(encoded)
    assert result == [["A", 1], ["B", 2]]

    # Index
    index = pd.Index([1, 2, 3])
    encoded = encode_json_str(index)
    assert encoded == "[1,2,3]"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_polars_encoding() -> None:
    import polars as pl

    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    encoded = encode_json_str(df)
    assert encoded == '{"a":[1,2],"b":[3,4]}'

    series = pl.Series([1, 2, 3])
    encoded_series = encode_json_str(series)
    assert encoded_series == "[1,2,3]"

    # LazyFrame
    lazy_df = pl.DataFrame({"a": [1, 2], "b": [3, 4]}).lazy()
    encoded = encode_json_str(lazy_df)
    result = json.loads(encoded)
    assert result == {"a": [1, 2], "b": [3, 4]}

    # Polars data types
    dtype = pl.Int64()
    encoded = encode_json_str(dtype)
    assert "Int64" in encoded


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


def test_collections_encoding() -> None:
    # frozenset
    frozen_set_obj = frozenset(["a", "b"])
    encoded = encode_json_str(frozen_set_obj)
    assert encoded == '["a","b"]' or encoded == '["b","a"]'
    empty_frozen_set = frozenset()
    encoded_empty = encode_json_str(empty_frozen_set)
    assert encoded_empty == "[]"
    number_frozen_set = frozenset([1, 2])
    encoded_number = encode_json_str(number_frozen_set)
    assert encoded_number == "[1,2]" or encoded_number == "[2,1]"

    # deque
    deque_obj = collections.deque([1, 2, 3])
    encoded = encode_json_str(deque_obj)
    assert encoded == "[1,2,3]"

    # defaultdict
    default_dict = collections.defaultdict(int, {"a": 1, "b": 2})
    encoded = encode_json_str(default_dict)
    result = json.loads(encoded)
    assert result == {"a": 1, "b": 2}

    # OrderedDict
    ordered_dict = collections.OrderedDict([("a", 1), ("b", 2)])
    encoded = encode_json_str(ordered_dict)
    result = json.loads(encoded)
    assert result == {"a": 1, "b": 2}

    # Counter
    counter = collections.Counter(["a", "b", "a"])
    encoded = encode_json_str(counter)
    result = json.loads(encoded)
    assert result == {"a": 2, "b": 1}


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
    # Standard datetime types
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
    # Standard timedelta
    timedelta_obj = datetime.timedelta(days=1, seconds=2, microseconds=3)
    encoded = encode_json_str(timedelta_obj)
    assert encoded == '"P1DT2.000003S"'

    delta = datetime.timedelta(days=1, hours=2, minutes=3)
    encoded = encode_json_str(delta)
    assert encoded == '"P1DT7380S"'  # ISO 8601 duration format


def test_enum_encoding() -> None:
    from enum import Enum, IntEnum

    class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3

    class StringColor(Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    class Number(IntEnum):
        ONE = 1
        TWO = 2
        THREE = 3

    # Int enum
    encoded = encode_json_str(Color.RED)
    assert encoded == "1"

    # String enum
    encoded = encode_json_str(StringColor.RED)
    assert encoded == '"red"'

    # IntEnum
    encoded = encode_json_str(Number.TWO)
    assert encoded == "2"


@pytest.mark.skipif(
    sys.version_info < (3, 11), reason="StrEnum not supported in Python 3.10"
)
def test_str_enum() -> None:
    from enum import StrEnum

    class Color(StrEnum):
        RED = "RED"
        GREEN = "GREEN"
        BLUE = "BLUE"

    encoded = encode_json_str(Color.RED)
    assert encoded == '"RED"'


def test_uuid_encoding() -> None:
    # Random UUID
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
    purple_square = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x14\x00\x00\x00\x14\x08\x02\x00\x00\x00\x02\xeb\x8aZ\x00\x00\x00\tpHYs\x00\x00.#\x00\x00.#\x01x\xa5?v\x00\x00\x00\x1dIDAT8\xcbc\xac\x11\xa9g \x1701P\x00F5\x8fj\x1e\xd5<\xaa\x99r\xcd\x00m\xba\x017\xd3\x00\xdf\xcb\x00\x00\x00\x00IEND\xaeB`\x82"  # noqa: E501
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


def test_numeric_types_encoding() -> None:
    # Decimal
    decimal_obj = Decimal("123.45")
    encoded = encode_json_str(decimal_obj)
    assert encoded == "123.45"

    # More precise decimal
    decimal_val = Decimal("123.456")
    encoded = encode_json_str(decimal_val)
    assert encoded == "123.456"

    # Fraction
    fraction_val = fractions.Fraction(3, 4)
    encoded = encode_json_str(fraction_val)
    assert encoded == '"3/4"'


@pytest.mark.skipif(is_windows(), reason="Test specific to POSIX")
def test_pathlib_encoding() -> None:
    """Test encoding of pathlib Path objects."""
    # PosixPath
    path = pathlib.Path("/tmp/test.txt")
    encoded = encode_json_str(path)
    assert encoded == '"/tmp/test.txt"'

    # PurePath
    pure_path = pathlib.PurePath("relative/path.txt")
    encoded = encode_json_str(pure_path)
    assert encoded == '"relative/path.txt"'


def test_generator_encoding() -> None:
    """Test encoding of generator objects."""

    def gen():
        yield 1
        yield 2
        yield 3

    generator = gen()
    encoded = encode_json_str(generator)
    assert "<generator" in encoded


def test_html_encoding() -> None:
    from marimo._output.hypertext import Html

    html_obj = Html("<h1>Hello World</h1>")
    encoded = encode_json_str(html_obj)
    assert (
        encoded
        == '{"_serialized_mime_bundle":{"mimetype":"text/html","data":"<h1>Hello World</h1>"}}'
    )


def test_binary_data_encoding() -> None:
    # Test various binary data types
    binary_data = bytearray(b"binary data")
    encoded = encode_json_str(binary_data)
    assert encoded == '"YmluYXJ5IGRhdGE="'  # base64 encoded


def test_memoryview_additional_encoding() -> None:
    # Additional memoryview tests beyond the existing one
    data = bytearray(b"memory view test")
    memview = memoryview(data)
    encoded = encode_json_str(memview)
    assert encoded == '"bWVtb3J5IHZpZXcgdGVzdA=="'  # base64 encoded

    # Test memoryview with different data types
    int_array = memoryview(b"\x01\x02\x03\x04")
    encoded_int = encode_json_str(int_array)
    assert encoded_int == '"AQIDBA=="'


class MockMarimoSerializable:
    """Mock class that implements _marimo_serialize_"""

    def __init__(self, data):
        self.data = data

    def _marimo_serialize_(self):
        return {"serialized_data": self.data, "type": "mock"}


def test_marimo_serialize_encoding() -> None:
    mock_obj = MockMarimoSerializable("test data")
    encoded = encode_json_str(mock_obj)
    assert encoded == '{"serialized_data":"test data","type":"mock"}'

    # Test with nested data
    nested_mock = MockMarimoSerializable({"nested": [1, 2, 3]})
    encoded_nested = encode_json_str(nested_mock)
    assert (
        encoded_nested
        == '{"serialized_data":{"nested":[1,2,3]},"type":"mock"}'
    )


def test_list_of_inf_encoding() -> None:
    inf_list = [float("inf"), -float("inf"), float("nan"), 1.0, 2.0]
    encoded = encode_json_str(inf_list)
    # msgspec encodes infinity and NaN as null
    assert encoded == "[null,null,null,1.0,2.0]"

    # Test nested list with inf
    nested_inf_list = [[float("inf")], [1, float("-inf")], [float("nan"), 3]]
    encoded_nested = encode_json_str(nested_inf_list)
    assert encoded_nested == "[[null],[1,null],[null,3]]"


def test_superjson_with_custom_objects() -> None:
    from marimo._output.superjson import SuperJson

    # Test SuperJson with objects that have __dict__ (custom classes)
    @dataclass
    class CustomData:
        name: str
        value: int

    custom_data = CustomData(name="test", value=42)
    superjson_obj = SuperJson(custom_data)
    encoded = encode_json_str(superjson_obj)
    assert encoded == '{"name":"test","value":42}'


def test_superjson_with_mime_objects() -> None:
    from marimo._output.superjson import SuperJson

    # Test SuperJson with MIME objects (which have _mime_ method)
    mime_data = MockMIMEObject()
    superjson_obj = SuperJson(mime_data)
    encoded = encode_json_str(superjson_obj)
    assert encoded == '{"mimetype":"text/plain","data":"data"}'


def test_superjson_with_marimo_serializable() -> None:
    from marimo._output.superjson import SuperJson

    # Test SuperJson with objects that have _marimo_serialize_
    serializable_data = MockMarimoSerializable("superjson test")
    superjson_obj = SuperJson(serializable_data)
    encoded = encode_json_str(superjson_obj)
    assert encoded == '{"serialized_data":"superjson test","type":"mock"}'


def test_superjson_with_ranges() -> None:
    from marimo._output.superjson import SuperJson

    # Test SuperJson with range objects (handled by enc_hook)
    range_data = range(5)
    superjson_obj = SuperJson(range_data)
    encoded = encode_json_str(superjson_obj)
    assert encoded == "[0,1,2,3,4]"


def test_superjson_with_complex_numbers() -> None:
    from marimo._output.superjson import SuperJson

    # Test SuperJson with complex numbers (handled by enc_hook)
    complex_data = 3 + 4j
    superjson_obj = SuperJson(complex_data)
    encoded = encode_json_str(superjson_obj)
    assert encoded == '"(3+4j)"'


def test_superjson_with_inf_nan() -> None:
    from marimo._output.superjson import SuperJson

    # Test SuperJson with inf and nan (handled by enc_hook)
    superjson_obj = SuperJson(
        [float("inf"), float("nan"), 1.0, 2.0, float("-inf")]
    )
    encoded = encode_json_str(superjson_obj)
    assert encoded == '["Infinity","NaN",1.0,2.0,"-Infinity"]'


def test_superjson_with_bytes() -> None:
    from marimo._output.superjson import SuperJson

    # ASCII bytes
    bytes_data = b"hello"
    superjson_obj = SuperJson(bytes_data)
    encoded = encode_json_str(superjson_obj)
    assert encoded == '"hello"'

    # Unicode bytes
    bytes_data = b"hello\x80\x81\x82"
    superjson_obj = SuperJson(bytes_data)
    encoded = encode_json_str(superjson_obj)
    assert encoded == '"hello\x80\x81\x82"'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, "1"),
        (True, "true"),
        ("hello", '"hello"'),
        (None, "null"),
        ([1, 2, 3], "[1,2,3]"),
        ({"a": 1, "b": 2}, '{"a":1,"b":2}'),
        ((), "[]"),
        (set([1, 2, 3]), "[1,2,3]"),
        (frozenset([1, 2, 3]), "[1,2,3]"),
        (range(10), "[0,1,2,3,4,5,6,7,8,9]"),
        (datetime.datetime(2023, 1, 1, 12, 30, 45), '"2023-01-01 12:30:45"'),
        (datetime.timedelta(days=1, hours=2, minutes=3), '"1 day, 2:03:00"'),
        (datetime.date(2023, 1, 1), '"2023-01-01"'),
        (3 + 4j, '"(3+4j)"'),
        (
            [float("inf"), float("nan"), 1.0, 2.0, float("-inf")],
            '["Infinity","NaN",1.0,2.0,"-Infinity"]',
        ),
        (b"hello", '"hello"'),
        (memoryview(b"hello"), '"hello"'),
        (
            MockMarimoSerializable("test data"),
            '{"serialized_data":"test data","type":"mock"}',
        ),
    ],
)
def test_wrapped_in_superjson(value: Any, expected: str) -> None:
    from marimo._output.superjson import SuperJson

    obj = SuperJson(value)
    encoded = encode_json_str(obj)
    assert encoded == expected
