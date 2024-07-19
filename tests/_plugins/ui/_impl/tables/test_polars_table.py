from __future__ import annotations

import datetime
import json
import unittest
from typing import Any

import pytest

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from tests.mocks import snapshotter

HAS_DEPS = DependencyManager.has_polars()

snapshot = snapshotter(__file__)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPolarsTableManagerFactory(unittest.TestCase):
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
                "struct": [
                    {"a": 1, "b": 2},
                    {"a": 3, "b": 4},
                    {"a": 5, "b": 6},
                ],
                "list": [[1, 2], [3, 4], [5, 6]],
                "array": [[1, 2, 3], [4], []],
                "nulls": [None, "data", None],
                "categorical": pl.Series(["cat", "dog", "mouse"]).cast(
                    pl.Categorical
                ),
                # raises:
                #   pyo3_runtime.PanicException:
                #   not yet implemented: Writing Time64(Nanosecond) to JSON
                # "time": [
                #     datetime.time(12, 30),
                #     datetime.time(13, 45),
                #     datetime.time(14, 15),
                # ],
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

        complex_data = self.get_complex_data()
        data = complex_data.to_csv()
        assert isinstance(data, bytes)
        snapshot("polars.csv", data.decode("utf-8"))

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

        complex_data = self.get_complex_data()
        data = complex_data.to_json()
        assert isinstance(data, bytes)
        snapshot("polars.json", data.decode("utf-8"))

    def test_complex_data_field_types(self) -> None:
        complex_data = self.get_complex_data()
        field_types = complex_data.get_field_types()
        snapshot("polars.field_types.json", json.dumps(field_types))

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data[indices]
        assert selected_manager.data.equals(expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.shape == (0, 5)
        assert selected_manager.data.columns == ["A", "B", "C", "D", "E"]

    def test_select_columns(self) -> None:
        columns = ["A"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = self.data.select(columns)
        assert selected_manager.data.equals(expected_data)

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import polars as pl

        expected_field_types = {
            "A": ("integer", "i64"),
            "B": ("string", "str"),
            "C": ("number", "f64"),
            "D": ("boolean", "bool"),
            "E": ("date", "datetime[μs]"),
        }
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
        expected_field_types = {
            "A": ("integer", "i64"),
            "B": ("string", "str"),
            "C": ("number", "f64"),
            "D": ("boolean", "bool"),
            "E": ("unknown", "object"),
            "F": ("unknown", "null"),
            "G": ("unknown", "object"),
            "H": ("date", "datetime[μs]"),
            "I": ("string", "str"),
            "J": ("string", "str"),
        }
        assert (
            self.factory.create()(complex_data).get_field_types()
            == expected_field_types
        )

    def test_limit(self) -> None:
        limited_manager = self.manager.limit(1)
        expected_data = self.data.head(1)
        assert limited_manager.data.equals(expected_data)

    def test_summary_integer(self) -> None:
        column = "A"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
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
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=3,
        )

    def test_summary_number(self) -> None:
        column = "C"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
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
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            true=2,
            false=1,
        )

    def test_summary_date(self) -> None:
        column = "E"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            min=datetime.datetime(2021, 1, 1, 0, 0),
            max=datetime.datetime(2021, 1, 3, 0, 0),
            mean=datetime.datetime(2021, 1, 2, 0, 0),
            median=datetime.datetime(2021, 1, 2, 0, 0),
        )

    def test_sort_values(self) -> None:
        sorted_df = self.manager.sort_values("A", descending=True).data
        expected_df = self.data.sort("A", descending=True)
        assert sorted_df.equals(expected_df)

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
            }
        )
        manager = self.factory.create()(df)
        assert manager.search("foo").get_num_rows() == 1
        assert manager.search("a").get_num_rows() == 2
        assert manager.search("true").get_num_rows() == 2
        assert manager.search("food").get_num_rows() == 0
