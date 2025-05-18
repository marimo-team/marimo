# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

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
) -> duckdb.DuckDBPyRelation:
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

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        relation = connection.sql(query=query)
    else:
        relation = eval(
            "connection.sql(query=query)",
            ctx.globals,
            {"query": query, "connection": connection},
        )
    return relation


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
