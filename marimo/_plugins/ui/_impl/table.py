# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Final,
    List,
    Literal,
    Optional,
    Sequence,
    Union,
    cast,
)

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]

if TYPE_CHECKING:
    import pandas as pd

TableData = Union[
    Sequence[Union[str, int, float, bool, MIME, None]],
    Sequence[Dict[str, Union[str, int, float, bool, MIME, None]]],
    "pd.DataFrame",
]


@mddoc
class table(UIElement[List[str], List[object]]):
    """
    A table component.

    **Example.**

    ```python
    table = mo.ui.table(
      data=[
        {'first_name': 'Michael', 'last_name': 'Scott'},
        {'first_name': 'Dwight', 'last_name': 'Schrute'}
      ],
      label='Users'
    )
    ```

    ```python
    # df is a Pandas dataframe
    table = mo.ui.table(
        data=df,
        # use pagination when your table has many rows
        pagination=True,
        label='Dataset'
    )
    ```

    **Attributes.**

    - `value`: the selected values, or `None` if no selection.
    - `data`: the table data

    **Initialization Args.**

    - `data`: A pandas dataframe, or a list of values representing a column,
        or a list of dicts where each dict represents a row in the table
        (mapping column names to values). values can be
        primitives (`str`, `int`, `float`, `bool`, or `None`)
        or Marimo elements: e.g.
        `mo.ui.button(...)`, `mo.md(...)`, `mo.as_html(...)`, etc.
    - `pagination`: whether to paginate; if `False`, all rows will be shown
      defaults to `True` when above 10 rows, `False` otherwise
    - `selection`: 'single' or 'multi' to enable row selection, or `None` to
        disable
    - `label`: text label for the element
    - `on_change`: optional callback to run when this element's value changes
    """

    _name: Final[str] = "marimo-table"

    def __init__(
        self,
        data: Union[
            Sequence[Union[str, int, float, bool, MIME, None]],
            Sequence[Dict[str, Union[str, int, float, bool, MIME, None]]],
            "pd.DataFrame",
        ],
        pagination: Optional[bool] = None,
        selection: Optional[Literal["single", "multi"]] = "multi",
        *,
        label: str = "",
        on_change: Optional[Callable[[List[object]], None]] = None,
    ) -> None:
        self._data = data
        normalized_data = _normalize_data(data)

        # pagination defaults to True if there are more than 10 rows
        if pagination is None:
            pagination = len(self._data) > 10

        super().__init__(
            component_name=table._name,
            label=label,
            initial_value=[],
            args={
                "data": normalized_data,
                "pagination": pagination,
                "selection": selection,
            },
            on_change=on_change,
        )

    @property
    def data(
        self,
    ) -> TableData:
        return self._data

    def _convert_value(self, value: list[str]) -> list[object]:
        if DependencyManager.has_pandas():
            import pandas as pd

            if isinstance(self._data, pd.DataFrame):
                return self._data.iloc[[int(v) for v in value]]
        return [self._data[int(v)] for v in value]


def _normalize_data(data: TableData) -> JSONType:
    # Handle pandas
    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            return data.to_dict("records")  # type: ignore

    # Assert that data is a list
    if not isinstance(data, (list, tuple)):
        raise ValueError("data must be a list or tuple.")

    # Handle single-column data
    if not isinstance(data[0], dict) and isinstance(
        data[0], (str, int, float, bool, type(None))
    ):
        # we're going to assume that data has the right shape, after
        # having checked just the first entry
        casted = cast(List[Union[str, int, float, bool, MIME, None]], data)
        return [{"value": datum} for datum in casted]
    elif not isinstance(data[0], dict):
        raise ValueError(
            "data must be a sequence of JSON-serializable types, or a "
            "sequence of dicts."
        )

    # Sequence of dicts
    return data
