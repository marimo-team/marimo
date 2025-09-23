# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional, Union, cast

from marimo import _loggers
from marimo._config.config import SqlOutputType
from marimo._data.models import DataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)

if TYPE_CHECKING:
    import duckdb
    import pandas as pd
    import polars as pl
    from polars._typing import ConnectionOrCursor

LOGGER = _loggers.marimo_logger()


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


def try_convert_to_polars(
    *,
    query: str,
    connection: ConnectionOrCursor,
    lazy: bool,
) -> tuple[Optional[pl.DataFrame | pl.LazyFrame], Optional[str]]:
    """Try to convert the query to a polars dataframe.

    Returns:
        - The polars dataframe, or None if the conversion failed.
        - Error message, or None if the conversion succeeded.
    """
    import polars as pl

    try:
        df = pl.read_database(query=query, connection=connection)
        return df.lazy() if lazy else df, None
    except (
        pl.exceptions.PanicException,
        pl.exceptions.ComputeError,
    ) as e:
        return None, e


def convert_to_output(
    *,
    sql_output_format: SqlOutputType,
    to_polars: Callable[[], Union[pl.DataFrame, pl.Series]],
    to_pandas: Callable[[], pd.DataFrame],
    to_native: Optional[Callable[[], Any]] = None,
    to_lazy_polars: Optional[Callable[[], pl.LazyFrame]] = None,
) -> Any:
    """Convert a result to the specified output format.

    Args:
        result (Any): The result to convert.
        sql_output_format (SqlOutputType): The output format to convert to.
        to_polars (Callable[[], Any]): A function to convert the result to polars.
        to_pandas (Callable[[], Any]): A function to convert the result to pandas.
        to_native (Callable[[], Any]): A function to convert the result to native.
        to_lazy_polars (Optional[Callable[[], Any]]): A function to convert the result to lazy polars.
            If not present, will use to_polars().lazy()

    Returns:
        Any: The converted result.
    """
    if sql_output_format == "native":
        if to_native is None:
            raise ValueError("to_native is required for native output format")
        return to_native()

    if sql_output_format in ("polars", "lazy-polars"):
        if not DependencyManager.polars.has():
            raise_df_import_error("polars[pyarrow]")

    if sql_output_format == "polars":
        return to_polars()

    if sql_output_format == "lazy-polars":
        import polars as pl

        if to_lazy_polars is not None:
            return to_lazy_polars()

        # Default handling, we convert to polars and then to lazy polars
        result = to_polars()
        if isinstance(result, pl.Series):
            return result.to_frame().lazy()
        return result.lazy()

    if sql_output_format == "pandas":
        if not DependencyManager.pandas.has():
            raise_df_import_error("pandas")
        return to_pandas()

    # Auto
    if DependencyManager.polars.has():
        import polars as pl

        try:
            return to_polars()
        except (
            pl.exceptions.PanicException,
            pl.exceptions.ComputeError,
        ):
            LOGGER.info("Failed to convert to polars, falling back to pandas")
            DependencyManager.pandas.require("to convert this data")

    if DependencyManager.pandas.has():
        try:
            return to_pandas()
        except Exception as e:
            LOGGER.warning("Failed to convert dataframe", exc_info=e)
            return None

    raise_df_import_error("polars[pyarrow]")


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
    elif "time" in type_str:
        return "time"
    elif "bool" in type_str:
        return "boolean"
    elif any(x in type_str for x in ("char", "text")):
        return "string"
    else:
        return "string"


def is_explain_query(query: str) -> bool:
    """Check if a SQL query is an EXPLAIN query."""
    return query.lstrip().lower().startswith("explain ")


def wrap_query_with_explain(query: str) -> str:
    """
    Wrap a SQL query with an EXPLAIN query if it is not already.

    If the query is just comments, return it. Executing this would return nothing.
    """
    if is_explain_query(query):
        return query

    return f"EXPLAIN {query}"


def is_query_empty(query: str) -> bool:
    """Check if a SQL query is empty or just comments"""
    stripped = query.strip()
    if not stripped:
        return True

    # If the query starts with -- or /*, it's likely just comments
    if stripped.startswith("--") or stripped.startswith("/*"):
        import re

        # Remove /* */ comments
        no_block_comments = re.sub(r"/\*.*?\*/", "", query, flags=re.DOTALL)

        # Remove -- comments (just split on \n and check each line)
        lines = no_block_comments.split("\n")
        for line in lines:
            # Find first non-whitespace character
            for char in line:
                if char.isspace():
                    continue
                elif char == "-":
                    if line.strip().startswith("--"):
                        break  # This line is a comment, continue to next line
                    else:
                        return False  # Found non-comment content
                else:
                    return False  # Found non-comment content
        return True

    # If it doesn't start with comment markers, it's not empty
    return False


def extract_explain_content(df: Any) -> str:
    """Extract all content from a DataFrame for EXPLAIN queries.

    Args:
        df: DataFrame (pandas or polars). If not pandas / polars, return repr(df).

    Returns:
        String containing content of dataframe
    """
    try:
        if DependencyManager.polars.has():
            import polars as pl

            if isinstance(df, pl.LazyFrame):
                df = df.collect()
            if isinstance(df, pl.DataFrame):
                # Display full strings without truncation
                with pl.Config(fmt_str_lengths=1000):
                    return str(df)

        if DependencyManager.pandas.has():
            import pandas as pd

            if isinstance(df, pd.DataFrame):
                # Preserve newlines in the data
                all_values = df.values.flatten().tolist()
                return "\n".join(str(val) for val in all_values)

        # Fallback to repr for other types
        return repr(df)

    except Exception as e:
        LOGGER.debug("Failed to extract explain content: %s", e)
        return repr(df)
