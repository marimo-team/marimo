# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    Optional,
)

import pandas as pd

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._server.api.model import parse_raw

from .handlers import apply_transforms
from .transforms import Transformations


@mddoc
class dataframe(UIElement[Dict[str, Any], pd.DataFrame]):
    """
    Run transformations on a DataFrame or series.

    **Example.**

    ```python
    transformed = mo.ui.transforms(data)
    ```

    **Attributes.**

    - `value`: the transformed DataFrame or series

    **Initialization Args.**

    - `data`: the DataFrame or series to transform
    """

    _name: Final[str] = "marimo-dataframe"

    def __init__(
        self,
        df: pd.DataFrame,
        on_change: Optional[Callable[[pd.DataFrame], None]] = None,
    ) -> None:
        # HACK: this is a hack to get the name of the variable that was passed
        dataframe_name = "df"
        try:
            frame = inspect.currentframe()
            if frame is not None and frame.f_back is not None:
                for (
                    var_name,
                    var_value,
                ) in frame.f_back.f_locals.items():
                    if var_value is df:
                        dataframe_name = var_name
                        break
        except Exception:
            pass

        self._data = df
        # described = df.describe(include="all")
        super().__init__(
            component_name=dataframe._name,
            initial_value={
                "transformations": [],
            },
            on_change=on_change,
            label="",
            args={
                "columns": df.dtypes.to_dict(),
                "name": dataframe_name,
                # "info": df.info(),
                # "describe-data": described.to_dict("records"),
                # "describe-row-headers": described.index.to_list(),
                "total": len(df),
            },
        )

    def _convert_value(self, value: Dict[str, Any]) -> pd.DataFrame:
        if value is None:
            return self._data
        transformations = parse_raw(value, Transformations)
        return apply_transforms(self._data, transformations)
