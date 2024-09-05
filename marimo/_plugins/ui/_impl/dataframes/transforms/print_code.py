# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, List, Union

from marimo._plugins.ui._impl.dataframes.transforms.types import (
    Condition,
    Transform,
    TransformType,
)
from marimo._utils.assert_never import assert_never


def python_print_transforms(
    df_name: str,
    all_columns: List[str],
    transforms: List[Transform],
    print_transform: Callable[[str, List[str], Transform], str],
) -> str:
    df_next_name = f"{df_name}_next"
    strs: List[str] = []
    for transform in transforms:
        strs.append(
            f"{df_next_name} = {print_transform(df_next_name,all_columns, transform)}"  # noqa: E501
        )
    return "\n".join([f"{df_next_name} = {df_name}"] + strs)


def python_print_pandas(
    df_name: str, all_columns: List[str], transform: Transform
) -> str:
    del all_columns

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
        elif operator == "in":
            return f"{df_name}[{_as_literal(column_id)}].isin({_list_of_strings(value)})"  # noqa: E501
        elif operator == "!=":
            return (
                f"{df_name}[{_as_literal(column_id)}].ne({_as_literal(value)})"
            )
        elif operator in [">", ">=", "<", "<="]:
            return f"{df_name}[{_as_literal(column_id)}] {operator} {_as_literal(value)}"  # noqa: E501
        elif operator == "is_nan":
            return f"{df_name}[{_as_literal(column_id)}].isna()"
        elif operator == "is_not_nan":
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
        return f'{df_name}.agg({{{", ".join(f"{_as_literal(column_id)}: {_list_of_strings(aggregations)}" for column_id in column_ids)}}})'  # noqa: E501

    elif transform.type == TransformType.GROUP_BY:
        column_ids, aggregation, drop_na = (
            transform.column_ids,
            transform.aggregation,
            transform.drop_na,
        )
        args = _args_list(_list_of_strings(column_ids), f"dropna={drop_na}")
        group_by = f"{df_name}.groupby({args})"
        if aggregation == "count":
            return f"{group_by}.count()"
        elif aggregation == "sum":
            return f"{group_by}.sum()"
        elif aggregation == "mean":
            return f"{group_by}.mean(numeric_only=True)"
        elif aggregation == "median":
            return f"{group_by}.median(numeric_only=True)"
        elif aggregation == "min":
            return f"{group_by}.min()"
        elif aggregation == "max":
            return f"{group_by}.max()"
        assert_never(aggregation)

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

    assert_never(transform.type)


def python_print_polars(
    df_name: str, all_columns: List[str], transform: Transform
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
        elif operator == "in":
            return f"pl.col({_as_literal(column_id)}).is_in({_list_of_strings(value)})"  # noqa: E501
        elif operator in [">", ">=", "<", "<="]:
            return f"pl.col({_as_literal(column_id)}) {operator} {_as_literal(value)}"  # noqa: E501
        elif operator == "is_nan":
            return f"pl.col({_as_literal(column_id)}).is_null()"
        elif operator == "is_not_nan":
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
                f"{column}: f'{column}_{agg_func}'" for column in all_columns
            }
            agg_df = f"{agg_df}.rename({rename_dict})"
            result_df = f"{result_df}.join({agg_df})"
        return result_df

    elif transform.type == TransformType.GROUP_BY:
        column_ids, aggregation = transform.column_ids, transform.aggregation
        aggs: list[str] = []
        for column_id in all_columns:
            if column_id not in column_ids:
                if aggregation == "count":
                    aggs.append(
                        f'pl.col("{column_id}").count().alias("{column_id}_count")'
                    )
                elif aggregation == "sum":
                    aggs.append(
                        f'pl.col("{column_id}").sum().alias("{column_id}_sum")'
                    )
                elif aggregation == "mean":
                    aggs.append(
                        f'pl.col("{column_id}").mean().alias("{column_id}_mean")'
                    )
                elif aggregation == "median":
                    aggs.append(
                        f'pl.col("{column_id}").median().alias("{column_id}_median")'
                    )
                elif aggregation == "min":
                    aggs.append(
                        f'pl.col("{column_id}").min().alias("{column_id}_min")'
                    )
                elif aggregation == "max":
                    aggs.append(
                        f'pl.col("{column_id}").max().alias("{column_id}_max")'
                    )
        return f"{df_name}.group_by({_list_of_strings(column_ids)}, maintain_order=True).agg([{', '.join(aggs)}])"  # noqa: E501

    elif transform.type == TransformType.SELECT_COLUMNS:
        column_ids = transform.column_ids
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
    assert_never(transform.type)


def python_print_ibis(
    df_name: str, all_columns: List[str], transform: Transform
) -> str:
    del df_name, all_columns, transform
    # TODO: this does not fully work yet, but we can output the SQL for Ibis so
    # let's table this for now
    return ""


#     def generate_where_clause(df_name: str, where: Condition) -> str:
#         column_id, operator, value = (
#             where.column_id,
#             where.operator,
#             where.value,
#         )

#         if operator == "==":
#             return (
#                 f"{df_name}[{_as_literal(column_id)}] == {_as_literal(value)}" # noqa: E501
#             )
#         elif operator == "equals":
#             return (
#                 f"{df_name}[{_as_literal(column_id)}].eq({_as_literal(value)})"  # noqa: E501
#             )
#         elif operator == "does_not_equal" or operator == "!=":
#             return (
#                 f"{df_name}[{_as_literal(column_id)}].ne({_as_literal(value)})"  # noqa: E501
#             )
#         elif operator == "contains":
#             return f"{df_name}[{_as_literal(column_id)}].contains({_as_literal(value)})"  # noqa: E501
#         elif operator == "regex":
#             return f"{df_name}[{_as_literal(column_id)}].re_search({_as_literal(value)})"  # noqa: E501
#         elif operator == "starts_with":
#             return f"{df_name}[{_as_literal(column_id)}].startswith({_as_literal(value)})"  # noqa: E501
#         elif operator == "ends_with":
#             return f"{df_name}[{_as_literal(column_id)}].endswith({_as_literal(value)})"  # noqa: E501
#         elif operator == "in":
#             return f"{df_name}[{_as_literal(column_id)}].isin({_list_of_strings(value)})"  # noqa: E501
#         elif operator in [">", ">=", "<", "<="]:
#             return f"{df_name}[{_as_literal(column_id)}] {operator} {_as_literal(value)}"  # noqa: E501
#         elif operator == "is_nan":
#             return f"{df_name}[{_as_literal(column_id)}].isnull()"
#         elif operator == "is_not_nan":
#             return f"{df_name}[{_as_literal(column_id)}].notnull()"
#         elif operator == "is_true":
#             return f"{df_name}[{_as_literal(column_id)}] == True"
#         elif operator == "is_false":
#             return f"{df_name}[{_as_literal(column_id)}] == False"
#         else:
#             raise ValueError(f"Unknown operator: {operator}")

#     if transform.type == TransformType.COLUMN_CONVERSION:
#         column_id, data_type, errors = (
#             transform.column_id,
#             transform.data_type,
#             transform.errors,
#         )
#         if errors == "ignore":
#             return (
#                 f"{df_name}.select('*', "
#                 f"ibis.coalesce("
#                 f"{df_name}[{_as_literal(column_id)}].cast(ibis.dtype({_as_literal(data_type)})), "  # noqa: E501
#                 f"{df_name}[{_as_literal(column_id)}]"
#                 f").name({_as_literal(column_id)}))"
#             )
#         else:
#             return (
#                 f"{df_name}.select('*', "
#                 f"{df_name}[{_as_literal(column_id)}]"
#                 f".cast(ibis.dtype({_as_literal(data_type)}))"
#                 f".name({_as_literal(column_id)}))"
#             )

#     elif transform.type == TransformType.RENAME_COLUMN:
#         column_id, new_column_id = transform.column_id, transform.new_column_id  # noqa: E501
#         return f"{df_name}.rename({{{_as_literal(new_column_id)}: {_as_literal(column_id)}}})"  # noqa: E501

#     elif transform.type == TransformType.SORT_COLUMN:
#         column_id, ascending = transform.column_id, transform.ascending
#         return f"{df_name}.order_by([{df_name}[{_as_literal(column_id)}].{'asc' if ascending else 'desc'}()])"  # noqa: E501

#     elif transform.type == TransformType.FILTER_ROWS:
#         conditions, operation = transform.where, transform.operation
#         expressions = [
#             generate_where_clause(df_name, condition)
#             for condition in conditions
#         ]
#         expression = " & ".join(expressions)
#         return (
#             f"{df_name}.filter({expression})"
#             if operation == "keep_rows"
#             else f"{df_name}.filter(~({expression}))"
#         )

#     elif transform.type == TransformType.AGGREGATE:
#         column_ids, aggregations = transform.column_ids, transform.aggregations  # noqa: E501
#         agg_dict: Dict[str, str] = {}
#         for col, aggs in zip(column_ids, aggregations):
#             for agg in aggs:
#                 agg_dict[f"{col}_{agg}"] = (
#                     f"{df_name}[{_as_literal(col)}].{agg}()"
#                 )
#         return f"{df_name}.agg({{{', '.join(f'{_as_literal(k)}: {v}' for k, v in agg_dict.items())}}})"  # noqa: E501

#     elif transform.type == TransformType.GROUP_BY:
#         column_ids, aggregation = transform.column_ids, transform.aggregation
#         return f"{df_name}.group_by({_list_of_strings(column_ids)}).{aggregation}()"  # noqa: E501

#     elif transform.type == TransformType.SELECT_COLUMNS:
#         column_ids = transform.column_ids
#         return f"{df_name}.select({_list_of_strings(column_ids)})"

#     elif transform.type == TransformType.SAMPLE_ROWS:
#         n, seed = transform.n, transform.seed
#         return f"{df_name}.sample({n} / {df_name}.count().execute(), method='row', seed={seed})"  # noqa: E501

#     elif transform.type == TransformType.SHUFFLE_ROWS:
#         return f"{df_name}.order_by(ibis.random())"

#     elif transform.type == TransformType.EXPLODE_COLUMNS:
#         column_ids = transform.column_ids
#         return f"{df_name}.unnest({_list_of_strings(column_ids)})"

#     elif transform.type == TransformType.EXPAND_DICT:
#         column_id = transform.column_id
#         return f"{df_name}.unpack({_as_literal(column_id)})"

#     assert_never(transform.type)


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


def _list_of_strings(value: Union[List[Any], Any]) -> str:
    if isinstance(value, list):
        return f'[{", ".join(_as_literal(v) for v in value)}]'
    return _as_literal(value)


def _args_list(*args: str) -> str:
    return ", ".join(arg for arg in args if arg)
