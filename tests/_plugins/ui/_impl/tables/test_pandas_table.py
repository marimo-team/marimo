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
        self.assertEqual(self.factory.package_name(), "pandas")

    def test_to_csv(self) -> None:
        expected_csv = self.data.to_csv(index=False).encode("utf-8")
        self.assertEqual(self.manager.to_csv(), expected_csv)

    def test_to_json(self) -> None:
        expected_json = self.data.to_json(orient="records").encode("utf-8")
        self.assertEqual(self.manager.to_json(), expected_json)

    def test_select_rows(self) -> None:
        import pandas as pd

        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data.iloc[indices]
        pd.testing.assert_frame_equal(selected_manager.data, expected_data)

    def test_select_rows_empty(self) -> None:
        selected_manager = self.manager.select_rows([])
        self.assertEqual(selected_manager.data.shape, (0, 2))

    def test_get_row_headers(self) -> None:
        expected_headers = []
        self.assertEqual(self.manager.get_row_headers(), expected_headers)

    def test_is_type(self) -> None:
        self.assertTrue(self.manager.is_type(self.data))
        self.assertFalse(self.manager.is_type("not a dataframe"))
