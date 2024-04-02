# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    List,
    Sequence,
    Union,
)

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]

TableData = Union[
    Sequence[Union[str, int, float, bool, MIME, None]],
    Sequence[JSONType],
    List[JSONType],
    "pd.DataFrame",
    "pl.DataFrame",
]


def get_row_headers(
    data: TableData,
) -> List[tuple[str, List[str | int | float]]]:
    if not DependencyManager.has_pandas():
        return []

    import pandas as pd

    if isinstance(data, pd.DataFrame):
        return _get_row_headers_for_index(data.index)

    return []


def _get_row_headers_for_index(
    index: pd.Index[Any],
) -> List[tuple[str, List[str | int | float]]]:
    import pandas as pd

    if isinstance(index, pd.RangeIndex):
        return []

    if isinstance(index, pd.MultiIndex):
        # recurse
        headers = []
        for i in range(index.nlevels):
            headers.extend(
                _get_row_headers_for_index(index.get_level_values(i))
            )
        return headers

    # we only care about the index if it has a name
    # or if it is type 'object'
    # otherwise, it may look like meaningless number
    if isinstance(index, pd.Index):
        dtype = str(index.dtype)
        if (
            index.name
            or dtype == "object"
            or dtype == "string"
            or dtype == "category"
        ):
            name = str(index.name) if index.name else ""
            return [(name, index.tolist())]  # type: ignore[list-item]

    return []
