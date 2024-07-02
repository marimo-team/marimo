# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._impl import table
from marimo._runtime import output


@mddoc
def sql(query: str) -> Any:
    """
    Execute a SQL query.

    This uses duckdb to execute the query. Any dataframes in the global
    namespace can be used inside the query.

    The result of the query is displayed in the UI.

    Args:
        query: The SQL query to execute.

    Returns:
        The result of the query.
    """
    DependencyManager.require_duckdb("to execute sql")

    import duckdb  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

    if DependencyManager.has_polars():
        df = duckdb.execute(query=query).pl()
        t = table.table(df, selection=None, page_size=5, pagination=True)
        output.replace(t)
        return df
    if DependencyManager.has_pandas():
        df = duckdb.execute(query=query).df()
        t = table.table(df, selection=None, page_size=5, pagination=True)
        output.replace(t)
        return df

    raise ModuleNotFoundError(
        "pandas or polars is required to execute sql. "
        + "You can install them with 'pip install pandas polars'"
    )
