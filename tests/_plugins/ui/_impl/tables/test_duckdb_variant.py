# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest

from marimo._data.get_datasets import _db_type_to_data_type
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.data.data import BIGINT_KEY
from marimo._plugins import ui
from marimo._plugins.ui._impl.table import SearchTableArgs
from marimo._plugins.ui._impl.tables.utils import get_table_manager

if TYPE_CHECKING:
    from collections.abc import Generator

    import duckdb

pytestmark = pytest.mark.skipif(
    not DependencyManager.duckdb.has_at_version(min_version="1.5.0"),
    reason="VARIANT requires DuckDB >= 1.5",
)


@pytest.fixture
def connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    import duckdb

    with duckdb.connect() as connection:
        yield connection


def test_native_variant_json(connection: duckdb.DuckDBPyConnection) -> None:
    relation = connection.sql(
        """
        SELECT * FROM (VALUES
            (0, 42::VARIANT),
            (1, true::VARIANT),
            (2, 'héllo 🦆'::VARIANT),
            (3, {'name': 'Alice', 'age': 30}::VARIANT),
            (4, [1::VARIANT, 'two'::VARIANT, NULL::VARIANT]::VARIANT),
            (5, NULL::VARIANT),
            (6, 'null'::VARIANT)
        ) AS source(id, data)
        """
    )
    assert relation is not None
    original_rows = relation.fetchall()
    original_types = relation.types
    manager = get_table_manager(relation)

    assert json.loads(manager.to_json_str(ensure_ascii=False)) == [
        {"id": 0, "data": 42},
        {"id": 1, "data": True},
        {"id": 2, "data": "héllo 🦆"},
        {"id": 3, "data": {"age": 30, "name": "Alice"}},
        {"id": 4, "data": [1, "two", None]},
        {"id": 5, "data": None},
        {"id": 6, "data": "null"},
    ]
    assert (manager.data.to_native(), relation.types, relation.fetchall()) == (
        relation,
        original_types,
        original_rows,
    )
    assert manager.get_field_types() == [
        ("id", ("integer", "Int32")),
        ("data", ("unknown", "VARIANT")),
    ]
    assert "héllo 🦆" in manager.to_json_str(ensure_ascii=False)
    assert "\\u00e9" in manager.to_json_str(ensure_ascii=True)


def test_nested_variant_and_ordinary_storage_struct(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    relation = connection.sql(
        """
        SELECT
            {'item': 42::VARIANT, 'items': ['世界'::VARIANT]} AS nested,
            [1::VARIANT, false::VARIANT] AS items,
            [1::VARIANT, 'two'::VARIANT]::VARIANT[2] AS fixed,
            MAP {'key': 'value'::VARIANT} AS mapping,
            {'size': 42::VARIANT} AS size_field,
            {'metadata': 'ordinary'::BLOB, 'value': 'bytes'::BLOB} AS storage
        """
    )
    assert relation is not None
    manager = get_table_manager(relation)

    assert json.loads(manager.to_json_str()) == [
        {
            "nested": {"item": 42, "items": ["世界"]},
            "items": [1, False],
            "fixed": [1, "two"],
            "mapping": {"key": "value"},
            "size_field": {"size": 42},
            "storage": {"metadata": "ordinary", "value": "bytes"},
        }
    ]
    assert manager.get_field_types()[:5] == [
        (name, ("unknown", str(dtype)))
        for name, dtype in zip(
            relation.columns[:5], relation.types[:5], strict=True
        )
    ]
    assert manager.take(0, 0).to_json_str() == "[]"


def test_variant_rich_values_preserve_source(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    relation = connection.sql(
        """
        SELECT
            123456789012345678901234567890::HUGEINT::VARIANT AS large,
            12345678901234567890.123456789::DECIMAL(38, 9)::VARIANT AS exact,
            INTERVAL '1 month 2 days'::VARIANT AS duration,
            TIMESTAMP_NS '2026-11-02 12:34:56.123456789'::VARIANT AS stamp
        """
    )
    assert relation is not None
    manager = get_table_manager(relation)
    assert json.loads(manager.to_json_str()) == [
        {
            "large": {BIGINT_KEY: "123456789012345678901234567890"},
            "exact": "12345678901234567890.123456789",
            "duration": "32 days, 0:00:00",
            "stamp": "2026-11-02 12:34:56.123456",
        }
    ]
    assert relation.project(
        "duration::VARCHAR, stamp::VARCHAR, exact::VARCHAR"
    ).fetchall() == [
        (
            "1 month 2 days",
            "2026-11-02 12:34:56.123456789",
            "12345678901234567890.123456789",
        )
    ]


def test_variant_strict_json(connection: duckdb.DuckDBPyConnection) -> None:
    relation = connection.sql(
        """
        SELECT {'values': ['NaN'::DOUBLE, 'Infinity'::DOUBLE, 1.5]}::VARIANT AS data
        """
    )
    assert relation is not None
    manager = get_table_manager(relation)
    assert "NaN" in manager.to_json_str()

    def reject_constant(value: str) -> None:
        raise AssertionError(f"Invalid JSON constant: {value}")

    assert json.loads(
        manager.to_json_str(strict_json=True), parse_constant=reject_constant
    ) == [{"data": {"values": [None, None, 1.5]}}]


@pytest.mark.parametrize("lazy", [False, True])
def test_variant_table_pages(
    connection: duckdb.DuckDBPyConnection, lazy: bool
) -> None:
    relation = connection.sql(
        """
        SELECT i AS id, {'name': 'Alice', 'age': i}::VARIANT AS data
        FROM range(5) AS source(i)
        """
    )
    assert relation is not None
    table = ui.table.lazy(relation) if lazy else ui.table(relation)
    formatter = Mock(
        side_effect=lambda value: f"{value['name']}: {value['age']}"
    )
    table._format_mapping = {"data": formatter}

    for page_number, ids in [(0, [0, 1]), (1, [2, 3]), (2, [4]), (3, [])]:
        formatter.reset_mock()
        response = table._search(
            SearchTableArgs(page_size=2, page_number=page_number)
        )
        assert response.raw_data is not None
        assert (
            json.loads(response.data),
            json.loads(response.raw_data),
            response.has_next_page,
            formatter.call_count,
        ) == (
            [{"id": i, "data": f"Alice: {i}"} for i in ids],
            [{"id": i, "data": {"age": i, "name": "Alice"}} for i in ids],
            page_number < 2 if lazy else None,
            len(ids),
        )
        assert connection.sql("SELECT 1").fetchall() == [(1,)]

    assert table._manager.data.to_native() is relation
    assert relation.types[1] == connection.sql("SELECT 1::VARIANT").types[0]
    assert relation.project("data.age::BIGINT").fetchall() == [
        (i,) for i in range(5)
    ]


def test_variant_lazy_page_uses_same_execution_for_formatting(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    relation = connection.sql("SELECT random()::VARIANT AS data FROM range(5)")
    assert relation is not None
    table = ui.table.lazy(relation)
    table._format_mapping = {"data": str}
    response = table._search(SearchTableArgs(page_size=2, page_number=0))

    assert response.raw_data is not None
    assert json.loads(response.data) == [
        {"data": str(row["data"])} for row in json.loads(response.raw_data)
    ]
    assert response.has_next_page is True


@pytest.mark.parametrize("lazy", [False, True])
def test_variant_preserves_ordinary_column_display(
    connection: duckdb.DuckDBPyConnection, lazy: bool
) -> None:
    relation = connection.sql(
        """
        SELECT
            42::VARIANT AS data,
            1 AS materialize,
            TIMESTAMP_NS '2026-01-01 12:34:56.123456789' AS stamp,
            INTERVAL '1 month 2 days' AS duration,
            MAP(
                [TIMESTAMP_NS '2026-01-01 00:00:00.000000001',
                 TIMESTAMP_NS '2026-01-01 00:00:00.000000002'],
                ['first', 'second']
            ) AS mapping
        """
    )
    assert relation is not None
    table = ui.table.lazy(relation) if lazy else ui.table(relation)
    response = table._search(SearchTableArgs(page_size=2, page_number=0))

    assert json.loads(response.data) == [
        {
            "data": 42,
            "materialize": 1,
            "stamp": "2026-01-01 12:34:56.123456789",
            "duration": [1, 2, 0],
            "mapping": [
                ["2026-01-01 00:00:00.000000001", "first"],
                ["2026-01-01 00:00:00.000000002", "second"],
            ],
        }
    ]


@pytest.mark.parametrize("lazy", [False, True])
def test_variant_and_ordinary_columns_use_same_execution(
    connection: duckdb.DuckDBPyConnection, lazy: bool
) -> None:
    relation = connection.sql(
        """
        SELECT value AS ordinary, value::VARIANT AS data
        FROM (SELECT random() AS value FROM range(5))
        """
    )
    assert relation is not None
    table = ui.table.lazy(relation) if lazy else ui.table(relation)
    response = table._search(SearchTableArgs(page_size=3, page_number=0))
    rows = json.loads(response.data)

    assert len(rows) == 3
    assert all(row["ordinary"] == row["data"] for row in rows)


def test_variant_formatter_cannot_mutate_raw_values(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    relation = connection.sql(
        "SELECT {'name': 'Alice', 'tags': ['one']}::VARIANT AS data"
    )
    assert relation is not None
    manager = get_table_manager(relation)

    def mutate(value: Any) -> str:
        value["tags"].append("formatted")
        return str(value.pop("name"))

    for _ in range(2):
        assert json.loads(manager.to_json_str({"data": mutate})) == [
            {"data": "Alice"}
        ]
        assert json.loads(manager.to_json_str()) == [
            {"data": {"name": "Alice", "tags": ["one"]}}
        ]


@pytest.mark.parametrize("fail_collection", [False, True])
def test_variant_snapshot_cleans_up(
    connection: duckdb.DuckDBPyConnection,
    monkeypatch: pytest.MonkeyPatch,
    fail_collection: bool,
) -> None:
    import narwhals.stable.v2 as nw

    relation = connection.sql("SELECT 1 AS id, 42::VARIANT AS data")
    assert relation is not None
    manager = get_table_manager(relation)
    if fail_collection:
        monkeypatch.setattr(
            nw.LazyFrame,
            "collect",
            Mock(side_effect=RuntimeError("Arrow conversion failed")),
        )
        with pytest.raises(RuntimeError, match="Arrow conversion failed"):
            manager.to_json_str()
    else:
        assert json.loads(manager.to_json_str()) == [{"id": 1, "data": 42}]

    assert (
        connection.sql(
            """
        SELECT table_name FROM duckdb_tables()
        WHERE table_name LIKE '__marimo_display_%'
        UNION ALL
        SELECT view_name FROM duckdb_views()
        WHERE view_name LIKE '__marimo_display_%'
        """
        ).fetchall()
        == []
    )
    assert relation.fetchall() == [(1, 42)]


@pytest.mark.parametrize("db_type", ["VARIANT", "variant"])
def test_variant_dataset_type(
    db_type: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    warning = Mock()
    monkeypatch.setattr("marimo._data.get_datasets.LOGGER.warning", warning)
    assert _db_type_to_data_type(db_type) == "unknown"
    warning.assert_not_called()
