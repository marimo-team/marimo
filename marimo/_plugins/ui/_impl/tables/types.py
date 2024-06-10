# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Protocol, runtime_checkable

from marimo._plugins.ui._impl.tables.dataframe_protocol import DataFrame


@runtime_checkable
class DataFrameLike(Protocol):
    def __dataframe__(
        self, nan_as_null: bool = False, allow_copy: bool = True
    ) -> DataFrame: ...
