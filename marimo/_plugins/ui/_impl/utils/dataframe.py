# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Sequence,
    Union,
)

from marimo import _loggers
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa  # type: ignore

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]

TableData = Union[
    Sequence[Union[str, int, float, bool, MIME, None]],
    Sequence[JSONType],
    List[JSONType],
    Dict[str, Sequence[Union[str, int, float, bool, MIME, None]]],
    "pd.DataFrame",
    "pl.DataFrame",
    "pa.Table",
]
