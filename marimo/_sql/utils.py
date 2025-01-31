from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

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
) -> "duckdb.DuckDBPyRelation":
    DependencyManager.duckdb.require("to execute sql")

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
