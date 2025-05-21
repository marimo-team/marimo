from __future__ import annotations

import datetime
import json
import unittest
from math import isnan
from typing import Any

import narwhals.stable.v1 as nw
import pytest

from marimo._data.models import ColumnStats
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.format import FormatMapping
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._utils.platform import is_windows
from tests.mocks import snapshotter

HAS_DEPS = DependencyManager.polars.has()

snapshot = snapshotter(__file__)


def assert_frame_equal(a: Any, b: Any) -> bool:
    import polars.testing

    if isinstance(a, nw.DataFrame):
        a = a.to_native()
    if isinstance(b, nw.DataFrame):
        b = b.to_native()
    polars.testing.assert_frame_equal(a, b)
    return True


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPolarsTableManagerFactory(unittest.TestCase):
    def get_complex_data(self) -> TableManager[Any]:
        import polars as pl

        complex_data = pl.DataFrame(
            {
                "strings": ["a", "b", "c"],
                "bool": [True, False, True],
                "int": [1, 2, 3],
                "large_int": [2**64, 2**65 + 1, 2**66 + 2],
                "float": [1.0, 2.0, 3.0],
                "datetime": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "date": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 2),
                    datetime.date(2021, 1, 3),
                ],
                "struct": [
                    {"a": 1, "b": 2},
                    {"a": 3, "b": 4},
                    {"a": 5, "b": 6},
                ],
                "list": pl.Series(
                    [[1, 2], [3, 4], [5, 6]], dtype=pl.List(pl.Int64)
                ),
                "nested_lists": pl.Series(
                    [[[1, 2]], [[3, 4]], [[5, 6]]],
                    dtype=pl.List(pl.List(pl.Int64)),
                ),
                "nested_arrays": pl.Series(
                    [[[1, 2]], [[3, 4]], [[5, 6]]],
                    dtype=pl.Array(pl.Array(pl.Int64, shape=(2,)), shape=(1,)),
                ),
                "array": pl.Series(
                    [[1], [2], [3]], dtype=pl.Array(pl.Int64, 1)
                ),
                "nulls": pl.Series([None, "data", None]),
                "category": pl.Series(
                    ["cat", "dog", "mouse"], dtype=pl.Categorical
                ),
                "set": [set([1, 2]), set([3, 4]), set([5, 6])],
                "imaginary": [1 + 2j, 3 + 4j, 5 + 6j],
                "time": [
                    datetime.time(12, 30),
                    datetime.time(13, 45),
                    datetime.time(14, 15),
                ],
                "duration": [
                    datetime.timedelta(days=1),
                    datetime.timedelta(microseconds=315),
                    datetime.timedelta(hours=2, minutes=30),
                ],
                "mixed_list": [
                    [1, "two"],
                    [3.0, False],
                    [None, datetime.datetime(2021, 1, 1)],
                ],
                "structs_with_list": pl.Series(
                    "mixed",
                    [{"a": [1, 2], "b": 2}, {"a": [3, 4], "b": 4}, [5, 6]],
                ),
                "list_with_structs": pl.Series(
                    "list_with_structs",
                    [
                        [{"a": 1}, {"c": 3}],
                        [{"e": 5}],
                        [],
                    ],
                ),
            },
            strict=False,
        )

        return self.factory.create()(complex_data)

    def setUp(self) -> None:
        import polars as pl

        self.factory = PolarsTableManagerFactory()
        self.data = pl.DataFrame(
            {
                # Integer
                "A": [1, 2, 3],
                # String
                "B": ["a", "b", "c"],
                # Float
                "C": [1.0, 2.0, 3.0],
                # Boolean
                "D": [True, False, True],
                # DateTime
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
            }
        )
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        assert self.factory.package_name() == "polars"

    def test_to_csv(self) -> None:
        assert isinstance(self.manager.to_csv(), bytes)

    @pytest.mark.skipif(
        is_windows(),
        reason="Windows doesn't show microseconds unicode properly",
    )
    def test_to_csv_complex(self) -> None:
        complex_data = self.get_complex_data()
        # CSV does not support nested data types
        columns = [
            col
            for col in complex_data.get_column_names()
            if col
            not in [
                "nested_lists",
                "nested_arrays",
                "list_with_structs",
                "structs_with_list",
            ]
        ]
        manager = complex_data.select_columns(columns)
        data = manager.to_csv()
        assert isinstance(data, bytes)
        snapshot("polars.csv", data.decode("utf-8"))

    def test_to_csv_array(self) -> None:
        import numpy as np
        import polars as pl

        df = pl.DataFrame(
            {"a": [np.arange(5) for _ in range(10)]},
            schema={"a": pl.Array(pl.Int64, 5)},
        )
        manager = self.factory.create()(df)
        assert isinstance(manager.to_csv(), bytes)

    def test_to_parquet(self) -> None:
        assert isinstance(self.manager.to_parquet(), bytes)

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

    def test_to_json_apply_format_mapping(self) -> None:
        import polars as pl

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }
        json_bytes = self.manager.to_json(format_mapping)
        assert isinstance(json_bytes, bytes)

        formatted_data = pl.read_json(json_bytes)
        assert formatted_data["A"].to_list() == [2, 4, 6]

    @pytest.mark.skipif(
        is_windows(),
        reason="Windows doesn't show microseconds unicode properly",
    )
    def test_to_json_complex(self) -> None:
        complex_data = self.get_complex_data()
        data = complex_data.to_json()
        assert isinstance(data, bytes)
        snapshot("polars.json", data.decode("utf-8"))

        json_data = json.loads(data)
        assert json_data[0]["duration"] == "1d"
        assert json_data[1]["duration"] == "315µs"
        assert json_data[2]["duration"] == "2h 30m"

    def test_complex_data_field_types(self) -> None:
        complex_data = self.get_complex_data()
        field_types = complex_data.get_field_types()
        snapshot("polars.field_types.json", json.dumps(field_types))

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        assert "PolarsTableManager" in str(type(selected_manager))
        expected_data = self.data[indices]
        assert assert_frame_equal(selected_manager.data, expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.shape == (0, 5)
        assert selected_manager.data.columns == ["A", "B", "C", "D", "E"]

    def test_select_columns(self) -> None:
        columns = ["A"]
        selected_manager = self.manager.select_columns(columns)
        assert "PolarsTableManager" in str(type(selected_manager))
        expected_data = self.data.select(columns)
        assert assert_frame_equal(selected_manager.data, expected_data)

    def test_drop_columns(self) -> None:
        columns = ["A"]
        dropped_manager = self.manager.drop_columns(columns)
        expected_data = self.data.drop(columns)
        assert assert_frame_equal(dropped_manager.data, expected_data)

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import polars as pl

        expected_field_types = [
            ("A", ("integer", "i64")),
            ("B", ("string", "str")),
            ("C", ("number", "f64")),
            ("D", ("boolean", "bool")),
            ("E", ("datetime", "datetime[μs]")),
        ]
        assert self.manager.get_field_types() == expected_field_types

        complex_data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [1 + 2j, 3 + 4j, 5 + 6j],
                "F": [None, None, None],
                "G": [set([1, 2]), set([3, 4]), set([5, 6])],
                "H": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "I": [
                    "1 days",
                    "2 days",
                    "3 days",
                ],
                "J": [
                    "0-5",
                    "5-10",
                    "10-15",
                ],
                "K": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 2),
                    datetime.date(2021, 1, 3),
                ],
                "L": [
                    datetime.time(1, 2, 3),
                    datetime.time(4, 5, 6),
                    datetime.time(7, 8, 9),
                ],
            }
        )
        expected_field_types = [
            ("A", ("integer", "i64")),
            ("B", ("string", "str")),
            ("C", ("number", "f64")),
            ("D", ("boolean", "bool")),
            ("E", ("unknown", "object")),
            ("F", ("unknown", "null")),
            ("G", ("unknown", "object")),
            ("H", ("datetime", "datetime[μs]")),
            ("I", ("string", "str")),
            ("J", ("string", "str")),
            ("K", ("date", "date")),
            ("L", ("time", "Time")),
        ]
        assert (
            self.factory.create()(complex_data).get_field_types()
            == expected_field_types
        )

    def test_limit(self) -> None:
        limited_manager = self.manager.take(1, 0)
        expected_data = self.data.head(1)
        assert "PolarsTableManager" in str(type(limited_manager))
        assert assert_frame_equal(limited_manager.data, expected_data)

    def test_take(self) -> None:
        assert self.manager.take(1, 0).data["A"].to_list() == [1]
        assert self.manager.take(2, 0).data["A"].to_list() == [1, 2]
        assert self.manager.take(2, 1).data["A"].to_list() == [2, 3]
        assert self.manager.take(2, 2).data["A"].to_list() == [3]

    def test_take_zero(self) -> None:
        limited_manager = self.manager.take(0, 0)
        assert limited_manager.data.is_empty()

    def test_take_negative(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(-1, 0)

    def test_take_negative_offset(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(1, -1)

    def test_take_out_of_bounds(self) -> None:
        # Too large of page
        assert len(self.manager.take(10, 0).data) == 3
        assert len(self.data) == 3

        # Too large of page and offset
        assert self.manager.take(10, 10).data.is_empty()

    def test_stats_integer(self) -> None:
        column = "A"
        stats = self.manager.get_stats(column)
        assert stats == ColumnStats(
            total=3,
            nulls=0,
            unique=3,
            min=1,
            max=3,
            mean=2.0,
            median=2.0,
            std=1.0,
            p5=1.0,
            p25=2.0,
            p75=3.0,
            p95=3.0,
        )

    def test_stats_string(self) -> None:
        column = "B"
        stats = self.manager.get_stats(column)
        assert stats == ColumnStats(
            total=3,
            nulls=0,
            unique=3,
        )

    def test_stats_number(self) -> None:
        column = "C"
        stats = self.manager.get_stats(column)
        assert stats == ColumnStats(
            total=3,
            nulls=0,
            min=1.0,
            max=3.0,
            mean=2.0,
            median=2.0,
            std=1.0,
            p5=1.0,
            p25=2.0,
            p75=3.0,
            p95=3.0,
        )

    def test_stats_boolean(self) -> None:
        column = "D"
        stats = self.manager.get_stats(column)
        assert stats == ColumnStats(
            total=3,
            nulls=0,
            true=2,
            false=1,
        )

    def test_stats_datetime(self) -> None:
        column = "E"
        stats = self.manager.get_stats(column)
        assert stats == ColumnStats(
            total=3,
            nulls=0,
            min=datetime.datetime(2021, 1, 1, 0, 0),
            max=datetime.datetime(2021, 1, 3, 0, 0),
            mean=datetime.datetime(2021, 1, 2, 0, 0),
            # TODO: narwhals doesn't support median
            # and polars doesn't support quantiles for dates
            # median=datetime.datetime(2021, 1, 2, 0, 0),
        )

    def test_stats_date(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [datetime.date(2021, 1, 1), datetime.date(2021, 1, 2)],
            }
        )
        manager = self.factory.create()(data)
        stats = manager.get_stats("A")
        assert stats == ColumnStats(
            total=2,
            nulls=0,
            min=datetime.date(2021, 1, 1),
            max=datetime.date(2021, 1, 2),
            mean=datetime.datetime(2021, 1, 1, 12, 0),
            # TODO: narwhals doesn't support median
            # and polars doesn't support quantiles for dates
            # median=datetime.datetime(2021, 1, 1, 12, 0),
        )

    def test_stats_does_fail_on_each_column(self) -> None:
        complex_data = self.get_complex_data()
        for column in complex_data.get_column_names():
            assert complex_data.get_stats(column) is not None

    def test_sort_values(self) -> None:
        sorted_df = self.manager.sort_values("A", descending=True).data
        expected_df = self.data.sort("A", descending=True)
        assert assert_frame_equal(sorted_df, expected_df)

    def test_get_unique_column_values(self) -> None:
        column = "A"
        unique_values = self.manager.get_unique_column_values(column)
        assert unique_values == [1, 2, 3]

    def test_get_sample_values(self) -> None:
        sample_values = self.manager.get_sample_values("A")
        assert sample_values == [1, 2, 3]
        sample_values = self.manager.get_sample_values("B")
        assert sample_values == ["a", "b", "c"]

    def test_search(self) -> None:
        import polars as pl

        df = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["foo", "bar", "baz"],
                "C": [True, False, True],
                "D": [["zz", "yyy"], [], []],
                "E": [1.1, 2.2, 3.3],
                "G": ["U", "T", "V"],
            }
        )
        manager = self.factory.create()(df)
        # Exact match
        assert manager.search("foo").get_num_rows() == 1
        # Contains
        assert manager.search("a").get_num_rows() == 2
        # Case insensitive
        assert manager.search("v").get_num_rows() == 1
        assert manager.search("V").get_num_rows() == 1
        # Case insensitive / boolean
        assert manager.search("true").get_num_rows() == 2
        # Overmatch
        assert manager.search("food").get_num_rows() == 0
        # Int (exact match)
        assert manager.search("1").get_num_rows() == 1
        # Float (exact match)
        assert manager.search("1.1").get_num_rows() == 1
        # List (exact match)
        assert manager.search("yyy").get_num_rows() == 1
        assert manager.search("y").get_num_rows() == 0

    def test_apply_formatting_does_not_modify_original_data(self) -> None:
        original_data = self.data.clone()
        format_mapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }
        assert self.manager.apply_formatting(format_mapping).data is not None
        assert_frame_equal(self.manager.data, original_data)

    def test_apply_formatting(self) -> None:
        import polars as pl

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_empty_dataframe(self) -> None:
        import polars as pl

        empty_data = pl.DataFrame({"A": []})
        manager = self.factory.create()(empty_data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        assert_frame_equal(formatted_data, empty_data)

    def test_apply_formatting_partial(self) -> None:
        import polars as pl

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_empty(self) -> None:
        format_mapping: FormatMapping = {}

        formatted_data = self.manager.apply_formatting(format_mapping).data
        assert_frame_equal(formatted_data, self.data)

    def test_apply_formatting_invalid_column(self) -> None:
        format_mapping: FormatMapping = {
            "Z": lambda x: x * 2,
        }

        formatted_data = self.manager.apply_formatting(format_mapping).data
        assert_frame_equal(formatted_data, self.data)

    def test_apply_formatting_with_nan(self) -> None:
        import polars as pl

        data_with_nan = self.data.clone()
        data_with_nan = data_with_nan.with_columns(
            pl.when(pl.col("A").is_not_null())
            .then(pl.col("A"))
            .otherwise(None)
            .alias("A")
        )
        manager_with_nan = self.factory.create()(data_with_nan)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2 if x is not None else x,
        }

        formatted_data = manager_with_nan.apply_formatting(format_mapping).data
        expected_data = data_with_nan.clone()
        expected_data = expected_data.with_columns(
            pl.when(pl.col("A").is_not_null())
            .then(pl.col("A") * 2)
            .otherwise(None)
            .alias("A")
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_multi_index(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            }
        ).with_row_index()
        data = data.with_columns(pl.col("index").cast(pl.Utf8))

        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "index": ["0", "1", "2"],
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_categorical_data(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": pl.Series(["a", "b", "a"]).cast(pl.Categorical),
                "B": [1, 2, 3],
            }
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x.upper(),
            "B": lambda x: x * 2,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": pl.Series(["A", "B", "A"]),
                "B": [2, 4, 6],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_datetime_index(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            }
        ).with_columns(
            pl.date_range(
                start=datetime.datetime(2021, 1, 1),
                end=datetime.datetime(2021, 1, 3),
                interval="1d",
            ).alias("index")
        )
        data = data.with_columns(pl.col("index").cast(pl.Utf8))

        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
                "index": ["2021-01-01", "2021-01-02", "2021-01-03"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_complex_data(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "F": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                "G": [1 + 2j, 3 + 4j, 5 + 6j],
            }
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
            "G": abs,
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
                "F": [
                    [1, 2, 3],
                    [4, 5, 6],
                    [7, 8, 9],
                ],  # No formatting applied
                "G": [2.23606797749979, 5.0, 7.810249675906654],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_none_values(self) -> None:
        import polars as pl

        # Create test data with None values in different types of columns
        data = pl.DataFrame(
            {
                "strings": ["a", None, "c"],
                "integers": [1, None, 3],
                "floats": [1.5, None, 3.5],
                "booleans": [True, None, False],
                "dates": [
                    datetime.date(2021, 1, 1),
                    None,
                    datetime.date(2021, 1, 3),
                ],
                "lists": [[1, 2], None, [5, 6]],
            },
        )
        manager = self.factory.create()(data)

        format_mapping: FormatMapping = {
            "strings": lambda x: "MISSING" if x is None else x.upper(),
            "integers": lambda x: -100 if x is None else x * 2,
            "floats": lambda x: "---" if x is None else f"{x:.1f}",
            "booleans": lambda x: "MISSING" if x is None else str(x).upper(),
            "dates": lambda x: "No Date"
            if x is None
            else x.strftime("%Y-%m-%d"),
            "lists": lambda x: "Empty" if x is None else f"List({len(x)})",
        }

        formatted_data = manager.apply_formatting(format_mapping).data
        expected_data = pl.DataFrame(
            {
                "strings": ["A", "MISSING", "C"],
                "integers": [2, -100, 6],
                "floats": ["1.5", "---", "3.5"],
                "booleans": ["TRUE", "MISSING", "FALSE"],
                "dates": ["2021-01-01", "No Date", "2021-01-03"],
                "lists": ["List(2)", "Empty", "List(2)"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_empty_dataframe(self) -> None:
        import polars as pl

        empty_df = pl.DataFrame()
        empty_manager = self.factory.create()(empty_df)
        assert empty_manager.get_num_rows() == 0
        assert empty_manager.get_num_columns() == 0
        assert empty_manager.get_column_names() == []
        assert empty_manager.get_field_types() == []

    def test_dataframe_with_all_null_column(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": [1, 2, 3], "B": [None, None, None]})
        manager = self.factory.create()(df)
        stats = manager.get_stats("B")
        assert stats.nulls == 3
        assert stats.total == 3

    def test_dataframe_with_mixed_types(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": [1, "two", 3.0, True]}, strict=False)
        manager = self.factory.create()(df)
        assert manager.get_field_type("A") == ("string", "str")

    def test_search_with_regex(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": ["apple", "banana", "cherry"]})
        manager = self.factory.create()(df)
        result = manager.search("^[ab]")
        assert result.get_num_rows() == 2

    def test_sort_values_with_nulls(self) -> None:
        import polars as pl

        df = pl.DataFrame({"A": [3, 1, None, 2]})
        manager = self.factory.create()(df)
        sorted_manager = manager.sort_values("A", descending=True)
        assert sorted_manager.data["A"].to_list()[:-1] == [
            3.0,
            2.0,
            1.0,
        ]
        last = sorted_manager.data["A"][-1]
        assert last is None or isnan(last)

        # ascending
        sorted_manager = manager.sort_values("A", descending=False)
        assert sorted_manager.data["A"].to_list()[:-1] == [
            1.0,
            2.0,
            3.0,
        ]
        last = sorted_manager.data["A"][-1]
        assert last is None or isnan(last)

    def test_get_field_types_with_datetime(self):
        import polars as pl

        data = pl.DataFrame(
            {
                "date_col": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 3),
                ],
                "datetime_col": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 3),
                ],
                "time_col": [
                    datetime.time(1, 2, 3),
                    datetime.time(4, 5, 6),
                ],
            }
        )
        manager = self.factory.create()(data)

        assert manager.get_field_type("date_col") == ("date", "date")
        assert manager.get_field_type("datetime_col") == (
            "datetime",
            "datetime[μs]",
        )
        assert manager.get_field_type("time_col") == ("time", "Time")

    @pytest.mark.skipif(
        not DependencyManager.pillow.has(), reason="pillow not installed"
    )
    def test_get_field_types_with_pil_images(self):
        import numpy as np
        import polars as pl
        from PIL import Image

        # Create a simple image
        img_array = np.zeros((10, 10, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)

        # Create a dataframe with an image column
        data = pl.DataFrame(
            {"image_col": [img, img, img], "text_col": ["a", "b", "c"]}
        )

        manager = self.factory.create()(data)

        # PIL images should be treated as objects
        assert manager.get_field_type("image_col") == ("unknown", "object")
        assert manager.get_field_type("text_col") == ("string", "str")

        as_json = manager.to_json_str()
        assert "data:image/png" in as_json

    def test_lazy_frame(self):
        import warnings

        import polars as pl

        with warnings.catch_warnings(record=True) as recorded_warnings:
            df = pl.LazyFrame(
                {
                    "A": range(100000),
                    "B": range(100000),
                }
            )
            manager = self.factory.create()(df)
            assert manager.get_num_columns() == 2
            assert manager.get_num_rows(force=False) is None
            assert manager.get_num_rows(force=True) == 100000
            assert manager.get_field_types() == [
                ("A", ("integer", "i64")),
                ("B", ("integer", "i64")),
            ]
            assert manager.take(count=10, offset=0).get_num_rows() == 10

            # This is ok and expected, since we don't support pagination for lazy frames
            with pytest.raises(TypeError):
                manager.take(count=10, offset=10)

        assert len(recorded_warnings) == 0

    def test_to_json_bigint(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [
                    20,
                    9007199254740992,
                ],  # MAX_SAFE_INTEGER and MAX_SAFE_INTEGER + 1
                "B": [
                    -20,
                    -9007199254740992,
                ],  # MIN_SAFE_INTEGER and MIN_SAFE_INTEGER - 1
            }
        )
        manager = self.factory.create()(data)
        json_data = json.loads(manager.to_json())

        # Regular integers should remain as numbers
        assert json_data[0]["A"] == 20
        assert json_data[0]["B"] == -20

        # Large integers should be converted to strings
        assert json_data[1]["A"] == "9007199254740992"
        assert json_data[1]["B"] == "-9007199254740992"
