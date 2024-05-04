from __future__ import annotations

import unittest

import pytest

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
        self.data = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
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
        assert selected_manager.data.shape == (0, 2)

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
        expected_headers = [
            ("", ["2021-01-01", "2021-06-01", "2021-09-01"]),
        ]
        assert manager.get_row_headers() == expected_headers

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
        expected_headers = [
            ("", ["1 days", "2 days", "3 days"]),
        ]
        assert manager.get_row_headers() == expected_headers

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
        expected_headers = [
            ("X", ["a", "b", "c"]),
            ("Y", [1, 2, 3]),
        ]
        assert manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import pandas as pd

        expected_field_types = {
            "A": "integer",
            "B": "string",
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
            "A": "integer",
            "B": "string",
            "C": "number",
            "D": "boolean",
            "E": "unknown",
            "F": "string",
            "G": "string",
            "H": "date",
            "I": "string",
            "J": "string",
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
            "B": "string",
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
            "B": "string",
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
            "B": "string",
        }
        assert (
            self.factory.create()(data).get_field_types()
            == expected_field_types
        )
