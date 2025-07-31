# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Generic, TypeVar

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.dataframes.transforms.handlers import (
    IbisTransformHandler,
    PandasTransformHandler,
    PolarsTransformHandler,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    Transform,
    Transformations,
    TransformHandler,
    TransformType,
)
from marimo._utils.assert_never import assert_never

T = TypeVar("T")


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


def _apply_transforms(
    df: T, handler: TransformHandler[T], transforms: Transformations
) -> T:
    if not transforms.transforms:
        return df
    for transform in transforms.transforms:
        df = _handle(df, handler, transform)
    return df


def get_handler_for_dataframe(
    df: Any,
) -> TransformHandler[Any]:
    """
    Gets the handler for the given dataframe.

    raises ValueError if the dataframe type is not supported.
    """
    if DependencyManager.pandas.imported():
        import pandas as pd

        if isinstance(df, pd.DataFrame):
            return PandasTransformHandler()
    if DependencyManager.polars.imported():
        import polars as pl

        if isinstance(df, pl.DataFrame):
            return PolarsTransformHandler()

    if DependencyManager.ibis.imported():
        import ibis  # type: ignore

        if isinstance(df, ibis.Table):
            return IbisTransformHandler()

    if DependencyManager.narwhals.imported():
        import narwhals as nw

        if isinstance(df, nw.DataFrame):
            return get_handler_for_dataframe(df.to_native())

    raise ValueError(
        "Unsupported dataframe type. Must be Pandas or Polars."
        f" Got: {type(df)}"
    )


class TransformsContainer(Generic[T]):
    """
    Keeps internal state of the last transformation applied to the dataframe.
    So that we can incrementally apply transformations.
    """

    def __init__(self, df: T, handler: TransformHandler[T]) -> None:
        self._original_df = df
        # The dataframe for the given transform.
        self._snapshot_df = df
        self._handler = handler
        self._transforms: list[Transform] = []

    def apply(self, transform: Transformations) -> T:
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
