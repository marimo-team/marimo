# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Union,
)

from marimo import _loggers
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._impl.table import ListOrTuple

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa  # type: ignore

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]

TableData = Union[
    List[JSONType],
    ListOrTuple[Union[str, int, float, bool, MIME, None]],
    ListOrTuple[dict[str, JSONType]],
    Dict[str, ListOrTuple[JSONType]],
    "pd.DataFrame",
    "pl.DataFrame",
    "pa.Table",
]
