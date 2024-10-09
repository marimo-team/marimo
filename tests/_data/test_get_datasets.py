from __future__ import annotations

import pytest

from marimo._data.get_datasets import (
    get_datasets_from_duckdb,
    has_updates_to_datasource,
)
from marimo._data.models import DataTable, DataTableColumn
from marimo._dependencies.dependencies import DependencyManager

HAS_DEPS = DependencyManager.duckdb.has()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_has_updates_to_datasource() -> None:
    assert has_updates_to_datasource("hello") is False
    assert has_updates_to_datasource("ATTACH 'marimo.db'") is True
    assert has_updates_to_datasource("DETACH marimo") is True
    assert has_updates_to_datasource("CREATE TABLE cars (name TEXT)") is True


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_datasets() -> None:
    assert get_datasets_from_duckdb() == []

    import duckdb

    duckdb.execute("CREATE TABLE cars (name TEXT, year INTEGER)")
    assert get_datasets_from_duckdb() == [
        DataTable(
            name="memory.main.cars",
            source_type="duckdb",
            source="memory",
            num_rows=None,
            num_columns=2,
            variable_name=None,
            columns=[
                DataTableColumn(
                    name="name", type="string", external_type="VARCHAR"
                ),
                DataTableColumn(
                    name="year", type="integer", external_type="INTEGER"
                ),
            ],
        )
    ]
