# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, NoReturn, Optional, cast

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
    import ibis  # type: ignore
    import ibis.expr.types as ir  # type: ignore
    import pandas as pd
    import polars as pl


class PandasTransformHandler(TransformHandler["pd.DataFrame"]):
    @staticmethod
    def handle_column_conversion(
        df: pd.DataFrame, transform: ColumnConversionTransform
    ) -> pd.DataFrame:
        df[transform.column_id] = df[transform.column_id].astype(
            transform.data_type,
            errors=transform.errors,
        )  # type: ignore[call-overload]
        return df

    @staticmethod
    def handle_rename_column(
        df: pd.DataFrame, transform: RenameColumnTransform
    ) -> pd.DataFrame:
        return df.rename(
            columns={transform.column_id: transform.new_column_id}
        )

    @staticmethod
    def handle_sort_column(
        df: pd.DataFrame, transform: SortColumnTransform
    ) -> pd.DataFrame:
        return df.sort_values(
            by=cast(str, transform.column_id),
            ascending=transform.ascending,
            na_position=transform.na_position,
        )

    @staticmethod
    def handle_filter_rows(
        df: pd.DataFrame, transform: FilterRowsTransform
    ) -> pd.DataFrame:
        if not transform.where:
            return df

        import pandas as pd

        clauses: list[pd.Series[Any]] = []
        for condition in transform.where:
            column: pd.Series[Any] = df[condition.column_id]

            try:
                value = _coerce_value(
                    df[condition.column_id].dtype, condition.value
                )
            except Exception:
                value = condition.value or ""

            # Handle numeric comparisons
            if condition.operator == "==":
                df_filter = column == value
            elif condition.operator == "!=":
                df_filter = column != value
            elif condition.operator == ">":
                df_filter = column > value
            elif condition.operator == "<":
                df_filter = column < value
            elif condition.operator == ">=":
                df_filter = column >= value
            elif condition.operator == "<=":
                df_filter = column <= value
            # Handle boolean operations
            elif condition.operator == "is_true":
                df_filter = column.eq(True)
            elif condition.operator == "is_false":
                df_filter = column.eq(False)
            # Handle null checks
            elif condition.operator == "is_nan":
                df_filter = column.isna()
            elif condition.operator == "is_not_nan":
                df_filter = column.notna()
            # Handle equality operations
            elif condition.operator == "equals":
                df_filter = column == value
            elif condition.operator == "does_not_equal":
                df_filter = column != value
            # Handle string operations
            elif condition.operator == "contains":
                df_filter = column.str.contains(
                    str(value), regex=False, na=False
                )
            elif condition.operator == "regex":
                df_filter = column.str.contains(
                    str(value), regex=True, na=False
                )
            elif condition.operator == "starts_with":
                df_filter = column.str.startswith(str(value), na=False)
            elif condition.operator == "ends_with":
                df_filter = column.str.endswith(str(value), na=False)
            # Handle list operations with proper Unicode handling
            elif condition.operator == "in":
                # Nested lists can be filtered directly without converting the value
                if condition.value and isinstance(
                    condition.value[0], (list, tuple)
                ):
                    df_filter = df[condition.column_id].isin(condition.value)
                else:
                    df_filter = df[condition.column_id].isin(value)
            else:
                assert_never(condition.operator)

            clauses.append(df_filter)

        if transform.operation == "keep_rows":
            df = df[pd.concat(clauses, axis=1).all(axis=1)]
        elif transform.operation == "remove_rows":
            df = df[~pd.concat(clauses, axis=1).all(axis=1)]
        else:
            assert_never(transform.operation)

        return df

    @staticmethod
    def handle_group_by(
        df: pd.DataFrame, transform: GroupByTransform
    ) -> pd.DataFrame:
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
        df: pd.DataFrame, transform: AggregateTransform
    ) -> pd.DataFrame:
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
        df: pd.DataFrame, transform: SelectColumnsTransform
    ) -> pd.DataFrame:
        return df[transform.column_ids]

    @staticmethod
    def handle_shuffle_rows(
        df: pd.DataFrame, transform: ShuffleRowsTransform
    ) -> pd.DataFrame:
        return df.sample(frac=1, random_state=transform.seed)

    @staticmethod
    def handle_sample_rows(
        df: pd.DataFrame, transform: SampleRowsTransform
    ) -> pd.DataFrame:
        return df.sample(
            n=transform.n,
            random_state=transform.seed,
            replace=transform.replace,
        )

    @staticmethod
    def handle_explode_columns(
        df: pd.DataFrame, transform: ExplodeColumnsTransform
    ) -> pd.DataFrame:
        return df.explode(transform.column_ids)

    @staticmethod
    def handle_expand_dict(
        df: pd.DataFrame, transform: ExpandDictTransform
    ) -> pd.DataFrame:
        import pandas as pd

        column_id = transform.column_id
        return df.join(
            pd.DataFrame(df.pop(cast(str, column_id)).values.tolist())
        )

    @staticmethod
    def as_python_code(
        df_name: str, columns: list[str], transforms: list[Transform]
    ) -> str:
        return python_print_transforms(
            df_name, columns, transforms, python_print_pandas
        )

    @staticmethod
    def handle_unique(
        df: pd.DataFrame, transform: UniqueTransform
    ) -> pd.DataFrame:
        if transform.keep == "first":
            return df.drop_duplicates(
                subset=transform.column_ids, keep="first"
            )
        if transform.keep == "last":
            return df.drop_duplicates(subset=transform.column_ids, keep="last")
        if transform.keep == "none":
            return df.drop_duplicates(subset=transform.column_ids, keep=False)
        assert_never(cast(NoReturn, transform.keep))


class PolarsTransformHandler(TransformHandler["pl.DataFrame"]):
    @staticmethod
    def handle_column_conversion(
        df: pl.DataFrame, transform: ColumnConversionTransform
    ) -> pl.DataFrame:
        import polars.datatypes as pl_datatypes

        return df.cast(
            {
                str(
                    transform.column_id
                ): pl_datatypes.numpy_char_code_to_dtype(transform.data_type)
            },
            strict=transform.errors == "raise",
        )

    @staticmethod
    def handle_rename_column(
        df: pl.DataFrame, transform: RenameColumnTransform
    ) -> pl.DataFrame:
        return df.rename(
            {str(transform.column_id): str(transform.new_column_id)}
        )

    @staticmethod
    def handle_sort_column(
        df: pl.DataFrame, transform: SortColumnTransform
    ) -> pl.DataFrame:
        return df.sort(
            by=transform.column_id,
            descending=not transform.ascending,
            nulls_last=transform.na_position == "last",
        )

    @staticmethod
    def handle_filter_rows(
        df: pl.DataFrame, transform: FilterRowsTransform
    ) -> pl.DataFrame:
        import polars as pl
        from polars import col

        # Start with no filter (all rows included)
        filter_expr: Optional[pl.Expr] = None

        # Convert a value whether it's a list or single value
        def convert_value(v: Any, converter: Callable[[str], Any]) -> Any:
            if isinstance(v, (tuple, list)):
                return [converter(str(item)) for item in v]
            return converter(str(v))

        # Iterate over all conditions and build the filter expression
        for condition in transform.where:
            column = col(str(condition.column_id))
            dtype = df.schema[str(condition.column_id)]
            value = condition.value
            value_str = str(value)

            # If columns type is a Datetime, we need to convert the value to a datetime
            if dtype == pl.Datetime:
                value = convert_value(value, datetime.datetime.fromisoformat)
            elif dtype == pl.Date:
                value = convert_value(value, datetime.date.fromisoformat)
            elif dtype == pl.Time:
                value = convert_value(value, datetime.time.fromisoformat)

            # If columns type is a Categorical, we need to cast the value to a string
            if dtype == pl.Categorical:
                column = column.cast(pl.String)

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
                condition_expr = column.str.contains(value_str, literal=True)
            elif condition.operator == "regex":
                condition_expr = column.str.contains(value_str, literal=False)
            elif condition.operator == "starts_with":
                condition_expr = column.str.starts_with(value_str)
            elif condition.operator == "ends_with":
                condition_expr = column.str.ends_with(value_str)
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
            return df.filter(filter_expr)
        elif transform.operation == "remove_rows":
            return df.filter(~filter_expr)
        else:
            assert_never(transform.operation)

    @staticmethod
    def handle_group_by(
        df: pl.DataFrame, transform: GroupByTransform
    ) -> pl.DataFrame:
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
        df: pl.DataFrame, transform: AggregateTransform
    ) -> pl.DataFrame:
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
        df: pl.DataFrame, transform: SelectColumnsTransform
    ) -> pl.DataFrame:
        return df.select(transform.column_ids)

    @staticmethod
    def handle_shuffle_rows(
        df: pl.DataFrame, transform: ShuffleRowsTransform
    ) -> pl.DataFrame:
        return df.sample(fraction=1, shuffle=True, seed=transform.seed)

    @staticmethod
    def handle_sample_rows(
        df: pl.DataFrame, transform: SampleRowsTransform
    ) -> pl.DataFrame:
        return df.sample(
            n=transform.n,
            shuffle=True,
            seed=transform.seed,
            with_replacement=transform.replace,
        )

    @staticmethod
    def handle_explode_columns(
        df: pl.DataFrame, transform: ExplodeColumnsTransform
    ) -> pl.DataFrame:
        return df.explode(cast(Sequence[str], transform.column_ids))

    @staticmethod
    def handle_expand_dict(
        df: pl.DataFrame, transform: ExpandDictTransform
    ) -> pl.DataFrame:
        import polars as pl

        column_id = transform.column_id
        column = df.select(column_id).to_series()
        df = df.drop(cast(str, column_id))
        return df.hstack(pl.DataFrame(column.to_list()))

    @staticmethod
    def as_python_code(
        df_name: str, columns: list[str], transforms: list[Transform]
    ) -> str:
        return python_print_transforms(
            df_name, columns, transforms, python_print_polars
        )

    @staticmethod
    def handle_unique(
        df: pl.DataFrame, transform: UniqueTransform
    ) -> pl.DataFrame:
        keep = transform.keep
        if (
            keep == "first"
            or keep == "last"
            or keep == "any"
            or keep == "none"
        ):
            return df.unique(
                subset=cast(Sequence[str], transform.column_ids), keep=keep
            )
        assert_never(keep)


class IbisTransformHandler(TransformHandler["ibis.Table"]):
    @staticmethod
    def handle_column_conversion(
        df: ibis.Table, transform: ColumnConversionTransform
    ) -> ibis.Table:
        import ibis

        transform_data_type = transform.data_type.replace("_", "")

        if transform.errors == "ignore":
            try:
                # Use coalesce to handle conversion errors
                return df.mutate(
                    ibis.coalesce(
                        df[transform.column_id].cast(
                            ibis.dtype(transform_data_type)
                        ),
                        df[transform.column_id],
                    ).name(transform.column_id)
                )
            except ibis.common.exceptions.IbisTypeError:
                return df
        else:
            # Default behavior (raise errors)
            return df.mutate(
                df[transform.column_id]
                .cast(ibis.dtype(transform_data_type))
                .name(transform.column_id)
            )

    @staticmethod
    def handle_rename_column(
        df: ibis.Table, transform: RenameColumnTransform
    ) -> ibis.Table:
        return df.rename({transform.new_column_id: transform.column_id})

    @staticmethod
    def handle_sort_column(
        df: ibis.Table, transform: SortColumnTransform
    ) -> ibis.Table:
        return df.order_by(
            [
                (
                    df[transform.column_id].asc()
                    if transform.ascending
                    else df[transform.column_id].desc()
                )
            ]
        )

    @staticmethod
    def handle_filter_rows(
        df: ibis.Table, transform: FilterRowsTransform
    ) -> ibis.Table:
        import ibis

        filter_conditions: list[ir.BooleanValue] = []
        for condition in transform.where:
            column = df[str(condition.column_id)]
            value = condition.value
            if condition.operator == "==":
                filter_conditions.append(column == value)
            elif condition.operator == "!=":
                filter_conditions.append(column != value)
            elif condition.operator == ">":
                filter_conditions.append(column > value)
            elif condition.operator == "<":
                filter_conditions.append(column < value)
            elif condition.operator == ">=":
                filter_conditions.append(column >= value)
            elif condition.operator == "<=":
                filter_conditions.append(column <= value)
            elif condition.operator == "is_true":
                filter_conditions.append(column)
            elif condition.operator == "is_false":
                filter_conditions.append(~column)
            elif condition.operator == "is_nan":
                filter_conditions.append(column.isnull())
            elif condition.operator == "is_not_nan":
                filter_conditions.append(column.notnull())
            elif condition.operator == "equals":
                filter_conditions.append(column == value)
            elif condition.operator == "does_not_equal":
                filter_conditions.append(column != value)
            elif condition.operator == "contains":
                filter_conditions.append(column.contains(value))
            elif condition.operator == "regex":
                filter_conditions.append(column.re_search(value))
            elif condition.operator == "starts_with":
                filter_conditions.append(column.startswith(value))
            elif condition.operator == "ends_with":
                filter_conditions.append(column.endswith(value))
            elif condition.operator == "in":
                # is_in doesn't support None values, so we need to handle them separately
                if value is not None and None in value:
                    filter_conditions.append(
                        column.isnull() | column.isin(value)
                    )
                else:
                    filter_conditions.append(column.isin(value))
            else:
                assert_never(condition.operator)

        combined_condition = ibis.and_(*filter_conditions)

        if transform.operation == "keep_rows":
            return df.filter(combined_condition)
        elif transform.operation == "remove_rows":
            return df.filter(~combined_condition)
        else:
            assert_never(transform.operation)

    @staticmethod
    def handle_group_by(
        df: ibis.Table, transform: GroupByTransform
    ) -> ibis.Table:
        aggs: list[ir.Expr] = []

        group_by_column_id_set = set(transform.column_ids)
        agg_columns = [
            column_id
            for column_id in df.columns
            if column_id not in group_by_column_id_set
        ]
        for column_id in agg_columns:
            agg_func = transform.aggregation
            if agg_func == "count":
                aggs.append(df[column_id].count().name(f"{column_id}_count"))
            elif agg_func == "sum":
                aggs.append(df[column_id].sum().name(f"{column_id}_sum"))
            elif agg_func == "mean":
                aggs.append(df[column_id].mean().name(f"{column_id}_mean"))
            elif agg_func == "median":
                aggs.append(df[column_id].median().name(f"{column_id}_median"))
            elif agg_func == "min":
                aggs.append(df[column_id].min().name(f"{column_id}_min"))
            elif agg_func == "max":
                aggs.append(df[column_id].max().name(f"{column_id}_max"))
            else:
                assert_never(agg_func)

        return df.group_by(transform.column_ids).aggregate(aggs)

    @staticmethod
    def handle_aggregate(
        df: ibis.Table, transform: AggregateTransform
    ) -> ibis.Table:
        agg_dict: dict[str, Any] = {}
        for agg_func in transform.aggregations:
            for column_id in transform.column_ids:
                name = f"{column_id}_{agg_func}"
                agg_dict[name] = getattr(df[column_id], agg_func)()
        return df.aggregate(**agg_dict)

    @staticmethod
    def handle_select_columns(
        df: ibis.Table, transform: SelectColumnsTransform
    ) -> ibis.Table:
        return df.select(transform.column_ids)

    @staticmethod
    def handle_shuffle_rows(
        df: ibis.Table, transform: ShuffleRowsTransform
    ) -> ibis.Table:
        del transform
        import ibis

        return df.order_by(ibis.random())

    @staticmethod
    def handle_sample_rows(
        df: ibis.Table, transform: SampleRowsTransform
    ) -> ibis.Table:
        return df.sample(
            transform.n / df.count().execute(),
            method="row",
            seed=transform.seed,
        )

    @staticmethod
    def handle_explode_columns(
        df: ibis.Table, transform: ExplodeColumnsTransform
    ) -> ibis.Table:
        for column_id in transform.column_ids:
            df = df.unnest(column_id)
        return df

    @staticmethod
    def handle_expand_dict(
        df: ibis.Table, transform: ExpandDictTransform
    ) -> ibis.Table:
        return df.unpack(transform.column_id)

    @staticmethod
    def handle_unique(
        df: ibis.Table, transform: UniqueTransform
    ) -> ibis.Table:
        if transform.keep == "first":
            return df.distinct(on=transform.column_ids, keep="first")
        if transform.keep == "last":
            return df.distinct(on=transform.column_ids, keep="last")
        if transform.keep == "none":
            return df.distinct(on=transform.column_ids, keep=None)
        assert_never(cast(NoReturn, transform.keep))

    @staticmethod
    def as_python_code(
        df_name: str, columns: list[str], transforms: list[Transform]
    ) -> str | None:
        return python_print_transforms(
            df_name, columns, transforms, python_print_ibis
        )

    @staticmethod
    def as_sql_code(transformed_df: ibis.Table) -> str | None:
        import ibis

        try:
            return str(ibis.to_sql(transformed_df))
        except Exception:
            # In case it is not a SQL backend
            return None


def _coerce_value(dtype: Any, value: Any) -> Any:
    """Coerce value to match column dtype while preserving numeric precision."""
    import numpy as np

    # Handle None/empty values
    if value is None:
        return None

    # If its a int or float, return as is
    if isinstance(value, (int, float)):
        return value

    # Default coercion for other cases
    try:
        return np.array([value]).astype(dtype)[0]
    except Exception:
        return value
