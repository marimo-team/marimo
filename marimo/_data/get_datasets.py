# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataType,
    Schema,
)
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import duckdb


def get_datasets_from_variables(
    variables: list[tuple[VariableName, object]],
) -> list[DataTable]:
    tables: list[DataTable] = []
    for variable_name, value in variables:
        table = _get_data_table(value, variable_name)
        if table is not None:
            tables.append(table)

    return tables


def _get_data_table(
    value: object, variable_name: VariableName
) -> Optional[DataTable]:
    try:
        table = get_table_manager_or_none(value)
        if table is None:
            return None

        columns = [
            DataTableColumn(
                name=column_name,
                type=column_type[0],
                external_type=column_type[1],
                sample_values=table.get_sample_values(column_name),
            )
            for column_name, column_type in table.get_field_types()
        ]
        return DataTable(
            name=variable_name,
            variable_name=variable_name,
            num_rows=table.get_num_rows(force=False),
            num_columns=table.get_num_columns(),
            source_type="local",
            source="memory",
            columns=columns,
        )
    except Exception as e:
        LOGGER.error(
            "Failed to get table data for variable %s",
            variable_name,
            exc_info=e,
        )
        return None


def has_updates_to_datasource(query: str) -> bool:
    import duckdb  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

    try:
        statements = duckdb.extract_statements(query.strip())
    except Exception:
        # May not be valid SQL
        return False

    return any(
        statement.type == duckdb.StatementType.ATTACH
        or statement.type == duckdb.StatementType.DETACH
        or statement.type == duckdb.StatementType.ALTER
        # This may catch some false positives for other CREATE statements
        or statement.type == duckdb.StatementType.CREATE
        for statement in statements
    )


def get_databases_from_duckdb(
    connection: Optional[duckdb.DuckDBPyConnection],
    engine_name: Optional[VariableName] = None,
) -> list[Database]:
    try:
        return _get_databases_from_duckdb_internal(connection, engine_name)
    except Exception:
        LOGGER.exception("Failed to get databases from DuckDB")
        return []


def _get_databases_from_duckdb_internal(
    connection: Optional[duckdb.DuckDBPyConnection],
    engine_name: Optional[VariableName] = None,
) -> list[Database]:
    """Get database information from DuckDB."""
    # Columns
    # 0:"database"
    # 1:"schema"
    # 2:"name"
    # 3:"column_names"
    # 4:"column_types"
    # 5:"temporary"
    if connection is None:
        import duckdb

        databases = duckdb.execute("SHOW ALL TABLES").fetchall()
    else:
        databases = connection.execute("SHOW ALL TABLES").fetchall()
    if not len(databases):
        # No tables
        return []

    # Group tables by database and schema
    # databases_dict[database][schema] = [table1, table2, ...]
    databases_dict: dict[str, dict[str, list[DataTable]]] = {}

    for (
        database,
        schema,
        name,
        column_names,
        column_types,
        *_rest,
    ) in databases:
        assert len(column_names) == len(column_types)
        assert isinstance(column_names, list)
        assert isinstance(column_types, list)

        columns = [
            DataTableColumn(
                name=column_name,
                type=_db_type_to_data_type(column_type),
                external_type=column_type,
                sample_values=[],
            )
            for column_name, column_type in zip(
                cast(list[str], column_names),
                cast(list[str], column_types),
            )
        ]

        table = DataTable(
            source_type="duckdb" if engine_name is None else "connection",
            source=database,
            name=name,
            num_rows=None,
            num_columns=len(columns),
            variable_name=None,
            columns=columns,
            engine=engine_name,
        )

        if database not in databases_dict:
            databases_dict[database] = {}
        if schema not in databases_dict[database]:
            databases_dict[database][schema] = []

        databases_dict[database][schema].append(table)

    # Convert grouped data into Database objects
    databases = []
    for database, schemas_dict in databases_dict.items():
        schema_list = []
        for schema_name, tables in schemas_dict.items():
            schema_list.append(Schema(name=schema_name, tables=tables))
        databases.append(
            Database(
                name=database,
                dialect="duckdb",
                schemas=schema_list,
                engine=engine_name,
            )
        )
    return databases


def _db_type_to_data_type(db_type: str) -> DataType:
    db_type = db_type.lower()
    # Numeric types
    if db_type in [
        "tinyint",
        "smallint",
        "integer",
        "bigint",
        "hugeint",
        "utinyint",
        "usmallint",
        "uinteger",
        "ubigint",
        "uhugeint",
    ]:
        return "integer"
    if (
        db_type
        in [
            "float",
            "real",
            "double",
            "decimal",
            "numeric",
        ]
        or db_type.startswith("decimal")
        or db_type.startswith("float")
    ):
        return "number"
    # Boolean type
    if db_type == "boolean":
        return "boolean"
    # String types
    if db_type in [
        "varchar",
        "char",
        "bpchar",
        "text",
        "string",
        "blob",
        "uuid",
    ]:
        return "string"
    # Date and Time types
    if db_type == "date":
        return "date"
    if db_type == "time":
        return "time"
    if db_type in [
        "timestamp",
        "timestamp_ns",
        "timestamp with time zone",
        "timestamptz",
        "datetime",
        "interval",
    ]:
        return "datetime"
    # Nested types
    if db_type in ["array", "list", "struct", "map", "union", "varchar[]"]:
        return "unknown"
    # Special types
    if db_type == "bit":
        return "string"  # Representing bit as string
    if db_type == "enum" or db_type.startswith("enum"):
        return "string"  # Representing enum as string

    LOGGER.warning("Unknown DuckDB type: %s", db_type)
    # Unknown type
    return "unknown"
