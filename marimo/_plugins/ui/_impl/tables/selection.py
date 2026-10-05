# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TypeVar, cast

import narwhals.stable.v2 as nw
from narwhals.typing import IntoDataFrame

INDEX_COLUMN_NAME = "_marimo_row_id"

T = TypeVar("T")


def add_selection_column(data: T) -> tuple[T, bool]:
    if nw.dependencies.is_into_dataframe(data):
        df = nw.from_native(cast(IntoDataFrame, data), pass_through=False)
        if INDEX_COLUMN_NAME not in df.columns:
            if df.implementation.is_pandas():
                native = df.to_native().copy()
                native.insert(0, INDEX_COLUMN_NAME, range(len(native)))
                return cast(T, native), True
            if df.implementation.is_pyarrow():
                import pyarrow as pa

                native = df.to_native()
                index = pa.array(range(len(native)))
                return cast(
                    T, native.add_column(0, INDEX_COLUMN_NAME, index)
                ), True
            return df.with_row_index(name=INDEX_COLUMN_NAME).to_native(), True  # type: ignore[return-value]
        return data, True  # already has a row index
    return data, False


def remove_selection_column(data: T) -> T:
    if nw.dependencies.is_into_dataframe(data):
        df = nw.from_native(cast(IntoDataFrame, data), pass_through=False)
        if INDEX_COLUMN_NAME in df.columns:
            return df.drop(INDEX_COLUMN_NAME).to_native()  # type: ignore[return-value]
    return data
