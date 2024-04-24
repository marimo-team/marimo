from __future__ import annotations

import unittest

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)

HAS_DEPS = DependencyManager.has_polars()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPolarsTableManagerFactory(unittest.TestCase):
    def setUp(self) -> None:
        import polars as pl

        self.factory = PolarsTableManagerFactory()
        self.data = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        assert self.factory.package_name() == "polars"

    def test_to_csv(self) -> None:
        assert isinstance(self.manager.to_csv(), bytes)

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data[indices]
        assert selected_manager.data.frame_equal(expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.shape == (0, 0)
        assert selected_manager.data.columns == []

    def test_get_row_headers(self) -> None:
        expected_headers = []
        assert self.manager.get_row_headers() == expected_headers

    def test_is_type(self) -> None:
        assert self.manager.is_type(self.data)
        assert not self.manager.is_type("not a dataframe")

    def test_get_field_types(self) -> None:
        import polars as pl

        expected_field_types = {
            "A": "integer",
            "B": "string",
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
                    pl.Date(2021, 1, 1),
                    pl.Date(2021, 1, 2),
                    pl.Date(2021, 1, 3),
                ],
                "I": [
                    pl.Time(0, 0, 0),
                    pl.Time(1, 0, 0),
                    pl.Time(2, 0, 0),
                ],
                "J": [
                    pl.Duration("ms"),
                    pl.Duration("ms"),
                    pl.Duration("ms"),
                ],
            }
        )
        expected_field_types = {
            "A": "integer",
            "B": "string",
            "C": "number",
            "D": "boolean",
            "E": "unknown",
            "F": "number",
            "G": "unknown",
            "H": "unknown",
            "I": "unknown",
            "J": "unknown",
        }
        assert (
            self.factory.create()(complex_data).get_field_types()
            == expected_field_types
        )
