from __future__ import annotations

import datetime
import unittest

import pytest

from marimo._data.models import ColumnSummary
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

    def test_to_json(self) -> None:
        assert isinstance(self.manager.to_json(), bytes)

    def test_select_rows(self) -> None:
        indices = [0, 2]
        selected_manager = self.manager.select_rows(indices)
        expected_data = self.data[indices]
        assert selected_manager.data.equals(expected_data)

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
            "C": "number",
            "D": "boolean",
            "E": "date",
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
            "A": "integer",
            "B": "string",
            "C": "number",
            "D": "boolean",
            "E": "unknown",
            "F": "unknown",
            "G": "unknown",
            "H": "date",
            "I": "string",
            "J": "string",
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
