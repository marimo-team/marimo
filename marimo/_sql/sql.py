# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._runtime.output import replace
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._sql.engines.ibis import IbisEngine
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.engines.types import (
    ENGINE_REGISTRY,
    QueryEngine,
)
from marimo._sql.utils import raise_df_import_error
from marimo._types.ids import VariableName
from marimo._utils.narwhals_utils import can_narwhalify_lazyframe


def get_default_result_limit() -> Optional[int]:
    limit = os.environ.get("MARIMO_SQL_DEFAULT_LIMIT")
    return int(limit) if limit is not None else None


if TYPE_CHECKING:
    from chdb.state.sqlitelike import Connection as ChdbConnection  # type: ignore  # noqa: I001
    from clickhouse_connect.driver.client import Client as ClickhouseClient  # type: ignore
    from duckdb import DuckDBPyConnection
    from sqlalchemy.engine import Engine as SAEngine


@mddoc
def sql(
    query: str,
    *,
    output: bool = True,
    engine: Optional[
        SAEngine
        | DuckDBPyConnection
        | ClickhouseClient
        | ChdbConnection
        | IbisEngine
    ] = None,
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
        engine: Optional SQL engine to use. Can be a SQLAlchemy, Clickhouse, or DuckDB engine.
               If None, uses DuckDB.

    Returns:
        The result of the query.
    """
    if query is None or query.strip() == "":
        return None

    sql_engine: QueryEngine[Any]
    if engine is None:
        DependencyManager.require_many(
            "to execute sql",
            DependencyManager.duckdb,
            DependencyManager.sqlglot,
        )
        sql_engine = DuckDBEngine(connection=None)
    else:
        for engine_cls in ENGINE_REGISTRY:
            if engine_cls.is_compatible(engine):
                sql_engine = engine_cls(
                    connection=engine, engine_name=VariableName("custom")
                )  # type: ignore
                break
        else:
            raise ValueError(
                "Unsupported engine. Must be a SQLAlchemy, Ibis, Clickhouse, or DuckDB engine."
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

        if can_narwhalify_lazyframe(df):
            # For pl.LazyFrame and DuckDBRelation, we only show the first few rows
            # to avoid loading all the data into memory.
            # Also preload the first page of data without user confirmation.
            t = table.table.lazy(df, preload=True)
        else:
            # df may be a cursor result from an SQL Engine
            # In this case, we need to convert it to a DataFrame
            display_df = df
            if SQLAlchemyEngine.is_cursor_result(df):
                result = SQLAlchemyEngine.get_cursor_metadata(df)
                if result is not None:
                    display_df = result

            t = table.table(
                display_df,
                selection=None,
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
