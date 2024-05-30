# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DataFrameLike(Protocol):
    def __dataframe__(
        self, nan_as_null: bool = False, allow_copy: bool = True
    ) -> Any: ...
