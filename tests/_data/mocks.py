from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Sequence

from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame

DFType = Literal["pandas", "polars", "ibis", "pyarrow"]


def create_dataframes(
    data: Dict[str, Sequence[Any]],
    include: Optional[List[DFType]] = None,
    exclude: Optional[List[DFType]] = None,
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

        dfs.append(pl.DataFrame(data))

    if DependencyManager.ibis.has() and should_include("ibis"):
        import ibis  # type: ignore

        dfs.append(ibis.memtable(data))

    if DependencyManager.pyarrow.has() and should_include("pyarrow"):
        import pyarrow as pa

        dfs.append(pa.Table.from_pydict(data))

    return dfs


def create_series(data: list[Any]) -> list[Any]:
    if DependencyManager.pandas.has():
        import pandas as pd

        return [pd.Series(data)]
    if DependencyManager.polars.has():
        import polars as pl

        return [pl.Series(data)]
    return []
