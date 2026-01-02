# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataType,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
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
    import duckdb

    try:
        statements = duckdb.extract_statements(query.strip())
    except Exception:
        # May not be valid SQL
        return False

    # duckdb > 1.4.0 added _STATEMENT suffix to the statement types
    STATEMENT_TYPES = {
        "ATTACH_STATEMENT",
        "ATTACH",
        "DETACH_STATEMENT",
        "DETACH",
        "ALTER_STATEMENT",
        "ALTER",
        # This may catch some false positives for other CREATE statements
        "CREATE_STATEMENT",
        "CREATE",
    }

    for statement in statements:
        if statement.type.name in STATEMENT_TYPES:
            return True
    return False


def execute_duckdb_query(
    connection: Optional[duckdb.DuckDBPyConnection], query: str
) -> list[Any]:
    """Execute a DuckDB query and return the result. Uses connection if provided, otherwise uses duckdb."""
    try:
        if connection is None:
            import duckdb

            return duckdb.execute(query).fetchall()

        return connection.execute(query).fetchall()
    except Exception as e:
        if DependencyManager.duckdb.has():
            import duckdb

            # Connection is closed, return empty result
            if isinstance(e, duckdb.ConnectionException):
                LOGGER.debug("Skipping query on closed DuckDB connection")
                return []

        LOGGER.exception("Failed to execute DuckDB query %s", query)
        return []


def get_databases_from_duckdb(
    connection: Optional[duckdb.DuckDBPyConnection],
    engine_name: Optional[VariableName] = None,
) -> list[Database]:
    try:
        return _get_databases_from_duckdb_internal(connection, engine_name)
    except Exception:
        LOGGER.exception("Failed to get databases from DuckDB")
        return []


def _get_empty_databases(
    connection: Optional[duckdb.DuckDBPyConnection],
    engine_name: Optional[VariableName],
) -> list[Database]:
    # Fallback to get database names from DuckDB
    all_dbs = _get_duckdb_database_names(connection)
    return [
        Database(
            name=database,
            dialect="duckdb",
            schemas=[],
            engine=engine_name,
        )
        for database in all_dbs
    ]


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
    tables_result = []
    query = "SHOW ALL TABLES"
    try:
        if connection is None:
            import duckdb

            tables_result = duckdb.execute(query).fetchall()
        else:
            tables_result = connection.execute(query).fetchall()
    except Exception as e:
        if DependencyManager.duckdb.has():
            import duckdb

            # Connection is closed, skip gracefully
            if isinstance(e, duckdb.ConnectionException):
                LOGGER.debug(
                    "Skipping closed DuckDB connection for engine %s",
                    engine_name,
                )
                return []

            # Certain ducklakes don't support SHOW ALL TABLES
            if isinstance(e, duckdb.NotImplementedException):
                return get_duckdb_databases_agg_query(connection, engine_name)

        LOGGER.exception("Failed to get tables from DuckDB")
        return []

    if len(tables_result) == 0:
        return _get_empty_databases(connection, engine_name)

    # Group tables by database and schema
    # databases_dict[database][schema] = [table1, table2, ...]
    databases_dict: dict[str, dict[str, list[DataTable]]] = {}

    SKIP_TABLES = ["duckdb_functions()", "duckdb_types()", "duckdb_settings()"]

    # Bug with Iceberg catalog tables where there is a single column named "__"
    # https://github.com/marimo-team/marimo/issues/6688
    CATALOG_TABLE_COLUMN_NAME = "__"

    for (
        database,
        schema,
        name,
        column_names,
        column_types,
        *_rest,
    ) in tables_result:
        if name in SKIP_TABLES:
            continue

        assert len(column_names) == len(column_types)
        assert isinstance(column_names, list)
        assert isinstance(column_types, list)

        catalog_table = (
            len(column_names) == 1
            and column_names[0] == CATALOG_TABLE_COLUMN_NAME
        )
        if catalog_table:
            qualified_name = f"{database}.{schema}.{name}"
            columns = get_table_columns(connection, qualified_name)
        else:
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

    return form_databases_from_dict(databases_dict, connection, engine_name)


def get_table_columns(
    connection: Optional[duckdb.DuckDBPyConnection], table_name: str
) -> list[DataTableColumn]:
    """Dedicated query to get columns from a table."""
    query = f"DESCRIBE TABLE {table_name}"

    try:
        columns_result = execute_duckdb_query(connection, query)
        if len(columns_result) == 0:
            return []

        columns: list[DataTableColumn] = []

        for (
            column_name,
            column_type,
            _null,
            _key,
            _default,
            _extra,
        ) in columns_result:
            column = DataTableColumn(
                name=column_name,
                type=_db_type_to_data_type(column_type),
                external_type=column_type,
                sample_values=[],
            )
            columns.append(column)
        return columns

    except Exception:
        LOGGER.debug("Failed to get columns from DuckDB")
        return []


def form_databases_from_dict(
    databases_dict: dict[str, dict[str, list[DataTable]]],
    connection: Optional[duckdb.DuckDBPyConnection],
    engine_name: Optional[VariableName],
) -> list[Database]:
    # Convert grouped data into Database objects
    databases: list[Database] = []
    for database, schemas_dict in databases_dict.items():
        schema_list: list[Schema] = []
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

    # There may be remaining databases not surfaced with SHOW ALL TABLES
    # These db's likely have no tables
    for database_name in _get_duckdb_database_names(connection):
        if database_name not in databases_dict:
            databases.append(
                Database(
                    name=database_name,
                    dialect="duckdb",
                    schemas=[],
                    engine=engine_name,
                )
            )
    return databases


def get_duckdb_databases_agg_query(
    connection: Optional[duckdb.DuckDBPyConnection],
    engine_name: Optional[VariableName],
) -> list[Database]:
    """Uses a different query to get database information, which has wider support but has some aggregation overhead"""

    # Cols will be in the form of [{"col": "column_name", "dtype": "data_type"}]
    NAME_KEY = "col"
    DTYPE_KEY = "dtype"

    QUERY = f"""
    SELECT
        database_name,
        schema_name,
        table_name,
        ARRAY_AGG(
            struct_pack({NAME_KEY} := column_name, {DTYPE_KEY} := data_type)
            ORDER BY
                column_index
        ) AS cols
    FROM
        duckdb_columns()
    WHERE
        internal = false
        AND table_name NOT IN ('duckdb_functions()', 'duckdb_types()', 'duckdb_settings()')
    GROUP BY
        database_name,
        schema_name,
        table_name
    ORDER BY database_name, schema_name, table_name
    """

    tables_result = execute_duckdb_query(connection, QUERY)
    if len(tables_result) == 0:
        return _get_empty_databases(connection, engine_name)

    # Group tables by database and schema
    # databases_dict[database][schema] = [table1, table2, ...]
    databases_dict: dict[str, dict[str, list[DataTable]]] = {}

    for (
        database_name,
        schema_name,
        table_name,
        cols,
    ) in tables_result:
        columns: list[DataTableColumn] = []
        assert isinstance(cols, list)
        for col in cols:
            assert isinstance(col, dict)
            assert NAME_KEY in col
            assert DTYPE_KEY in col
            dtype = col[DTYPE_KEY]
            columns.append(
                DataTableColumn(
                    name=col[NAME_KEY],
                    type=_db_type_to_data_type(dtype),
                    external_type=dtype,
                    sample_values=[],
                )
            )

        table = DataTable(
            name=table_name,
            columns=columns,
            source_type="duckdb" if engine_name is None else "connection",
            source=database_name,
            num_rows=None,
            num_columns=len(columns),
            variable_name=None,
            engine=engine_name,
            type="table",
            primary_keys=None,
            indexes=None,
        )

        if database_name not in databases_dict:
            databases_dict[database_name] = {}
        if schema_name not in databases_dict[database_name]:
            databases_dict[database_name][schema_name] = []

        databases_dict[database_name][schema_name].append(table)

    return form_databases_from_dict(databases_dict, connection, engine_name)


def _get_duckdb_database_names(
    connection: Optional[duckdb.DuckDBPyConnection],
) -> list[str]:
    """Get database names from DuckDB. This includes internal databases and databases that have no tables."""
    # Columns
    # 0:"database_name"
    # 1: "database_old"
    # 2: "path"
    # 3: "comment"
    # 4: "tags"
    # 5: "internal"
    # 6: "type"
    # 7: "readonly"
    database_query = "SELECT * FROM duckdb_databases()"

    try:
        databases_result = execute_duckdb_query(connection, database_query)
        if not len(databases_result):
            return []

        database_names: list[str] = []
        for (
            database_name,
            _database_old,
            _path,
            _comment,
            _tags,
            internal,
            *_rest,
        ) in databases_result:
            internal = bool(internal)
            # Only include non-internal databases
            if not internal:
                database_names.append(database_name)
        return database_names
    except Exception as e:
        if DependencyManager.duckdb.has():
            import duckdb

            # Connection is closed, skip gracefully
            if isinstance(e, duckdb.ConnectionException):
                LOGGER.debug("Skipping closed DuckDB connection")
                return []

        LOGGER.debug("Failed to get database names from DuckDB")
        return []


_INTEGER_TYPES = {
    "tinyint",
    "smallint",
    "integer",
    "bigint",
    "hugeint",
    "integral",
    "long",
    "short",
    "signed",
    "oid",
    "varint",
    "int",
    "int1",
    "int2",
    "int4",
    "int8",
    "int16",
    "int32",
    "int64",
    "int128",
    "ubigint",
    "uhugeint",
    "usmallint",
    "utinyint",
}
_NUMERIC_TYPES = {"float", "real", "double", "decimal", "numeric", "dec"}
_BOOLEAN_TYPES = {"boolean", "bool", "logical"}
_STRING_TYPES = {
    "varchar",
    "char",
    "bpchar",
    "text",
    "string",
    "blob",
    "uuid",
    "guid",
    "nvarchar",
}
_TIME_TYPES = {"time", "time with time zone", "timetz"}
_DATETIME_TYPES = {"datetime", "interval"}
_BINARY_TYPES = {"bit", "bitstring", "binary", "varbinary", "bytea"}
_UNKNOWN_TYPES = {
    "row",
    "geometry",
    # Null type (can occur when attaching databases or with unknown column types)
    "null",
    '"null"',
}


def _db_type_to_data_type(db_type: str) -> DataType:
    """Convert a DuckDB type to a Marimo data type.
    Reference: https://duckdb.org/docs/stable/sql/data_types/overview
    Latest types: https://github.com/marimo-team/codemirror-sql/blob/caa7c664135988b634f55a3e57a1327a5ffeede2/src/dialects/duckdb/duckdb.ts
    """
    db_type = db_type.lower()

    # Check for exact matches first, then patterns

    if db_type in _INTEGER_TYPES or db_type.startswith("uint"):
        return "integer"

    if (
        db_type in _NUMERIC_TYPES
        or db_type.startswith("decimal")
        or db_type.startswith("float")
    ):
        return "number"

    if db_type in _BOOLEAN_TYPES:
        return "boolean"

    if db_type in _STRING_TYPES:
        return "string"

    if db_type == "date":
        return "date"
    if db_type in _TIME_TYPES:
        return "time"
    if db_type in _DATETIME_TYPES or db_type.startswith("timestamp"):
        return "datetime"

    # Binary types (represented as string)
    if db_type in _BINARY_TYPES:
        return "string"

    # Enum types (represented as string)
    if db_type == "enum" or db_type.startswith("enum"):
        return "string"

    # Nested types
    if (
        db_type.startswith("union")
        or db_type.startswith("map")
        or db_type.startswith("struct")
        or db_type.startswith("list")
        or db_type.startswith("array")
        or db_type.startswith("json")
        or ("[" in db_type and "]" in db_type)
    ):
        return "unknown"

    # Other special types
    if db_type in _UNKNOWN_TYPES:
        return "unknown"

    LOGGER.warning("Unknown DuckDB type: %s", db_type)
    return "unknown"
