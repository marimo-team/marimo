# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from marimo._plugins.ui._impl.dataframes.transforms.types import (
    AggregateTransform,
    ColumnConversionTransform,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnTransform,
    SampleRowsTransform,
    SelectColumnsTransform,
    ShuffleRowsTransform,
    SortColumnTransform,
    TransformHandler,
)
from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl


class PandasTransformHandler(TransformHandler["pd.DataFrame"]):
    @staticmethod
    def supports_code_sample() -> bool:
        return True

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
            by=cast(str, transform.column_id),
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
                assert_never(condition.operator)

            if transform.operation == "keep_rows":
                df = df[df_filter]
            elif transform.operation == "remove_rows":
                df = df[~df_filter]
            else:
                assert_never(transform.operation)
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
            assert_never(transform.aggregation)

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
        return cast("pd.DataFrame", df.agg(dict_of_aggs))  # type: ignore  # noqa: E501

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


class PolarsTransformHandler(TransformHandler["pl.DataFrame"]):
    @staticmethod
    def supports_code_sample() -> bool:
        return False

    @staticmethod
    def handle_column_conversion(
        df: "pl.DataFrame", transform: ColumnConversionTransform
    ) -> "pl.DataFrame":
        import polars.datatypes as pl_datatypes

        def numpy_type_to_polars_type(dtype: str) -> pl.PolarsDataType:
            polars_dtype = pl_datatypes.numpy_char_code_to_dtype(dtype)
            return polars_dtype

        return df.cast(
            {
                str(transform.column_id): numpy_type_to_polars_type(
                    transform.data_type
                )
            },
            strict=transform.errors == "raise",
        )

    @staticmethod
    def handle_rename_column(
        df: "pl.DataFrame", transform: RenameColumnTransform
    ) -> "pl.DataFrame":
        return df.rename(
            {str(transform.column_id): str(transform.new_column_id)}
        )

    @staticmethod
    def handle_sort_column(
        df: "pl.DataFrame", transform: SortColumnTransform
    ) -> "pl.DataFrame":
        return df.sort(
            by=transform.column_id,
            descending=not transform.ascending,
            nulls_last=transform.na_position == "last",
        )

    @staticmethod
    def handle_filter_rows(
        df: "pl.DataFrame", transform: FilterRowsTransform
    ) -> "pl.DataFrame":
        from polars import col

        # Start with no filter (all rows included)
        filter_expr: Optional[pl.Expr] = None

        # Iterate over all conditions and build the filter expression
        for condition in transform.where:
            column = col(str(condition.column_id))
            value = condition.value

            # Build the expression based on the operator
            if condition.operator == "==":
                condition_expr = column == value
            elif condition.operator == "!=":
                condition_expr = column != value
            elif condition.operator == ">":
                condition_expr = column > value
            elif condition.operator == "<":
                condition_expr = column < value
            elif condition.operator == ">=":
                condition_expr = column >= value
            elif condition.operator == "<=":
                condition_expr = column <= value
            elif condition.operator == "is_true":
                condition_expr = column.eq(True)
            elif condition.operator == "is_false":
                condition_expr = column.eq(False)
            elif condition.operator == "is_nan":
                condition_expr = column.is_null()
            elif condition.operator == "is_not_nan":
                condition_expr = column.is_not_null()
            elif condition.operator == "equals":
                condition_expr = column == value
            elif condition.operator == "does_not_equal":
                condition_expr = column != value
            elif condition.operator == "contains":
                condition_expr = column.str.contains(value or "", literal=True)
            elif condition.operator == "regex":
                condition_expr = column.str.contains(
                    value or "", literal=False
                )
            elif condition.operator == "starts_with":
                condition_expr = column.str.starts_with(value or "")
            elif condition.operator == "ends_with":
                condition_expr = column.str.ends_with(value or "")
            elif condition.operator == "in":
                condition_expr = column.is_in(value or [])
            else:
                assert_never(condition.operator)

            # Combine the condition expression with the filter expression
            if filter_expr is None:
                filter_expr = condition_expr
            else:
                filter_expr = filter_expr & condition_expr

        if filter_expr is None:
            return df

        # Handle the operation (keep_rows or remove_rows)
        if transform.operation == "keep_rows":
            return df.filter(filter_expr)
        elif transform.operation == "remove_rows":
            return df.filter(~filter_expr)
        else:
            assert_never(transform.operation)

    @staticmethod
    def handle_group_by(
        df: "pl.DataFrame", transform: GroupByTransform
    ) -> "pl.DataFrame":
        aggs: list[pl.Expr] = []
        from polars import col

        group_by_column_id_set = set(transform.column_ids)
        agg_columns = [
            column_id
            for column_id in df.columns
            if column_id not in group_by_column_id_set
        ]
        for column_id in agg_columns:
            agg_func = transform.aggregation
            if agg_func == "count":
                aggs.append(col(column_id).count().alias(f"{column_id}_count"))
            elif agg_func == "sum":
                aggs.append(col(column_id).sum().alias(f"{column_id}_sum"))
            elif agg_func == "mean":
                aggs.append(col(column_id).mean().alias(f"{column_id}_mean"))
            elif agg_func == "median":
                aggs.append(
                    col(column_id).median().alias(f"{column_id}_median")
                )
            elif agg_func == "min":
                aggs.append(col(column_id).min().alias(f"{column_id}_min"))
            elif agg_func == "max":
                aggs.append(col(column_id).max().alias(f"{column_id}_max"))
            else:
                assert_never(agg_func)

        return df.group_by(transform.column_ids, maintain_order=True).agg(aggs)

    @staticmethod
    def handle_aggregate(
        df: "pl.DataFrame", transform: AggregateTransform
    ) -> "pl.DataFrame":
        import polars as pl

        selected_df = df.select(transform.column_ids)
        result_df = pl.DataFrame()
        for agg_func in transform.aggregations:
            if agg_func == "count":
                agg_df = selected_df.count()
            elif agg_func == "sum":
                agg_df = selected_df.sum()
            elif agg_func == "mean":
                agg_df = selected_df.mean()
            elif agg_func == "median":
                agg_df = selected_df.median()
            elif agg_func == "min":
                agg_df = selected_df.min()
            elif agg_func == "max":
                agg_df = selected_df.max()
            else:
                assert_never(agg_func)

            # Rename all
            agg_df = agg_df.rename(
                {column: f"{column}_{agg_func}" for column in agg_df.columns}
            )
            # Add to result
            result_df = result_df.hstack(agg_df)

        return result_df

    @staticmethod
    def handle_select_columns(
        df: "pl.DataFrame", transform: SelectColumnsTransform
    ) -> "pl.DataFrame":
        return df.select(transform.column_ids)

    @staticmethod
    def handle_shuffle_rows(
        df: "pl.DataFrame", transform: ShuffleRowsTransform
    ) -> "pl.DataFrame":
        return df.sample(fraction=1, shuffle=True, seed=transform.seed)

    @staticmethod
    def handle_sample_rows(
        df: "pl.DataFrame", transform: SampleRowsTransform
    ) -> "pl.DataFrame":
        return df.sample(
            n=transform.n,
            shuffle=True,
            seed=transform.seed,
            with_replacement=transform.replace,
        )


def _coerce_value(dtype: Any, value: Any) -> Any:
    import numpy as np

    return np.array([value]).astype(dtype)[0]
