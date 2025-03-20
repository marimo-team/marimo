# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._runtime.output import replace
from marimo._sql.engines import (
    INTERNAL_CLICKHOUSE_ENGINE,
    ClickhouseEmbedded,
    DuckDBEngine,
    SQLAlchemyEngine,
    raise_df_import_error,
)


def get_default_result_limit() -> Optional[int]:
    limit = os.environ.get("MARIMO_SQL_DEFAULT_LIMIT")
    return int(limit) if limit is not None else None


if TYPE_CHECKING:
    import duckdb
    import sqlalchemy


@mddoc
def sql(
    query: str,
    *,
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
        DependencyManager.require_many(
            "to execute sql",
            DependencyManager.duckdb,
            DependencyManager.sqlglot,
        )
        sql_engine = DuckDBEngine(connection=None)
    elif SQLAlchemyEngine.is_compatible(engine):
        sql_engine = SQLAlchemyEngine(engine)  # type: ignore
    elif DuckDBEngine.is_compatible(engine):
        sql_engine = DuckDBEngine(engine)  # type: ignore
    elif ClickhouseEmbedded.is_compatible(engine):
        sql_engine = ClickhouseEmbedded(engine)
    elif engine == INTERNAL_CLICKHOUSE_ENGINE:
        # Check if user defined an engine first to ensure
        # we don't override the connection
        DependencyManager.require_many(
            "to execute sql",
            DependencyManager.chdb,
            DependencyManager.sqlglot,
        )
        sql_engine = ClickhouseEmbedded(connection=None)
    else:
        raise ValueError(
            "Unsupported engine. Must be a SQLAlchemy engine or DuckDB connection."
        )

    df = sql_engine.execute(query)
    if df is None:
        return None

    has_limit = _query_includes_limit(query)
    try:
        default_result_limit = get_default_result_limit()
    except OSError:
        default_result_limit = None

    enforce_own_limit = not has_limit and default_result_limit is not None

    custom_total_count: Optional[Literal["too_many"]] = None
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
            raise_df_import_error("polars[pyarrow]")

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
