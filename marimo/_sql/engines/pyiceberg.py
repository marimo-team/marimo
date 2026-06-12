# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from marimo import _loggers
from marimo._data.models import (
    CatalogNode,
    Database,
    DataTable,
    DataTableColumn,
    Namespace,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import (
    NO_SCHEMA_NAME,
    EngineCatalog,
    InferenceConfig,
)
from marimo._sql.utils import sql_type_to_data_type
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from pyiceberg.catalog import Catalog


class PyIcebergEngine(EngineCatalog["Catalog"]):
    """PyIceberg engine."""

    def __init__(
        self, connection: Catalog, engine_name: VariableName | None = None
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
        # List the first level of namespaces eagerly; fetch their tables and
        # deeper sub-namespaces on expand.
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables=False,
            auto_discover_columns=False,
        )

    def get_default_database(self) -> str | None:
        return None

    def get_default_schema(self) -> str | None:
        return None  # Iceberg doesn't have schemas in the traditional sense

    def get_databases(
        self,
        *,
        include_schemas: bool | Literal["auto"],
        include_tables: bool | Literal["auto"],
        include_table_details: bool | Literal["auto"],
    ) -> list[Database]:
        """Get all databases from the engine.

        Each top-level Iceberg namespace becomes a `Database`. Nested
        sub-namespaces are exposed as `Namespace` nodes in `children`.
        """
        from pyiceberg.catalog import Catalog

        children_resolved = self._resolve_should_auto_discover(include_schemas)
        should_include_tables = self._resolve_should_auto_discover(
            include_tables
        )
        should_include_details = self._resolve_should_auto_discover(
            include_table_details
        )
        databases: list[Database] = []
        try:
            # Top-level namespaces only; deeper children are discovered lazily.
            namespaces = sorted(self._connection.list_namespaces())
            for namespace in namespaces:
                database_name = Catalog.namespace_to_string(namespace)
                children: list[CatalogNode] = []
                if children_resolved:
                    children = self._database_children(
                        namespace,
                        include_tables=should_include_tables,
                        include_table_details=should_include_details,
                    )
                databases.append(
                    Database(
                        name=database_name,
                        dialect=self.dialect,
                        children=children,
                        children_resolved=children_resolved,
                        engine=self._engine_name,
                    )
                )
        except Exception as e:
            # Check if this is a permission/auth error (e.g., 403 Forbidden)
            error_str = str(e).lower()
            if "403" in error_str or "forbidden" in error_str:
                LOGGER.debug(
                    "Cannot list namespaces due to insufficient permissions. "
                    "You can still access tables if you know the namespace name."
                )
            else:
                LOGGER.warning("Failed to get databases", exc_info=True)

        return databases

    def get_schemas(
        self,
        *,
        database: str | None,
        include_tables: bool,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[CatalogNode]:
        """Get catalog nodes within a top-level namespace `database`.

        Empty `schema_path` returns a schemaless `Schema` (the namespace's own
        tables) plus one `Namespace` per immediate sub-namespace; a non-empty
        path returns the immediate child namespaces at that path.
        """
        if database is None:
            raise ValueError("database is required for Iceberg schemas")

        from pyiceberg.catalog import Catalog

        namespace = Catalog.identifier_to_tuple(database)
        if schema_path:
            namespace = (*namespace, *schema_path)
            # At a nested path we only list immediate child namespaces. Leaf
            # namespaces that hold tables directly (no sub-namespaces) return
            # an empty list here; tables are fetched via get_tables_in_schema.
            return self._child_namespaces(
                namespace,
                include_tables=include_tables,
                include_table_details=include_table_details,
            )

        return self._database_children(
            namespace,
            include_tables=include_tables,
            include_table_details=include_table_details,
        )

    def _database_children(
        self,
        namespace: tuple[str, ...],
        *,
        include_tables: bool,
        include_table_details: bool,
    ) -> list[CatalogNode]:
        """Top-level children for a database namespace."""
        from pyiceberg.catalog import Catalog

        database_name = Catalog.namespace_to_string(namespace)
        children: list[CatalogNode] = [
            Schema(
                name=NO_SCHEMA_NAME,
                tables=self.get_tables_in_schema(
                    schema=NO_SCHEMA_NAME,
                    database=database_name,
                    include_table_details=include_table_details,
                )
                if include_tables
                else [],
                tables_resolved=include_tables,
            )
        ]
        children.extend(
            self._child_namespaces(
                namespace,
                include_tables=include_tables,
                include_table_details=include_table_details,
            )
        )
        return children

    def _child_namespaces(
        self,
        namespace: tuple[str, ...],
        *,
        include_tables: bool,
        include_table_details: bool,
    ) -> list[CatalogNode]:
        """Immediate child namespaces of `namespace` as `Namespace` nodes."""
        try:
            children = sorted(self._connection.list_namespaces(namespace))
        except Exception:
            LOGGER.warning("Failed to list child namespaces", exc_info=True)
            return []
        nodes: list[CatalogNode] = [
            self._namespace_to_node(
                child,
                include_tables=include_tables,
                include_table_details=include_table_details,
            )
            for child in children
        ]
        return nodes

    def _namespace_to_node(
        self,
        namespace: tuple[str, ...],
        *,
        include_tables: bool,
        include_table_details: bool,
    ) -> Namespace:
        """Convert an absolute namespace tuple into a `Namespace`.

        `include_tables` also gates sub-namespace recursion: when False, tables
        and children are left deferred and fetched lazily on expand, so a
        collapsed node does no catalog I/O.
        """
        from pyiceberg.catalog import Catalog

        namespace_str = Catalog.namespace_to_string(namespace)
        node_children: list[CatalogNode] = []
        if include_tables:
            node_children.extend(
                self.get_tables_in_schema(
                    schema=NO_SCHEMA_NAME,
                    database=namespace_str,
                    include_table_details=include_table_details,
                )
            )
            node_children.extend(
                self._child_namespaces(
                    namespace,
                    include_tables=include_tables,
                    include_table_details=include_table_details,
                )
            )
        return Namespace(
            name=namespace[-1],
            children=node_children,
            children_resolved=include_tables,
            tables_resolved=include_tables,
        )

    @staticmethod
    def _qualified_namespace(
        database: str, schema_path: list[str] | None
    ) -> str:
        """Fold a `database` + nested `schema_path` into a dotted namespace
        string (the form pyiceberg's catalog calls expect)."""
        if not schema_path:
            return database
        return ".".join([database, *schema_path])

    def get_tables_in_schema(
        self,
        *,
        schema: str,
        database: str,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[DataTable]:
        """Return all tables in a schema."""
        del schema  # Not used since Iceberg doesn't have schemas

        from pyiceberg.catalog import Catalog

        namespace = self._qualified_namespace(database, schema_path)
        try:
            tables = self._connection.list_tables(namespace)
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
                    database_name=namespace,
                )
                if table is not None:
                    data_tables.append(table)

            return data_tables
        except Exception:
            LOGGER.warning("Failed to get tables in schema", exc_info=True)
            return []

    def get_table_details(
        self,
        *,
        table_name: str,
        schema_name: str,
        database_name: str,
        schema_path: list[str] | None = None,
    ) -> DataTable | None:
        """Get a single table from the engine."""
        del schema_name  # Not used since Iceberg doesn't have schemas
        database_name = self._qualified_namespace(database_name, schema_path)
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

    def _is_cheap_discovery(self) -> bool:
        return True  # Iceberg metadata is generally fast to access
