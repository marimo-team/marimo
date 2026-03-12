# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.get_datasets import _db_type_to_data_type
from marimo._data.models import ColumnStats, DataType
from marimo._sql.sql_quoting import parse_fully_qualified_table_name
from marimo._sql.utils import execute_duckdb_sql, wrapped_sql


def get_sql_stats(
    table_name: str, column_name: str, column_type: DataType
) -> ColumnStats:
    """
    Get stats of a column in a SQL table.
    """

    # Prepare the stats query based on the column type
    if column_type in ("integer", "number"):
        stats_query = f"""
        SELECT
            COUNT(*) as count,
            COUNT(DISTINCT "{column_name}") as unique,
            SUM(CASE WHEN "{column_name}" IS NULL THEN 1 ELSE 0 END) as null_count,
            MIN("{column_name}") as min,
            MAX("{column_name}") as max,
            AVG("{column_name}") as mean,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "{column_name}") as median,
            STDDEV("{column_name}") as std,
            PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY "{column_name}") as p5,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY "{column_name}") as p25,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY "{column_name}") as p75,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY "{column_name}") as p95
        FROM {table_name}
        """  # noqa: E501
    elif (
        column_type == "date"
        or column_type == "datetime"
        or column_type == "time"
    ):
        stats_query = f"""
        SELECT
            COUNT(*) as count,
            COUNT(DISTINCT "{column_name}") as unique,
            SUM(CASE WHEN "{column_name}" IS NULL THEN 1 ELSE 0 END) as null_count,
            MIN("{column_name}") as min,
            MAX("{column_name}") as max
        FROM {table_name}
        """  # noqa: E501
    elif column_type == "boolean":
        stats_query = f"""
        SELECT
            COUNT(*) as count,
            COUNT(DISTINCT "{column_name}") as unique,
            SUM(CASE WHEN "{column_name}" IS NULL THEN 1 ELSE 0 END) as null_count,
            SUM(CASE WHEN "{column_name}" = TRUE THEN 1 ELSE 0 END) as true_count,
            SUM(CASE WHEN "{column_name}" = FALSE THEN 1 ELSE 0 END) as false_count
        FROM {table_name}
        """  # noqa: E501
    else:
        stats_query = f"""
        SELECT
            COUNT(*) as count,
            COUNT(DISTINCT "{column_name}") as unique,
            SUM(CASE WHEN "{column_name}" IS NULL THEN 1 ELSE 0 END) as null_count
        FROM {table_name}
        """  # noqa: E501

    stats_result: tuple[int, ...] | None = wrapped_sql(
        stats_query, connection=None
    ).fetchone()
    if stats_result is None:
        raise ValueError(
            f"Column {column_name} not found in table {table_name}"
        )

    if column_type in ("integer", "number"):
        (
            count,
            unique,
            null_count,
            min_val,
            max_val,
            mean,
            median,
            std,
            p5,
            p25,
            p75,
            p95,
        ) = stats_result
        return ColumnStats(
            total=count,
            unique=unique,
            nulls=null_count,
            min=min_val,
            max=max_val,
            mean=mean,
            median=median,
            std=std,
            p5=p5,
            p25=p25,
            p75=p75,
            p95=p95,
        )
    elif (
        column_type == "date"
        or column_type == "datetime"
        or column_type == "time"
    ):
        count, unique, null_count, min_val, max_val = stats_result
        return ColumnStats(
            total=count,
            unique=unique,
            nulls=null_count,
            min=min_val,
            max=max_val,
        )
    elif column_type == "boolean":
        count, unique, null_count, true_count, false_count = stats_result
        return ColumnStats(
            total=count,
            unique=unique,
            nulls=null_count,
            true=true_count,
            false=false_count,
        )
    else:
        count, unique, null_count = stats_result
        return ColumnStats(total=count, unique=unique, nulls=null_count)


def get_column_type(
    fully_qualified_table_name: str, column_name: str
) -> DataType:
    """
    Get the type of a column in a SQL table.
    """

    # First, get the column info and data type
    if "." in fully_qualified_table_name:
        # Fully qualified table name
        db_name, schema_name, table_name = parse_fully_qualified_table_name(
            fully_qualified_table_name
        )
        column_info_query = """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = $1
        AND table_schema = $2
        AND table_catalog = $3
        AND column_name = $4
        """
        column_info_result: tuple[str] | None = execute_duckdb_sql(
            column_info_query,
            [table_name, schema_name, db_name, column_name],
        ).fetchone()
    else:
        # Simple table name
        table_name = fully_qualified_table_name
        column_info_query = """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = $1
        AND column_name = $2
        """
        column_info_result = execute_duckdb_sql(
            column_info_query,
            [table_name, column_name],
        ).fetchone()

    if column_info_result is None:
        raise ValueError(
            f"Column {column_name} not found in table {table_name}"
        )

    db_column_type = column_info_result[0].lower()
    return _db_type_to_data_type(db_column_type)


def get_histogram_data(
    table_name: str, column_name: str
) -> list[tuple[str, int]]:
    """
    Get the histogram data for a column in a SQL table.
    """
    del table_name, column_name
    # TODO: Implement this

    return []
