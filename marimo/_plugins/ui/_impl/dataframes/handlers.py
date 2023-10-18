# Copyright 2023 Marimo. All rights reserved.
from typing import TYPE_CHECKING, Any, NoReturn, cast

from .transforms import (
    AggregateTransform,
    ColumnConversionTransform,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnTransform,
    SortColumnTransform,
    Transform,
    Transformations,
    TransformType,
)

if TYPE_CHECKING:
    import pandas as pd


class TransformHandlers:
    @staticmethod
    def handle(df: "pd.DataFrame", transform: Transform) -> "pd.DataFrame":
        transform_type: TransformType = transform.type

        if transform_type is TransformType.COLUMN_CONVERSION:
            return TransformHandlers.handle_column_conversion(
                df, cast(ColumnConversionTransform, transform)
            )
        elif transform_type is TransformType.RENAME_COLUMN:
            return TransformHandlers.handle_rename_column(
                df, cast(RenameColumnTransform, transform)
            )
        elif transform_type is TransformType.SORT_COLUMN:
            return TransformHandlers.handle_sort_column(
                df, cast(SortColumnTransform, transform)
            )
        elif transform_type is TransformType.FILTER_ROWS:
            return TransformHandlers.handle_filter_rows(
                df, cast(FilterRowsTransform, transform)
            )
        elif transform_type is TransformType.GROUP_BY:
            return TransformHandlers.handle_group_by(
                df, cast(GroupByTransform, transform)
            )
        elif transform_type is TransformType.AGGREGATE:
            return TransformHandlers.handle_aggregate(
                df, cast(AggregateTransform, transform)
            )

        else:
            _assert_never(transform_type)

    @staticmethod
    def handle_column_conversion(
        df: "pd.DataFrame", transform: ColumnConversionTransform
    ) -> "pd.DataFrame":
        df[transform.column_id] = df[transform.column_id].astype(
            transform.data_type,
            errors=transform.errors,
        )
        return df

    @staticmethod
    def handle_rename_column(
        df: "pd.DataFrame", transform: RenameColumnTransform
    ) -> "pd.DataFrame":
        return df.rename(
            columns={transform.column_id: transform.new_column_id}
        )

    @staticmethod
    def handle_sort_column(
        df: "pd.DataFrame", transform: SortColumnTransform
    ) -> "pd.DataFrame":
        return df.sort_values(
            by=transform.column_id,
            ascending=transform.ascending,
            na_position=transform.na_position,
        )

    @staticmethod
    def handle_filter_rows(
        df: "pd.DataFrame", transform: FilterRowsTransform
    ) -> "pd.DataFrame":
        for condition in transform.where:
            value = _coerce_value(
                df[condition.column_id].dtype, condition.value
            )
            if condition.operator == "==":
                df_filter = df[condition.column_id] == value
            elif condition.operator == "!=":
                df_filter = df[condition.column_id] != value
            elif condition.operator == ">":
                df_filter = df[condition.column_id] > value
            elif condition.operator == "<":
                df_filter = df[condition.column_id] < value
            elif condition.operator == ">=":
                df_filter = df[condition.column_id] >= value
            elif condition.operator == "<=":
                df_filter = df[condition.column_id] <= value
            elif condition.operator == "is_true":
                df_filter = df[condition.column_id] is True
            elif condition.operator == "is_false":
                df_filter = df[condition.column_id] is False
            elif condition.operator == "is_nan":
                df_filter = df[condition.column_id].isna()
            elif condition.operator == "is_not_nan":
                df_filter = df[condition.column_id].notna()
            elif condition.operator == "equals":
                df_filter = df[condition.column_id].eq(value)
            elif condition.operator == "contains":
                df_filter = df[condition.column_id].str.contains(
                    value, regex=False
                )
            elif condition.operator == "regex":
                df_filter = df[condition.column_id].str.contains(
                    value, regex=True
                )
            elif condition.operator == "starts_with":
                df_filter = df[condition.column_id].str.startswith(value)
            elif condition.operator == "ends_with":
                df_filter = df[condition.column_id].str.endswith(value)
            elif condition.operator == "in":
                df_filter = df[condition.column_id].isin(value)
            else:
                _assert_never(condition.operator)

            if transform.operation == "keep_rows":
                df = df[df_filter]
            elif transform.operation == "remove_rows":
                df = df[~df_filter]
            else:
                _assert_never(transform.operation)
        return df

    @staticmethod
    def handle_group_by(
        df: "pd.DataFrame", transform: GroupByTransform
    ) -> "pd.DataFrame":
        group = df.groupby(transform.column_ids, dropna=transform.drop_na)
        if transform.aggregation == "count":
            return group.count()
        elif transform.aggregation == "sum":
            return group.sum()
        elif transform.aggregation == "mean":
            return group.mean()
        elif transform.aggregation == "median":
            return group.median()
        elif transform.aggregation == "min":
            return group.min()
        elif transform.aggregation == "max":
            return group.max()
        else:
            _assert_never(transform.aggregation)

    @staticmethod
    def handle_aggregate(
        df: "pd.DataFrame", transform: AggregateTransform
    ) -> "pd.DataFrame":
        dict_of_aggs = {
            column_id: transform.aggregations
            for column_id in transform.column_ids
        }
        return df.agg(dict_of_aggs)


def apply_transforms(
    df_prev: "pd.DataFrame", transforms: Transformations
) -> "pd.DataFrame":
    if transforms.transforms is None or len(transforms.transforms) == 0:
        return df_prev
    # defensive copy
    df = df_prev.copy()
    for transform in transforms.transforms:
        df = TransformHandlers.handle(df, transform)
    return df


def _assert_never(value: NoReturn) -> NoReturn:
    raise AssertionError(f"Unhandled value: {value} ({type(value).__name__})")


def _coerce_value(dtype: Any, value: Any) -> Any:
    import numpy as np

    return np.array([value]).astype(dtype)[0]
