from __future__ import annotations

import datetime
import json
import unittest
from typing import Any

import pytest

from marimo._data.models import BinValue, ColumnStats
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.format import FormatMapping
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
        data = complex_data.to_csv_str()
        assert isinstance(data, str)
        snapshot("ibis.csv", data)

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

        complex_data = self.get_complex_data()
        data = complex_data.to_json_str()
        assert isinstance(data, str)
        snapshot("ibis.json", data)

    def test_to_json_format_mapping(self) -> None:
        import ibis

        table = ibis.memtable({"int": [1, 2, 3]}, schema={"int": "int64"})
        data = self.factory.create()(table)

        format_mapping: FormatMapping = {"int": lambda x: x * 2}
        json_data = data.to_json_str(format_mapping)

        json_object = json.loads(json_data)
        assert json_object == [{"int": 2}, {"int": 4}, {"int": 6}]

    def test_complex_data_field_types(self) -> None:
        complex_data = self.get_complex_data()
        field_types = complex_data.get_field_types()
        snapshot("ibis.field_types.json", json.dumps(field_types))

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        assert selected_manager.data.to_dict(as_series=False) == {
            "A": [1, 3],
            "B": ["a", "c"],
            "C": [1.0, 3.0],
            "D": [True, True],
            "E": [
                datetime.datetime(2021, 1, 1),
                datetime.datetime(2021, 1, 3),
            ],
        }

    def test_select_columns(self) -> None:
        columns = ["A"]
        selected_manager = self.manager.select_columns(columns)
        assert selected_manager.data.collect().to_dict(as_series=False) == {
            "A": [1, 2, 3],
        }

    def test_drop_columns(self) -> None:
        columns = ["A"]
        dropped_manager = self.manager.drop_columns(columns)
        assert dropped_manager.data.columns == ["B", "C", "D", "E"]

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
        assert limited_manager.get_num_rows() == 1

    def test_take(self) -> None:
        def as_list(df: Any) -> list[Any]:
            return df.to_dict(as_series=False)["A"]

        assert as_list(self.manager.take(1, 0).data.collect()) == [1]
        assert as_list(self.manager.take(2, 0).data.collect()) == [
            1,
            2,
        ]

        assert as_list(self.manager.take(2, 1).select_columns(["A"]).data) == [
            2,
            3,
        ]

        assert as_list(self.manager.take(2, 2).select_columns(["A"]).data) == [
            3,
        ]

    def test_to_parquet(self) -> None:
        assert isinstance(self.manager.to_parquet(), bytes)

    def test_take_zero(self) -> None:
        limited_manager = self.manager.take(0, 0)
        assert limited_manager.data.collect().to_dict(as_series=False) == {
            "A": [],
            "B": [],
            "C": [],
            "D": [],
            "E": [],
        }

    def test_take_negative(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(-1, 0)

    def test_take_negative_offset(self) -> None:
        with pytest.raises(ValueError):
            self.manager.take(1, -1)

    def test_take_out_of_bounds(self) -> None:
        # Too large of page
        assert self.manager.take(10, 0).get_num_rows() == 3
        assert self.manager.get_num_rows() == 3

        # Too large of page and offset
        assert self.manager.take(10, 10).get_num_rows() == 0

    def test_stats_integer(self) -> None:
        column = "A"
        stats = self.manager.get_stats(column)
        assert stats == ColumnStats(
            total=3,
            nulls=0,
            min=1,
            max=3,
            mean=2.0,
            median=2.0,
            unique=3,
            std=1.0,
        )

    def test_stats_string(self) -> None:
        column = "B"
        stats = self.manager.get_stats(column)
        assert stats == ColumnStats(
            total=3,
            nulls=0,
            unique=3,
        )

    def test_sort_values(self) -> None:
        sorted_manager = self.manager.sort_values("A", descending=True)
        assert sorted_manager.data.collect().to_dict(as_series=False) == {
            "A": [3, 2, 1],
            "B": ["c", "b", "a"],
            "C": [3.0, 2.0, 1.0],
            "D": [True, False, True],
            "E": [
                datetime.datetime(2021, 1, 3),
                datetime.datetime(2021, 1, 2),
                datetime.datetime(2021, 1, 1),
            ],
        }

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

    def test_apply_formatting(self) -> None:
        format_mapping: FormatMapping = {
            "A": lambda x: x * 2,
            "B": lambda x: x.upper(),
            "C": lambda x: f"{x:.2f}",
            "D": lambda x: not x,
            "E": lambda x: x.strftime("%Y-%m-%d"),
        }

        formatted_data = self.manager.apply_formatting(format_mapping)
        assert formatted_data.data.to_dict(as_series=False) == {
            "A": [2, 4, 6],
            "B": ["A", "B", "C"],
            "C": ["1.00", "2.00", "3.00"],
            "D": [False, True, False],
            "E": ["2021-01-01", "2021-01-02", "2021-01-03"],
        }

    def test_empty_table(self) -> None:
        import ibis

        empty_table = ibis.memtable({"A": []})
        empty_manager = self.factory.create()(empty_table)
        assert empty_manager.get_num_rows() == 0

    def test_table_with_all_null_column(self) -> None:
        import ibis

        table = ibis.memtable({"A": [1, 2, 3], "B": [None, None, None]})
        manager = self.factory.create()(table)
        stats = manager.get_stats("B")
        assert stats.nulls == 3
        assert stats.total == 3

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

        table = ibis.memtable({"A": [3, 1, None, 2]})
        manager = self.factory.create()(table)

        # Descending true
        sorted_manager = manager.sort_values("A", descending=True)
        sorted_data = sorted_manager.data.collect().to_dict(as_series=False)[
            "A"
        ]
        assert sorted_data == [
            3.0,
            2.0,
            1.0,
            None,
        ]

        # Descending false
        sorted_manager = manager.sort_values("A", descending=False)
        sorted_data = sorted_manager.data.collect().to_dict(as_series=False)[
            "A"
        ]
        assert sorted_data == [
            1.0,
            2.0,
            3.0,
            None,
        ]

    def test_calculate_top_k_rows(self) -> None:
        import ibis

        table = ibis.memtable({"A": [2, 3, 3], "B": ["a", "b", "c"]})
        manager = self.factory.create()(table)
        result = manager.calculate_top_k_rows("A", 10)
        assert result == [(3, 2), (2, 1)]

        # Test equal counts with k limit
        table = ibis.memtable({"A": [1, 1, 2, 2, 2, 3]})
        manager = self.factory.create()(table)
        result = manager.calculate_top_k_rows("A", 2)
        assert result == [(2, 3), (1, 2)]

    def test_calculate_top_k_rows_nulls(self) -> None:
        import ibis

        # Test single null value
        table = ibis.memtable({"A": [3, None, None]})
        manager = self.factory.create()(table)
        result = manager.calculate_top_k_rows("A", 10)
        assert result == [
            (None, 2),
            (3, 1),
        ]

        # Test all null values
        table = ibis.memtable({"A": [None, None, None]})
        manager = self.factory.create()(table)
        result = manager.calculate_top_k_rows("A", 10)
        assert result == [(None, 3)]

        # Test mixed values with nulls
        table = ibis.memtable({"A": [1, None, 2, 2, None, 3, None]})
        manager = self.factory.create()(table)
        result = manager.calculate_top_k_rows("A", 10)
        assert len(result) == 4
        assert result[0][0] is None
        assert result[0][1] == 3
        assert set(result[1:]) == {(1, 1), (2, 2), (3, 1)}

    def test_calculate_top_k_rows_nested_lists(self) -> None:
        import ibis

        # Test nested lists
        table = ibis.memtable({"A": [[1, 2], [1, 2], [3, 4]]})
        manager = self.factory.create()(table)
        result = manager.calculate_top_k_rows("A", 10)
        assert result == [([1, 2], 2), ([3, 4], 1)]

    def test_calculate_top_k_rows_dicts(self) -> None:
        import ibis

        # Test dicts
        table = ibis.memtable(
            {"A": [{"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 3, "b": 4}]}
        )
        manager = self.factory.create()(table)
        result = manager.calculate_top_k_rows("A", 10)
        assert result == [({"a": 1, "b": 2}, 2), ({"a": 3, "b": 4}, 1)]

    def test_get_bin_values(self) -> None:
        import ibis

        table = ibis.memtable(
            {
                "int": [3, 5, -1, 6, 8, 10, 11, 23, 25],
                "float": [3.2, 4.8, -1.0, 8.0, 7.5, 9.5, 11.0, None, 24.8],
                "string": ["a", "b", "c", "d", "e", "f", "g", "h", "i"],
            }
        )
        manager = self.factory.create()(table)
        result = manager.get_bin_values("int", 5)
        assert result == [
            BinValue(bin_start=-1.0, bin_end=4.2, count=2),
            BinValue(bin_start=4.2, bin_end=9.4, count=3),
            BinValue(bin_start=9.4, bin_end=pytest.approx(14.6), count=2),
            BinValue(bin_start=pytest.approx(14.6), bin_end=19.8, count=0),
            BinValue(bin_start=19.8, bin_end=25.0, count=2),
        ]

        result = manager.get_bin_values("float", 3)
        print(result)
        assert result == [
            BinValue(bin_start=-1.0, bin_end=7.6, count=4),
            BinValue(bin_start=7.6, bin_end=16.2, count=3),
            BinValue(bin_start=16.2, bin_end=24.8, count=1),
        ]

        # Not supported for other column types
        result = manager.get_bin_values("string", 3)
        assert result == []


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestTemporalColSummaries(unittest.TestCase):
    """Tests are quite flaky with exact values, so we test length and counts"""

    manager: TableManager[Any]

    def setUp(self) -> None:
        import ibis

        self.factory = IbisTableManagerFactory()
        self.data = ibis.memtable(
            {
                "date": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 2),
                    datetime.date(2021, 1, 3),
                    datetime.date(2021, 1, 4),
                    datetime.date(2021, 1, 5),
                ],
                "datetime": [
                    datetime.datetime(2021, 1, 1),
                    datetime.datetime(2021, 1, 2),
                    datetime.datetime(2021, 1, 3),
                    datetime.datetime(2021, 1, 4),
                    datetime.datetime(2021, 1, 5),
                ],
                "datetime_with_tz": [
                    datetime.datetime(
                        2021, 1, 1, tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime(
                        2021, 1, 2, tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime(
                        2021, 1, 3, tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime(
                        2021, 1, 4, tzinfo=datetime.timezone.utc
                    ),
                    datetime.datetime(
                        2021, 1, 5, tzinfo=datetime.timezone.utc
                    ),
                ],
                "time": [
                    datetime.time(1, 2, 3),
                    datetime.time(4, 5, 6),
                    datetime.time(7, 8, 9),
                    datetime.time(10, 11, 12),
                    datetime.time(13, 14, 15),
                ],
                "dates_multiple": [
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 1),
                    datetime.date(2021, 1, 1),
                ],
                "timedelta": [
                    datetime.timedelta(days=1),
                    datetime.timedelta(days=2),
                    datetime.timedelta(days=3),
                    datetime.timedelta(days=4),
                    datetime.timedelta(days=5),
                ],
            }
        )
        self.manager = self.factory.create()(self.data)

    def test_date_column(self) -> None:
        bin_values = self.manager.get_bin_values("date", 3)

        assert len(bin_values) == 3
        assert bin_values[0].count == 2
        assert bin_values[1].count == 1
        assert bin_values[2].count == 2

    def test_datetime_column(self) -> None:
        bin_values = self.manager.get_bin_values("datetime", 3)

        assert len(bin_values) == 3
        assert bin_values[0].count == 2
        assert bin_values[1].count == 1
        assert bin_values[2].count == 2

    def test_time_column(self) -> None:
        bin_values = self.manager.get_bin_values("time", 3)

        assert len(bin_values) == 3
        assert bin_values[0].count == 2
        assert bin_values[1].count == 1
        assert bin_values[2].count == 2

    def test_dates_multiple(self) -> None:
        bin_values = self.manager.get_bin_values("dates_multiple", 3)
        assert len(bin_values) == 1
        assert bin_values[0].count == 5

    @pytest.mark.xfail(reason="datetime with tz is not supported")
    def test_datetime_with_tz(self) -> None:
        bin_values = self.manager.get_bin_values("datetime_with_tz", 3)
        assert bin_values == [
            BinValue(
                bin_start=datetime.datetime(
                    2021, 1, 1, 8, 0, 0, tzinfo=datetime.timezone.utc
                ),
                bin_end=datetime.datetime(
                    2021, 1, 2, 16, 0, 0, tzinfo=datetime.timezone.utc
                ),
                count=2,
            ),
            BinValue(
                bin_start=datetime.datetime(
                    2021, 1, 2, 16, 0, 0, tzinfo=datetime.timezone.utc
                ),
                bin_end=datetime.datetime(
                    2021, 1, 4, 0, 0, 0, tzinfo=datetime.timezone.utc
                ),
                count=1,
            ),
            BinValue(
                bin_start=datetime.datetime(
                    2021, 1, 4, 0, 0, 0, tzinfo=datetime.timezone.utc
                ),
                bin_end=datetime.datetime(
                    2021, 1, 5, 8, 0, 0, tzinfo=datetime.timezone.utc
                ),
                count=2,
            ),
        ]

    @pytest.mark.xfail(reason="timedelta is not supported")
    def test_timedelta_column(self) -> None:
        bin_values = self.manager.get_bin_values("timedelta", 3)
        assert bin_values == [
            BinValue(
                bin_start=datetime.timedelta(days=1),
                bin_end=datetime.timedelta(days=2),
                count=2,
            )
        ]
        result = self.manager.calculate_top_k_rows("A", 2)
        assert result == [(None, 3), (2, 2)]
