# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._runtime.output import replace

if TYPE_CHECKING:
    import duckdb


def get_default_result_limit() -> Optional[int]:
    limit = os.environ.get("MARIMO_SQL_DEFAULT_LIMIT")
    return int(limit) if limit is not None else None


@mddoc
def sql(
    query: str,
    output: bool = True,
) -> Any:
    """
    Execute a SQL query.

    This uses duckdb to execute the query. Any dataframes in the global
    namespace can be used inside the query.

    The result of the query is displayed in the UI if output is True.

    Args:
        query: The SQL query to execute.
        output: Whether to display the result in the UI. Defaults to True.

    Returns:
        The result of the query.
    """
    DependencyManager.duckdb.require("to execute sql")

    relation = _wrapped_sql(query)

    if not relation:
        return None

    has_limit = _query_includes_limit(query)
    try:
        default_result_limit = get_default_result_limit()
    except OSError:
        default_result_limit = None

    enforce_own_limit = not has_limit and default_result_limit is not None

    if enforce_own_limit:
        relation = relation.limit(
            cast(int, default_result_limit) + 1
        )  # request 1 more

    custom_total_count: Optional[Literal["too_many"]] = None

    df: Any
    if DependencyManager.polars.has():
        df = relation.pl()
        if enforce_own_limit:
            custom_total_count = (
                "too_many"
                if len(df) > cast(int, default_result_limit)
                else None
            )
            df = df.limit(default_result_limit)
    elif DependencyManager.pandas.has():
        df = relation.df()
        if enforce_own_limit:
            custom_total_count = (
                "too_many"
                if len(df) > cast(int, default_result_limit)
                else None
            )
            df = df.head(default_result_limit)
    else:
        raise ModuleNotFoundError(
            "pandas or polars is required to execute sql. "
            + "You can install them with 'pip install pandas polars'"
        )

    if output:
        from marimo._plugins.ui._impl import table

        t = table.table(
            df,
            selection=None,
            page_size=5,
            pagination=True,
            _internal_total_rows=custom_total_count,
        )
        replace(t)
    return df


def _query_includes_limit(query: str) -> bool:
    import duckdb

    try:
        statements = duckdb.extract_statements(query.strip())
    except Exception:
        # May not be valid SQL
        return False

    if not statements:
        return False

    last_statement = statements[-1]

    return last_statement.type == duckdb.StatementType.SELECT and (
        "LIMIT " in last_statement.query.upper()
        or "LIMIT\n" in last_statement.query.upper()
    )


def _wrapped_sql(query: str) -> "duckdb.DuckDBPyRelation":
    import duckdb

    # In Python globals() are scoped to modules; since this function
    # is in a different module than user code, globals() doesn't return
    # the kernel globals, it just returns this module's global namespace.
    #
    # However, duckdb needs access to the kernel's globals. For this reason,
    # we manually exec duckdb and provide it with the kernel's globals.
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        relation = duckdb.sql(query=query)
    else:
        relation = eval(
            "duckdb.sql(query=query)",
            ctx.globals,
            {"query": query, "duckdb": duckdb},
        )
    return relation
