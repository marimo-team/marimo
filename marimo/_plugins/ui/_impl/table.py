# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
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

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import Function

LOGGER = _loggers.marimo_logger()

Numeric = Union[int, float]

if TYPE_CHECKING:
    import pandas as pd

TableData = Union[
    Sequence[Union[str, int, float, bool, MIME, None]],
    Sequence[Dict[str, Union[str, int, float, bool, MIME, None]]],
    "pd.DataFrame",
]


@dataclass
class DownloadAsArgs:
    format: Literal["csv", "json"]


@mddoc
class table(UIElement[List[str], Union[List[object], "pd.DataFrame"]]):
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
    - `page_size`: the number of rows to show per page.
      defaults to 10
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
        page_size: int = 10,
        *,
        label: str = "",
        on_change: Optional[
            Callable[[Union[List[object], "pd.DataFrame"]], None]
        ] = None,
    ) -> None:
        self._data = data
        normalized_data = _normalize_data(data)
        self._normalized_data = normalized_data

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
                "page-size": page_size,
                "selection": selection,
                "show-download": DependencyManager.has_pandas(),
                "row-headers": _get_row_headers(data),
            },
            on_change=on_change,
            functions=(
                Function(
                    name=self.download_as.__name__,
                    arg_cls=DownloadAsArgs,
                    function=self.download_as,
                ),
            ),
        )

    @property
    def data(
        self,
    ) -> TableData:
        return self._data

    def _convert_value(
        self, value: list[str]
    ) -> Union[List[object], "pd.DataFrame"]:
        if DependencyManager.has_pandas():
            import pandas as pd

            if isinstance(self._data, pd.DataFrame):
                return self._data.iloc[[int(v) for v in value]]
        return [self._data[int(v)] for v in value]

    def download_as(self, args: DownloadAsArgs) -> str:
        if not DependencyManager.has_pandas():
            raise RuntimeError("Pandas must be installed to download tables.")

        import pandas as pd

        # download selected rows if there are any, otherwise use all rows
        data = self._value if len(self._value) > 0 else self._data

        as_dataframe = (
            data
            if isinstance(data, pd.DataFrame)
            # TODO: fix types to remove type ignore
            else pd.DataFrame(self._normalized_data)  # type:ignore[arg-type]
        )

        ext = args.format
        if ext == "csv":
            return mo_data.csv(as_dataframe).url
        elif ext == "json":
            return mo_data.json(as_dataframe).url
        else:
            raise ValueError("format must be one of 'csv' or 'json'.")


# TODO: more narrow return type
def _normalize_data(data: TableData) -> JSONType:
    # Handle pandas
    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            vf = mo_data.csv(data)
            return vf.url

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


def _get_row_headers(
    data: TableData,
) -> List[tuple[str, List[str | int | float]]]:
    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            return _get_row_headers_for_index(data.index)
    return []


def _get_row_headers_for_index(
    index: pd.Index[Any],
) -> List[tuple[str, List[str | int | float]]]:
    import pandas as pd

    if isinstance(index, pd.RangeIndex):
        return []

    if isinstance(index, pd.MultiIndex):
        # recurse
        headers = []
        for i in range(index.nlevels):
            headers.extend(
                _get_row_headers_for_index(index.get_level_values(i))
            )
        return headers

    # we only care about the index if it has a name
    # or if it is type 'object'
    # otherwise, it may look like meaningless number
    if isinstance(index, pd.Index):
        dtype = str(index.dtype)
        if (
            index.name
            or dtype == "object"
            or dtype == "string"
            or dtype == "category"
        ):
            name = str(index.name) if index.name else ""
            return [(name, index.tolist())]  # type: ignore[list-item]

    return []
