# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TypeVar,
    Union,
)

from narwhals.typing import IntoDataFrame

from marimo import _loggers
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")
Numeric = Union[int, float]
ListOrTuple = Union[list[T], tuple[T, ...]]


TableData = Union[
    list[JSONType],
    ListOrTuple[Union[str, int, float, bool, MIME, None]],
    ListOrTuple[dict[str, JSONType]],
    dict[str, ListOrTuple[JSONType]],
    IntoDataFrame,
]
