# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Final, Optional

import marimo._output.data.data as mo_data
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.tables.utils import get_table_manager

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


@mddoc
class data_explorer(UIElement[dict[str, Any], dict[str, Any]]):
    """Quickly explore a DataFrame with automatically suggested visualizations.

    Examples:
        ```python
        mo.ui.data_explorer(data)
        mo.ui.data_explorer(data, x="col_A", y="col_B", color="col_C")
        ```

    Attributes:
        value (Dict[str, Any]): The chart specification, which may include
            initial selections if provided via keyword arguments.

    Args:
        df (IntoDataFrame): The DataFrame to visualize.
        on_change (Callable[[dict[str, Any]], None], optional): Optional callback
            to run when this element's value changes.
        x (Optional[str]): Initial column for the x-axis. Defaults to None.
        y (Optional[str]): Initial column for the y-axis. Defaults to None.
        row (Optional[str]): Initial column for the row dimension. Defaults to None.
        column (Optional[str]): Initial column for the column dimension. Defaults to None.
        color (Optional[str]): Initial column for the color encoding. Defaults to None.
        size (Optional[str]): Initial column for the size encoding. Defaults to None.
        shape (Optional[str]): Initial column for the shape encoding. Defaults to None.
    """

    _name: Final[str] = "marimo-data-explorer"

    def __init__(
        self,
        df: IntoDataFrame,
        on_change: Optional[Callable[[dict[str, Any]], None]] = None,
        x: Optional[str] = None,
        y: Optional[str] = None,
        row: Optional[str] = None,
        column: Optional[str] = None,
        color: Optional[str] = None,
        size: Optional[str] = None,
        shape: Optional[str] = None,
    ) -> None:
        # Drop the index since empty column names break the data explorer
        df_no_idx = _drop_index(df)
        self._data = df_no_idx

        manager = get_table_manager(df_no_idx)

        encoding_fields = dict(
            x=x,
            y=y,
            row=row,
            column=column,
            color=color,
            size=size,
            shape=shape,
        )

        # Create ChartSpec structure for frontend
        initial_value: dict[str, Any] = {
            "mark": "?",
            "encoding": {
                channel: {"field": field}
                for channel, field in encoding_fields.items()
                if field is not None
            },
            "config": {},
        }

        super().__init__(
            component_name=data_explorer._name,
            initial_value=initial_value,
            on_change=on_change,
            label="",
            args={"data": mo_data.csv(manager.to_csv()).url},
        )

    def _convert_value(self, value: dict[str, Any]) -> dict[str, Any]:
        """Convert ChartSpec format to simple field mapping for public API."""
        if isinstance(value, dict) and "encoding" in value:
            return {
                channel: field_def["field"]
                for channel, field_def in value["encoding"].items()
                if isinstance(field_def, dict) and "field" in field_def
            }
        return value


def _drop_index(df: IntoDataFrame) -> IntoDataFrame:
    if DependencyManager.pandas.imported():
        import pandas as pd

        if isinstance(df, pd.DataFrame):
            return df.reset_index(drop=True)
    return df
