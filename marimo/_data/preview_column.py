from __future__ import annotations

from typing import Any, Optional

from marimo._data.charts import get_chart_builder
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import DataColumnPreview
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none
from marimo._runtime.requests import PreviewDatasetColumnRequest


def get_column_preview(
    item: object,
    request: PreviewDatasetColumnRequest,
) -> DataColumnPreview | None:
    """
    Get a preview of the column in the dataset.

    This may return a chart and a aggregation summary of the column.
    """
    try:
        table = get_table_manager_or_none(item)
        if table is None:
            return None

        summary = table.get_summary(request.column_name)
        chart_spec, chart_code = _get_altair_chart(request, table)
        return DataColumnPreview(
            table_name=request.table_name,
            column_name=request.column_name,
            chart_spec=chart_spec,
            chart_code=chart_code,
            summary=summary,
        )
    except Exception as e:
        return DataColumnPreview(
            table_name=request.table_name,
            column_name=request.column_name,
            error=str(e),
        )


def _get_altair_chart(
    request: PreviewDatasetColumnRequest,
    table: TableManager[Any],
) -> tuple[Optional[str], Optional[str]]:
    # We require altair to render the chart
    if not DependencyManager.has_altair() or not table.supports_altair():
        return None, None

    column_type = table.get_field_types()[request.column_name]
    chart_builder = get_chart_builder(column_type)

    return chart_builder.altair_json(
        table.data,
        request.column_name,
    ), chart_builder.altair_code(
        request.table_name,
        request.column_name,
    )
