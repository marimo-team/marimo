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
