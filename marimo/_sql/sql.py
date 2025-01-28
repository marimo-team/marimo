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
from marimo._sql.engines import (
    DuckDBEngine,
    SQLAlchemyEngine,
    raise_df_import_error,
)
from marimo._sql.types import SQLEngine


def get_default_result_limit() -> Optional[int]:
    limit = os.environ.get("MARIMO_SQL_DEFAULT_LIMIT")
    return int(limit) if limit is not None else None


if TYPE_CHECKING:
    import duckdb
    import sqlalchemy


@mddoc
def sql(
    query: str,
    output: bool = True,
    engine: Optional[sqlalchemy.Engine | duckdb.DuckDBPyConnection] = None,
) -> Any:
    """
    Execute a SQL query.

    By default, this uses duckdb to execute the query. Any dataframes in the global
    namespace can be used inside the query.

    You can also pass a SQLAlchemy engine to execute queries against other databases.

    The result of the query is displayed in the UI if output is True.

    Args:
        query: The SQL query to execute.
        output: Whether to display the result in the UI. Defaults to True.
        engine: Optional SQL engine to use. Can be a SQLAlchemy engine or DuckDB connection.
               If None, uses DuckDB.

    Returns:
        The result of the query.
    """
    if query is None or query.strip() == "":
        return None

    if engine is None:
        DependencyManager.duckdb.require("to execute sql")
        sql_engine = DuckDBEngine(connection=None)
    elif SQLAlchemyEngine.is_compatible(engine):
        sql_engine = SQLAlchemyEngine(engine)  # type: ignore
    elif DuckDBEngine.is_compatible(engine):
        sql_engine = DuckDBEngine(engine)  # type: ignore
    else:
        raise ValueError(
            "Unsupported engine. Must be a SQLAlchemy engine or DuckDB connection."
        )

    df = _execute_query(query, sql_engine)
    if df is None:
        return None

    has_limit = _query_includes_limit(query)
    try:
        default_result_limit = get_default_result_limit()
    except OSError:
        default_result_limit = None

    enforce_own_limit = not has_limit and default_result_limit is not None

    custom_total_count: Optional[Literal["too_many"]]
    if enforce_own_limit:
        if DependencyManager.polars.has():
            custom_total_count = (
                "too_many"
                if len(df) > cast(int, default_result_limit)
                else None
            )
            df = df.limit(default_result_limit)
        elif DependencyManager.pandas.has():
            custom_total_count = (
                "too_many"
                if len(df) > cast(int, default_result_limit)
                else None
            )
            df = df.head(default_result_limit)
        else:
            raise_df_import_error("polars")

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
    """Check if a SQL query includes a LIMIT clause."""
    import sqlglot
    from sqlglot.expressions import Limit, Select

    try:
        expressions = sqlglot.parse(query.strip())
    except Exception:
        # May not be valid SQL
        return False

    if not expressions:
        return False

    # Only check the last statement in case of multiple statements
    last_expr = expressions[-1]
    if not isinstance(last_expr, Select):
        return False

    # Look for any LIMIT clause in the SELECT statement
    return last_expr.find(Limit) is not None


def _execute_query(query: str, engine: SQLEngine) -> Any:
    # In Python globals() are scoped to modules; since this function
    # is in a different module than user code, globals() doesn't return
    # the kernel globals, it just returns this module's global namespace.
    #
    # However, duckdb needs access to the kernel's globals. For this reason,
    # we manually exec duckdb and provide it with the kernel's globals.
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return engine.execute(query)
    else:
        return eval(
            "engine.execute(query)",
            ctx.globals,
            {"query": query, "engine": engine},
        )


def wrapped_sql(query: str) -> "duckdb.DuckDBPyRelation":
    import duckdb

    # Same as above, but for plain duckdb
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
