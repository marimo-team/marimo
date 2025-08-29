# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, TypeVar, cast

import narwhals.stable.v1 as nw
from narwhals.dataframe import DataFrame
from narwhals.typing import IntoDataFrame

INDEX_COLUMN_NAME = "_marimo_row_id"

T = TypeVar("T")


def _is_into_dataframe(native_dataframe: Any) -> bool:
    # Mirrors nw.dependencies.is_into_dataframe introduced later than minimum
    # version
    return (
        isinstance(native_dataframe, DataFrame)
        or hasattr(native_dataframe, "__narwhals_dataframe__")
        or nw.is_polars_dataframe(native_dataframe)
        or nw.is_pyarrow_table(native_dataframe)
        or nw.is_pandas_like_dataframe(native_dataframe)
    )


def add_selection_column(data: T) -> tuple[T, bool]:
    if _is_into_dataframe(data):
        df = nw.from_native(cast(IntoDataFrame, data), pass_through=False)
        if INDEX_COLUMN_NAME not in df.columns:
            return df.with_row_index(name=INDEX_COLUMN_NAME).to_native(), True  # type: ignore[return-value]
        return data, True  # already has a row index
    return data, False


def remove_selection_column(data: T) -> T:
    if _is_into_dataframe(data):
        df = nw.from_native(cast(IntoDataFrame, data), pass_through=False)
        if INDEX_COLUMN_NAME in df.columns:
            return df.drop(INDEX_COLUMN_NAME).to_native()  # type: ignore[return-value]
    return data
