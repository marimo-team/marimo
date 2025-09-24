# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Any, Literal, Optional, cast

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._runtime.output import replace
from marimo._sql.engines.dbapi import DBAPIConnection, DBAPIEngine
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.engines.types import QueryEngine
from marimo._sql.error_utils import MarimoSQLException, is_sql_parse_error
from marimo._sql.get_engines import SUPPORTED_ENGINES
from marimo._sql.utils import (
    extract_explain_content,
    is_explain_query,
    raise_df_import_error,
)
from marimo._types.ids import VariableName
from marimo._utils.narwhals_utils import can_narwhalify_lazyframe


def get_default_result_limit() -> Optional[int]:
    limit = os.environ.get("MARIMO_SQL_DEFAULT_LIMIT")
    return int(limit) if limit is not None else None


@mddoc
def sql(
    query: str,
    *,
    output: bool = True,
    engine: Optional[DBAPIConnection] = None,
) -> Any:
    """
    Execute a SQL query.

    By default, this uses duckdb to execute the query. Any dataframes in the global
    namespace can be used inside the query.

    You can also pass a custom engine to execute queries against other databases. The custom engine must be a DBAPI 2.0 compatible engine.

    The result of the query is displayed in the UI if output is True.

    Args:
        query: The SQL query to execute.
        output: Whether to display the result in the UI. Defaults to True.
        engine: Optional SQL engine to use. Can be a SQLAlchemy, DuckDB, Clickhouse, Redshift, Ibis, or DBAPI 2.0 compatible engine.
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
        for engine_cls in SUPPORTED_ENGINES:
            if engine_cls.is_compatible(engine):
                sql_engine = engine_cls(
                    connection=engine, engine_name=VariableName("custom")
                )  # type: ignore
                break
        else:
            raise ValueError(
                "Unsupported engine. Must be a SQLAlchemy, Ibis, Clickhouse, DuckDB, Redshift or DBAPI 2.0 compatible engine."
            )

    try:
        df = sql_engine.execute(query)
    except Exception as e:
        if is_sql_parse_error(e):
            # Use centralized error processing
            from marimo._sql.error_utils import (
                create_sql_error_metadata,
            )

            metadata = create_sql_error_metadata(
                e,
                rule_code="runtime",
                node=None,
                sql_content=query,
                context="sql_execution",
            )

            # Enhance error messages based on exception type
            exception_type = metadata["error_type"]
            clean_message = metadata["clean_message"]
            if exception_type == "ParserException":
                clean_message = f"SQL syntax error: {clean_message}"
            elif "ParseError" in exception_type:
                clean_message = f"SQL parse error: {clean_message}"
            elif "ProgrammingError" in exception_type:
                clean_message = f"SQL programming error: {clean_message}"

            # Truncate long SQL statements
            truncated_query = (
                query[:200] + "..." if len(query) > 200 else query
            )

            # Raise MarimoSQLException with structured hint data
            raise MarimoSQLException(
                message=clean_message,
                sql_statement=truncated_query,
                sql_line=metadata["sql_line"],
                sql_col=metadata["sql_col"],
                hint=metadata["hint"],
            ) from None
        raise

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
        from marimo._plugins.stateless.plain_text import plain_text
        from marimo._plugins.ui._impl import table

        if isinstance(sql_engine, DuckDBEngine) and is_explain_query(query):
            # For EXPLAIN queries in DuckDB, display plain output to preserve box drawings
            text_output = extract_explain_content(df)
            t = plain_text(text_output)
        elif can_narwhalify_lazyframe(df):
            # For pl.LazyFrame and DuckDBRelation, we only show the first few rows
            # to avoid loading all the data into memory.
            # Also preload the first page of data without user confirmation.
            t = table.table.lazy(df, preload=True)
        else:
            # df may be a cursor result from an SQL Engine
            # In this case, we need to convert it to a DataFrame
            display_df = df
            if SQLAlchemyEngine.is_cursor_result(df):
                display_df = SQLAlchemyEngine.get_cursor_metadata(df)
            elif DBAPIEngine.is_dbapi_cursor(df):
                display_df = DBAPIEngine.get_cursor_metadata(df)

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
