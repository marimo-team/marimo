# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from marimo import _loggers
from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import InferenceConfig, SQLConnection
from marimo._sql.sql_quoting import quote_sql_identifier
from marimo._sql.utils import convert_to_output, sql_type_to_data_type
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    from sqlalchemy import Engine

# StarRocks databases (marimo Schemas) that are internal and not useful to surface.
_SYSTEM_SCHEMAS = frozenset({"information_schema", "sys", "_statistics_"})


def _quote(name: str) -> str:
    return quote_sql_identifier(name, dialect="starrocks")


class StarRocksEngine(SQLConnection["Engine"]):
    """StarRocks SQL engine with multi-catalog support.

    StarRocks uses a three-level hierarchy: Catalog → Database → Table.
    This maps to marimo's Database → Schema → Table model:

      - marimo ``Database``  ↔  StarRocks Catalog
      - marimo ``Schema``    ↔  StarRocks Database
      - marimo ``DataTable`` ↔  StarRocks Table
    """

    def __init__(
        self, connection: Engine, engine_name: Optional[VariableName] = None
    ) -> None:
        super().__init__(connection, engine_name)

    @property
    def source(self) -> str:
        return "starrocks"

    @property
    def dialect(self) -> str:
        return "starrocks"

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.sqlalchemy.imported():
            return False
        if not DependencyManager.starrocks.imported():
            return False

        from sqlalchemy.engine import Engine

        return isinstance(var, Engine) and str(var.dialect.name) == "starrocks"

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables="auto",
            auto_discover_columns=False,
        )

    def execute(self, query: str) -> Any:
        from sqlalchemy import text

        sql_output_format = self.sql_output_format()

        with self._connection.connect() as conn:
            result = conn.execute(text(query))
            if sql_output_format == "native":
                return result

            rows = result.fetchall() if result.returns_rows else None

            try:
                conn.commit()
            except Exception:
                LOGGER.info("Unable to commit transaction", exc_info=True)

            if rows is None:
                return None

            def convert_to_polars() -> pl.DataFrame:
                import polars as pl

                return pl.DataFrame(rows)

            def convert_to_pandas() -> pd.DataFrame:
                import pandas as pd

                return pd.DataFrame(rows)

            return convert_to_output(
                sql_output_format=sql_output_format,
                to_polars=convert_to_polars,
                to_pandas=convert_to_pandas,
            )

    def get_default_database(self) -> Optional[str]:
        """Return the name of the current catalog."""
        try:
            from sqlalchemy import text

            with self._connection.connect() as conn:
                row = conn.execute(
                    text("SELECT CATALOG()")
                ).fetchone()
            if row is not None and row[0] is not None:
                return str(row[0])
        except Exception:
            LOGGER.warning("Failed to get current catalog", exc_info=True)
        return None

    def get_default_schema(self) -> Optional[str]:
        """Return the name of the current database within the current catalog."""
        try:
            from sqlalchemy import text

            with self._connection.connect() as conn:
                row = conn.execute(text("SELECT DATABASE()")).fetchone()
            if row is not None and row[0] is not None:
                return str(row[0])
        except Exception:
            LOGGER.warning("Failed to get current database", exc_info=True)
        return None

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        """Return all catalogs, each containing its databases as schemas.

        Args:
            include_schemas: Whether to enumerate databases within each
                catalog. ``"auto"`` resolves to ``True``.
            include_tables: Whether to enumerate tables within each database.
                ``"auto"`` resolves to ``False`` (StarRocks catalogs can be
                very large, so table discovery is opt-in).
            include_table_details: Whether to fetch column-level metadata for
                each table. ``"auto"`` resolves to ``False``.
        """
        should_include_schemas = self._resolve_auto(include_schemas, default=True)
        should_include_tables = self._resolve_auto(include_tables, default=False)
        should_include_details = self._resolve_auto(
            include_table_details, default=False
        )

        databases: list[Database] = []
        for catalog in self._list_catalogs():
            schemas: list[Schema] = []
            if should_include_schemas:
                for db_name in self._list_databases_in_catalog(catalog):
                    tables: list[DataTable] = []
                    if should_include_tables:
                        tables = self.get_tables_in_schema(
                            schema=db_name,
                            database=catalog,
                            include_table_details=should_include_details,
                        )
                    schemas.append(Schema(name=db_name, tables=tables))
            databases.append(
                Database(
                    name=catalog,
                    dialect=self.dialect,
                    schemas=schemas,
                    engine=self._engine_name,
                )
            )
        return databases

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a StarRocks database.

        Args:
            schema: The StarRocks database name.
            database: The StarRocks catalog name.
            include_table_details: Whether to fetch column metadata.
        """
        try:
            from sqlalchemy import text

            query = (
                f"SELECT TABLE_NAME, TABLE_TYPE "
                f"FROM {_quote(database)}.information_schema.tables "
                f"WHERE TABLE_SCHEMA = :schema"
            )
            with self._connection.connect() as conn:
                rows = conn.execute(text(query), {"schema": schema}).fetchall()
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
                table = self.get_table_details(
                    table_name=table_name,
                    schema_name=schema,
                    database_name=database,
                )
                if table is not None:
                    table.type = table_type
                    tables.append(table)

        return tables

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Fetch column-level metadata for a table.

        Args:
            table_name: The table name.
            schema_name: The StarRocks database name.
            database_name: The StarRocks catalog name.
        """
        try:
            from sqlalchemy import text

            query = (
                f"SELECT COLUMN_NAME, DATA_TYPE "
                f"FROM {_quote(database_name)}.information_schema.columns "
                f"WHERE TABLE_SCHEMA = :schema AND TABLE_NAME = :table "
                f"ORDER BY ORDINAL_POSITION"
            )
            with self._connection.connect() as conn:
                rows = conn.execute(
                    text(query),
                    {"schema": schema_name, "table": table_name},
                ).fetchall()
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

    def _list_catalogs(self) -> list[str]:
        """Return all catalog names, excluding built-in system catalogs."""
        try:
            from sqlalchemy import text

            with self._connection.connect() as conn:
                rows = conn.execute(text("SHOW CATALOGS")).fetchall()
            return [str(row[0]) for row in rows]
        except Exception:
            LOGGER.warning("Failed to list catalogs", exc_info=True)
            return []

    def _list_databases_in_catalog(self, catalog: str) -> list[str]:
        """Return all database names within *catalog*, excluding system databases."""
        try:
            from sqlalchemy import text

            with self._connection.connect() as conn:
                rows = conn.execute(
                    text(f"SHOW DATABASES IN {_quote(catalog)}")
                ).fetchall()
            return [
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

    @staticmethod
    def _resolve_auto(
        value: Union[bool, Literal["auto"]], *, default: bool
    ) -> bool:
        """Resolve an ``"auto"`` inference flag to a concrete boolean."""
        if value == "auto":
            return default
        return value
