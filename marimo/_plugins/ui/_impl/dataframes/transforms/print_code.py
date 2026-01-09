# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Union

from marimo._plugins.ui._impl.dataframes.transforms.types import (
    Condition,
    Transform,
    TransformType,
)
from marimo._utils.assert_never import assert_never


def python_print_transforms(
    df_name: str,
    all_columns: list[str],
    transforms: list[Transform],
    print_transform: Callable[[str, list[str], Transform], str],
) -> str:
    df_next_name = f"{df_name}_next"
    strs: list[str] = []
    for transform in transforms:
        strs.append(
            f"{df_next_name} = {print_transform(df_next_name, all_columns, transform)}"  # noqa: E501
        )
    return "\n".join([f"{df_next_name} = {df_name}"] + strs)


def python_print_pandas(
    df_name: str, all_columns: list[str], transform: Transform
) -> str:
    def generate_where_clause(df_name: str, where: Condition) -> str:
        column_id, operator, value = (
            where.column_id,
            where.operator,
            where.value,
        )

        if operator == "==":
            return (
                f"{df_name}[{_as_literal(column_id)}] == {_as_literal(value)}"
            )
        elif operator == "equals":
            return (
                f"{df_name}[{_as_literal(column_id)}].eq({_as_literal(value)})"
            )
        elif operator == "does_not_equal":
            return (
                f"{df_name}[{_as_literal(column_id)}].ne({_as_literal(value)})"
            )
        elif operator == "contains":
            return f"{df_name}[{_as_literal(column_id)}].str.contains({_as_literal(value)})"  # noqa: E501
        elif operator == "regex":
            return f"{df_name}[{_as_literal(column_id)}].str.contains({_as_literal(value)}, regex=True)"  # noqa: E501
        elif operator == "starts_with":
            return f"{df_name}[{_as_literal(column_id)}].str.startswith({_as_literal(value)})"  # noqa: E501
        elif operator == "ends_with":
            return f"{df_name}[{_as_literal(column_id)}].str.endswith({_as_literal(value)})"  # noqa: E501
        elif operator == "in" or operator == "not_in":
            result = f"{df_name}[{_as_literal(column_id)}].isin({_list_of_strings(value)})"  # noqa: E501
            return result if operator == "in" else f"~{result}"
        elif operator == "!=":
            return (
                f"{df_name}[{_as_literal(column_id)}].ne({_as_literal(value)})"
            )
        elif operator in [">", ">=", "<", "<="]:
            return f"{df_name}[{_as_literal(column_id)}] {operator} {_as_literal(value)}"  # noqa: E501
        elif operator == "is_null":
            return f"{df_name}[{_as_literal(column_id)}].isna()"
        elif operator == "is_not_null":
            return f"{df_name}[{_as_literal(column_id)}].notna()"
        elif operator == "is_true":
            return f"{df_name}[{_as_literal(column_id)}].eq(True)"
        elif operator == "is_false":
            return f"{df_name}[{_as_literal(column_id)}].eq(False)"
        else:
            raise ValueError(f"Unknown operator: {operator}")

    if transform.type == TransformType.COLUMN_CONVERSION:
        column_id, data_type, errors = (
            transform.column_id,
            transform.data_type,
            transform.errors,
        )
        return f'{df_name}\n{df_name}[{_as_literal(column_id)}] = {df_name}[{_as_literal(column_id)}].astype("{data_type}", errors="{errors}")'  # noqa: E501

    elif transform.type == TransformType.RENAME_COLUMN:
        column_id, new_column_id = (
            transform.column_id,
            transform.new_column_id,
        )
        return f"{df_name}.rename(columns={{{_as_literal(column_id)}: {_as_literal(new_column_id)}}})"  # noqa: E501

    elif transform.type == TransformType.SORT_COLUMN:
        column_id, ascending, na_position = (
            transform.column_id,
            transform.ascending,
            transform.na_position,
        )
        args = _args_list(
            f"by={_as_literal(column_id)}",
            f"ascending={ascending}",
            f"na_position={_as_literal(na_position)}",
        )
        return f"{df_name}.sort_values({args})"

    elif transform.type == TransformType.FILTER_ROWS:
        operation, where = transform.operation, transform.where
        if not where:
            return df_name
        where_clauses = [
            generate_where_clause(df_name, condition) for condition in where
        ]
        if operation == "keep_rows" and len(where_clauses) == 1:
            return f"{df_name}[{where_clauses[0]}]"
        expression = " & ".join(f"({clause})" for clause in where_clauses)
        return (
            f"{df_name}[{expression}]"
            if operation == "keep_rows"
            else f"{df_name}[~({expression})]"
        )

    elif transform.type == TransformType.AGGREGATE:
        column_ids, aggregations = (
            transform.column_ids,
            transform.aggregations,
        )
        if not column_ids:
            return f"{df_name}.agg({_list_of_strings(aggregations)})"
        # Generate code that matches narwhals behavior: columns named like 'column_agg'
        # Use pd.DataFrame to create a single-row dataframe with proper column names
        agg_parts = []
        for agg in aggregations:
            for col in column_ids:
                agg_parts.append(
                    f"{_as_literal(f'{col}_{agg}')}: [{df_name}[{_as_literal(col)}].{agg}()]"
                )
        return f"pd.DataFrame({{{', '.join(agg_parts)}}})"

    elif transform.type == TransformType.GROUP_BY:
        column_ids, aggregation, drop_na = (
            transform.column_ids,
            transform.aggregation,
            transform.drop_na,
        )
        # Use explicit aggregation columns if provided, otherwise all except group-by columns
        # Filter out group-by columns from aggregation columns to match narwhals behavior
        group_by_column_id_set = set(column_ids)
        if transform.aggregation_column_ids:
            aggregation_columns = [
                col
                for col in transform.aggregation_column_ids
                if col not in group_by_column_id_set
            ]
        else:
            aggregation_columns = [
                col for col in all_columns if col not in group_by_column_id_set
            ]
        args = _args_list(_list_of_strings(column_ids), f"dropna={drop_na}")
        group_by = f"{df_name}.groupby({args})"
        # Narwhals adds suffixes to aggregated columns like 'column_count'
        # We need to replicate this behavior by using agg() with explicit column names
        if aggregation == "count":
            agg_func = "count"
        elif aggregation == "sum":
            agg_func = "sum"
        elif aggregation == "mean":
            agg_func = "mean"
        elif aggregation == "median":
            agg_func = "median"
        elif aggregation == "min":
            agg_func = "min"
        elif aggregation == "max":
            agg_func = "max"
        else:
            assert_never(aggregation)

        # If aggregation_columns is empty after filtering, just return unique grouped columns
        # This matches narwhals behavior when agg() is called with empty list
        if not aggregation_columns:
            return f"{df_name}[{_list_of_strings(column_ids)}].drop_duplicates().reset_index(drop=True)"

        # If specific aggregation columns are provided, only aggregate those and rename explicitly.
        agg_dict = ", ".join(
            f"{_as_literal(f'{col}_{aggregation}')} : ({_as_literal(col)}, {_as_literal(agg_func)})"
            for col in aggregation_columns
        )
        return f"{group_by}.agg(**{{{agg_dict}}}).reset_index()"

    elif transform.type == TransformType.SELECT_COLUMNS:
        column_ids = transform.column_ids
        if not column_ids:
            return df_name
        return (
            f"{df_name}[{_as_literal(column_ids[0])}]"
            if len(column_ids) == 1
            else f"{df_name}[{_list_of_strings(column_ids)}]"
        )

    elif transform.type == TransformType.SAMPLE_ROWS:
        n = transform.n
        return f"{df_name}.sample(n={n})"

    elif transform.type == TransformType.SHUFFLE_ROWS:
        return f"{df_name}.sample(frac=1)"

    elif transform.type == TransformType.EXPLODE_COLUMNS:
        column_ids = transform.column_ids
        return f"{df_name}.explode({_list_of_strings(column_ids)})"

    elif transform.type == TransformType.EXPAND_DICT:
        column_id = _as_literal(transform.column_id)
        args = f"{df_name}.pop({column_id}).values.tolist()"
        return f"{df_name}.join(pd.DataFrame({args}))"

    elif transform.type == TransformType.UNIQUE:
        column_ids = transform.column_ids
        return f"{df_name}.drop_duplicates({_list_of_strings(column_ids)}, keep={_as_literal(transform.keep)})"

    elif transform.type == TransformType.PIVOT:
        if not transform.index_column_ids:
            index_columns = _list_of_strings(
                list(
                    filter(
                        lambda col: col not in transform.column_ids
                        and col not in transform.value_column_ids,
                        all_columns,
                    )
                )
            )
        else:
            index_columns = _list_of_strings(transform.index_column_ids)

        if not transform.value_column_ids:
            value_columns = _list_of_strings(
                list(
                    filter(
                        lambda col: col not in transform.column_ids
                        and col not in transform.index_column_ids,
                        all_columns,
                    )
                )
            )
        else:
            value_columns = _list_of_strings(transform.value_column_ids)
        column_ids = transform.column_ids
        agg_func = transform.aggregation

        args = _args_list(
            f"index={index_columns}",
            f"columns={_list_of_strings(column_ids)}",
            f"values={value_columns}",
            f"aggfunc={_as_literal(agg_func)}",
            "sort=False",
        )
        pivot_code = f"{df_name}.pivot_table({args}).sort_index(axis=0)"
        flatten_columns_code = (
            f"{df_name}.columns = ["
            f"f\"{{'_'.join(map(str, col)).strip()}}_{agg_func}\" "
            f'if isinstance(col, tuple) else f"{{col}}_{agg_func}" '
            f"for col in {df_name}.columns]"
        )
        reset_index_code = f"{df_name} = {df_name}.reset_index()"
        return f"{pivot_code}\n{flatten_columns_code}\n{reset_index_code}"

    assert_never(transform.type)


def python_print_polars(
    df_name: str, all_columns: list[str], transform: Transform
) -> str:
    def generate_where_clause_polars(where: Condition) -> str:
        column_id, operator, value = (
            where.column_id,
            where.operator,
            where.value,
        )

        if operator == "==" or operator == "equals":
            return f"pl.col({_as_literal(column_id)}) == {_as_literal(value)}"
        elif operator == "does_not_equal" or operator == "!=":
            return f"pl.col({_as_literal(column_id)}) != {_as_literal(value)}"
        elif operator == "contains":
            return f"pl.col({_as_literal(column_id)}).str.contains({_as_literal(value)})"  # noqa: E501
        elif operator == "regex":
            return f"pl.col({_as_literal(column_id)}).str.contains({_as_literal(value)}, literal=False)"  # noqa: E501
        elif operator == "starts_with":
            return f"pl.col({_as_literal(column_id)}).str.starts_with({_as_literal(value)})"  # noqa: E501
        elif operator == "ends_with":
            return f"pl.col({_as_literal(column_id)}).str.ends_with({_as_literal(value)})"  # noqa: E501
        elif operator == "in" or operator == "not_in":
            result = f"pl.col({_as_literal(column_id)}).is_in({_list_of_strings(value)})"  # noqa: E501
            return result if operator == "in" else f"~{result}"
        elif operator in [">", ">=", "<", "<="]:
            return f"pl.col({_as_literal(column_id)}) {operator} {_as_literal(value)}"  # noqa: E501
        elif operator == "is_null":
            return f"pl.col({_as_literal(column_id)}).is_null()"
        elif operator == "is_not_null":
            return f"pl.col({_as_literal(column_id)}).is_not_null()"
        elif operator == "is_true":
            return f"pl.col({_as_literal(column_id)}) == True"
        elif operator == "is_false":
            return f"pl.col({_as_literal(column_id)}) == False"
        else:
            raise ValueError(f"Unknown operator: {operator}")

    if transform.type == TransformType.COLUMN_CONVERSION:
        column_id, data_type = transform.column_id, transform.data_type
        try:
            import polars.datatypes as pl_datatypes

            data_type = str(pl_datatypes.numpy_char_code_to_dtype(data_type))
        except Exception:
            pass
        return f"{df_name}.cast({{{_as_literal(column_id)}: pl.{data_type}}}, strict={transform.errors == 'raise'})"  # noqa: E501

    elif transform.type == TransformType.RENAME_COLUMN:
        column_id, new_column_id = (
            transform.column_id,
            transform.new_column_id,
        )
        # Update column names in place
        all_columns[:] = [
            str(new_column_id) if col == column_id else col
            for col in all_columns
        ]
        return f"{df_name}.rename({{{_as_literal(column_id)}: {_as_literal(new_column_id)}}})"  # noqa: E501

    elif transform.type == TransformType.SORT_COLUMN:
        column_id, ascending, na_position = (
            transform.column_id,
            transform.ascending,
            transform.na_position,
        )
        return f"{df_name}.sort({_as_literal(column_id)}, descending={not ascending}, nulls_last={na_position == 'last'})"  # noqa: E501

    elif transform.type == TransformType.FILTER_ROWS:
        operation, where = transform.operation, transform.where
        if not where:
            return df_name
        where_clauses = [
            generate_where_clause_polars(condition) for condition in where
        ]
        if operation == "keep_rows" and len(where_clauses) == 1:
            return f"{df_name}.filter({where_clauses[0]})"
        expression = " & ".join(f"({clause})" for clause in where_clauses)
        return (
            f"{df_name}.filter({expression})"
            if operation == "keep_rows"
            else f"{df_name}.filter(~({expression}))"
        )

    elif transform.type == TransformType.AGGREGATE:
        column_ids, aggregations = transform.column_ids, transform.aggregations
        selected_df = f"{df_name}.select({_list_of_strings(column_ids)})"
        result_df = "pl.DataFrame()"
        for agg_func in aggregations:
            agg_df = f"{selected_df}.{agg_func}()"
            rename_dict = {
                column: f"{column}_{agg_func}" for column in column_ids
            }
            agg_df = f"{agg_df}.rename({rename_dict})"
            result_df = f"{result_df}.hstack({agg_df})"
        return result_df

    elif transform.type == TransformType.GROUP_BY:
        column_ids, aggregation = transform.column_ids, transform.aggregation
        columns = transform.aggregation_column_ids or all_columns
        aggregation_columns = [col for col in columns if col not in column_ids]
        aggs: list[str] = []
        # Use _as_literal to properly escape column names
        for column_id in aggregation_columns:
            col_ref = _as_literal(column_id)
            agg_alias = f"{column_id}_{aggregation}"
            if aggregation == "count":
                aggs.append(
                    f"pl.col({col_ref}).count().alias({_as_literal(agg_alias)})"
                )
            elif aggregation == "sum":
                aggs.append(
                    f"pl.col({col_ref}).sum().alias({_as_literal(agg_alias)})"
                )
            elif aggregation == "mean":
                aggs.append(
                    f"pl.col({col_ref}).mean().alias({_as_literal(agg_alias)})"
                )
            elif aggregation == "median":
                aggs.append(
                    f"pl.col({col_ref}).median().alias({_as_literal(agg_alias)})"
                )
            elif aggregation == "min":
                aggs.append(
                    f"pl.col({col_ref}).min().alias({_as_literal(agg_alias)})"
                )
            elif aggregation == "max":
                aggs.append(
                    f"pl.col({col_ref}).max().alias({_as_literal(agg_alias)})"
                )
        group_cols = [f"pl.col({_as_literal(col)})" for col in column_ids]
        return f"{df_name}.group_by([{', '.join(group_cols)}], maintain_order=True).agg([{', '.join(aggs)}])"  # noqa: E501

    elif transform.type == TransformType.SELECT_COLUMNS:
        column_ids = transform.column_ids
        # Update columns in place for subsequent transforms
        all_columns[:] = [str(col) for col in column_ids]
        return f"{df_name}.select({_list_of_strings(column_ids)})"

    elif transform.type == TransformType.SAMPLE_ROWS:
        n = transform.n
        return f"{df_name}.sample_n(n={n})"

    elif transform.type == TransformType.SHUFFLE_ROWS:
        return f"{df_name}.sample(fraction=1.0, shuffle=True)"

    elif transform.type == TransformType.EXPLODE_COLUMNS:
        column_ids = transform.column_ids
        return f"{df_name}.explode({_list_of_strings(column_ids)})"

    elif transform.type == TransformType.EXPAND_DICT:
        column_id = _as_literal(transform.column_id)
        return f"{df_name}.hstack(pl.DataFrame({df_name}.select({column_id}).to_series().to_list())).drop({column_id})"  # noqa: E501

    elif transform.type == TransformType.UNIQUE:
        column_ids = transform.column_ids
        return f"{df_name}.unique(subset={_list_of_strings(column_ids)}, keep={_as_literal(transform.keep)})"  # noqa: E501

    elif transform.type == TransformType.PIVOT:
        if not transform.index_column_ids:
            index_column_ids = _list_of_strings(
                list(
                    filter(
                        lambda col: col not in transform.column_ids
                        and col not in transform.value_column_ids,
                        all_columns,
                    )
                )
            )
        else:
            index_column_ids = _list_of_strings(transform.index_column_ids)

        if not transform.value_column_ids:
            value_column_ids = _list_of_strings(
                list(
                    filter(
                        lambda col: col not in transform.column_ids
                        and col not in transform.index_column_ids,
                        all_columns,
                    )
                )
            )
        else:
            value_column_ids = _list_of_strings(transform.value_column_ids)

        args = _args_list(
            f"on={_list_of_strings(transform.column_ids)}",
            f"index={index_column_ids}",
            f"values={value_column_ids}",
            f"aggregate_function={_as_literal(transform.aggregation) if transform.aggregation != 'count' else _as_literal('len')}",
        )
        fill_null_code = (
            ".select(pl.all().fill_null(0))"
            if transform.aggregation in ["count", "sum"]
            else ""
        )  # noqa: E501
        pivot_code = f"{df_name}{fill_null_code}.pivot({args}).sort(by={index_column_ids})"  # noqa: E501
        lambda_code = (
            f'lambda col,replacements=replacements: f"{transform.value_column_ids[0]}_{{col.translate(replacements)}}_{transform.aggregation}"'  # noqa: E501
            if len(transform.value_column_ids) == 1
            else f"lambda col, replacements=replacements: f'{{col.translate(replacements)}}_{transform.aggregation}'"
        ) + f" if col not in {index_column_ids} else col"
        rename_code = (
            'replacements = str.maketrans({"{": "", "}": "", \'"\': "", ",": "_"})\n'
            f"{df_name} = {df_name}.rename({lambda_code})"
        )
        return f"{pivot_code}\n{rename_code}"

    assert_never(transform.type)


def python_print_ibis(
    df_name: str, all_columns: list[str], transform: Transform
) -> str:
    def generate_where_clause(df_name: str, where: Condition) -> str:
        column_id, operator, value = (
            where.column_id,
            where.operator,
            where.value,
        )

        if operator == "==" or operator == "equals":
            return f"({df_name}[{_as_literal(column_id)}] == {_as_literal(value)})"
        elif operator == "does_not_equal" or operator == "!=":
            return f"({df_name}[{_as_literal(column_id)}] != {_as_literal(value)}))"  # noqa: E501
        elif operator == "contains":
            return f"({df_name}[{_as_literal(column_id)}].contains({_as_literal(value)}))"  # noqa: E501
        elif operator == "regex":
            return f"({df_name}[{_as_literal(column_id)}].re_search({_as_literal(value)}))"  # noqa: E501
        elif operator == "starts_with":
            return f"({df_name}[{_as_literal(column_id)}].startswith({_as_literal(value)}))"  # noqa: E501
        elif operator == "ends_with":
            return f"({df_name}[{_as_literal(column_id)}].endswith({_as_literal(value)}))"  # noqa: E501
        elif operator == "in" or operator == "not_in":
            result = f"({df_name}[{_as_literal(column_id)}].isin({_list_of_strings(value)}))"  # noqa: E501
            return result if operator == "in" else f"~{result}"
        elif operator in [">", ">=", "<", "<="]:
            return f"({df_name}[{_as_literal(column_id)}] {operator} {_as_literal(value)})"  # noqa: E501
        elif operator == "is_null":
            return f"({df_name}[{_as_literal(column_id)}].isnull())"
        elif operator == "is_not_null":
            return f"({df_name}[{_as_literal(column_id)}].notnull())"
        elif operator == "is_true":
            return f"({df_name}[{_as_literal(column_id)}] == True)"
        elif operator == "is_false":
            return f"({df_name}[{_as_literal(column_id)}] == False)"
        else:
            raise ValueError(f"Unknown operator: {operator}")

    if transform.type == TransformType.COLUMN_CONVERSION:
        column_id, data_type, errors = (
            transform.column_id,
            transform.data_type,
            transform.errors,
        )
        transform_data_type = _as_literal(data_type).replace("_", "")
        if errors == "ignore":
            return (
                f"{df_name}.mutate("
                f"ibis.coalesce("
                f"{df_name}[{_as_literal(column_id)}].cast(ibis.dtype({transform_data_type})), "  # noqa: E501
                f"{df_name}[{_as_literal(column_id)}]"
                f").name({_as_literal(column_id)}))"
            )
        else:
            return (
                f"{df_name}.mutate("
                f"{df_name}[{_as_literal(column_id)}]"
                f".cast(ibis.dtype({transform_data_type}))"
                f".name({_as_literal(column_id)}))"
            )

    elif transform.type == TransformType.RENAME_COLUMN:
        column_id, new_column_id = transform.column_id, transform.new_column_id  # noqa: E501
        return f"{df_name}.rename({{{_as_literal(new_column_id)}: {_as_literal(column_id)}}})"  # noqa: E501

    elif transform.type == TransformType.SORT_COLUMN:
        column_id, ascending = transform.column_id, transform.ascending
        return f"{df_name}.order_by([{df_name}[{_as_literal(column_id)}].{'asc' if ascending else 'desc'}()])"  # noqa: E501

    elif transform.type == TransformType.FILTER_ROWS:
        conditions, operation = transform.where, transform.operation
        expressions = [
            generate_where_clause(df_name, condition)
            for condition in conditions
        ]
        expression = " & ".join(expressions)
        return (
            f"{df_name}.filter({expression})"
            if operation == "keep_rows"
            else f"{df_name}.filter(~({expression}))"
        )

    elif transform.type == TransformType.AGGREGATE:
        agg_dict = []
        for agg_func in transform.aggregations:
            for column_id in transform.column_ids:
                name = f"{column_id}_{agg_func}"
                agg_dict.append(
                    f"'{name}' : {df_name}['{column_id}'].{agg_func}()"
                )
        return f"{df_name}.agg(**{{{','.join(agg_dict)}}})"

    elif transform.type == TransformType.GROUP_BY:
        column_ids, aggregation = transform.column_ids, transform.aggregation
        columns = transform.aggregation_column_ids or all_columns
        aggregation_columns = [col for col in columns if col not in column_ids]
        aggs: list[str] = []
        for column_id in aggregation_columns:
            agg_alias = f"{column_id}_{aggregation}"
            aggs.append(
                f'"{agg_alias}" : {df_name}["{column_id}"].{aggregation}()'
            )
        return f"{df_name}.group_by({_list_of_strings(column_ids)}).aggregate(**{{{','.join(aggs)}}})"  # noqa: E501

    elif transform.type == TransformType.SELECT_COLUMNS:
        column_ids = transform.column_ids
        return f"{df_name}.select({_list_of_strings(column_ids)})"

    elif transform.type == TransformType.SAMPLE_ROWS:
        n, seed = transform.n, transform.seed
        return f"{df_name}.sample({n} / {df_name}.count().execute(), method='row', seed={seed})"  # noqa: E501

    elif transform.type == TransformType.SHUFFLE_ROWS:
        return f"{df_name}.order_by(ibis.random())"

    elif transform.type == TransformType.EXPLODE_COLUMNS:
        column_ids = transform.column_ids
        return f"{df_name}.unnest({_list_of_strings(column_ids)})"

    elif transform.type == TransformType.EXPAND_DICT:
        column_id = transform.column_id
        return f"{df_name}.unpack({_as_literal(column_id)})"

    elif transform.type == TransformType.UNIQUE:
        column_ids = transform.column_ids
        return f"{df_name}.distinct(on={_list_of_strings(column_ids)}, keep={_as_literal(transform.keep)})"  # noqa: E501

    elif transform.type == TransformType.PIVOT:
        if not transform.index_column_ids:
            index_column_ids = _list_of_strings(
                list(
                    filter(
                        lambda col: col not in transform.column_ids
                        and col not in transform.value_column_ids,
                        all_columns,
                    )
                )
            )
        else:
            index_column_ids = _list_of_strings(transform.index_column_ids)

        if not transform.value_column_ids:
            value_column_ids = _list_of_strings(
                list(
                    filter(
                        lambda col: col not in transform.column_ids
                        and col not in transform.index_column_ids,
                        all_columns,
                    )
                )
            )
        else:
            value_column_ids = _list_of_strings(transform.value_column_ids)

        column_ids = transform.column_ids
        agg_func = transform.aggregation

        pivot_code = (
            f"{df_name}.pivot_wider("
            f"names_from={_list_of_strings(column_ids)}, "
            f"id_cols={_list_of_strings(index_column_ids)}, "
            f"values_from={_list_of_strings(value_column_ids)}, "
            f"names_prefix={_as_literal(value_column_ids[0]) if len(value_column_ids) == 1 else _as_literal('')}, "
            f"values_agg={_as_literal(agg_func)})"
        )

        rename_code = f'{df_name} = {df_name}.rename(**{{f"{{col}}_{agg_func}": col for col in {df_name}.columns if col not in {_list_of_strings(index_column_ids)}}})'  # noqa: E501
        return f"{pivot_code}\n{rename_code}"

    assert_never(transform.type)


def _as_literal(value: Any) -> str:
    if isinstance(value, str):
        # escape backslashes
        value = value.replace("\\", "\\\\")
        # convert newlines to spaces
        value = value.replace("\n", " ")
        # convert \r to spaces
        value = value.replace("\r", " ")
        # escape double quotes
        value = value.replace('"', '\\"')
        # remove null bytes
        value = value.replace("\x00", "")
        return f'"{value}"'
    if value == "inf":
        return "float('inf')"
    if value == "-inf":
        return "float('-inf')"
    return f"{value}"


def _list_of_strings(value: Union[list[Any], Any]) -> str:
    if isinstance(value, list):
        return f"[{', '.join(_as_literal(v) for v in value)}]"
    return _as_literal(value)


def _args_list(*args: str) -> str:
    return ", ".join(arg for arg in args if arg)
