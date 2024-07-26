from __future__ import annotations

import datetime
import unittest

import pytest

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.pandas_table import (
    PandasTableManagerFactory,
)

HAS_DEPS = DependencyManager.has_pandas()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPandasTableManager(unittest.TestCase):
    def setUp(self) -> None:
        import pandas as pd

        self.factory = PandasTableManagerFactory()
        self.data = pd.DataFrame(
            {
                # Integer
                "A": [1, 2, 3],
                # String
                "B": ["a", "b", " b"],
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
                # List
                "F": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            }
        )
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        assert self.factory.package_name() == "pandas"

    def test_to_csv(self) -> None:
        expected_csv = self.data.to_csv(index=False).encode("utf-8")
        assert self.manager.to_csv() == expected_csv

    def test_to_json(self) -> None:
        expected_json = self.data.to_json(orient="records").encode("utf-8")
        assert self.manager.to_json() == expected_json

    def test_select_rows(self) -> None:
        import pandas as pd

        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data.iloc[indices]
        pd.testing.assert_frame_equal(selected_manager.data, expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.shape == (0, 6)

    def test_select_columns(self) -> None:
        import pandas as pd

        columns = ["A", "C"]
        selected_manager = self.manager.select_columns(columns)
        expected_data = self.data[columns]
        pd.testing.assert_frame_equal(selected_manager.data, expected_data)

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_get_row_headers_date_index(self) -> None:
        import pandas as pd

        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
                "C": [7, 8, 9],
            },
            index=pd.to_datetime(["2021-01-01", "2021-06-01", "2021-09-01"]),
        )
        manager = self.factory.create()(data)
        assert manager.get_row_headers() == [""]

    def test_get_row_headers_timedelta_index(self) -> None:
        import pandas as pd

        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
                "C": [7, 8, 9],
            },
            index=pd.to_timedelta(["1 days", "2 days", "3 days"]),
        )
        manager = self.factory.create()(data)
        assert manager.get_row_headers() == [""]

    def test_get_row_headers_multi_index(self) -> None:
        import pandas as pd

        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
                "C": [7, 8, 9],
            },
            index=pd.MultiIndex.from_tuples(
                [("a", 1), ("b", 2), ("c", 3)], names=["X", "Y"]
            ),
        )
        manager = self.factory.create()(data)
        assert manager.get_row_headers() == ["X", "Y"]

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import pandas as pd

        expected_field_types = {
            "A": ("integer", "int64"),
            "B": ("string", "object"),
            "C": ("number", "float64"),
            "D": ("boolean", "bool"),
            "E": ("date", "datetime64[ns]"),
            "F": ("string", "object"),
        }
        assert self.manager.get_field_types() == expected_field_types

        complex_data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
                "C": [1.0, 2.0, 3.0],
                "D": [True, False, True],
                "E": [1 + 2j, 3 + 4j, 5 + 6j],
                "F": [None, None, None],
                "G": [set([1, 2]), set([3, 4]), set([5, 6])],
                "H": [
                    pd.Timestamp("2021-01-01"),
                    pd.Timestamp("2021-01-02"),
                    pd.Timestamp("2021-01-03"),
                ],
                "I": [
                    pd.Timedelta("1 days"),
                    pd.Timedelta("2 days"),
                    pd.Timedelta("3 days"),
                ],
                "J": [
                    pd.Interval(left=0, right=5),
                    pd.Interval(left=5, right=10),
                    pd.Interval(left=10, right=15),
                ],
            }
        )
        expected_field_types = {
            "A": ("integer", "int64"),
            "B": ("string", "object"),
            "C": ("number", "float64"),
            "D": ("boolean", "bool"),
            "E": ("unknown", "complex128"),
            "F": ("string", "object"),
            "G": ("string", "object"),
            "H": ("date", "datetime64[ns]"),
            "I": ("string", "timedelta64[ns]"),
            "J": ("string", "interval[int64, right]"),
        }
        assert (
            self.factory.create()(complex_data).get_field_types()
            == expected_field_types
        )

    def test_get_fields_types_duplicate_columns(self) -> None:
        import pandas as pd

        # Different types
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "c"],
            }
        )
        data = data.rename(columns={"A": "B"})
        expected_field_types = {
            "B": ("string", "object"),
        }
        assert (
            self.factory.create()(data).get_field_types()
            == expected_field_types
        )

        # Both strings
        data = pd.DataFrame(
            {
                "A": ["a", "b", "c"],
                "B": ["d", "e", "f"],
            }
        )
        data = data.rename(columns={"A": "B"})
        expected_field_types = {
            "B": ("string", "object"),
        }
        assert (
            self.factory.create()(data).get_field_types()
            == expected_field_types
        )

        # Both integers
        data = pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": [4, 5, 6],
            }
        )
        data = data.rename(columns={"A": "B"})
        expected_field_types = {
            "B": ("string", "object"),
        }
        assert (
            self.factory.create()(data).get_field_types()
            == expected_field_types
        )

    def test_limit(self) -> None:
        import pandas as pd

        limit = 2
        limited_manager = self.manager.limit(limit)
        expected_data = self.data.head(limit)
        pd.testing.assert_frame_equal(limited_manager.data, expected_data)

    def test_summary_integer(self) -> None:
        column = "A"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=None,
            min=1,
            max=3,
            mean=2.0,
            median=2.0,
            std=1.0,
            p5=1.1,
            p25=1.5,
            p75=2.5,
            p95=2.9,
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
            p5=1.1,
            p25=1.5,
            p75=2.5,
            p95=2.9,
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
        import pandas as pd

        assert summary == ColumnSummary(
            total=3,
            nulls=0,
            unique=None,
            min=pd.Timestamp("2021-01-01 00:00:00"),
            max=pd.Timestamp("2021-01-03 00:00:00"),
            mean=pd.Timestamp("2021-01-02 00:00:00"),
            median=pd.Timestamp("2021-01-02 00:00:00"),
            std=None,
            true=None,
            false=None,
            p5=pd.Timestamp("2021-01-01 02:24:00"),
            p25=pd.Timestamp("2021-01-01 12:00:00"),
            p75=pd.Timestamp("2021-01-02 12:00:00"),
            p95=pd.Timestamp("2021-01-02 21:36:00"),
        )

    def test_summary_list(self) -> None:
        column = "F"
        summary = self.manager.get_summary(column)
        assert summary == ColumnSummary(
            total=3,
            nulls=0,
        )

    def test_sort_values(self) -> None:
        sorted_df = self.manager.sort_values("A", descending=True).data
        expected_df = self.data.sort_values("A", ascending=False)
        assert sorted_df.equals(expected_df)

    def test_sort_values_with_index(self) -> None:
        import pandas as pd

        data = pd.DataFrame(
            {
                "A": [1, 3, 2],
            },
            index=[1, 3, 2],
        )
        data.index.name = "index"
        manager = self.factory.create()(data)
        sorted_df = manager.sort_values("A", descending=True).data
        assert sorted_df.index.tolist() == [3, 2, 1]

    def test_get_unique_column_values(self) -> None:
        column = "B"
        assert self.manager.get_unique_column_values(column) == [
            "a",
            "b",
            " b",
        ]

    def test_search(self) -> None:
        import pandas as pd

        df = pd.DataFrame(
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
