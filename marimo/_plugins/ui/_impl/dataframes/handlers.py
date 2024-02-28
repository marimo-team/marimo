# Copyright 2024 Marimo. All rights reserved.
from typing import TYPE_CHECKING, Any, List, NoReturn, cast

from .transforms import (
    AggregateTransform,
    ColumnConversionTransform,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnTransform,
    SampleRowsTransform,
    SelectColumnsTransform,
    ShuffleRowsTransform,
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
        elif transform_type is TransformType.SELECT_COLUMNS:
            return TransformHandlers.handle_select_columns(
                df, cast(SelectColumnsTransform, transform)
            )
        elif transform_type is TransformType.SHUFFLE_ROWS:
            return TransformHandlers.handle_shuffle_rows(
                df, cast(ShuffleRowsTransform, transform)
            )
        elif transform_type is TransformType.SAMPLE_ROWS:
            return TransformHandlers.handle_sample_rows(
                df, cast(SampleRowsTransform, transform)
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
        )  # type: ignore[call-overload]
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
                df_filter = df[condition.column_id].eq(True)
            elif condition.operator == "is_false":
                df_filter = df[condition.column_id].eq(False)
            elif condition.operator == "is_nan":
                df_filter = df[condition.column_id].isna()
            elif condition.operator == "is_not_nan":
                df_filter = df[condition.column_id].notna()
            elif condition.operator == "equals":
                df_filter = df[condition.column_id].eq(value)
            elif condition.operator == "does_not_equal":
                df_filter = df[condition.column_id].ne(value)
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
            return group.mean(numeric_only=True)
        elif transform.aggregation == "median":
            return group.median(numeric_only=True)
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

        # Pandas type-checking doesn't like the fact that the values
        # are lists of strings (function names), even though the docs permit
        # such a value
        return cast("pd.DataFrame", df.agg(dict_of_aggs))  # type: ignore[arg-type]  # noqa: E501

    @staticmethod
    def handle_select_columns(
        df: "pd.DataFrame", transform: SelectColumnsTransform
    ) -> "pd.DataFrame":
        return df[transform.column_ids]

    @staticmethod
    def handle_shuffle_rows(
        df: "pd.DataFrame", transform: ShuffleRowsTransform
    ) -> "pd.DataFrame":
        return df.sample(frac=1, random_state=transform.seed)

    @staticmethod
    def handle_sample_rows(
        df: "pd.DataFrame", transform: SampleRowsTransform
    ) -> "pd.DataFrame":
        return df.sample(
            n=transform.n,
            random_state=transform.seed,
            replace=transform.replace,
        )


def apply_transforms(
    df: "pd.DataFrame", transforms: Transformations
) -> "pd.DataFrame":
    if not transforms.transforms:
        return df
    for transform in transforms.transforms:
        df = TransformHandlers.handle(df, transform)
    return df


def _assert_never(value: NoReturn) -> NoReturn:
    raise AssertionError(f"Unhandled value: {value} ({type(value).__name__})")


def _coerce_value(dtype: Any, value: Any) -> Any:
    import numpy as np

    return np.array([value]).astype(dtype)[0]


class TransformsContainer:
    """
    Keeps internal state of the last transformation applied to the dataframe.
    So that we can incrementally apply transformations.
    """

    def __init__(self, df: "pd.DataFrame") -> None:
        self._original_df = df
        # The dataframe for the given transform.
        self._snapshot_df = df
        self._transforms: List[Transform] = []

    def apply(self, transform: Transformations) -> "pd.DataFrame":
        """
        Applies the given transformations to the dataframe.
        """
        # If the new transformations are a superset of the existing ones,
        # then we can just apply the new ones to the snapshot dataframe.
        if self._is_superset(transform):
            transforms_to_apply = self._get_next_transformations(transform)
            self._snapshot_df = apply_transforms(
                self._snapshot_df, transforms_to_apply
            )
            self._transforms = transform.transforms
            return self._snapshot_df

        # If the new transformations are not a superset of the existing ones,
        # then we need to start from the original dataframe.
        else:
            self._snapshot_df = apply_transforms(self._original_df, transform)
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
