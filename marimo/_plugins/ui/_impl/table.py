# Copyright 2024 Marimo. All rights reserved.
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
    Union,
)

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._plugins.ui._impl.utils.dataframe import ListOrTuple, TableData
from marimo._runtime.functions import Function

LOGGER = _loggers.marimo_logger()


if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa  # ignore


@dataclass
class DownloadAsArgs:
    format: Literal["csv", "json"]


@mddoc
class table(
    UIElement[List[str], Union[List[JSONType], "pd.DataFrame", "pl.DataFrame"]]
):
    """
    A table component with selectable rows. Get the selected rows with
    `table.value`.

    The table data can be supplied a:

    1. a list of dicts, with one dict for each row, keyed by column names;
    2. a list of values, representing a table with a single column;
    3. a Pandas dataframe; or
    4. a Polars dataframe.

    **Examples.**

    Create a table from a list of dicts, one for each row.

    ```python
    table = mo.ui.table(
      data=[
        {'first_name': 'Michael', 'last_name': 'Scott'},
        {'first_name': 'Dwight', 'last_name': 'Schrute'}
      ],
      label='Users'
    )
    ```

    Create a table from a single column of data:

    table = mo.ui.table(
      data=[
        {'first_name': 'Michael', 'last_name': 'Scott'},
        {'first_name': 'Dwight', 'last_name': 'Schrute'}
      ],
      label='Users'
    )

    Create a table from a dataframe:

    ```python
    # df is a Pandas or Polars dataframe
    table = mo.ui.table(
        data=df,
        # use pagination when your table has many rows
        pagination=True,
        label='Dataframe'
    )
    ```

    In each case, access the table data with `table.value`.

    **Attributes.**

    - `value`: the selected rows, in the same format as the original data,
       or `None` if no selection
    - `data`: the original table data

    **Initialization Args.**

    - `data`: Values can be primitives (`str`,
      `int`, `float`, `bool`, or `None`) or marimo elements: e.g.
      `mo.ui.button(...)`, `mo.md(...)`, `mo.as_html(...)`, etc. Data can be
      passed in many ways:
        - as dataframes: a pandas dataframe, a polars dataframe
        - as rows: a list of dicts, where each dict represents a row in the
          table
        - as columns: a dict keyed by column names, where the value of each
          entry is a list representing a column
        - as a single column: a list of values
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
            ListOrTuple[Union[str, int, float, bool, MIME, None]],
            ListOrTuple[Dict[str, JSONType]],
            Dict[str, ListOrTuple[JSONType]],
            "pd.DataFrame",
            "pl.DataFrame",
            "pa.Table",
        ],
        pagination: Optional[bool] = None,
        selection: Optional[Literal["single", "multi"]] = "multi",
        page_size: int = 10,
        *,
        label: str = "",
        on_change: Optional[
            Callable[
                [
                    Union[
                        List[JSONType],
                        Dict[str, ListOrTuple[JSONType]],
                        "pd.DataFrame",
                        "pl.DataFrame",
                        "pa.Table",
                    ]
                ],
                None,
            ]
        ] = None,
    ) -> None:
        self._data = data
        self._manager = get_table_manager(data)
        self._filtered_manager: Optional[TableManager[Any]] = None

        # pagination defaults to True if there are more than 10 rows
        if pagination is None:
            pagination = len(self._data) > 10

        can_download = (
            DependencyManager.has_pandas() or DependencyManager.has_polars()
        )

        super().__init__(
            component_name=table._name,
            label=label,
            initial_value=[],
            args={
                "data": self._manager.to_data(),
                "pagination": pagination,
                "page-size": page_size,
                "selection": selection,
                "show-download": can_download,
                "row-headers": self._manager.get_row_headers(),
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
    ) -> Union[List[JSONType], "pd.DataFrame", "pl.DataFrame"]:
        indices = [int(v) for v in value]
        self._filtered_manager = self._manager.select_rows(indices)
        self._has_any_selection = len(indices) > 0
        return self._filtered_manager.data  # type: ignore[no-any-return]

    def download_as(self, args: DownloadAsArgs) -> str:
        # download selected rows if there are any, otherwise use all rows
        manager = (
            self._filtered_manager
            if self._filtered_manager and self._has_any_selection
            else self._manager
        )

        ext = args.format
        if ext == "csv":
            return mo_data.csv(manager.to_csv()).url
        elif ext == "json":
            return mo_data.json(manager.to_json()).url
        else:
            raise ValueError("format must be one of 'csv' or 'json'.")
