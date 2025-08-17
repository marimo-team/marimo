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
        return (df.lazy(), None) if lazy else (df, None)
    except (
        pl.exceptions.PanicException,
        pl.exceptions.ComputeError,
    ) as e:
        return (None, str(e))


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
