# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import decimal
from collections.abc import Callable
from functools import reduce
from typing import TYPE_CHECKING, Any

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
    FilterCondition,
    FilterGroup,
    FilterRowsTransform,
    GroupByTransform,
    PivotTransform,
    RangeValue,
    RenameColumnTransform,
    SampleRowsTransform,
    SelectColumnsTransform,
    ShuffleRowsTransform,
    SortColumnTransform,
    Transform,
    TransformHandler,
    UniqueTransform,
)
from marimo._plugins.ui._impl.tables.narwhals_table import (
    NAN_VALUE,
    NEGATIVE_INF,
    POSITIVE_INF,
)
from marimo._utils.assert_never import assert_never
from marimo._utils.narwhals_utils import collect_and_preserve_type

if TYPE_CHECKING:
    from collections.abc import Callable

    import polars as pl
    from narwhals.expr import Expr
    from typing_extensions import TypeIs


__all__ = [
    "NarwhalsTransformHandler",
]


DataFrame = nw.LazyFrame[IntoLazyFrame]


def convert_value(v: Any, converter: Callable[[str], Any]) -> Any:
    """
    Convert a value whether it's a list or single value.
    Ignore None as they usually raise errors when converted
    """
    if isinstance(v, (tuple, list)):
        return [
            converter(str(item)) if item is not None else None for item in v
        ]
    if v is None:
        return None
    return converter(str(v))


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
    def _evaluate_condition(df: DataFrame, condition: FilterCondition) -> Expr:
        column = col(condition.column_id)
        column_name = str(condition.column_id)
        value = condition.value
        dtype = df.collect_schema().get(column_name)

        # Convert string values to the appropriate type based on dtype
        if dtype == nw.Datetime:
            value = convert_value(value, datetime.datetime.fromisoformat)
        elif dtype == nw.Date:
            value = convert_value(value, datetime.date.fromisoformat)
        elif dtype == nw.Time:
            value = convert_value(value, datetime.time.fromisoformat)
        elif dtype == nw.Object:
            # Object dtype may contain date/datetime/Decimal values
            # (e.g., pandas stores these as Python objects)
            try:
                sample = (
                    df.select(column_name)
                    .filter(~col(column_name).is_null())
                    .head(1)
                    .collect()
                    .get_column(column_name)
                    .to_list()
                )
                if sample:
                    if isinstance(sample[0], datetime.datetime):
                        value = convert_value(
                            value, datetime.datetime.fromisoformat
                        )
                    elif isinstance(sample[0], datetime.date):
                        value = convert_value(
                            value, datetime.date.fromisoformat
                        )
                    elif isinstance(sample[0], datetime.time):
                        value = convert_value(
                            value, datetime.time.fromisoformat
                        )
                    elif isinstance(sample[0], decimal.Decimal):
                        # Cast to Float64 so Decimal values can be compared, minor precision loss
                        value = convert_value(value, float)
                        column = column.cast(nw.Float64)
            except Exception:
                pass

        # If the value includes NaNs or infs, we convert to floats so the filters apply correctly
        if (
            isinstance(value, tuple)
            and any(
                token in value
                for token in [NAN_VALUE, POSITIVE_INF, NEGATIVE_INF]
            )
            and dtype is not None
            and dtype.is_float()  # Note: this doesn't cover Object types for pandas
        ):
            value = convert_value(value, float)
        elif dtype is not None and dtype.is_decimal():
            # Cast to Float64 so Decimal values can be compared, minor precision loss
            value = convert_value(value, float)
            column = column.cast(nw.Float64)

        # Build the expression based on the operator
        condition_expr: nw.Expr

        is_negated = condition.negate
        match condition.operator:
            case "==":
                condition_expr = (
                    column != value if is_negated else column == value
                )
            case "!=":
                condition_expr = (
                    column == value if is_negated else column != value
                )
            case ">":
                condition_expr = (
                    column <= value if is_negated else column > value
                )
            case "<":
                condition_expr = (
                    column >= value if is_negated else column < value
                )
            case ">=":
                condition_expr = (
                    column < value if is_negated else column >= value
                )
            case "<=":
                condition_expr = (
                    column > value if is_negated else column <= value
                )
            case "is_true":
                condition_expr = (
                    column == False  # type: ignore[comparison-overlap] # noqa: E712
                    if is_negated
                    else column == True  # type: ignore[comparison-overlap] # noqa: E712
                )
            case "is_false":
                condition_expr = (
                    column == True  # type: ignore[comparison-overlap] # noqa: E712
                    if is_negated
                    else column == False  # type: ignore[comparison-overlap] # noqa: E712
                )
            case "is_null":
                condition_expr = (
                    ~column.is_null() if is_negated else column.is_null()
                )
            case "is_not_null":
                condition_expr = (
                    column.is_null() if is_negated else ~column.is_null()
                )
            case "equals":
                condition_expr = (
                    column != value if is_negated else column == value
                )
            case "does_not_equal":
                condition_expr = (
                    column == value if is_negated else column != value
                )
            case "contains":
                base_expr = column.fill_null("").str.contains(
                    str(value), literal=True
                )
                condition_expr = (
                    ~base_expr & ~column.is_null() if is_negated else base_expr
                )
            case "regex":
                base_expr = column.fill_null("").str.contains(
                    str(value), literal=False
                )
                condition_expr = (
                    ~base_expr & ~column.is_null() if is_negated else base_expr
                )
            case "starts_with":
                base_expr = column.fill_null("").str.starts_with(str(value))
                condition_expr = (
                    ~base_expr & ~column.is_null() if is_negated else base_expr
                )
            case "ends_with":
                base_expr = column.fill_null("").str.ends_with(str(value))
                condition_expr = (
                    ~base_expr & ~column.is_null() if is_negated else base_expr
                )
            case "in":
                if value is not None and None in value:
                    condition_expr = (
                        ~column.is_in(value) & ~column.is_null()
                        if is_negated
                        else column.is_in(value) | column.is_null()
                    )
                else:
                    condition_expr = (
                        ~column.is_in(value or []) | column.is_null()
                        if is_negated
                        else column.is_in(value or [])
                    )
            case "not_in":
                if value is not None and None in value:
                    base_expr = ~column.is_in(value) & ~column.is_null()
                    condition_expr = (
                        column.is_in(value) | column.is_null()
                        if is_negated
                        else base_expr
                    )
                else:
                    base_expr = ~column.is_in(value or []) | column.is_null()
                    condition_expr = (
                        column.is_in(value or []) if is_negated else base_expr
                    )
            case "between":
                if isinstance(value, RangeValue):
                    if is_negated:
                        condition_expr = (column < value.min) | (
                            column > value.max
                        )
                    else:
                        condition_expr = (column >= value.min) & (
                            column <= value.max
                        )
                else:
                    raise TypeError(
                        f"between operator requires RangeValue, got {type(value)}"
                    )
            case "is_empty":
                condition_expr = (
                    (column != "") | column.is_null()
                    if is_negated
                    else (column == "") & ~column.is_null()
                )
            case _:
                assert_never(condition.operator)

        return condition_expr

    @staticmethod
    def _evaluate_filter_group(
        df: DataFrame, group: FilterGroup
    ) -> Expr | None:
        operator = group.operator
        conditions = group.children
        filter_expr: Expr | None = None

        for condition in conditions:
            expr: Expr | None = None
            if isinstance(condition, FilterCondition):
                expr = NarwhalsTransformHandler._evaluate_condition(
                    df, condition
                )
            elif isinstance(condition, FilterGroup):
                expr = NarwhalsTransformHandler._evaluate_filter_group(
                    df, condition
                )
            else:
                assert_never(condition)

            if expr is None:
                continue

            if filter_expr is None:
                filter_expr = expr
            else:
                if operator == "and":
                    filter_expr = filter_expr & expr
                elif operator == "or":
                    filter_expr = filter_expr | expr
                else:
                    assert_never(operator)

        if filter_expr is not None and group.negate:
            filter_expr = ~filter_expr

        return filter_expr

    @staticmethod
    def handle_filter_rows(
        df: DataFrame, transform: FilterRowsTransform
    ) -> DataFrame:
        filter_expr = NarwhalsTransformHandler._evaluate_filter_group(
            df, transform.where
        )

        if filter_expr is None:
            return df

        if transform.operation == "keep_rows":
            return df.filter(filter_expr)
        elif transform.operation == "remove_rows":
            return df.filter(~filter_expr)  # type: ignore[operator]
        else:
            assert_never(transform.operation)

    @staticmethod
    def handle_group_by(
        df: DataFrame, transform: GroupByTransform
    ) -> DataFrame:
        aggs: list[Expr] = []
        group_by_column_id_set = set(transform.column_ids)
        columns = (
            transform.aggregation_column_ids or df.collect_schema().names()
        )
        agg_columns = [
            column_id
            for column_id in columns
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
        collected_df, undo = collect_and_preserve_type(df)
        result = collected_df.sample(fraction=1, seed=transform.seed)
        return undo(result)

    @staticmethod
    def handle_sample_rows(
        df: DataFrame, transform: SampleRowsTransform
    ) -> DataFrame:
        # Note: narwhals sample requires collecting first for shuffle with seed
        collected_df, undo = collect_and_preserve_type(df)
        result = collected_df.sample(
            n=transform.n,
            seed=transform.seed,
            with_replacement=transform.replace,
        )
        return undo(result)

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
    def handle_pivot(df: DataFrame, transform: PivotTransform) -> DataFrame:
        # Since ibis does not have a native pivot, and pivot is not supported for LazyFrame
        # we implement it manually
        # pivot results are also highly inconsistent across backends, so we standardize the output here

        if not transform.index_column_ids and not transform.value_column_ids:
            raise nw.exceptions.InvalidOperationError(
                "Pivot transform requires at least one index column and or value column."
            )

        columns = df.collect_schema().names()
        if not transform.index_column_ids:
            index_columns = list(
                filter(
                    lambda col: (
                        col not in transform.column_ids
                        and col not in transform.value_column_ids
                    ),
                    columns,
                )
            )
        else:
            index_columns = transform.index_column_ids

        if not transform.value_column_ids:
            value_columns = list(
                filter(
                    lambda col: (
                        col not in transform.column_ids
                        and col not in transform.index_column_ids
                    ),
                    columns,
                )
            )
        else:
            value_columns = transform.value_column_ids

        raw_pivot_columns = (
            df.select(*transform.column_ids)
            .unique()
            .sort(by=transform.column_ids)
            .collect()
            .rows()
        )

        dfs = []
        for raw_pivot_column in raw_pivot_columns:
            aggs = []
            mask = reduce(
                lambda x, y: x & y,
                [
                    nw.col(on_col) == on_val
                    for on_col, on_val in zip(
                        transform.column_ids, raw_pivot_column, strict=False
                    )
                ],
            )
            for value_column in value_columns:
                expr = nw.col(value_column).alias(
                    f"{value_column}_{'_'.join(map(str, raw_pivot_column))}_{transform.aggregation}"
                )
                if transform.aggregation == "count":
                    aggs.append(expr.len())
                elif transform.aggregation == "sum":
                    aggs.append(expr.sum())
                elif transform.aggregation == "mean":
                    aggs.append(expr.mean())
                elif transform.aggregation == "median":
                    aggs.append(expr.median())
                elif transform.aggregation == "min":
                    aggs.append(expr.min())
                elif transform.aggregation == "max":
                    aggs.append(expr.max())
                else:
                    raise ValueError(
                        f"Unsupported aggregation function: {transform.aggregation}"
                    )
            dfs.append(df.filter(mask).group_by(*index_columns).agg(*aggs))

        result = df.select(*index_columns).unique()
        for df_ in dfs:
            result = result.join(df_, on=index_columns, how="left")
        if transform.aggregation in {"count", "sum"}:
            result = result.with_columns(
                nw.exclude(*index_columns).fill_null(0)
            )
        return result.sort(by=index_columns)

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
        elif _is_polars_dataframe_or_lazyframe(native_df):
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
