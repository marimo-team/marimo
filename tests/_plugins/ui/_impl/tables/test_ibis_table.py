from __future__ import annotations

import datetime
import json
import unittest
from typing import Any

import pytest

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.ibis_table import (
    IbisTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from tests.mocks import snapshotter

HAS_DEPS = DependencyManager.ibis.has()

snapshot = snapshotter(__file__)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestIbisTableManagerFactory(unittest.TestCase):
    def get_complex_data(self) -> TableManager[Any]:
        import ibis

        complex_data = ibis.memtable(
            {
                "strings": ["a", "b", "c"],
                "bool": [True, False, True],
                "int": [1, 2, 3],
                "float": [1.0, 2.0, 3.0],
                "date": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 2),
                    datetime.date(2021, 1, 3),
                ],
                "datetime": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                ],
                "time": [
                    datetime.time(1, 2, 3),
                    datetime.time(4, 5, 6),
                    datetime.time(7, 8, 9),
                ],
                "nulls": [None, "data", None],
            }
        )
        return self.factory.create()(complex_data)

    def setUp(self) -> None:
        import ibis

        self.factory = IbisTableManagerFactory()
        self.data = ibis.memtable(
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
            }
        )
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        assert self.factory.package_name() == "ibis"

    def test_to_csv(self) -> None:
        assert isinstance(self.manager.to_csv(), bytes)

        complex_data = self.get_complex_data()
        data = complex_data.to_csv()
        assert isinstance(data, bytes)
        snapshot("ibis.csv", data.decode("utf-8"))

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

        complex_data = self.get_complex_data()
        data = complex_data.to_json()
        assert isinstance(data, bytes)
        snapshot("ibis.json", data.decode("utf-8"))

    def test_complex_data_field_types(self) -> None:
        complex_data = self.get_complex_data()
        field_types = complex_data.get_field_types()
        snapshot("ibis.field_types.json", json.dumps(field_types))

    def test_select_rows(self) -> None:
        import ibis

        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data.filter(ibis.row_number().isin(indices))
        assert selected_manager.data.to_pandas().equals(
            expected_data.to_pandas()
        )

    def test_select_columns(self) -> None:
        columns = ["A"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = self.data.select(columns)
        assert selected_manager.data.to_pandas().equals(
            expected_data.to_pandas()
        )

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a table")

    def test_get_field_types(self) -> None:
        expected_field_types = [
            ("A", ("integer", "int64")),
            ("B", ("string", "string")),
            ("C", ("number", "float64")),
            ("D", ("boolean", "boolean")),
            ("E", ("datetime", "timestamp")),
        ]
        assert self.manager.get_field_types() == expected_field_types

    def test_limit(self) -> None:
        limited_manager = self.manager.take(1, 0)
        expected_data = self.data.limit(1)
        assert limited_manager.data.to_pandas().equals(
            expected_data.to_pandas()
        )

    def test_take(self) -> None:
        assert (
            self.manager.take(1, 0).select_columns(["A"]).to_json()
            == b'[{"A":1}]'
        )
        assert (
            self.manager.take(2, 0).select_columns(["A"]).to_json()
            == b'[{"A":1},{"A":2}]'
        )
        assert (
            self.manager.take(2, 1).select_columns(["A"]).to_json()
            == b'[{"A":2},{"A":3}]'
        )
        assert (
            self.manager.take(2, 2).select_columns(["A"]).to_json()
            == b'[{"A":3}]'
        )

    def test_take_zero(self) -> None:
        limited_manager = self.manager.take(0, 0)
        assert limited_manager.data.count().execute() == 0

    def test_take_negative(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(-1, 0)

    def test_take_negative_offset(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(1, -1)

    def test_take_out_of_bounds(self) -> None:
        # Too large of page
        assert self.manager.take(10, 0).data.count().execute() == 3
        assert self.data.count().execute() == 3

        # Too large of page and offset
        assert self.manager.take(10, 10).data.count().execute() == 0

    def test_summary_integer(self) -> None:
        column = "A"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            min=1,
            max=3,
            mean=2.0,
            median=2.0,
            std=1.0,
        )

    def test_summary_string(self) -> None:
        column = "B"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
        )

    def test_sort_values(self) -> None:
        import ibis

        sorted_manager = self.manager.sort_values("A", descending=True)
        expected_df = self.data.order_by(ibis.desc("A"))
        assert sorted_manager.data.to_pandas().equals(expected_df.to_pandas())

    def test_get_unique_column_values(self) -> None:
        column = "A"
        unique_values = self.manager.get_unique_column_values(column)
        assert sorted(unique_values) == [1, 2, 3]

    def test_get_sample_values(self) -> None:
        sample_values = self.manager.get_sample_values("A")
        assert sample_values == []

    def test_search(self) -> None:
        import ibis

        df = ibis.memtable(
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

    @pytest.mark.xfail(
        reason="column formatting is not supported in ibis",
    )
    def test_apply_formatting(self) -> None:
        import ibis

        from marimo._plugins.ui._impl.tables.format import FormatMapping

        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
        }

        formatted_data = self.manager.apply_formatting(format_mapping)
        expected_data = ibis.memtable(
            {
                "A": [2, 4, 6],
                "B": ["A", "B", "C"],
                "C": ["1.00", "2.00", "3.00"],
                "D": [False, True, False],
                "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
            }
        )
        assert formatted_data.to_pandas().equals(expected_data.to_pandas())

    def test_empty_table(self) -> None:
        import ibis

        empty_table = ibis.memtable({"A": []})
        empty_manager = self.factory.create()(empty_table)
        assert empty_manager.get_num_rows() == 0

    def test_table_with_all_null_column(self) -> None:
        import ibis

        table = ibis.memtable({"A": [1, 2, 3], "B": [None, None, None]})
        manager = self.factory.create()(table)
        summary = manager.get_summary("B")
        assert summary.nulls == 3
        assert summary.total == 3

    def test_table_with_mixed_types(self) -> None:
        import ibis

        table = ibis.memtable({"A": [1, "two", 3.0, True]})
        manager = self.factory.create()(table)
        assert manager.get_field_type("A") == ("unknown", "unknown")

    def test_search_with_regex(self) -> None:
        import ibis

        table = ibis.memtable({"A": ["apple", "banana", "cherry"]})
        manager = self.factory.create()(table)
        result = manager.search("^[ab]")
        assert result.get_num_rows() == 2

    def test_sort_values_with_nulls(self) -> None:
        import ibis
        import numpy as np

        table = ibis.memtable({"A": [3, 1, None, 2]})
        manager = self.factory.create()(table)

        # Descending true
        sorted_manager = manager.sort_values("A", descending=True)
        sorted_data = sorted_manager.data.to_pandas()["A"].tolist()
        assert sorted_data[0:3] == [
            3.0,
            2.0,
            1.0,
        ]
        assert np.isnan(sorted_data[3])

        # Descending false
        sorted_manager = manager.sort_values("A", descending=False)
        sorted_data = sorted_manager.data.to_pandas()["A"].tolist()
        assert sorted_data[0:3] == [
            1.0,
            2.0,
            3.0,
        ]
        assert np.isnan(sorted_data[3])
