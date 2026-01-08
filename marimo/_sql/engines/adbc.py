# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, Optional, Protocol, Union, cast

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataTableType,
    DataType,
    Schema,
)
from marimo._sql.engines.types import InferenceConfig, SQLConnection
from marimo._sql.utils import CHEAP_DISCOVERY_DATABASES, convert_to_output
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pandas as pd
    import polars as pl
    import pyarrow as pa

AdbcGetObjectsDepth = Literal[
    "all", "catalogs", "db_schemas", "tables", "columns"
]


class AdbcDbApiCursor(Protocol):
    description: Any

    def execute(
        self, query: str, parameters: Sequence[Any] = ...
    ) -> AdbcDbApiCursor: ...

    def fetch_arrow_table(self) -> pa.Table: ...

    def close(self) -> None: ...


class AdbcDbApiConnection(Protocol):
    """ADBC DB-API wrapper connection.

    For the canonical DB-API types/signatures, see:
    https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html#adbc_driver_manager.dbapi.Connection
    """

    def cursor(self) -> AdbcDbApiCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...

    adbc_current_catalog: str
    adbc_current_db_schema: str

    def adbc_get_objects(
        self,
        *,
        depth: AdbcGetObjectsDepth = "all",
        catalog_filter: str | None = None,
        db_schema_filter: str | None = None,
        table_name_filter: str | None = None,
        table_types_filter: list[str] | None = None,
        column_name_filter: str | None = None,
    ) -> pa.RecordBatchReader: ...

    def adbc_get_table_schema(
        self, table_name: str, *, db_schema_filter: str | None = None
    ) -> pa.Schema: ...

    def adbc_get_info(self) -> dict[str | int, Any]: ...


def _resolve_table_type(table_type: str) -> DataTableType:
    if "view" in table_type.lower():
        return "view"
    return "table"


def _adbc_info_to_dialect(*, info: dict[str | int, Any]) -> str:
    """Infer marimo's dialect identifier from ADBC metadata.

    Notes:
    ADBC DB-API wrappers expose driver/database metadata via ``adbc_get_info()``,
    including a ``vendor_name`` and ``driver_name`` (see ADBC quickstart:
    https://arrow.apache.org/adbc/current/python/quickstart.html).

    In marimo, ``engine.dialect`` is used primarily for editor/formatter dialect
    selection and for display in the UI.
    """

    vendor_name = info.get("vendor_name")
    vendor = vendor_name if isinstance(vendor_name, str) else None

    if vendor is not None and vendor.strip():
        return vendor.strip().lower()

    return "sql"


def _schema_field_to_data_type(external_type: str) -> DataType:
    """Map an Arrow-like dtype string to marimo DataType."""
    t = external_type.lower()
    if "bool" in t:
        return "boolean"
    if "int" in t or "uint" in t:
        return "integer"
    if "float" in t or "double" in t or "decimal" in t:
        return "number"
    if "timestamp" in t:
        return "datetime"
    if t.startswith("date") or " date" in t:
        return "date"
    if t.startswith("time") or " time" in t:
        return "time"
    return "string"


class AdbcConnectionCatalog:
    """Catalog implementation backed by ADBC DB-API wrapper extensions."""

    def __init__(
        self,
        *,
        adbc_connection: AdbcDbApiConnection,
        dialect: str,
        engine_name: Optional[VariableName],
    ) -> None:
        self._adbc_connection = adbc_connection
        self._dialect = dialect
        self._engine_name = engine_name

    def get_default_database(self) -> Optional[str]:
        try:
            return self._adbc_connection.adbc_current_catalog
        except Exception:
            # Some drivers (like arrow-adbc-driver-sqlite) do not support the standardized option for current
            # catalog/schema; treat as unavailable.
            LOGGER.debug("Failed to read ADBC current catalog", exc_info=True)
            return None

    def get_default_schema(self) -> Optional[str]:
        try:
            return self._adbc_connection.adbc_current_db_schema
        except Exception:
            LOGGER.debug("Failed to read ADBC current schema", exc_info=True)
            return None

    def _resolve_should_auto_discover(
        self, value: Union[bool, Literal["auto"]]
    ) -> bool:
        if value == "auto":
            return self._dialect.lower() in CHEAP_DISCOVERY_DATABASES
        return value

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        databases: list[Database] = []
        include_schemas_bool = self._resolve_should_auto_discover(
            include_schemas
        )
        include_tables_bool = self._resolve_should_auto_discover(
            include_tables
        )
        include_table_details_bool = self._resolve_should_auto_discover(
            include_table_details
        )
        if not include_schemas_bool:
            include_tables_bool = False
        if not include_tables_bool:
            include_table_details_bool = False

        depth: AdbcGetObjectsDepth
        if not include_schemas_bool:
            depth = "catalogs"
        elif not include_tables_bool:
            depth = "db_schemas"
        else:
            depth = "tables"

        objects_pylist = (
            self._adbc_connection.adbc_get_objects(depth=depth)
            .read_all()
            .to_pylist()
        )

        for catalog_row in objects_pylist:
            catalog_name_obj = catalog_row.get("catalog_name")
            catalog_name = (
                "" if catalog_name_obj is None else str(catalog_name_obj)
            )

            schemas: list[Schema] = []
            if include_schemas_bool:
                schema_rows = catalog_row.get("catalog_db_schemas") or []
                for schema_row in schema_rows:
                    schema_name_obj = schema_row.get("db_schema_name")
                    schema_name = (
                        "" if schema_name_obj is None else str(schema_name_obj)
                    )

                    tables: list[DataTable] = []
                    if include_tables_bool:
                        table_rows = schema_row.get("db_schema_tables") or []
                        for table_row in table_rows:
                            table_name_obj = table_row.get("table_name")
                            if table_name_obj is None:
                                continue
                            table_name = str(table_name_obj)
                            table_type_obj = (
                                table_row.get("table_type") or "TABLE"
                            )
                            table_type = str(table_type_obj)

                            if include_table_details_bool:
                                details = self.get_table_details(
                                    table_name=table_name,
                                    schema_name=schema_name,
                                    database_name=catalog_name,
                                )
                                if details is not None:
                                    details.type = _resolve_table_type(
                                        table_type
                                    )
                                    tables.append(details)
                            else:
                                tables.append(
                                    DataTable(
                                        source_type="connection",
                                        source=self._dialect,
                                        name=table_name,
                                        num_rows=None,
                                        num_columns=None,
                                        variable_name=None,
                                        engine=self._engine_name,
                                        type=_resolve_table_type(table_type),
                                        columns=[],
                                        primary_keys=[],
                                        indexes=[],
                                    )
                                )

                    schemas.append(Schema(name=schema_name, tables=tables))

            databases.append(
                Database(
                    name=catalog_name,
                    dialect=self._dialect,
                    schemas=schemas,
                    engine=self._engine_name,
                )
            )

        return databases

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        tables: list[DataTable] = []
        objects_pylist = (
            self._adbc_connection.adbc_get_objects(
                depth="tables",
                catalog_filter=database or None,
                db_schema_filter=schema or None,
            )
            .read_all()
            .to_pylist()
        )

        for catalog_row in objects_pylist:
            schema_rows = catalog_row.get("catalog_db_schemas") or []
            for schema_row in schema_rows:
                table_rows = schema_row.get("db_schema_tables") or []
                for table_row in table_rows:
                    table_name_obj = table_row.get("table_name")
                    if table_name_obj is None:
                        continue
                    table_name = str(table_name_obj)
                    table_type_obj = table_row.get("table_type") or "TABLE"
                    table_type = str(table_type_obj)

                    if include_table_details:
                        details = self.get_table_details(
                            table_name=table_name,
                            schema_name=schema,
                            database_name=database,
                        )
                        if details is not None:
                            details.type = _resolve_table_type(table_type)
                            tables.append(details)
                    else:
                        tables.append(
                            DataTable(
                                source_type="connection",
                                source=self._dialect,
                                name=table_name,
                                num_rows=None,
                                num_columns=None,
                                variable_name=None,
                                engine=self._engine_name,
                                type=_resolve_table_type(table_type),
                                columns=[],
                                primary_keys=[],
                                indexes=[],
                            )
                        )
        return tables

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        _ = database_name
        try:
            schema = self._adbc_connection.adbc_get_table_schema(
                table_name, db_schema_filter=schema_name or None
            )
        except Exception:
            LOGGER.warning(
                "Failed to get table schema for %s.%s.%s",
                database_name,
                schema_name,
                table_name,
                exc_info=True,
            )
            return None

        cols: list[DataTableColumn] = []
        try:
            for field in cast(Any, schema):
                external_type = str(getattr(field, "type", "string"))
                cols.append(
                    DataTableColumn(
                        name=str(getattr(field, "name", "")),
                        type=_schema_field_to_data_type(external_type),
                        external_type=external_type,
                        sample_values=[],
                    )
                )
        except Exception:
            LOGGER.warning("Failed to parse ADBC table schema", exc_info=True)
            cols = []

        return DataTable(
            source_type="connection",
            source=self._dialect,
            name=table_name,
            num_rows=None,
            num_columns=len(cols) if cols else None,
            variable_name=None,
            engine=self._engine_name,
            columns=cols,
            primary_keys=[],
            indexes=[],
        )


class AdbcDBAPIEngine(SQLConnection[AdbcDbApiConnection]):
    """ADBC DB-API wrapper connection."""

    def __init__(
        self,
        connection: AdbcDbApiConnection,
        engine_name: Optional[VariableName] = None,
    ) -> None:
        super().__init__(connection, engine_name)
        self._catalog = AdbcConnectionCatalog(
            adbc_connection=self._connection,
            dialect=self.dialect,
            engine_name=self._engine_name,
        )

    @property
    def source(self) -> str:
        return "adbc"

    @property
    def dialect(self) -> str:
        try:
            info = self._connection.adbc_get_info()
            if isinstance(info, dict):
                return _adbc_info_to_dialect(info=info)
        except Exception:
            LOGGER.debug("Failed to read ADBC driver metadata", exc_info=True)
        return "sql"

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if isinstance(var, ModuleType):
            return False

        try:
            # First, validate the connection-level surface area to avoid
            # accidentally classifying regular DB-API connections as ADBC.
            required_connection_methods = (
                "cursor",
                "commit",
                "rollback",
                "close",
                # ADBC DB-API extension methods.
                "adbc_get_objects",
                "adbc_get_table_schema",
                "adbc_get_info",
            )
            if not all(
                callable(getattr(var, method, None))
                for method in required_connection_methods
            ):
                return False

            # Then, validate the cursor shape (ADBC-specific).
            # We do not execute queries; we also best-effort close the cursor
            # to avoid leaking resources during compatibility checks.
            cursor = var.cursor()
            try:
                required_cursor_methods = ("execute", "fetch_arrow_table")
                return all(
                    callable(getattr(cursor, method, None))
                    for method in required_cursor_methods
                )
            finally:
                # Never fail compatibility checks due to close errors
                try:
                    cursor.close()
                except Exception:
                    LOGGER.debug(
                        "Failed to close cursor during ADBC compatibility check",
                        exc_info=True,
                    )
        except Exception:
            LOGGER.debug("ADBC compatibility check failed", exc_info=True)
            return False

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables="auto",
            auto_discover_columns=False,
        )

    def get_default_database(self) -> Optional[str]:
        return self._catalog.get_default_database()

    def get_default_schema(self) -> Optional[str]:
        return self._catalog.get_default_schema()

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        return self._catalog.get_databases(
            include_schemas=include_schemas,
            include_tables=include_tables,
            include_table_details=include_table_details,
        )

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        return self._catalog.get_tables_in_schema(
            schema=schema,
            database=database,
            include_table_details=include_table_details,
        )

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        return self._catalog.get_table_details(
            table_name=table_name,
            schema_name=schema_name,
            database_name=database_name,
        )

    def execute(
        self, query: str, parameters: Optional[Sequence[Any]] = None
    ) -> Any:
        sql_output_format = self.sql_output_format()
        cursor = self._connection.cursor()

        def _try_commit() -> None:
            try:
                self._connection.commit()
            except Exception:
                LOGGER.info("Unable to commit transaction", exc_info=True)

        try:
            cursor.execute(query, parameters or ())

            if not getattr(cursor, "description", None):
                _try_commit()
                return None

            arrow_table = cursor.fetch_arrow_table()

            def convert_to_polars() -> pl.DataFrame | pl.Series:
                import polars as pl

                return pl.from_arrow(arrow_table)

            def convert_to_pandas() -> pd.DataFrame:
                return arrow_table.to_pandas()

            result = convert_to_output(
                sql_output_format=sql_output_format,
                to_polars=convert_to_polars,
                to_pandas=convert_to_pandas,
                to_native=lambda: arrow_table,
            )
            _try_commit()
            return result
        finally:
            try:
                cursor.close()
            except Exception:
                LOGGER.info("Failed to close cursor", exc_info=True)
