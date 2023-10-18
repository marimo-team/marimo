# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    Callable,
    Final,
    Optional,
    Sequence,
)

import pandas as pd

from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._server.api.model import parse_raw

from .handlers import apply_transforms
from .transforms import Transformations


@mddoc
class dataframe(UIElement[Transformations, pd.DataFrame]):
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

    _name: Final[str] = "marimo-transform"

    def __init__(
        self,
        df: pd.DataFrame,
        on_change: Optional[Callable[[pd.DataFrame], None]] = None,
    ) -> None:
        self._data = df
        super().__init__(
            component_name=dataframe._name,
            initial_value=None,
            on_change=on_change,
            label="",
            args={
                "columns": df.dtypes.to_dict(),
                # "info": df.info(),
                # "describe": df.describe().to_dict(),
                "total": len(df),
            },
        )

    def _convert_value(self, value: Transformations) -> pd.DataFrame:
        if value is None:
            return self._data
        transformations = parse_raw(value, Transformations)
        return apply_transforms(self._data, transformations)
