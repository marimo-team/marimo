# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Literal, Optional

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._impl import table
from marimo._runtime import output

DEFAULT_RESULT_LIMIT = 300


@mddoc
def sql(
    query: str,
) -> Any:
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

    relation = duckdb.sql(query=query)

    if not relation:
        return None

    enforce_own_limit = not _query_includes_limit(query)

    if enforce_own_limit:
        relation = relation.limit(DEFAULT_RESULT_LIMIT + 1)  # request 1 more

    custom_total_count: Optional[Literal["too_many"]] = None

    df: Any
    if DependencyManager.has_polars():
        df = relation.pl()
        if enforce_own_limit:
            custom_total_count = (
                "too_many" if len(df) > DEFAULT_RESULT_LIMIT else None
            )
            df = df.limit(DEFAULT_RESULT_LIMIT)
    elif DependencyManager.has_pandas():
        df = relation.df()
        if enforce_own_limit:
            custom_total_count = (
                "too_many" if len(df) > DEFAULT_RESULT_LIMIT else None
            )
            df = df.head(DEFAULT_RESULT_LIMIT)
    else:
        raise ModuleNotFoundError(
            "pandas or polars is required to execute sql. "
            + "You can install them with 'pip install pandas polars'"
        )

    t = table.table(
        df,
        selection=None,
        page_size=5,
        pagination=True,
        _internal_row_limit=DEFAULT_RESULT_LIMIT
        if custom_total_count == "too_many"
        else None,
        _internal_total_rows=custom_total_count,
    )
    output.replace(t)
    return df


def _query_includes_limit(query: str) -> bool:
    import duckdb  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

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
