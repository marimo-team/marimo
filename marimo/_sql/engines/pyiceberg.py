# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import (
    NO_SCHEMA_NAME,
    EngineCatalog,
    InferenceConfig,
    register_engine,
)
from marimo._sql.utils import sql_type_to_data_type
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog


@register_engine
class PyIcebergEngine(EngineCatalog["Catalog"]):
    """PyIceberg engine."""

    def __init__(
        self, connection: Catalog, engine_name: Optional[VariableName] = None
    ) -> None:
        super().__init__(connection, engine_name)
        self.default_database = self.get_default_database()
        self.default_schema = self.get_default_schema()

    @property
    def source(self) -> str:
        return "iceberg"

    @property
    def dialect(self) -> str:
        return "iceberg"

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.pyiceberg.imported():
            return False

        from pyiceberg.catalog import Catalog

        return isinstance(var, Catalog)

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables="auto",
            auto_discover_columns=False,
        )

    def get_default_database(self) -> Optional[str]:
        return None

    def get_default_schema(self) -> Optional[str]:
        return None  # Iceberg doesn't have schemas in the traditional sense

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        """Get all databases from the engine."""
        from pyiceberg.catalog import Catalog

        del include_schemas
        databases: list[Database] = []
        try:
            namespaces = sorted(
                self._connection.list_namespaces()
            )  # Sort for consistent ordering
            for namespace in namespaces:
                tables = []
                if self._resolve_should_auto_discover(include_tables):
                    tables = self.get_tables_in_schema(
                        schema=NO_SCHEMA_NAME,
                        database=Catalog.identifier_to_database(namespace),
                        include_table_details=self._resolve_should_auto_discover(
                            include_table_details
                        ),
                    )

                databases.append(
                    Database(
                        name=Catalog.identifier_to_database(namespace),
                        dialect=self.dialect,
                        schemas=[
                            Schema(
                                name=NO_SCHEMA_NAME,
                                tables=tables,
                            )
                        ],
                        engine=self._engine_name,
                    )
                )
        except Exception:
            LOGGER.warning("Failed to get databases", exc_info=True)

        return databases

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema."""
        del schema  # Not used since Iceberg doesn't have schemas

        from pyiceberg.catalog import Catalog

        try:
            tables = self._connection.list_tables(database)
            if not include_table_details:
                return [
                    DataTable(
                        source_type="catalog",
                        source=self.dialect,
                        name=Catalog.table_name_from(table),
                        num_rows=None,
                        num_columns=None,
                        variable_name=None,
                        engine=self._engine_name,
                        type="table",
                        columns=[],
                        primary_keys=[],
                        indexes=[],
                    )
                    for table in tables
                ]

            data_tables: list[DataTable] = []
            for table_name in tables:
                table: DataTable | None = self.get_table_details(
                    table_name=Catalog.table_name_from(table_name),
                    schema_name=NO_SCHEMA_NAME,
                    database_name=Catalog.identifier_to_database(database),
                )
                if table is not None:
                    data_tables.append(table)

            return data_tables
        except Exception:
            LOGGER.warning("Failed to get tables in schema", exc_info=True)
            return []

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""
        del schema_name  # Not used since Iceberg doesn't have schemas
        try:
            table = self._connection.load_table((database_name, table_name))
            schema = table.schema()

            cols: list[DataTableColumn] = []
            for field in schema.fields:
                cols.append(
                    DataTableColumn(
                        name=field.name,
                        type=sql_type_to_data_type(str(field.field_type)),
                        external_type=str(field.field_type),
                        sample_values=[],
                    )
                )

            return DataTable(
                source_type="catalog",
                source=self.dialect,
                name=table_name,
                num_rows=None,
                num_columns=len(cols),
                variable_name=None,
                engine=self._engine_name,
                columns=cols,
                primary_keys=[],
                indexes=[],
            )
        except Exception:
            LOGGER.warning(
                f"Failed to get table {table_name} in namespace {database_name}",
                exc_info=True,
            )
            return None

    def _resolve_should_auto_discover(
        self,
        value: Union[bool, Literal["auto"]],
    ) -> bool:
        if value == "auto":
            return self._is_cheap_discovery()
        return value

    def _is_cheap_discovery(self) -> bool:
        return True  # Iceberg metadata is generally fast to access
