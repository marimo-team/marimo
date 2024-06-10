# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List, Optional

from marimo import _loggers
from marimo._data.models import DataTable, DataTableColumn
from marimo._plugins.ui._impl.tables.utils import get_table_manager_or_none

LOGGER = _loggers.marimo_logger()


def get_datasets_from_variables(
    variables: List[tuple[str, object]],
) -> List[DataTable]:
    tables: List[DataTable] = []
    for variable_name, value in variables:
        table = _get_data_table(value, variable_name)
        if table is not None:
            tables.append(table)

    return tables


def _get_data_table(value: object, variable_name: str) -> Optional[DataTable]:
    try:
        table = get_table_manager_or_none(value)
        if table is None:
            return None

        columns = [
            DataTableColumn(name=column_name, type=column_type)
            for column_name, column_type in table.get_field_types().items()
        ]
        return DataTable(
            name=variable_name,
            variable_name=variable_name,
            num_rows=table.get_num_rows(force=False),
            num_columns=table.get_num_columns(),
            source=f"Local ({table.type})",
            columns=columns,
        )
    except Exception as e:
        LOGGER.error(
            "Failed to get table data for variable %s",
            variable_name,
            exc_info=e,
        )
        return None
