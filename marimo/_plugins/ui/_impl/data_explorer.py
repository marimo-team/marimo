# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Final, Optional

import marimo._output.data.data as mo_data
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.tables.utils import get_table_manager

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


@mddoc
class data_explorer(UIElement[Dict[str, Any], Dict[str, Any]]):
    """Quickly explore a DataFrame with automatically suggested visualizations.

    Examples:
        ```python
        mo.ui.data_explorer(data)
        ```

    Attributes:
        value (Dict[str, Any]): The resulting DataFrame chart spec.

    Args:
        df (IntoDataFrame): The DataFrame to visualize.
    """

    _name: Final[str] = "marimo-data-explorer"

    def __init__(
        self,
        df: IntoDataFrame,
        on_change: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        # Drop the index since empty column names break the data explorer
        df = _drop_index(df)
        self._data = df

        manager = get_table_manager(df)

        super().__init__(
            component_name=data_explorer._name,
            initial_value={},
            on_change=on_change,
            label="",
            args={
                "data": mo_data.csv(manager.to_csv()).url,
            },
        )

    def _convert_value(self, value: Dict[str, Any]) -> Dict[str, Any]:
        return value


def _drop_index(df: IntoDataFrame) -> IntoDataFrame:
    if DependencyManager.pandas.imported():
        import pandas as pd

        if isinstance(df, pd.DataFrame):
            return df.reset_index(drop=True)
    return df
