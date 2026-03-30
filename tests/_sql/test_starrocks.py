# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from marimo._sql.engines.starrocks import (
    _SYSTEM_SCHEMAS,
    StarRocksEngine,
)
from marimo._sql.sql_quoting import quote_sql_identifier

# Skip the entire module when sqlalchemy is not installed.
pytestmark = pytest.mark.requires("sqlalchemy")


def _make_mock_engine(dialect_name: str = "starrocks") -> MagicMock:
    """Return a mock SQLAlchemy Engine with the given dialect name."""
    mock_engine = MagicMock()
    mock_engine.dialect.name = dialect_name
    return mock_engine


def _make_engine(dialect_name: str = "starrocks") -> StarRocksEngine:
    return StarRocksEngine(_make_mock_engine(dialect_name), engine_name="sr")


def _mock_connection_ctx(engine: StarRocksEngine, side_effects: list[Any]):
    """Patch _connection.connect() so that successive execute() calls return
    the given side_effects in order (each item is the rows list for one call).
    """
    conn_ctx = MagicMock()
    conn = MagicMock()
    conn_ctx.__enter__ = MagicMock(return_value=conn)
    conn_ctx.__exit__ = MagicMock(return_value=False)
    engine._connection.connect = MagicMock(return_value=conn_ctx)

    results = []
    for rows in side_effects:
        result = MagicMock()
        result.fetchone = MagicMock(return_value=rows[0] if rows else None)
        result.fetchall = MagicMock(return_value=rows)
        results.append(result)

    conn.execute = MagicMock(side_effect=results)
    return conn


class TestIsCompatible:
    @pytest.mark.requires("sqlalchemy", "starrocks")
    def test_compatible_with_starrocks_dialect(self) -> None:
        import sqlalchemy as sa
        import starrocks  # noqa: F401

        mock_engine = MagicMock(spec=sa.Engine)
        mock_engine.dialect = MagicMock()
        mock_engine.dialect.name = "starrocks"
        assert StarRocksEngine.is_compatible(mock_engine)

    @pytest.mark.requires("sqlalchemy", "starrocks")
    def test_not_compatible_with_other_dialects(self) -> None:
        import sqlalchemy as sa

        for dialect in ("mysql", "postgresql", "sqlite", "clickhouse"):
            mock_engine = MagicMock(spec=sa.Engine)
            mock_engine.dialect = MagicMock()
            mock_engine.dialect.name = dialect
            assert not StarRocksEngine.is_compatible(mock_engine)

    @pytest.mark.requires("sqlalchemy", "starrocks")
    def test_not_compatible_with_non_engine(self) -> None:
        assert not StarRocksEngine.is_compatible("not_an_engine")
        assert not StarRocksEngine.is_compatible(42)
        assert not StarRocksEngine.is_compatible(None)


class TestSourceAndDialect:
    def test_source(self) -> None:
        engine = _make_engine()
        assert engine.source == "starrocks"

    def test_dialect(self) -> None:
        engine = _make_engine()
        assert engine.dialect == "starrocks"


class TestDefaults:
    def test_get_default_database(self) -> None:
        engine = _make_engine()
        _mock_connection_ctx(engine, [[("default_catalog",)]])
        assert engine.get_default_database() == "default_catalog"

    def test_get_default_database_none_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("connection failed")
        assert engine.get_default_database() is None

    def test_get_default_schema(self) -> None:
        # get_default_schema() is inherited from SQLAlchemyEngine and tries
        # inspector.default_schema_name first.
        engine = _make_engine()
        engine.inspector = MagicMock()
        engine.inspector.default_schema_name = "my_db"
        assert engine.get_default_schema() == "my_db"

    def test_get_default_schema_none_on_error(self) -> None:
        engine = _make_engine()
        engine.inspector = None
        engine._connection.connect.side_effect = Exception("connection failed")
        assert engine.get_default_schema() is None


class TestListCatalogs:
    def test_lists_all_catalogs(self) -> None:
        engine = _make_engine()
        rows = [
            ("default_catalog",),
            ("hive_catalog",),
            ("iceberg_catalog",),
        ]
        _mock_connection_ctx(engine, [rows])
        result = engine._list_catalogs()
        assert result == ["default_catalog", "hive_catalog", "iceberg_catalog"]

    def test_returns_empty_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("oops")
        assert engine._list_catalogs() == []


class TestExternalSchemas:
    def test_lists_databases_excluding_system(self) -> None:
        engine = _make_engine()
        rows = [
            ("tpch",),
            ("analytics",),
            ("information_schema",),  # excluded
            ("sys",),  # excluded
            ("_statistics_",),  # excluded
        ]
        _mock_connection_ctx(engine, [rows])
        schemas = engine._get_external_schemas(
            catalog="hive_catalog",
            include_tables=False,
            include_table_details=False,
        )
        assert [s.name for s in schemas] == ["tpch", "analytics"]

    def test_returns_empty_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("oops")
        assert (
            engine._get_external_schemas(
                catalog="hive_catalog",
                include_tables=False,
                include_table_details=False,
            )
            == []
        )


class TestGetDatabases:
    def test_returns_catalogs_with_empty_schemas(self) -> None:
        """get_databases() lists catalogs only; schemas are fetched lazily."""
        engine = _make_engine()
        catalogs_rows = [("default_catalog",), ("hive_catalog",)]
        _mock_connection_ctx(engine, [catalogs_rows])

        databases = engine.get_databases(
            include_schemas=True,
            include_tables=False,
            include_table_details=False,
        )

        assert len(databases) == 2
        assert databases[0].name == "default_catalog"
        assert databases[1].name == "hive_catalog"
        # Schemas are always empty — lazy loading handles them
        for db in databases:
            assert db.schemas == []
            assert db.dialect == "starrocks"
            assert db.engine == "sr"

    def test_returns_empty_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("oops")
        databases = engine.get_databases(
            include_schemas=False,
            include_tables=False,
            include_table_details=False,
        )
        assert databases == []


class TestGetSchemas:
    def test_external_catalog_returns_schemas(self) -> None:
        """get_schemas() for an external catalog uses SHOW DATABASES."""
        engine = _make_engine()
        rows = [
            ("tpch",),
            ("analytics",),
            ("information_schema",),  # excluded
            ("sys",),  # excluded
        ]
        _mock_connection_ctx(engine, [rows])

        schemas = engine.get_schemas(
            database="hive_catalog",
            include_tables=False,
            include_table_details=False,
        )
        assert [s.name for s in schemas] == ["tpch", "analytics"]

    def test_returns_empty_for_none_database(self) -> None:
        engine = _make_engine()
        schemas = engine.get_schemas(
            database=None,
            include_tables=False,
            include_table_details=False,
        )
        assert schemas == []

    def test_returns_empty_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("oops")
        schemas = engine.get_schemas(
            database="hive_catalog",
            include_tables=False,
            include_table_details=False,
        )
        assert schemas == []


class TestGetTablesInSchema:
    def test_returns_tables_and_views(self) -> None:
        engine = _make_engine()
        # SHOW FULL TABLES returns (Tables_in_<db>, Table_type)
        rows = [
            ("orders", "BASE TABLE"),
            ("lineitem", "BASE TABLE"),
            ("revenue_view", "VIEW"),
        ]
        _mock_connection_ctx(engine, [rows])

        tables = engine.get_tables_in_schema(
            schema="tpch",
            database="default_catalog",
            include_table_details=False,
        )

        assert len(tables) == 3
        names = [t.name for t in tables]
        assert "orders" in names
        assert "lineitem" in names
        assert "revenue_view" in names
        view = next(t for t in tables if t.name == "revenue_view")
        assert view.type == "view"
        base = next(t for t in tables if t.name == "orders")
        assert base.type == "table"
        # No columns without details
        assert base.columns == []

    def test_returns_empty_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("fail")
        result = engine.get_tables_in_schema(
            schema="tpch",
            database="default_catalog",
            include_table_details=False,
        )
        assert result == []


class TestGetTableDetails:
    def test_returns_columns(self) -> None:
        engine = _make_engine()
        # DESC output: Field, Type, Null, Key, Default, Extra, Comment
        rows = [
            ("id", "INT", "YES", "", None, "", ""),
            ("name", "VARCHAR(255)", "YES", "", None, "", ""),
            ("created_at", "DATETIME", "YES", "", None, "", ""),
            ("score", "DOUBLE", "YES", "", None, "", ""),
            ("is_active", "BOOLEAN", "YES", "", None, "", ""),
        ]
        _mock_connection_ctx(engine, [rows])

        table = engine.get_table_details(
            table_name="orders",
            schema_name="tpch",
            database_name="default_catalog",
        )

        assert table is not None
        assert table.name == "orders"
        assert table.num_columns == 5
        assert len(table.columns) == 5

        types = {c.name: c.type for c in table.columns}
        assert types["id"] == "integer"
        assert types["name"] == "string"
        assert types["created_at"] == "datetime"
        assert types["score"] == "number"
        assert types["is_active"] == "boolean"

    def test_returns_none_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("fail")
        result = engine.get_table_details(
            table_name="orders",
            schema_name="tpch",
            database_name="default_catalog",
        )
        assert result is None


class TestStarRocksQuoting:
    def test_starrocks_uses_backtick_style(self) -> None:
        assert (
            quote_sql_identifier("my_catalog", dialect="starrocks")
            == "`my_catalog`"
        )
        assert (
            quote_sql_identifier("catalog`with`ticks", dialect="starrocks")
            == "`catalog``with``ticks`"
        )
        assert (
            quote_sql_identifier("catalog with spaces", dialect="starrocks")
            == "`catalog with spaces`"
        )


class TestSystemConstants:
    def test_system_schemas_excluded(self) -> None:
        assert "information_schema" in _SYSTEM_SCHEMAS
        assert "sys" in _SYSTEM_SCHEMAS
        assert "_statistics_" in _SYSTEM_SCHEMAS
