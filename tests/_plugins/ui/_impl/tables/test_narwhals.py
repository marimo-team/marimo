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
from marimo._plugins.ui._impl.tables.narwhals_table import (
    NarwhalsTableManager,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    TableCell,
    TableCoordinate,
    TableManager,
)
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._utils.narwhals_utils import unwrap_py_scalar
from tests._data.mocks import (
    EAGER_LIBS,
    NON_EAGER_LIBS,
    DFType,
    create_dataframes,
)
from tests.mocks import snapshotter

HAS_DEPS = DependencyManager.polars.has()

snapshot = snapshotter(__file__)

SUPPORTED_LIBS: list[DFType] = [
    "pandas",
    "polars",
    # TODO: Either we can import narwhals `main` or wait for v0.1.0
    # "ibis",
    "lazy-polars",
    "pyarrow",
]


def assert_frame_equal(a: Any, b: Any) -> None:
    return a.to_dict() == b.to_dict()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestNarwhalsTableManagerFactory(unittest.TestCase):
    def get_complex_data(self) -> TableManager[Any]:
        import polars as pl

        complex_data = pl.DataFrame(
            {
                "strings": ["a", "b", "c"],
                "bool": [True, False, True],
                "int": [1, 2, 3],
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
                    datetime.timedelta(days=2),
                    datetime.timedelta(days=3),
                ],
                "mixed_list": [
                    [1, "two"],
                    [3.0, False],
                    [None, datetime.datetime(2021, 1, 1)],
                ],
            },
            strict=False,
        )

        return NarwhalsTableManager.from_dataframe(complex_data)

    def setUp(self) -> None:
        import polars as pl

        self.data = pl.DataFrame(
            {  # type: ignore
                # Integer
                "A": [1, 2, 3],
                # String
                "B": ["aaa", "b", "c"],
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
        self.manager = NarwhalsTableManager.from_dataframe(self.data)

    def test_to_csv(self) -> None:
        assert isinstance(self.manager.to_csv(), bytes)

        complex_data = self.get_complex_data()
        with pytest.raises(nw.exceptions.NarwhalsError):
            # Polars doesn't support writing nested lists to csv
            complex_data.to_csv()

    def test_to_csv_array(self) -> None:
        import numpy as np
        import polars as pl

        df = pl.DataFrame(
            {"a": [np.arange(5) for _ in range(10)]},
            schema={"a": pl.Array(pl.Int64, 5)},
        )
        manager = NarwhalsTableManager.from_dataframe(df)
        with pytest.raises(nw.exceptions.NarwhalsError):
            # Polars doesn't support writing nested lists to csv
            manager.to_csv()

    @pytest.mark.xfail(
        reason="Narwhals (polars) doesn't support writing nested lists to csv"
    )
    def test_to_csv_complex(self) -> None:
        complex_data = self.get_complex_data()
        data = complex_data.to_csv_str()
        assert isinstance(data, str)
        snapshot("narwhals.csv", data)

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

    def test_to_json_complex(self) -> None:
        complex_data = self.get_complex_data()
        data = complex_data.to_json_str()
        assert isinstance(data, str)
        snapshot("narwhals.json", data)

    def test_complex_data_field_types(self) -> None:
        complex_data = self.get_complex_data()
        field_types = complex_data.get_field_types()
        snapshot("narwhals.field_types.json", json.dumps(field_types))

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data[indices]
        assert_frame_equal(selected_manager.data, expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.shape == (0, 5)
        assert selected_manager.data.columns == ["A", "B", "C", "D", "E"]

    def test_select_columns(self) -> None:
        columns = ["A"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = self.data.select(columns)
        assert_frame_equal(selected_manager.data, expected_data)

    def test_select_cells(self) -> None:
        cells = [
            TableCoordinate(column_name="A", row_id=0),
            TableCoordinate(column_name="B", row_id=1),
            TableCoordinate(column_name="C", row_id=2),
            TableCoordinate(column_name="D", row_id=1),
            TableCoordinate(column_name="E", row_id=0),
        ]
        selected_cells = self.manager.select_cells(cells)
        expected_cells = [
            TableCell(column="A", row=0, value=1),
            TableCell(column="B", row=1, value="b"),
            TableCell(column="C", row=2, value=3.0),
            TableCell(column="D", row=1, value=False),
            TableCell(column="E", row=0, value=datetime.datetime(2021, 1, 1)),
        ]
        assert selected_cells == expected_cells

    def test_drop_columns(self) -> None:
        columns = ["A"]
        dropped_manager = self.manager.drop_columns(columns)
        expected_data = self.data.drop(columns)
        assert_frame_equal(dropped_manager.data, expected_data)

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import polars as pl

        expected_field_types = [
            ("A", ("integer", "Int64")),
            ("B", ("string", "String")),
            ("C", ("number", "Float64")),
            ("D", ("boolean", "Boolean")),
            ("E", ("datetime", "Datetime(time_unit='us', time_zone=None)")),
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
            }
        )
        expected_field_types = [
            ("A", ("integer", "Int64")),
            ("B", ("string", "String")),
            ("C", ("number", "Float64")),
            ("D", ("boolean", "Boolean")),
            ("E", ("unknown", "Object")),
            ("F", ("unknown", "Unknown")),
            ("G", ("unknown", "Object")),
            ("H", ("datetime", "Datetime(time_unit='us', time_zone=None)")),
            ("I", ("string", "String")),
            ("J", ("string", "String")),
        ]
        assert (
            NarwhalsTableManager.from_dataframe(complex_data).get_field_types()
            == expected_field_types
        )

    def test_limit(self) -> None:
        limited_manager = self.manager.take(1, 0)
        expected_data = self.data.head(1)
        assert_frame_equal(limited_manager.data, expected_data)

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

    def test_summary_integer(self) -> None:
        column = "A"
        summary = self.manager.get_stats(column)
        assert summary == ColumnStats(
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

    def test_summary_string(self) -> None:
        column = "B"
        summary = self.manager.get_stats(column)
        assert summary == ColumnStats(
            total=3,
            nulls=0,
            unique=3,
        )

    def test_summary_number(self) -> None:
        column = "C"
        summary = self.manager.get_stats(column)
        assert summary == ColumnStats(
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

    def test_summary_boolean(self) -> None:
        column = "D"
        summary = self.manager.get_stats(column)
        assert summary == ColumnStats(
            total=3,
            nulls=0,
            true=2,
            false=1,
        )

    def test_summary_datetime(self) -> None:
        column = "E"
        summary = self.manager.get_stats(column)
        assert summary == ColumnStats(
            total=3,
            nulls=0,
            min=datetime.datetime(2021, 1, 1, 0, 0),
            max=datetime.datetime(2021, 1, 3, 0, 0),
            mean=datetime.datetime(2021, 1, 2, 0, 0),
            # median=datetime.datetime(2021, 1, 2, 0, 0),
        )

    def test_summary_date(self) -> None:
        import polars as pl

        data = pl.DataFrame(
            {
                "A": [datetime.date(2021, 1, 1), datetime.date(2021, 1, 2)],
            }
        )
        manager = NarwhalsTableManager.from_dataframe(data)
        summary = manager.get_stats("A")
        assert summary == ColumnStats(
            total=2,
            nulls=0,
            min=datetime.date(2021, 1, 1),
            max=datetime.date(2021, 1, 2),
            mean=datetime.datetime(2021, 1, 1, 12, 0),
            # median=datetime.datetime(2021, 1, 1, 12, 0),
        )

    def test_summary_does_fail_on_each_column(self) -> None:
        complex_data = self.get_complex_data()
        for column in complex_data.get_column_names():
            assert complex_data.get_stats(column) is not None

    def test_sort_values(self) -> None:
        sorted_df = self.manager.sort_values("A", descending=True).data
        expected_df = self.data.sort("A", descending=True)
        assert_frame_equal(sorted_df, expected_df)

    def test_get_unique_column_values(self) -> None:
        column = "A"
        unique_values = self.manager.get_unique_column_values(column)
        assert unique_values == [1, 2, 3]

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
        manager = NarwhalsTableManager.from_dataframe(df)
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
        # TODO: Unsupported by narwhals
        assert manager.search("yyy").get_num_rows() == 0
        assert manager.search("y").get_num_rows() == 0

    def test_apply_formatting_does_not_modify_original_data(self) -> None:
        original_data = self.data.clone()
        format_mapping: FormatMapping = {
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
                "B": ["AAA", "B", "C"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
            }
        )
        assert_frame_equal(formatted_data, expected_data)

    def test_apply_formatting_with_empty_dataframe(self) -> None:
        import polars as pl

        empty_data = pl.DataFrame(
            {"A": []}
        )  # Create an empty DataFrame with a column
        manager = NarwhalsTableManager.from_dataframe(empty_data)

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
        manager_with_nan = NarwhalsTableManager.from_dataframe(data_with_nan)

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

        manager = NarwhalsTableManager.from_dataframe(data)

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
        manager = NarwhalsTableManager.from_dataframe(data)

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

        manager = NarwhalsTableManager.from_dataframe(data)

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
        manager = NarwhalsTableManager.from_dataframe(data)

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
            }
        )
        manager = NarwhalsTableManager.from_dataframe(data)

        format_mapping: FormatMapping = {
            "strings": lambda x: "MISSING" if x is None else x.upper(),
            "integers": lambda x: -100 if x is None else x * 2,
            "floats": lambda x: "---" if x is None else f"{x:.1f}",
            "booleans": lambda x: "MISSING" if x is None else str(x).upper(),
            "dates": lambda x: (
                "No Date" if x is None else x.strftime("%Y-%m-%d")
            ),
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


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [
                20,
                9007199254740992,
            ],  # MAX_SAFE_INTEGER and MAX_SAFE_INTEGER + 1
            "B": [
                -20,
                -9007199254740992,
            ],  # MIN_SAFE_INTEGER and MIN_SAFE_INTEGER - 1
        },
        include=SUPPORTED_LIBS,
    ),
)
def test_to_json_bigint(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    json_data = json.loads(manager.to_json())

    assert json_data[0]["A"] == 20
    assert json_data[0]["B"] == -20

    # Large integers should be converted to strings
    assert json_data[1]["A"] == "9007199254740992"
    assert json_data[1]["B"] == "-9007199254740992"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
            "C": [1.0, 2.0, 3.0],
        },
        include=SUPPORTED_LIBS,
    ),
)
def test_to_csv(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    assert isinstance(manager.to_csv(), bytes)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
            "C": [1.0, 2.0, 3.0],
        },
        exclude=["ibis", "duckdb"],
    ),
)
def test_to_parquet(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    assert isinstance(manager.to_parquet(), bytes)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3],
            "B": ["a", "b", "c"],
            "C": [1.0, 2.0, 3.0],
        },
    ),
)
def test_to_json(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    assert isinstance(manager.to_json(), bytes)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({"A": [1, 2, 3]}),
)
def test_to_json_format_mapping(df: Any) -> None:
    format_mapping = {"A": lambda x: x * 2}
    manager = NarwhalsTableManager.from_dataframe(df)
    json_data = manager.to_json(format_mapping)

    json_object = json.loads(json_data)
    assert json_object == [{"A": 2}, {"A": 4}, {"A": 6}]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({}, exclude=["ibis", "duckdb"]),
)
def test_empty_dataframe(df: Any) -> None:
    empty_manager = NarwhalsTableManager.from_dataframe(df)
    assert empty_manager.get_num_rows() == 0
    assert empty_manager.get_num_columns() == 0
    assert empty_manager.get_column_names() == []
    assert empty_manager.get_field_types() == []


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": [None, None, None]}, exclude=["ibis", "duckdb"]
    ),
)
def test_dataframe_with_all_null_column(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    summary = manager.get_stats("B")
    assert summary.nulls == 3
    assert summary.total == 3


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, "two", 3.0, True]}, include=["polars"], strict=False
    ),
)
def test_dataframe_with_mixed_types(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    assert manager.get_field_type("A") == ("string", "String")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_summary_all_types() -> None:
    dfs = create_dataframes(
        {
            "integer": [1, 2, 3],
            "float": [1.1, 2.2, 3.3],
            "string": ["a", "b", "c"],
            "boolean": [True, False, True],
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
            "list": [["a", "b"], ["c", "d"], ["e", "f"]],
            "null": [None, None, None],
            "duration": [
                datetime.timedelta(days=1),
                datetime.timedelta(hours=2),
                datetime.timedelta(minutes=3),
            ],
        },
        exclude=["duckdb", "ibis"],
    )

    error_count = 0
    for df in dfs:
        manager: NarwhalsTableManager[Any] = (
            NarwhalsTableManager.from_dataframe(df)
        )

        for column in manager.get_column_names():
            try:
                summary = manager._get_stats_internal(column)
                assert isinstance(summary, ColumnStats)
                assert summary.total == 3
            except Exception as e:
                error_count += 1
                print(f"Error getting summary for column {column}: {e}")

    assert error_count == 0, (
        f"Got {error_count} errors when getting column summaries"
    )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": ["apple", "banana", "cherry"]}, exclude=["ibis", "duckdb"]
    ),
)
def test_search_with_regex(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    result = manager.search("^[ab]")
    assert result.get_num_rows() == 2


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({"A": [3, 1, None, 2]}, exclude=["ibis", "duckdb"]),
)
def test_sort_values_with_nulls(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    sorted_manager: NarwhalsTableManager[Any] = manager.sort_values(
        "A", descending=True
    )
    assert sorted_manager.as_frame()["A"].head(3).to_list() == [3, 2, 1]
    last = unwrap_py_scalar(sorted_manager.as_frame()["A"].tail(1).item())
    assert last is None or isnan(last)

    # ascending
    sorted_manager = manager.sort_values("A", descending=False)
    assert sorted_manager.as_frame()["A"].head(3).to_list() == [1, 2, 3]
    last = unwrap_py_scalar(sorted_manager.as_frame()["A"].tail(1).item())
    assert last is None or isnan(last)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3, 4],  # Integer
            "B": ["a", "b", "c", "d"],  # String
            "C": [
                datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
                datetime.datetime(2021, 1, 2, tzinfo=datetime.timezone.utc),
                datetime.datetime(2021, 1, 3, tzinfo=datetime.timezone.utc),
                datetime.datetime(2021, 1, 4, tzinfo=datetime.timezone.utc),
            ],  # Datetime with timezone
            "D": [1.1, 2.2, 3.3, 4.4],  # Float
            "E": [True, False, True, False],  # Boolean
            "F": [None, "b", "c", None],  # Mixed with nulls
            "G": [
                datetime.date(2021, 1, 1),
                datetime.date(2021, 1, 2),
                datetime.date(2021, 1, 3),
                datetime.date(2021, 1, 4),
            ],  # Date
            "H": [10_000, -5_000, 0, 999_999],  # Large integers
            "I": [
                float("inf"),
                float("-inf"),
                float("nan"),
                1.0,
            ],  # Special floats
            "J": ["", "  ", "test", "\t\n"],  # Whitespace strings
            "K": [b"bytes1", b"bytes2", b"bytes3", b"bytes4"],  # Bytes
        },
        exclude=NON_EAGER_LIBS,
    ),
)
def test_get_sample_values(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)

    # Integer
    sample_values = manager.get_sample_values("A")
    assert sample_values == [1, 2, 3]

    # String
    sample_values = manager.get_sample_values("B")
    assert sample_values == ["a", "b", "c"]

    # Datetime with timezone
    sample_values = manager.get_sample_values("C")
    assert (
        sample_values
        == [
            "2021-01-01 00:00:00",
            "2021-01-02 00:00:00",
            "2021-01-03 00:00:00",
        ]
        # Polars on windows is missing timezone info
        or sample_values == []
    )

    # Float
    sample_values = manager.get_sample_values("D")
    assert sample_values == [1.1, 2.2, 3.3]

    # Boolean
    sample_values = manager.get_sample_values("E")
    assert sample_values == [True, False, True]

    # Mixed with nulls
    sample_values = manager.get_sample_values("F")
    assert sample_values == ["None", "b", "c"]

    # Date
    sample_values = manager.get_sample_values("G")
    # Polars on windows is missing timezone info
    assert sample_values == [
        "2021-01-01",
        "2021-01-02",
        "2021-01-03",
    ] or sample_values == [
        "2021-01-01 00:00:00",
        "2021-01-02 00:00:00",
        "2021-01-03 00:00:00",
    ]

    # Large integers
    sample_values = manager.get_sample_values("H")
    assert sample_values == [10_000, -5_000, 0]

    # Special floats
    sample_values = manager.get_sample_values("I")
    assert len(sample_values) == 3

    # Whitespace strings
    sample_values = manager.get_sample_values("J")
    assert sample_values == ["", "  ", "test"]

    # Bytes
    sample_values = manager.get_sample_values("K")
    assert sample_values == ["b'bytes1'", "b'bytes2'", "b'bytes3'"]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3, 3, 3, None, None],
            "B": [4, 5, 6, 6, 6, None, None],
        },
        include=SUPPORTED_LIBS,
    ),
)
def test_calculate_top_k_rows(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    result = manager.calculate_top_k_rows("A", 10)
    normalized_result = _normalize_result(result)
    assert normalized_result == [(3, 3), (None, 2), (1, 1), (2, 1)]

    # Test with limit
    result = manager.calculate_top_k_rows("A", 2)
    normalized_result = _normalize_result(result)
    assert normalized_result == [(3, 3), (None, 2)]


@pytest.mark.skipif(
    not DependencyManager.ibis.has(),
    reason="Ibis not installed",
)
def test_calculate_top_k_rows_metadata_only_frame() -> None:
    import ibis

    df = ibis.memtable({"A": [1, 2, 3, 3, None, None]})
    manager = NarwhalsTableManager.from_dataframe(df)
    result = manager.calculate_top_k_rows("A", 10)
    assert result == [(None, 2), (3, 2), (1, 1), (2, 1)]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [[1, 2], [1, 2], [3, 4]]}, include=["polars", "pandas"]
    ),
)
def test_calculate_top_k_rows_nested_lists(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    result = manager.calculate_top_k_rows("A", 10)
    assert result == [([1, 2], 2), ([3, 4], 1)]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [{"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 3, "b": 4}]},
        include=["polars", "pandas"],
    ),
)
def test_calculate_top_k_rows_dicts(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    result = manager.calculate_top_k_rows("A", 10)
    assert result == [({"a": 1, "b": 2}, 2), ({"a": 3, "b": 4}, 1)]


def _normalize_result(result: list[tuple[Any, int]]) -> list[tuple[Any, int]]:
    """Normalize None and NaN values for comparison."""
    return [
        (None if val is None or isnan(val) else val, count)
        for val, count in result
    ]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3, 4],  # Integer
            "B": ["a", "b", "c", "d"],  # String
        },
        exclude=EAGER_LIBS,
    ),
)
def test_get_sample_values_with_non_lazy_df(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    sample_values = manager.get_sample_values("A")
    assert sample_values == []
    sample_values = manager.get_sample_values("B")
    assert sample_values == []


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3, 4], "B": ["a", "b", "c", "d"]},
        include=["ibis", "duckdb"],
    ),
)
def test_get_sample_values_with_metadata_only_frame(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    sample_values = manager.get_sample_values("A")
    assert sample_values == []
    sample_values = manager.get_sample_values("B")
    assert sample_values == []


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_sample_values_returns_primitives() -> None:
    """Test that get_sample_values always returns primitive types."""
    import polars as pl

    def is_primitive(value: Any) -> bool:
        return isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
                type(None),
                datetime.datetime,
                datetime.date,
            ),
        )

    class Enum:
        A = "a"
        B = "b"
        C = "c"

    # Create a DataFrame with various types including categorical/enum-like columns
    df = pl.DataFrame(
        {
            "category": pl.Series(["A", "B", "C"], dtype=pl.Categorical),
            "mixed": pl.Series(["str", "123", "45.67"]),
            "list": pl.Series([[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
            "dict": pl.Series(
                [
                    {"a": 1, "b": Enum.A},
                    {"c": 3, "d": Enum.B},
                    {"e": 5, "f": Enum.C},
                ]
            ),
            "enum": pl.Series([Enum.A, Enum.B, Enum.C]),
            "dates": [
                datetime.datetime(2021, 1, 1),
                datetime.datetime(2021, 1, 2),
                datetime.datetime(2021, 1, 3),
            ],
        },
    )

    manager: NarwhalsTableManager[Any] = NarwhalsTableManager.from_dataframe(
        df
    )

    # Verify all values are primitives
    for column in df.columns:
        values = manager.get_sample_values(column)
        for val in values:
            assert is_primitive(val), (
                f"Column {column} returned non-primitive or non-datetime value: {val} of type {type(val)}"
            )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({f"col_{i}": [1, 2, 3] for i in range(2000)}),
)
def test_get_field_types_with_many_columns_is_performant(df: Any) -> None:
    import time

    manager = get_table_manager(df)

    start_time = time.time()
    manager.get_field_types()
    end_time = time.time()

    # This can be slow if get_field_types is not optimized.
    # https://github.com/marimo-team/marimo/issues/3107
    total_ms = (end_time - start_time) * 1000
    assert total_ms < 500, (
        f"Total time: {total_ms}ms for {df.shape[1]} columns with {type(df)}"
    )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({"name": ["Alice", "Eve", None], "age": [25, 35, None]}),
)
def test_calculate_top_k_rows_caching(df: Any) -> None:
    manager = NarwhalsTableManager.from_dataframe(df)
    """Test that calculate_top_k_rows caching works correctly."""
    # First call should compute the result
    result1 = manager.calculate_top_k_rows("name", 10)

    # Second call with same args should use cache and return same object
    result2 = manager.calculate_top_k_rows("name", 10)
    assert result1 is result2

    # Different k value should compute new result
    result3 = manager.calculate_top_k_rows("name", 5)
    assert result3 is not result1

    # Different column name should compute new result
    result4 = manager.calculate_top_k_rows("age", 10)
    assert result4 is not result1


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"name": ["Alice", "Eve", None], "age": [25, 35, None]},
        exclude=["ibis", "duckdb"],
    ),
)
def test_calculate_top_k_rows_cache_invalidation(df: Any) -> None:
    """Test that cache is properly invalidated when data changes."""
    manager = NarwhalsTableManager.from_dataframe(df)

    # Initial calculation
    result1 = manager.calculate_top_k_rows("name", 2)

    # Modify the data
    new_data = nw.from_dict(
        {
            "name": ["Alice", "Alice", "Eve", "Bob", None],
        },
        backend=nw.get_native_namespace(manager.as_frame()),
    )

    # Create a new manager with the new data
    manager = NarwhalsTableManager.from_dataframe(new_data)

    # New calculation should be performed and return different result
    result2 = manager.calculate_top_k_rows("name", 2)
    assert result2 is not result1  # Different result due to data change

    # Verify the actual results are different
    assert result1 != result2
