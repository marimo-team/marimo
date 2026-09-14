# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import os
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

from marimo._config.config import SqlOutputType
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._output.rich_help import mddoc
from marimo._runtime.output import replace
from marimo._sql.engines.dbapi import DBAPIConnection, DBAPIEngine
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._sql.engines.polars import PolarsEngine
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.engines.types import QueryEngine
from marimo._sql.error_utils import MarimoSQLException, is_sql_parse_error
from marimo._sql.get_engines import SUPPORTED_ENGINES
from marimo._sql.utils import (
    extract_explain_content,
    get_configured_sql_output_format,
    is_explain_query,
    raise_df_import_error,
)
from marimo._types.ids import VariableName
from marimo._utils.assert_never import log_never
from marimo._utils.narwhals_utils import can_narwhalify_lazyframe


def get_default_result_limit() -> int | None:
    limit = os.environ.get("MARIMO_SQL_DEFAULT_LIMIT")
    return int(limit) if limit is not None else None


def _resolve_default_duckdb_deps(
    sql_output: SqlOutputType,
    *,
    polars_installed: Callable[[], bool],
    pandas_installed: Callable[[], bool],
) -> list[Dependency]:
    deps: list[Dependency] = [
        DependencyManager.duckdb,
        DependencyManager.sqlglot,
    ]
    polars_with_pyarrow = Dependency(
        "polars", pkg_name_to_install="polars[pyarrow]"
    )

    if sql_output == "polars" or sql_output == "lazy-polars":
        deps.append(polars_with_pyarrow)
    elif sql_output == "pandas":
        deps.append(DependencyManager.pandas)
    elif sql_output == "auto":
        if not polars_installed() and not pandas_installed():
            deps.append(polars_with_pyarrow)
    elif sql_output == "native":
        # "native" returns the underlying DuckDB relation and needs no df lib.
        pass
    else:
        log_never(sql_output)

    return deps


def _default_duckdb_deps() -> list[Dependency]:
    """
    Return all deps required to run `mo.sql(query)` with the default DuckDB
    engine, including the dataframe library used for the configured output
    format.
    """
    return _resolve_default_duckdb_deps(
        get_configured_sql_output_format(),
        polars_installed=DependencyManager.polars.has,
        pandas_installed=DependencyManager.pandas.has,
    )


def _resolve_polars_deps(sql_output: SqlOutputType) -> list[Dependency]:
    deps = [DependencyManager.polars, DependencyManager.sqlglot]
    if sql_output == "pandas":
        deps.extend([DependencyManager.pandas, DependencyManager.pyarrow])
    return deps


def _namespace_for_polars(caller: FrameType | None) -> dict[str, Any]:
    """Return notebook globals, falling back to the direct caller namespace."""
    from marimo._runtime.context.types import (
        ContextNotInitializedError,
        get_context,
    )

    try:
        return get_context().globals
    except ContextNotInitializedError:
        if caller is None:
            return {}
        namespace = dict(caller.f_globals)
        namespace.update(caller.f_locals)
        return namespace


@mddoc
def sql(
    query: str,
    *,
    output: bool = True,
    engine: DBAPIConnection | Literal["polars"] | None = None,
) -> Any:
    """
    Execute a SQL query.

    By default, this uses duckdb to execute the query. Any dataframes in the global
    namespace can be used inside the query.

    You can also pass a custom engine to execute queries against other databases.
    The custom engine can be a DB-API 2.0 compatible connection (PEP 249), including
    DB-API wrappers provided by ADBC drivers.

    The result of the query is displayed in the UI if output is True.

    Args:
        query: The SQL query to execute.
        output: Whether to display the result in the UI. Defaults to True.
        engine: Optional SQL engine to use. Pass `"polars"` to query Polars
            DataFrames and LazyFrames in the notebook namespace. Can also be a
            SQLAlchemy, DuckDB, Clickhouse, Redshift, Ibis, or DB-API 2.0
            compatible connection (including ADBC drivers). If None, uses DuckDB.

    Returns:
        The result of the query.
    """
    if query is None or query.strip() == "":
        return None

    sql_engine: QueryEngine[Any]
    if engine is None:
        DependencyManager.require_many(
            "to execute sql",
            *_default_duckdb_deps(),
            source="kernel",
        )
        sql_engine = DuckDBEngine(connection=None)
    elif isinstance(engine, str) and engine == "polars":
        DependencyManager.require_many(
            "to execute SQL with Polars",
            *_resolve_polars_deps(get_configured_sql_output_format()),
            source="kernel",
        )
        frame = inspect.currentframe()
        try:
            caller = frame.f_back if frame is not None else None
            sql_engine = PolarsEngine(_namespace_for_polars(caller))
        finally:
            # Frames can participate in reference cycles.
            del frame
    else:
        for engine_cls in SUPPORTED_ENGINES:
            if engine_cls.is_compatible(engine):
                sql_engine = engine_cls(
                    connection=engine, engine_name=VariableName("custom")
                )  # type: ignore
                break
        else:
            raise ValueError(
                "Unsupported engine. Must be 'polars' or a SQLAlchemy, Ibis, "
                "Clickhouse, DuckDB, Redshift, StarRocks or DBAPI 2.0 "
                "compatible engine."
            )

    try:
        df = sql_engine.execute(query)
    except Exception as e:
        is_polars_sql_error = False
        if isinstance(sql_engine, PolarsEngine):
            import polars as pl

            # SQLContext can raise general Polars planning/execution errors,
            # which should only be classified as SQL errors on this path.
            is_polars_sql_error = isinstance(e, pl.exceptions.PolarsError)
        if is_polars_sql_error or is_sql_parse_error(e):
            # NB. raising _from_ creates a noisier stack trace, but preserves
            # the original exception context for debugging.
            raise MarimoSQLException(
                message=str(e),
                sql_statement=query,
                sql_line=None,
                sql_col=None,
                hint=None,
            ) from e
        raise

    if df is None:
        return None

    has_limit = False
    try:
        default_result_limit = get_default_result_limit()
        if default_result_limit is not None:
            has_limit = _query_includes_limit(query)
    except OSError:
        default_result_limit = None

    enforce_own_limit = not has_limit and default_result_limit is not None

    custom_total_count: Literal["too_many"] | None = None
    if enforce_own_limit:
        result_limit = cast(int, default_result_limit)
        if can_narwhalify_lazyframe(df):
            # Limiting a lazy result must remain lazy; determining the total
            # row count would execute the query.
            df = df.limit(result_limit)
        elif DependencyManager.polars.has():
            import polars as pl

            if isinstance(df, pl.DataFrame):
                custom_total_count = (
                    "too_many" if len(df) > result_limit else None
                )
                df = df.limit(result_limit)
            elif DependencyManager.pandas.has():
                custom_total_count = (
                    "too_many" if len(df) > result_limit else None
                )
                df = df.head(result_limit)
            else:
                raise_df_import_error("polars[pyarrow]")
        elif DependencyManager.pandas.has():
            custom_total_count = "too_many" if len(df) > result_limit else None
            df = df.head(result_limit)
        else:
            raise_df_import_error("polars[pyarrow]")

    if output:
        from marimo._output.formatters.df_formatters import include_opinionated
        from marimo._output.formatting import plain
        from marimo._plugins.stateless.plain_text import plain_text
        from marimo._plugins.ui._impl import table

        if isinstance(sql_engine, DuckDBEngine) and is_explain_query(query):
            # For EXPLAIN queries in DuckDB, display plain output to preserve box drawings
            text_output = extract_explain_content(df)
            replace(plain_text(text_output))
        elif not include_opinionated():
            # Respect display.dataframes config - use plain formatting
            replace(plain(df))
        elif can_narwhalify_lazyframe(df):
            # For pl.LazyFrame and DuckDBRelation, we only show the first few rows
            # to avoid loading all the data into memory.
            # Also preload the first page of data without user confirmation.
            replace(table.table.lazy(df, preload=True))
        else:
            # df may be a cursor result from an SQL Engine
            # In this case, we need to convert it to a DataFrame
            display_df = df
            if SQLAlchemyEngine.is_cursor_result(df):
                display_df = SQLAlchemyEngine.get_cursor_metadata(df)
            elif DBAPIEngine.is_dbapi_cursor(df):
                display_df = DBAPIEngine.get_cursor_metadata(df)

            replace(
                table.table(
                    display_df,
                    selection=None,
                    pagination=True,
                    _internal_total_rows=custom_total_count,
                )
            )
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
