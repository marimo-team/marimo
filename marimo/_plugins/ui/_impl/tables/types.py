# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Protocol

from marimo._plugins.ui._impl.tables.dataframe_protocol import DataFrame


class DataFrameLike(Protocol):
    def __dataframe__(
        self, nan_as_null: bool = False, allow_copy: bool = True
    ) -> DataFrame: ...


def is_dataframe_like(value: object) -> bool:
    return (
        hasattr(value, "__dataframe__")
        and callable(value.__dataframe__)
        # By checking these are equal, we likely guarding against
        # __getattr__ implementations that may return different callables
        and value.__dataframe__ == value.__dataframe__
        # We don't want to call __dataframe__, in case it has side effects
    )
