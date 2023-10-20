# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import sys
from typing import TYPE_CHECKING, Any, Callable, Dict, Final, Optional

if TYPE_CHECKING:
    import pandas as pd

from dataclasses import dataclass

import marimo._output.data.data as mo_data
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import Function
from marimo._utils.parse_dataclass import parse_raw

from .handlers import apply_transforms
from .transforms import Transformations


@dataclass
class GetDataFrameArgs:
    unused: Optional[bool] = None


@mddoc
class dataframe(UIElement[Dict[str, Any], "pd.DataFrame"]):
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

        super().__init__(
            component_name=dataframe._name,
            initial_value={
                "transforms": [],
            },
            on_change=on_change,
            label="",
            args={
                "columns": df.dtypes.to_dict(),
                "dataframe-name": dataframe_name,
                "total": len(df),
            },
            functions=(
                Function(
                    name=self.get_dataframe.__name__,
                    arg_cls=GetDataFrameArgs,
                    function=self.get_dataframe,
                ),
            ),
        )

    def get_dataframe(self, _args: GetDataFrameArgs) -> str:
        return mo_data.csv(self._value).url

    def _convert_value(self, value: Dict[str, Any]) -> pd.DataFrame:
        if value is None:
            return self._data

        try:
            transformations = parse_raw(value, Transformations)
            return apply_transforms(self._data, transformations)
        except Exception as e:
            sys.stderr.write(
                "Error applying dataframe transform: %s\n\n" % str(e)
            )
            return self._data
