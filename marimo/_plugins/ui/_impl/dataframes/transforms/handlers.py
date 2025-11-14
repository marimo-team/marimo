# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Callable, TypeIs

import narwhals.stable.v2 as nw
from narwhals.stable.v2 import col
from narwhals.typing import IntoLazyFrame

from marimo._plugins.ui._impl.dataframes.transforms.print_code import (
    python_print_ibis,
    python_print_pandas,
    python_print_polars,
    python_print_transforms,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    AggregateTransform,
    ColumnConversionTransform,
    ExpandDictTransform,
    ExplodeColumnsTransform,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnTransform,
    SampleRowsTransform,
    SelectColumnsTransform,
    ShuffleRowsTransform,
    SortColumnTransform,
    Transform,
    TransformHandler,
    UniqueTransform,
)
from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    import polars as pl
    from narwhals.expr import Expr


__all__ = [
    "NarwhalsTransformHandler",
]


DataFrame = nw.LazyFrame[IntoLazyFrame]


class NarwhalsTransformHandler(TransformHandler[DataFrame]):
    @staticmethod
    def handle_column_conversion(
        df: DataFrame, transform: ColumnConversionTransform
    ) -> DataFrame:
        # Convert numpy dtype string to narwhals dtype
        data_type_str = transform.data_type.replace("_", "").lower()

        # Map numpy/pandas dtype strings to narwhals dtypes
        dtype_map = {
            "int8": nw.Int8,
            "int16": nw.Int16,
            "int32": nw.Int32,
            "int64": nw.Int64,
            "uint8": nw.UInt8,
            "uint16": nw.UInt16,
            "uint32": nw.UInt32,
            "uint64": nw.UInt64,
            "float32": nw.Float32,
            "float64": nw.Float64,
            "bool": nw.Boolean,
            "str": nw.String,
            "string": nw.String,
            "datetime64": nw.Datetime,
            "date": nw.Date,
        }

        narwhals_dtype = dtype_map.get(data_type_str)
        if narwhals_dtype is None:
            raise ValueError(f"Unsupported dtype: {transform.data_type}")

        if transform.errors == "ignore":
            # For ignore mode, wrap cast in a try-except at the expression level
            # This will set invalid values to null rather than failing
            try:
                # Try casting with null handling for errors
                casted = col(transform.column_id).cast(narwhals_dtype)  # type: ignore[arg-type]
                result = df.with_columns(casted)
            except Exception:
                # If cast fails entirely, return original dataframe
                result = df
        else:
            # For raise mode, let exceptions propagate
            result = df.with_columns(
                col(transform.column_id).cast(narwhals_dtype)  # type: ignore[arg-type]
            )
        return result

    @staticmethod
    def handle_rename_column(
        df: DataFrame, transform: RenameColumnTransform
    ) -> DataFrame:
        return df.rename({transform.column_id: str(transform.new_column_id)})

    @staticmethod
    def handle_sort_column(
        df: DataFrame, transform: SortColumnTransform
    ) -> DataFrame:
        result = df.sort(
            transform.column_id,
            descending=not transform.ascending,
            nulls_last=transform.na_position == "last",
        )
        return result

    @staticmethod
    def handle_filter_rows(
        df: DataFrame, transform: FilterRowsTransform
    ) -> DataFrame:
        if not transform.where:
            return df

        filter_expr: nw.Expr | None = None

        def convert_value(v: Any, converter: Callable[[str], Any]) -> Any:
            # Convert a value whether it's a list or single value
            if isinstance(v, (tuple, list)):
                return [converter(str(item)) for item in v]
            return converter(str(v))

        for condition in transform.where:
            # Don't convert to string if already a string or int
            # Narwhals col() can handle both strings and integers
            column = col(condition.column_id)
            value = condition.value

            # For polars, we need to convert the values based on dtype
            native_df = df.to_native()
            if _is_polars_dataframe_or_lazyframe(native_df):
                import polars as pl

                dtype = native_df.collect_schema()[str(condition.column_id)]
                if dtype == pl.Datetime:
                    value = convert_value(
                        value, datetime.datetime.fromisoformat
                    )
                elif dtype == pl.Date:
                    value = convert_value(value, datetime.date.fromisoformat)
                elif dtype == pl.Time:
                    value = convert_value(value, datetime.time.fromisoformat)

            # Build the expression based on the operator
            condition_expr: nw.Expr
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
                condition_expr = column == True  # type: ignore[comparison-overlap] # noqa: E712
            elif condition.operator == "is_false":
                condition_expr = column == False  # type: ignore[comparison-overlap] # noqa: E712
            elif condition.operator == "is_null":
                condition_expr = column.is_null()
            elif condition.operator == "is_not_null":
                condition_expr = ~column.is_null()
            elif condition.operator == "equals":
                condition_expr = column == value
            elif condition.operator == "does_not_equal":
                condition_expr = column != value
            elif condition.operator == "contains":
                # Fill null before string operation to avoid pandas issues
                condition_expr = column.fill_null("").str.contains(
                    str(value), literal=True
                )
            elif condition.operator == "regex":
                # Fill null before string operation to avoid pandas issues
                condition_expr = column.fill_null("").str.contains(
                    str(value), literal=False
                )
            elif condition.operator == "starts_with":
                # Fill null before string operation to avoid pandas issues
                condition_expr = column.fill_null("").str.starts_with(
                    str(value)
                )
            elif condition.operator == "ends_with":
                # Fill null before string operation to avoid pandas issues
                condition_expr = column.fill_null("").str.ends_with(str(value))
            elif condition.operator == "in":
                # is_in doesn't support None values, so we need to handle them separately
                if value is not None and None in value:
                    condition_expr = column.is_in(value) | column.is_null()
                else:
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
            result = df.filter(filter_expr)
        elif transform.operation == "remove_rows":
            result = df.filter(~filter_expr)  # type: ignore[operator]
        else:
            assert_never(transform.operation)

        return result

    @staticmethod
    def handle_group_by(
        df: DataFrame, transform: GroupByTransform
    ) -> DataFrame:
        aggs: list[Expr] = []
        group_by_column_id_set = set(transform.column_ids)
        agg_columns = [
            column_id
            for column_id in df.collect_schema().names()
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

        return df.group_by(transform.column_ids).agg(aggs)

    @staticmethod
    def handle_aggregate(
        df: DataFrame, transform: AggregateTransform
    ) -> DataFrame:
        selected_df = df.select(transform.column_ids)

        agg_list: list[Expr] = []
        for agg_func in transform.aggregations:
            for column_id in transform.column_ids:
                name = f"{column_id}_{agg_func}"
                if agg_func == "count":
                    agg_list.append(col(str(column_id)).count().alias(name))
                elif agg_func == "sum":
                    agg_list.append(col(str(column_id)).sum().alias(name))
                elif agg_func == "mean":
                    agg_list.append(col(str(column_id)).mean().alias(name))
                elif agg_func == "median":
                    agg_list.append(col(str(column_id)).median().alias(name))
                elif agg_func == "min":
                    agg_list.append(col(str(column_id)).min().alias(name))
                elif agg_func == "max":
                    agg_list.append(col(str(column_id)).max().alias(name))
                else:
                    assert_never(agg_func)

        return selected_df.select(agg_list)

    @staticmethod
    def handle_select_columns(
        df: DataFrame, transform: SelectColumnsTransform
    ) -> DataFrame:
        return df.select(transform.column_ids)

    @staticmethod
    def handle_shuffle_rows(
        df: DataFrame, transform: ShuffleRowsTransform
    ) -> DataFrame:
        # Note: narwhals sample requires collecting first for shuffle with seed
        result = df.collect().sample(fraction=1, seed=transform.seed)
        return result.lazy()

    @staticmethod
    def handle_sample_rows(
        df: DataFrame, transform: SampleRowsTransform
    ) -> DataFrame:
        # Note: narwhals sample requires collecting first for shuffle with seed
        result = df.collect().sample(
            n=transform.n,
            seed=transform.seed,
            with_replacement=transform.replace,
        )
        return result.lazy()

    @staticmethod
    def handle_explode_columns(
        df: DataFrame, transform: ExplodeColumnsTransform
    ) -> DataFrame:
        return df.explode(transform.column_ids)

    @staticmethod
    def handle_expand_dict(
        df: DataFrame, transform: ExpandDictTransform
    ) -> DataFrame:
        return df.explode(transform.column_id)

    @staticmethod
    def handle_unique(df: DataFrame, transform: UniqueTransform) -> DataFrame:
        keep = transform.keep
        if keep == "any" or keep == "none":
            return df.unique(subset=transform.column_ids, keep=keep)
        if keep == "first" or keep == "last":
            # Note: narwhals unique requires collecting first for unique with keep "first/last
            return (
                df.collect()
                .unique(subset=transform.column_ids, keep=keep)
                .lazy()
            )
        assert_never(keep)

    @staticmethod
    def as_python_code(
        df: DataFrame,
        df_name: str,
        columns: list[str],
        transforms: list[Transform],
    ) -> str | None:
        native_df = df.to_native()
        if nw.dependencies.is_ibis_table(native_df):
            return python_print_transforms(
                df_name, columns, transforms, python_print_ibis
            )
        elif nw.dependencies.is_pandas_dataframe(native_df):
            return python_print_transforms(
                df_name, columns, transforms, python_print_pandas
            )
        elif nw.dependencies.is_polars_dataframe(native_df):
            return python_print_transforms(
                df_name, columns, transforms, python_print_polars
            )
        else:
            return python_print_transforms(
                df_name, columns, transforms, python_print_ibis
            )

    @staticmethod
    def as_sql_code(transformed_df: DataFrame) -> str | None:
        native_df = transformed_df.to_native()
        if nw.dependencies.is_ibis_table(native_df):
            import ibis  # type: ignore[import-not-found]

            try:
                return str(ibis.to_sql(native_df))
            except Exception:
                # In case it is not a SQL backend
                return None
        return None


def _is_polars_dataframe_or_lazyframe(
    df: Any,
) -> TypeIs[pl.DataFrame | pl.LazyFrame]:
    return nw.dependencies.is_polars_dataframe(
        df
    ) or nw.dependencies.is_polars_lazyframe(df)
