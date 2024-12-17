# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List, Optional, cast

from marimo import _loggers
from marimo._data.models import DataTable, DataTableColumn, DataType
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none

LOGGER = _loggers.marimo_logger()


def get_datasets_from_variables(
    variables: List[tuple[str, object]],
) -> List[DataTable]:
    tables: List[DataTable] = []
    for variable_name, value in variables:
        table = _get_data_table(value, variable_name)
        if table is not None:
            tables.append(table)

    return tables


def _get_data_table(value: object, variable_name: str) -> Optional[DataTable]:
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


def get_datasets_from_duckdb() -> List[DataTable]:
    try:
        return _get_datasets_from_duckdb_internal()
    except Exception as e:
        LOGGER.error(e)
        return []


def _get_datasets_from_duckdb_internal() -> List[DataTable]:
    import duckdb  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

    # Columns
    # 0:"database"
    # 1:"schema"
    # 2:"name"
    # 3:"column_names"
    # 4:"column_types"
    # 5:"temporary"
    databases = duckdb.execute("SHOW ALL TABLES").fetchall()
    if not len(databases):
        # No tables
        return []

    tables: list[DataTable] = []

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

        tables.append(
            DataTable(
                source_type="duckdb",
                source=database,
                name=f"{database}.{schema}.{name}",
                num_rows=None,
                num_columns=len(columns),
                variable_name=None,
                columns=columns,
            )
        )

    return tables


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
    if db_type in [
        "float",
        "real",
        "double",
        "decimal",
        "numeric",
    ] or db_type.startswith("decimal"):
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
        "timestamp with time zone",
        "timestamptz",
        "datetime",
        "interval",
    ]:
        return "datetime"
    # Nested types
    if db_type in ["array", "list", "struct", "map", "union"]:
        return "unknown"
    # Special types
    if db_type == "bit":
        return "string"  # Representing bit as string
    if db_type == "enum":
        return "string"  # Representing enum as string
    # Unknown type
    return "unknown"
