# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Final, Optional

if TYPE_CHECKING:
    import pandas as pd


import marimo._output.data.data as mo_data
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement


@mddoc
class data_explorer(UIElement[Dict[str, Any], Dict[str, Any]]):
    """
    Quickly explore a DataFrame.

    **Example.**

    ```python
    mo.ui.data_explorer(data)
    ```

    **Attributes.**

    - `value`: the resulting DataFrame chart spec

    **Initialization Args.**

    - `df`: the DataFrame or series to transform
    """

    _name: Final[str] = "marimo-data-explorer"

    def __init__(
        self,
        df: pd.DataFrame,
        on_change: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._data = df

        super().__init__(
            component_name=data_explorer._name,
            initial_value={},
            on_change=on_change,
            label="",
            args={
                "data": mo_data.csv(df).url,
            },
        )

    def _convert_value(self, value: Dict[str, Any]) -> Dict[str, Any]:
        return value
