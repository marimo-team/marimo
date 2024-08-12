# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional

from marimo import _loggers
from marimo._data.charts import get_chart_builder
from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import DataColumnPreview
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none
from marimo._runtime.requests import PreviewDatasetColumnRequest

LOGGER = _loggers.marimo_logger()


def get_column_preview(
    item: object,
    request: PreviewDatasetColumnRequest,
) -> DataColumnPreview | None:
    """
    Get a preview of the column in the dataset.

    This may return a chart and a aggregation summary of the column.
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

        # Get the summary of the column
        try:
            summary = table.get_summary(column_name)
        except Exception as e:
            LOGGER.warning(
                "Failed to get summary for column %s in table %s",
                column_name,
                table_name,
                exc_info=e,
            )
            summary = ColumnSummary()

        # We require altair to render the chart
        error = None
        if not DependencyManager.altair.has():
            error = (
                "Altair is required to render charts. "
                "Install it with `pip install altair`."
            )
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
                    _get_altair_chart(request, table, summary)
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
            summary=summary,
            error=error,
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
        )


def _get_altair_chart(
    request: PreviewDatasetColumnRequest,
    table: TableManager[Any],
    summary: ColumnSummary,
) -> tuple[Optional[str], Optional[str], bool]:
    # We require altair to render the chart
    if not DependencyManager.altair.has() or not table.supports_altair():
        return None, None, False

    import altair as alt  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
    from altair import (  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
        MaxRowsError,
    )

    (column_type, _external_type) = table.get_field_types()[
        request.column_name
    ]

    # For categorical columns with more than 10 unique values,
    # we limit the chart to 10 items
    should_limit_to_10_items = False
    if (
        column_type == "string"
        and summary.unique is not None
        and summary.unique > 10
    ):
        should_limit_to_10_items = True

    chart_builder = get_chart_builder(column_type, should_limit_to_10_items)
    code = chart_builder.altair_code(
        request.table_name,
        request.column_name,
    )

    chart_max_rows_errors = False
    try:
        column_data = table.select_columns([request.column_name]).data
        # Date types don't serialize well to csv,
        # so we don't transform them
        if column_type == "date":
            # Default max_rows is 5_000, but we can support more.
            with alt.data_transformers.enable("default", max_rows=20_000):
                chart_json = chart_builder.altair_json(
                    column_data,
                    request.column_name,
                )
        else:
            with alt.data_transformers.enable("marimo_inline_csv"):
                chart_json = chart_builder.altair_json(
                    column_data,
                    request.column_name,
                )
    except MaxRowsError:
        chart_json = None
        chart_max_rows_errors = True

    return chart_json, code, chart_max_rows_errors
