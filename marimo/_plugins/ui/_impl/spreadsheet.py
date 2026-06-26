# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Union,
)

import narwhals.stable.v2 as nw
from narwhals.typing import IntoDataFrame

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.tables.utils import get_table_manager

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Callable

RowOrientedData = list[dict[str, Any]]
ColumnOrientedData = dict[str, list[Any]]


def _convert_cell(value: Any, data_type: str) -> Any:
    if value is None or value == "":
        return None
    try:
        if data_type == "integer":
            return int(float(value))
        elif data_type == "number":
            return float(value)
        elif data_type == "boolean":
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        elif data_type == "date":
            if isinstance(value, str):
                return datetime.datetime.fromisoformat(
                    value.replace("Z", "")
                ).date()
            return value
        elif data_type == "datetime":
            if isinstance(value, str):
                return datetime.datetime.fromisoformat(value.replace("Z", ""))
            return value
        elif data_type == "string":
            return str(value)
    except Exception as e:
        LOGGER.warning(
            f"Failed to convert cell value {value} to {data_type}: {e}"
        )
        return value
    return value


def _cast_row_data(
    row_data: list[dict[str, Any]],
    field_types: dict[str, str],
) -> list[dict[str, Any]]:
    casted_rows = []
    for row in row_data:
        casted_row = {}
        for col, val in row.items():
            if col in field_types:
                casted_row[col] = _convert_cell(val, field_types[col])
            else:
                casted_row[col] = val
        casted_rows.append(casted_row)
    return casted_rows


@mddoc
class spreadsheet(
    UIElement[
        Union[RowOrientedData, None],
        Union[RowOrientedData, ColumnOrientedData, IntoDataFrame],
    ]
):
    """A spreadsheet component for Excel-like editing of tabular data.

    This component wraps FortuneSheet to provide bidirectional syncing, allowing
    users to edit cell values in an Excel-like grid and pass mutations back as
    Pandas/Polars DataFrames, list of dicts, or dict of lists.

    Examples:
        Create a spreadsheet from a Pandas dataframe:

        ```python
        import pandas as pd
        import marimo as mo

        df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        sheet = mo.ui.spreadsheet(data=df, label="Edit Spreadsheet")
        ```

    Attributes:
        value (RowOrientedData | ColumnOrientedData | IntoDataFrame): The current state of the edited data.
        data (RowOrientedData | ColumnOrientedData | IntoDataFrame): The original data passed to the spreadsheet.

    Args:
        data (RowOrientedData | ColumnOrientedData | IntoDataFrame): The data to be edited.
        label (str): Markdown label for the element.
        on_change (Optional[Callable]): Optional callback to run when this element's value changes.
    """

    _name: Final[str] = "marimo-spreadsheet"

    def __init__(
        self,
        data: RowOrientedData | ColumnOrientedData | IntoDataFrame,
        *,
        label: str = "",
        on_change: Callable[
            [RowOrientedData | ColumnOrientedData | IntoDataFrame], None
        ]
        | None = None,
    ) -> None:
        table_manager = get_table_manager(data)
        self._data = data

        field_types = table_manager.get_field_types()
        self._field_types_dict: dict[str, str] = {
            col: str(field_type[0]) for col, field_type in field_types
        }

        super().__init__(
            component_name=spreadsheet._name,
            label=label,
            initial_value=None,
            args={
                "data": mo_data.csv(table_manager.to_csv()).url,
                "field-types": field_types or None,
            },
            on_change=on_change,
        )

    @property
    def data(
        self,
    ) -> RowOrientedData | ColumnOrientedData | IntoDataFrame:
        return self._data

    def _convert_value(
        self, value: RowOrientedData | None
    ) -> RowOrientedData | ColumnOrientedData | IntoDataFrame:
        if value is None:
            return self._data

        # Cast cell values back to original data types where possible
        casted_value = _cast_row_data(value, self._field_types_dict)

        original_data = self._data
        if isinstance(original_data, list):
            return casted_value
        elif isinstance(original_data, dict):
            column_names = list(casted_value[0].keys()) if casted_value else []
            return {
                col: [row.get(col) for row in casted_value]
                for col in column_names
            }

        # Otherwise it is a DataFrame
        try:
            df = nw.from_native(original_data, eager_only=True)
            column_names = list(casted_value[0].keys()) if casted_value else []
            column_oriented = {
                col: [row.get(col) for row in casted_value]
                for col in column_names
            }
            new_native_df = nw.from_dict(
                column_oriented, backend=nw.get_native_namespace(df)
            ).to_native()
            return new_native_df  # type: ignore[no-any-return]
        except Exception as e:
            raise ValueError(
                f"Spreadsheet does not support this type of data: {type(original_data)}"
            ) from e

    def __hash__(self) -> int:
        return id(self)
