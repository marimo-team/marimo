# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from marimo._plugins.ui._impl.dataframes.transforms.handlers import (
    NarwhalsTransformHandler,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    DataFrameType,
    Transform,
    Transformations,
    TransformHandler,
    TransformType,
)
from marimo._utils.assert_never import assert_never
from marimo._utils.narwhals_utils import can_narwhalify, is_narwhals_lazyframe

T = TypeVar("T")


if TYPE_CHECKING:
    import narwhals.stable.v2 as nw
    from narwhals.typing import IntoLazyFrame


def _handle(df: T, handler: TransformHandler[T], transform: Transform) -> T:
    if transform.type is TransformType.COLUMN_CONVERSION:
        return handler.handle_column_conversion(df, transform)
    if transform.type is TransformType.RENAME_COLUMN:
        return handler.handle_rename_column(df, transform)
    if transform.type is TransformType.SORT_COLUMN:
        return handler.handle_sort_column(df, transform)
    if transform.type is TransformType.FILTER_ROWS:
        return handler.handle_filter_rows(df, transform)
    if transform.type is TransformType.GROUP_BY:
        return handler.handle_group_by(df, transform)
    if transform.type is TransformType.AGGREGATE:
        return handler.handle_aggregate(df, transform)
    if transform.type is TransformType.SELECT_COLUMNS:
        return handler.handle_select_columns(df, transform)
    if transform.type is TransformType.SHUFFLE_ROWS:
        return handler.handle_shuffle_rows(df, transform)
    if transform.type is TransformType.SAMPLE_ROWS:
        return handler.handle_sample_rows(df, transform)
    if transform.type is TransformType.EXPLODE_COLUMNS:
        return handler.handle_explode_columns(df, transform)
    if transform.type is TransformType.EXPAND_DICT:
        return handler.handle_expand_dict(df, transform)
    if transform.type is TransformType.UNIQUE:
        return handler.handle_unique(df, transform)
    assert_never(transform.type)


def apply_transforms_to_df(
    df: DataFrameType, transform: Transform
) -> DataFrameType:
    """Apply a transform to a dataframe using NarwhalsTransformHandler."""
    if not can_narwhalify(df):
        raise ValueError(
            f"Unsupported dataframe type. Must be Pandas, Polars, Ibis, Pyarrow, or DuckDB. Got: {type(df)}"
        )

    import narwhals.stable.v2 as nw

    nw_df = nw.from_native(df)
    was_lazy = is_narwhals_lazyframe(nw_df)
    nw_df = nw_df.lazy()

    result_nw = _apply_transforms(
        nw_df,
        NarwhalsTransformHandler(),
        Transformations(transforms=[transform]),
    )

    if was_lazy:
        return result_nw.to_native()

    return result_nw.collect().to_native()  # type: ignore[no-any-return]


def _apply_transforms(
    df: T, handler: TransformHandler[T], transforms: Transformations
) -> T:
    if not transforms.transforms:
        return df
    for transform in transforms.transforms:
        df = _handle(df, handler, transform)
    return df


def get_handler_for_dataframe(
    df: DataFrameType,
) -> NarwhalsTransformHandler:
    """
    Gets the handler for the given dataframe.

    raises ValueError if the dataframe type is not supported.
    """
    if not can_narwhalify(df):
        raise ValueError(
            f"Unsupported dataframe type. Must be Pandas, Polars, Ibis, Pyarrow, or DuckDB. Got: {type(df)}"
        )

    return NarwhalsTransformHandler()


class TransformsContainer:
    """
    Keeps internal state of the last transformation applied to the dataframe.
    So that we can incrementally apply transformations.
    """

    def __init__(
        self,
        df: nw.LazyFrame[IntoLazyFrame],
        handler: NarwhalsTransformHandler,
    ) -> None:
        self._original_df = df
        # The dataframe for the given transform.
        self._snapshot_df = df
        self._handler = handler
        self._transforms: list[Transform] = []

    def apply(self, transform: Transformations) -> nw.LazyFrame[IntoLazyFrame]:
        """
        Applies the given transformations to the dataframe.
        """
        # If the new transformations are a superset of the existing ones,
        # then we can just apply the new ones to the snapshot dataframe.
        if self._is_superset(transform):
            transforms_to_apply = self._get_next_transformations(transform)
            self._snapshot_df = _apply_transforms(
                self._snapshot_df, self._handler, transforms_to_apply
            )
            self._transforms = transform.transforms
            return self._snapshot_df

        # If the new transformations are not a superset of the existing ones,
        # then we need to start from the original dataframe.
        else:
            self._snapshot_df = _apply_transforms(
                self._original_df, self._handler, transform
            )
            self._transforms = transform.transforms
            return self._snapshot_df

    def _is_superset(self, transforms: Transformations) -> bool:
        """
        Checks if the new transformations are a superset of the existing ones.
        """
        if not self._transforms:
            return False

        # If the new transformations are smaller than the existing ones,
        # then it's not a superset.
        if len(self._transforms) > len(transforms.transforms):
            return False

        for i, transform in enumerate(self._transforms):
            if transform != transforms.transforms[i]:
                return False

        return True

    def _get_next_transformations(
        self, transforms: Transformations
    ) -> Transformations:
        """
        Gets the next transformations to apply.
        """
        if self._is_superset(transforms):
            return Transformations(
                transforms.transforms[len(self._transforms) :]
            )
        else:
            return transforms
