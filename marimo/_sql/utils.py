# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from marimo._data.models import DataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)

if TYPE_CHECKING:
    import duckdb


def wrapped_sql(
    query: str,
    connection: Optional[duckdb.DuckDBPyConnection],
    tables: Optional[dict[str, Any]] = None,
) -> Optional[duckdb.DuckDBPyRelation]:
    DependencyManager.duckdb.require("to execute sql")

    # In Python globals() are scoped to modules; since this function
    # is in a different module than user code, globals() doesn't return
    # the kernel globals, it just returns this module's global namespace.
    #
    # However, duckdb needs access to the kernel's globals. For this reason,
    # we manually exec duckdb and provide it with the kernel's globals.
    if connection is None:
        import duckdb

        connection = cast(duckdb.DuckDBPyConnection, duckdb)

    if tables is None:
        tables = {}

    previous_globals = {}
    try:
        ctx = get_context()
        previous_globals = ctx.globals.copy()
        ctx.globals.update(tables)
        tables = ctx.globals
    except ContextNotInitializedError:
        pass

    relation = None
    try:
        relation = eval(
            "connection.sql(query=query)",
            tables,
            {"query": query, "connection": connection},
        )
        import duckdb

        assert isinstance(relation, (type(None), duckdb.DuckDBPyRelation))
    finally:
        if previous_globals:
            ctx.globals.clear()
            ctx.globals.update(previous_globals)
    return relation


def fetch_one(
    query: str,
    connection: Optional[duckdb.DuckDBPyConnection] = None,
    tables: Optional[dict[str, Any]] = None,
) -> tuple[Any, ...] | None:
    stats_table = wrapped_sql(query, connection=connection, tables=tables)
    if stats_table is None:
        return None
    return stats_table.fetchone()


def raise_df_import_error(pkg: str) -> None:
    raise ModuleNotFoundError(
        "pandas or polars is required to execute sql. "
        + "You can install them with 'pip install pandas polars'",
        name=pkg,
    )


def sql_type_to_data_type(type_str: str) -> DataType:
    """Convert SQL type string to DataType"""
    type_str = type_str.lower()
    if any(x in type_str for x in ("int", "serial")):
        return "integer"
    elif any(x in type_str for x in ("float", "double", "decimal", "numeric")):
        return "number"
    elif any(x in type_str for x in ("timestamp", "datetime")):
        return "datetime"
    elif "date" in type_str:
        return "date"
    elif "bool" in type_str:
        return "boolean"
    elif any(x in type_str for x in ("char", "text")):
        return "string"
    else:
        return "string"
