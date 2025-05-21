# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional

import narwhals.stable.v1 as nw

from marimo import _loggers
from marimo._data.charts import get_chart_builder
from marimo._data.models import ColumnStats
from marimo._data.sql_summaries import (
    get_column_type,
    get_sql_stats,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import DataColumnPreview
from marimo._plugins.ui._impl.tables.table_manager import (
    FieldType,
    TableManager,
)
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none
from marimo._runtime.requests import PreviewDatasetColumnRequest
from marimo._sql.utils import wrapped_sql

LOGGER = _loggers.marimo_logger()

CHART_MAX_ROWS = 20_000


def get_column_preview_for_dataframe(
    item: object,
    request: PreviewDatasetColumnRequest,
) -> DataColumnPreview | None:
    """
    Get a preview of the column in the dataset.

    This may return a chart and aggregation stats of the column.
    """
    column_name = request.column_name
    table_name = request.table_name
    try:
        table = get_table_manager_or_none(item)
        if table is None:
            return None
        if table.get_num_rows(force=True) == 0:
            return DataColumnPreview(
                table_name=table_name,
                column_name=column_name,
                error="Table is empty",
            )

        try:
            stats = table.get_stats(column_name)
        except BaseException as e:
            # Catch-all: some libraries like Polars have bugs and raise
            # BaseExceptions, which shouldn't crash the kernel
            LOGGER.warning(
                "Failed to get stats for column %s in table %s",
                column_name,
                table_name,
                exc_info=e,
            )
            stats = ColumnStats()

        # We require altair to render the chart
        error = None
        missing_packages = None
        if not DependencyManager.altair.has():
            error = "Altair is required to render charts."
            missing_packages = ["altair"]
        else:
            # Check for special characters that can't be escaped easily
            # (e.g. backslash, quotes)
            for char in ["\\", '"', "'"]:
                if char in str(column_name):
                    error = (
                        f"Column names with `{char}` are not supported "
                        "in charts. Consider renaming the column."
                    )
                    break

        # Get the chart for the column
        chart_max_rows_errors = False
        chart_spec = None
        chart_code = None

        if error is None:
            try:
                chart_spec, chart_code, chart_max_rows_errors = (
                    _get_altair_chart(request, table, stats)
                )
            except Exception as e:
                error = str(e)
                LOGGER.warning(
                    "Failed to get chart for column %s in table %s",
                    column_name,
                    table_name,
                    exc_info=e,
                )

        return DataColumnPreview(
            table_name=table_name,
            column_name=column_name,
            chart_max_rows_errors=chart_max_rows_errors,
            chart_spec=chart_spec,
            chart_code=chart_code,
            stats=stats,
            error=error,
            missing_packages=missing_packages,
        )
    except Exception as e:
        LOGGER.warning(
            "Failed to get preview for column %s in table %s",
            column_name,
            table_name,
            exc_info=e,
        )
        return DataColumnPreview(
            table_name=table_name,
            column_name=column_name,
            error=str(e),
            missing_packages=None,
        )


def get_column_preview_for_duckdb(
    *,
    fully_qualified_table_name: str,
    column_name: str,
) -> Optional[DataColumnPreview]:
    DependencyManager.duckdb.require(why="previewing DuckDB columns")

    column_type = get_column_type(fully_qualified_table_name, column_name)
    stats = get_sql_stats(fully_qualified_table_name, column_name, column_type)

    # Generate Altair chart
    chart_spec = None
    chart_code = None
    chart_max_rows_errors = False
    error = None
    missing_packages = None
    should_limit_to_10_items = True

    if DependencyManager.altair.has():
        from altair import MaxRowsError

        try:
            total_rows: int = wrapped_sql(
                f"SELECT COUNT(*) FROM {fully_qualified_table_name}",
                connection=None,
            ).fetchone()[0]  # type: ignore[index]

            if total_rows <= CHART_MAX_ROWS:
                relation = wrapped_sql(
                    f"SELECT {column_name} FROM {fully_qualified_table_name}",
                    connection=None,
                )
                chart_spec = _get_chart_spec(
                    column_data=relation,
                    column_type=column_type,
                    column_name=column_name,
                    should_limit_to_10_items=should_limit_to_10_items,
                )
            else:
                chart_max_rows_errors = True
        except MaxRowsError:
            chart_spec = None
            chart_max_rows_errors = True
        except Exception as e:
            LOGGER.warning(f"Failed to generate Altair chart: {str(e)}")

    return DataColumnPreview(
        table_name=fully_qualified_table_name,
        column_name=column_name,
        chart_max_rows_errors=chart_max_rows_errors,
        chart_spec=chart_spec,
        chart_code=chart_code,
        stats=stats,
        error=error,
        missing_packages=missing_packages,
    )


def _get_altair_chart(
    request: PreviewDatasetColumnRequest,
    table: TableManager[Any],
    stats: ColumnStats,
) -> tuple[Optional[str], Optional[str], bool]:
    # We require altair to render the chart
    if not DependencyManager.altair.has() or not table.supports_altair():
        return None, None, False

    from altair import MaxRowsError

    (column_type, _external_type) = table.get_field_type(request.column_name)

    if stats.total == 0:
        return None, None, False

    # For categorical columns with more than 10 unique values,
    # we limit the chart to 10 items
    should_limit_to_10_items = False
    if (
        column_type == "string"
        and stats.unique is not None
        and stats.unique > 10
    ):
        should_limit_to_10_items = True

    chart_builder = get_chart_builder(column_type, should_limit_to_10_items)
    code = chart_builder.altair_code(
        request.table_name,
        request.column_name,
    )

    chart_max_rows_errors = False

    try:
        # Filter the data to the column we want
        column_data = table.select_columns([request.column_name]).data
        if isinstance(column_data, nw.LazyFrame):
            column_data = column_data.collect()

        chart_spec = _get_chart_spec(
            column_data=column_data,
            column_type=column_type,
            column_name=request.column_name,
            should_limit_to_10_items=should_limit_to_10_items,
        )
    except MaxRowsError:
        chart_spec = None
        chart_max_rows_errors = True

    return chart_spec, code, chart_max_rows_errors


def _get_chart_spec(
    *,
    column_data: Any,
    column_type: FieldType,
    column_name: str,
    should_limit_to_10_items: bool,
) -> str:
    import altair as alt

    chart_builder = get_chart_builder(column_type, should_limit_to_10_items)

    # If we have vegafusion and vl-convert-python, use it
    if (
        DependencyManager.vegafusion.has()
        and DependencyManager.vl_convert_python.has()
    ):
        with alt.data_transformers.enable("vegafusion"):
            return chart_builder.altair_json(
                column_data,
                column_name,
            )

    # Date types don't serialize well to csv,
    # so we don't transform them
    dont_use_csv = (
        column_type == "date"
        or column_type == "datetime"
        or column_type == "time"
    )
    if dont_use_csv:
        # Default max_rows is 5_000, but we can support more.
        with alt.data_transformers.enable("default", max_rows=CHART_MAX_ROWS):
            return chart_builder.altair_json(
                column_data,
                column_name,
            )
    with alt.data_transformers.enable("marimo_inline_csv"):
        return chart_builder.altair_json(
            column_data,
            column_name,
        )
