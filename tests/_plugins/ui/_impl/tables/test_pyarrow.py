import unittest

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.pyarrow_table import (
    PyArrowTableManagerFactory,
)

HAS_DEPS = DependencyManager.has_pyarrow()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
class TestPyArrowTableManagerFactory(unittest.TestCase):
    def setUp(self) -> None:
        import pyarrow as pa

        self.factory = PyArrowTableManagerFactory()
        self.data = pa.table({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        self.manager = self.factory.create()(self.data)

    def test_package_name(self) -> None:
        self.assertEqual(self.factory.package_name(), "pyarrow")

    def test_to_csv(self) -> None:
        self.assertIsInstance(self.manager.to_csv(), bytes)

    def test_to_json(self) -> None:
        self.assertIsInstance(self.manager.to_json(), bytes)

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data.take(indices)
        assert selected_manager.data == expected_data

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        assert selected_manager.data.num_rows == 0

    def test_get_row_headers(self) -> None:
        expected_headers = []
        self.assertEqual(self.manager.get_row_headers(), expected_headers)

    def test_is_type(self) -> None:
        self.assertTrue(self.manager.is_type(self.data))
        self.assertFalse(self.manager.is_type("not a dataframe"))
