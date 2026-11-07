# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from marimo._data.get_datasets import _db_type_to_data_type
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.utils import get_table_manager

if TYPE_CHECKING:
    from collections.abc import Generator

    import duckdb


@pytest.fixture
def connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    if not DependencyManager.duckdb.has_at_version(min_version="1.5.0"):
        pytest.skip("VARIANT requires DuckDB >= 1.5")
    import duckdb

    with duckdb.connect() as connection:
        yield connection


def test_variant_schema(connection: duckdb.DuckDBPyConnection) -> None:
    relation = connection.sql("""
        SELECT
            42::VARIANT AS data,
            {'size': 1::VARIANT} AS nested,
            ['hello'::VARIANT] AS items,
            [1::VARIANT]::VARIANT[1] AS fixed,
            MAP {'key': 1::VARIANT} AS mapping,
            1 AS ordinary
    """)
    assert relation is not None
    manager = get_table_manager(relation)
    assert manager.get_field_types() == [
        (name, ("unknown", str(dtype)))
        for name, dtype in zip(
            relation.columns[:-1], relation.types[:-1], strict=True
        )
    ] + [("ordinary", ("integer", "Int32"))]
    assert manager.data.to_native() is relation
    assert relation.project(
        "typeof(data), nested.size::INTEGER"
    ).fetchall() == [("VARIANT", 1)]


def test_variant_schema_does_not_execute_query(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    connection.execute("CREATE SEQUENCE schema_probe")
    connection.execute("SELECT nextval('schema_probe')").fetchall()
    relation = connection.sql(
        "SELECT nextval('schema_probe')::VARIANT AS data"
    )
    assert relation is not None
    sequence_state = "SELECT last_value FROM duckdb_sequences() WHERE sequence_name = 'schema_probe'"
    before = connection.sql(sequence_state).fetchall()
    assert get_table_manager(relation).get_field_types() == [
        ("data", ("unknown", "VARIANT"))
    ]
    assert connection.sql(sequence_state).fetchall() == before


@pytest.mark.parametrize("db_type", ["VARIANT", "variant", "VARIANT[]"])
def test_variant_dataset_type(
    db_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    warning = Mock()
    monkeypatch.setattr("marimo._data.get_datasets.LOGGER.warning", warning)
    assert _db_type_to_data_type(db_type) == "unknown"
    warning.assert_not_called()
