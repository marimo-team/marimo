# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from marimo import _loggers
from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.sql_quoting import quote_sql_identifier
from marimo._sql.utils import sql_type_to_data_type

LOGGER = _loggers.marimo_logger()

# StarRocks databases (marimo Schemas) that are internal and not useful to surface.
_SYSTEM_SCHEMAS = frozenset({"information_schema", "sys", "_statistics_"})


def _quote(name: str) -> str:
    return quote_sql_identifier(name, dialect="starrocks")


class StarRocksEngine(SQLAlchemyEngine):
    """StarRocks SQL engine with multi-catalog support.

    Extends :class:`SQLAlchemyEngine`, inheriting the SQLAlchemy inspector
    pattern for the connected (default) catalog.  External catalogs fall back
    to explicit SQL because the inspector is bound to a single catalog.

    StarRocks uses a three-level hierarchy: Catalog → Database → Table.
    This maps to marimo's Database → Schema → Table model:

      - marimo ``Database``  ↔  StarRocks Catalog
      - marimo ``Schema``    ↔  StarRocks Database
      - marimo ``DataTable`` ↔  StarRocks Table
    """

    @property
    def source(self) -> str:
        return "starrocks"

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.sqlalchemy.imported():
            return False
        if not DependencyManager.starrocks.imported():
            return False

        from sqlalchemy.engine import Engine

        return isinstance(var, Engine) and str(var.dialect.name) == "starrocks"

    def get_default_database(self) -> Optional[str]:
        """Return the current StarRocks catalog via ``SELECT CATALOG()``.

        Overrides the parent which reads from the SQLAlchemy connection URL,
        because StarRocks exposes catalogs rather than a single database.
        """
        try:
            from sqlalchemy import text

            with self._connection.connect() as conn:
                row = conn.execute(text("SELECT CATALOG()")).fetchone()
            if row is not None and row[0] is not None:
                return str(row[0])
        except Exception:
            LOGGER.warning("Failed to get current catalog", exc_info=True)
        return None

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        """Return all StarRocks catalogs as databases."""
        return [
            Database(
                name=catalog,
                dialect=self.dialect,
                schemas=[],
                engine=self._engine_name,
            )
            for catalog in self._list_catalogs()
        ]

    def get_schemas(
        self,
        *,
        database: Optional[str],
        include_tables: bool,
        include_table_details: bool,
    ) -> list[Schema]:
        """Return schemas for a catalog, lazily fetched on demand.

        Routes the default catalog through the inherited inspector path;
        external catalogs use ``SHOW DATABASES IN <catalog>``.
        """
        if database == self.default_database:
            return super().get_schemas(
                database=database,
                include_tables=include_tables,
                include_table_details=include_table_details,
            )
        if database is not None:
            return self._get_external_schemas(
                catalog=database,
                include_tables=include_tables,
                include_table_details=include_table_details,
            )
        return []

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return tables for *schema* inside *database* (a StarRocks catalog).

        Delegates to the inherited inspector path for the default catalog;
        falls back to a ``SHOW`` query for external catalogs.
        """
        if database == self.default_database:
            return super().get_tables_in_schema(
                schema=schema,
                database=database,
                include_table_details=include_table_details,
            )
        return self._get_external_tables(
            schema=schema,
            database=database,
            include_table_details=include_table_details,
        )

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Return column metadata for a table.

        Delegates to the inherited inspector path for the default catalog;
        falls back to an ``DESC`` query for external catalogs.
        """
        if database_name == self.default_database:
            return super().get_table_details(
                table_name=table_name,
                schema_name=schema_name,
                database_name=database_name,
            )
        return self._get_external_table_details(
            table_name=table_name,
            schema_name=schema_name,
            database_name=database_name,
        )

    def _get_meta_schemas(self) -> list[str]:
        return list(_SYSTEM_SCHEMAS)

    def _list_catalogs(self) -> list[str]:
        """Return all catalog names via ``SHOW CATALOGS``.

        There is no SQLAlchemy inspector equivalent for catalog enumeration.
        """
        try:
            from sqlalchemy import text

            with self._connection.connect() as conn:
                rows = conn.execute(text("SHOW CATALOGS")).fetchall()
            return [str(row[0]) for row in rows]
        except Exception:
            LOGGER.warning("Failed to list catalogs", exc_info=True)
            return []

    def _get_external_schemas(
        self,
        *,
        catalog: str,
        include_tables: bool,
        include_table_details: bool,
    ) -> list[Schema]:
        """List databases in an external catalog via ``SHOW DATABASES``."""
        try:
            from sqlalchemy import text

            with self._connection.connect() as conn:
                rows = conn.execute(
                    text(f"SHOW DATABASES IN {_quote(catalog)}")
                ).fetchall()
            db_names = [
                str(row[0])
                for row in rows
                if str(row[0]).lower() not in _SYSTEM_SCHEMAS
            ]
        except Exception:
            LOGGER.warning(
                "Failed to list databases in catalog %r",
                catalog,
                exc_info=True,
            )
            return []

        schemas: list[Schema] = []
        for db_name in db_names:
            tables: list[DataTable] = []
            if include_tables:
                tables = self._get_external_tables(
                    schema=db_name,
                    database=catalog,
                    include_table_details=include_table_details,
                )
            schemas.append(Schema(name=db_name, tables=tables))
        return schemas

    def _get_external_tables(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """List tables in an external catalog via ``SHOW FULL TABLES``."""
        try:
            from sqlalchemy import text

            qualified = f"{_quote(database)}.{_quote(schema)}"
            with self._connection.connect() as conn:
                rows = conn.execute(
                    text(f"SHOW FULL TABLES FROM {qualified}")
                ).fetchall()
        except Exception:
            LOGGER.warning(
                "Failed to get tables in %r.%r",
                database,
                schema,
                exc_info=True,
            )
            return []

        tables: list[DataTable] = []
        for row in rows:
            table_name = str(row[0])
            raw_type = str(row[1]).upper() if row[1] else "BASE TABLE"
            table_type: Literal["table", "view"] = (
                "view" if "VIEW" in raw_type else "table"
            )

            if not include_table_details:
                tables.append(
                    DataTable(
                        source_type="connection",
                        source=self.dialect,
                        name=table_name,
                        num_rows=None,
                        num_columns=None,
                        variable_name=None,
                        engine=self._engine_name,
                        type=table_type,
                        columns=[],
                        primary_keys=[],
                        indexes=[],
                    )
                )
            else:
                table = self._get_external_table_details(
                    table_name=table_name,
                    schema_name=schema,
                    database_name=database,
                )
                if table is not None:
                    table.type = table_type
                    tables.append(table)

        return tables

    def _get_external_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Describe an external-catalog table via ``DESC <catalog>.<db>.<table>``."""
        try:
            from sqlalchemy import text

            qualified = (
                f"{_quote(database_name)}"
                f".{_quote(schema_name)}"
                f".{_quote(table_name)}"
            )
            with self._connection.connect() as conn:
                rows = conn.execute(text(f"DESC {qualified}")).fetchall()
        except Exception:
            LOGGER.warning(
                "Failed to get details for %r.%r.%r",
                database_name,
                schema_name,
                table_name,
                exc_info=True,
            )
            return None

        columns = [
            DataTableColumn(
                name=str(row[0]),
                type=sql_type_to_data_type(str(row[1])),
                external_type=str(row[1]),
                sample_values=[],
            )
            for row in rows
        ]

        return DataTable(
            source_type="connection",
            source=self.dialect,
            name=table_name,
            num_rows=None,
            num_columns=len(columns),
            variable_name=None,
            engine=self._engine_name,
            columns=columns,
            primary_keys=[],
            indexes=[],
        )
