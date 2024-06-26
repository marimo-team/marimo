from __future__ import annotations

from typing import Any, List, Optional

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl import table


def sql(query: str, deps: Optional[List[Any]] = None) -> Any:
    DependencyManager.require_duckdb("to execute sql")

    import duckdb

    if DependencyManager.has_polars():
        return table.table(
            duckdb.execute(query=query).pl(),
            selection=None,
            page_size=5,
            pagination=True,
        )
    if DependencyManager.has_pandas():
        return table.table(
            duckdb.execute(query=query).df(),
            selection=None,
            page_size=5,
            pagination=True,
        )

    raise ModuleNotFoundError(
        "pandas or polars is required to execute sql. "
        + "You can install them with 'pip install pandas polars'"
    )
