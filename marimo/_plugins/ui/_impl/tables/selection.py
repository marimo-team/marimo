# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TypeVar, cast

import narwhals.stable.v2 as nw
from narwhals.typing import IntoDataFrame

INDEX_COLUMN_NAME = "_marimo_row_id"

T = TypeVar("T")


def add_selection_column(data: T) -> tuple[T, bool]:
    """Add a row-index column for selection tracking; returns (data, added) where added is True if supported."""
    if nw.dependencies.is_into_dataframe(data):
        df = nw.from_native(cast(IntoDataFrame, data), pass_through=False)
        if INDEX_COLUMN_NAME not in df.columns:
            return df.with_row_index(name=INDEX_COLUMN_NAME).to_native(), True  # type: ignore[return-value]
        return data, True  # already has a row index
    return data, False


def remove_selection_column(data: T) -> T:
    """Remove the row-index selection column from a dataframe if present."""
    if nw.dependencies.is_into_dataframe(data):
        df = nw.from_native(cast(IntoDataFrame, data), pass_through=False)
        if INDEX_COLUMN_NAME in df.columns:
            return df.drop(INDEX_COLUMN_NAME).to_native()  # type: ignore[return-value]
    return data
