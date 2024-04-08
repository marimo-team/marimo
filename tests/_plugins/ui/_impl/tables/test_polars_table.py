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
        self.assertEqual(self.factory.package_name(), "polars")

    def test_to_csv(self) -> None:
        self.assertIsInstance(self.manager.to_csv(), bytes)

    def test_to_json(self) -> None:
        self.assertIsInstance(self.manager.to_json(), bytes)

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
        self.assertEqual(self.manager.get_row_headers(), expected_headers)

    def test_is_type(self) -> None:
        self.assertTrue(self.manager.is_type(self.data))
        self.assertFalse(self.manager.is_type("not a dataframe"))
