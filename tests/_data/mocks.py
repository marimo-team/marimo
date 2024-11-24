from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Sequence

from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame

DFType = Literal["pandas", "polars", "ibis", "pyarrow", "duckdb"]


def create_dataframes(
    data: Dict[str, Sequence[Any]],
    include: Optional[List[DFType]] = None,
    exclude: Optional[List[DFType]] = None,
    strict: bool = True,
) -> list[IntoDataFrame]:
    dfs: list[IntoDataFrame] = []

    def should_include(lib: DFType) -> bool:
        if include is not None and lib not in include:
            return False
        if exclude is not None and lib in exclude:
            return False
        return True

    if DependencyManager.pandas.has() and should_include("pandas"):
        import pandas as pd

        # Map all datetime to pd.Datetime
        pandas_data = data.copy()
        for k, v in pandas_data.items():
            if any(isinstance(x, datetime.datetime) for x in v):
                pandas_data[k] = [pd.to_datetime(x) for x in v]
            if any(isinstance(x, datetime.date) for x in v):
                pandas_data[k] = [pd.to_datetime(x) for x in v]
        dfs.append(pd.DataFrame(pandas_data))

    if DependencyManager.polars.has() and should_include("polars"):
        import polars as pl

        dfs.append(pl.DataFrame(data, strict=strict))

    if DependencyManager.ibis.has() and should_include("ibis"):
        import ibis  # type: ignore

        dfs.append(ibis.memtable(data))

    if DependencyManager.pyarrow.has() and should_include("pyarrow"):
        import pyarrow as pa

        dfs.append(pa.Table.from_pydict(data))

    if DependencyManager.duckdb.has() and should_include("duckdb"):
        import duckdb

        if DependencyManager.polars.has():
            import polars as pl

            duck_df = pl.DataFrame(data)
            relation = duckdb.sql("SELECT * FROM duck_df")
            del duck_df
            dfs.append(relation)

    return dfs


def create_series(data: list[Any]) -> list[Any]:
    series: list[Any] = []
    if DependencyManager.pandas.has():
        import pandas as pd

        series.append(pd.Series(data))
    if DependencyManager.polars.has():
        import polars as pl

        series.append(pl.Series(data))
    return series
