# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest

from marimo._data.models import Database, DataTable, Schema
from marimo._sql.engines.starrocks import (
    _SYSTEM_SCHEMAS,
    StarRocksEngine,
)
from marimo._sql.sql_quoting import quote_sql_identifier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_sqlalchemy_if_missing():
    """Patch sys.modules with a lightweight sqlalchemy stub when the real
    package is not installed, so mock-based tests can still run without it."""
    if "sqlalchemy" in sys.modules:
        yield
        return

    mock_sa = MagicMock()
    # `text()` is used as a pass-through wrapper; the result is fed into the
    # mocked conn.execute, so its exact return value doesn't matter.
    mock_sa.text = MagicMock(side_effect=lambda q: q)
    with patch.dict(sys.modules, {"sqlalchemy": mock_sa}):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# is_compatible
# ---------------------------------------------------------------------------


class TestIsCompatible:
    @pytest.mark.requires("sqlalchemy", "starrocks")
    def test_compatible_with_starrocks_dialect(self) -> None:
        import sqlalchemy as sa

        mock_engine = MagicMock(spec=sa.Engine)
        mock_engine.dialect.name = "starrocks"
        assert StarRocksEngine.is_compatible(mock_engine)

    @pytest.mark.requires("sqlalchemy", "starrocks")
    def test_not_compatible_with_other_dialects(self) -> None:
        import sqlalchemy as sa

        for dialect in ("mysql", "postgresql", "sqlite", "clickhouse"):
            mock_engine = MagicMock(spec=sa.Engine)
            mock_engine.dialect.name = dialect
            assert not StarRocksEngine.is_compatible(mock_engine)

    @pytest.mark.requires("sqlalchemy", "starrocks")
    def test_not_compatible_with_non_engine(self) -> None:
        assert not StarRocksEngine.is_compatible("not_an_engine")
        assert not StarRocksEngine.is_compatible(42)
        assert not StarRocksEngine.is_compatible(None)


# ---------------------------------------------------------------------------
# source / dialect
# ---------------------------------------------------------------------------


class TestSourceAndDialect:
    def test_source(self) -> None:
        engine = _make_engine()
        assert engine.source == "starrocks"

    def test_dialect(self) -> None:
        engine = _make_engine()
        assert engine.dialect == "starrocks"


# ---------------------------------------------------------------------------
# get_default_database / get_default_schema
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_get_default_database(self) -> None:
        engine = _make_engine()
        _mock_connection_ctx(engine, [[("default_catalog",)]])
        assert engine.get_default_database() == "default_catalog"
        # Verify it uses CATALOG() not CURRENT_CATALOG()
        conn = engine._connection.connect().__enter__()
        call_args = conn.execute.call_args_list
        assert any("CATALOG()" in str(c) for c in call_args)

    def test_get_default_database_none_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("connection failed")
        assert engine.get_default_database() is None

    def test_get_default_schema(self) -> None:
        engine = _make_engine()
        _mock_connection_ctx(engine, [[("my_db",)]])
        assert engine.get_default_schema() == "my_db"

    def test_get_default_schema_none_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("connection failed")
        assert engine.get_default_schema() is None


# ---------------------------------------------------------------------------
# _list_catalogs / _list_databases_in_catalog
# ---------------------------------------------------------------------------


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


class TestListDatabases:
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
        result = engine._list_databases_in_catalog("default_catalog")
        assert result == ["tpch", "analytics"]

    def test_returns_empty_on_error(self) -> None:
        engine = _make_engine()
        engine._connection.connect.side_effect = Exception("oops")
        assert engine._list_databases_in_catalog("default_catalog") == []


# ---------------------------------------------------------------------------
# get_databases
# ---------------------------------------------------------------------------


class TestGetDatabases:
    def test_returns_catalog_as_database(self) -> None:
        engine = _make_engine()
        # Call 1: SHOW CATALOGS
        # Call 2: SHOW DATABASES IN `default_catalog`
        catalogs_rows = [("default_catalog",), ("hive_catalog",)]
        db_rows_default = [("tpch",), ("analytics",)]
        db_rows_hive = [("lake",)]

        conn_ctx = MagicMock()
        conn = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        engine._connection.connect = MagicMock(return_value=conn_ctx)

        results = []
        for rows in [catalogs_rows, db_rows_default, db_rows_hive]:
            r = MagicMock()
            r.fetchall = MagicMock(return_value=rows)
            results.append(r)
        conn.execute = MagicMock(side_effect=results)

        databases = engine.get_databases(
            include_schemas=True,
            include_tables=False,
            include_table_details=False,
        )

        assert len(databases) == 2
        assert databases[0].name == "default_catalog"
        assert databases[1].name == "hive_catalog"
        assert [s.name for s in databases[0].schemas] == ["tpch", "analytics"]
        assert [s.name for s in databases[1].schemas] == ["lake"]
        for db in databases:
            assert db.dialect == "starrocks"
            assert db.engine == "sr"

    def test_no_schemas_when_include_schemas_false(self) -> None:
        engine = _make_engine()
        conn_ctx = MagicMock()
        conn = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        engine._connection.connect = MagicMock(return_value=conn_ctx)

        catalogs_result = MagicMock()
        catalogs_result.fetchall = MagicMock(
            return_value=[("default_catalog",)]
        )
        conn.execute = MagicMock(return_value=catalogs_result)

        databases = engine.get_databases(
            include_schemas=False,
            include_tables=False,
            include_table_details=False,
        )

        assert len(databases) == 1
        assert databases[0].name == "default_catalog"
        assert databases[0].schemas == []

    def test_auto_includes_schemas_excludes_tables(self) -> None:
        """'auto' should resolve to include_schemas=True, include_tables=False."""
        engine = _make_engine()
        conn_ctx = MagicMock()
        conn = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        engine._connection.connect = MagicMock(return_value=conn_ctx)

        # SHOW CATALOGS → 1 catalog; SHOW DATABASES → 1 db
        r1 = MagicMock()
        r1.fetchall = MagicMock(return_value=[("default_catalog",)])
        r2 = MagicMock()
        r2.fetchall = MagicMock(return_value=[("tpch",)])
        conn.execute = MagicMock(side_effect=[r1, r2])

        databases = engine.get_databases(
            include_schemas="auto",
            include_tables="auto",
            include_table_details="auto",
        )

        assert len(databases) == 1
        assert databases[0].schemas[0].name == "tpch"
        # Tables should NOT be fetched (auto → False for tables)
        assert databases[0].schemas[0].tables == []


# ---------------------------------------------------------------------------
# get_tables_in_schema
# ---------------------------------------------------------------------------


class TestGetTablesInSchema:
    def test_returns_tables_and_views(self) -> None:
        engine = _make_engine()
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
            schema="tpch", database="default_catalog", include_table_details=False
        )
        assert result == []


# ---------------------------------------------------------------------------
# get_table_details
# ---------------------------------------------------------------------------


class TestGetTableDetails:
    def test_returns_columns(self) -> None:
        engine = _make_engine()
        rows = [
            ("id", "INT"),
            ("name", "VARCHAR"),
            ("created_at", "DATETIME"),
            ("score", "DOUBLE"),
            ("is_active", "BOOLEAN"),
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


# ---------------------------------------------------------------------------
# SQL quoting integration
# ---------------------------------------------------------------------------


class TestStarRocksQuoting:
    def test_starrocks_uses_backtick_style(self) -> None:
        assert quote_sql_identifier("my_catalog", dialect="starrocks") == "`my_catalog`"
        assert (
            quote_sql_identifier("catalog`with`ticks", dialect="starrocks")
            == "`catalog``with``ticks`"
        )
        assert (
            quote_sql_identifier("catalog with spaces", dialect="starrocks")
            == "`catalog with spaces`"
        )


# ---------------------------------------------------------------------------
# _resolve_auto
# ---------------------------------------------------------------------------


class TestResolveAuto:
    def test_true_stays_true(self) -> None:
        assert StarRocksEngine._resolve_auto(True, default=False) is True

    def test_false_stays_false(self) -> None:
        assert StarRocksEngine._resolve_auto(False, default=True) is False

    def test_auto_returns_default(self) -> None:
        assert StarRocksEngine._resolve_auto("auto", default=True) is True
        assert StarRocksEngine._resolve_auto("auto", default=False) is False


# ---------------------------------------------------------------------------
# System catalog / database constants
# ---------------------------------------------------------------------------


class TestSystemConstants:
    def test_system_schemas_excluded(self) -> None:
        assert "information_schema" in _SYSTEM_SCHEMAS
        assert "sys" in _SYSTEM_SCHEMAS
        assert "_statistics_" in _SYSTEM_SCHEMAS
