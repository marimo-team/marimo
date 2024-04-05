# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Callable,
    Final,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
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
from marimo._plugins.ui._impl.utils.dataframe import TableData, get_row_headers
from marimo._runtime.functions import Function

LOGGER = _loggers.marimo_logger()

T = TypeVar("T")

Numeric = Union[int, float]
ListOrTuple = Union[List[T], Tuple[T, ...]]

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl


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
            ListOrTuple[dict[str, JSONType]],
            dict[str, list[JSONType]],
            "pd.DataFrame",
            "pl.DataFrame",
        ],
        pagination: Optional[bool] = None,
        selection: Optional[Literal["single", "multi"]] = "multi",
        page_size: int = 10,
        *,
        label: str = "",
        on_change: Optional[
            Callable[
                [Union[List[JSONType], "pd.DataFrame", "pl.DataFrame"]], None
            ]
        ] = None,
    ) -> None:
        # TODO: instead of converting to row major, we should just support
        # column major tables -- in the frontend, users would select
        # columns instead of rows ...
        self._data = _as_row_major(data)
        normalized_data = _normalize_data(data)
        self._normalized_data = normalized_data

        # pagination defaults to True if there are more than 10 rows
        if pagination is None:
            if isinstance(self._data, dict):
                pagination = len(next(iter(self._data.values()))) > 10
            else:
                pagination = len(self._data) > 10

        can_download = (
            DependencyManager.has_pandas() or DependencyManager.has_polars()
        )

        super().__init__(
            component_name=table._name,
            label=label,
            initial_value=[],
            args={
                "data": normalized_data,
                "pagination": pagination,
                "page-size": page_size,
                "selection": selection,
                "show-download": can_download,
                "row-headers": get_row_headers(data),
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
        # Handle pandas
        if DependencyManager.has_pandas():
            import pandas as pd

            if isinstance(self._data, pd.DataFrame):
                return self._data.iloc[[int(v) for v in value]]

        # Handle polars
        if DependencyManager.has_polars():
            import polars as pl

            if isinstance(self._data, pl.DataFrame):
                return self._data[[int(v) for v in value]]

        return [self._data[int(v)] for v in value]  # type: ignore[misc]

    def _as_data_frame(
        self, data: TableData
    ) -> Union["pd.DataFrame", "pl.DataFrame"]:
        """
        Convert the given data to the same type as the original data.
        Otherwise, convert to whatever framework we have.
        """
        # Handle pandas
        if DependencyManager.has_pandas():
            import pandas as pd

            # Make result a dataframe of the original type
            if isinstance(self._data, pd.DataFrame) and not isinstance(
                data, pd.DataFrame
            ):
                return pd.DataFrame(data)  # type: ignore[arg-type]

        # Handle polars
        if DependencyManager.has_polars():
            import polars as pl

            # Make result a dataframe of the original type
            if isinstance(self._data, pl.DataFrame) and not isinstance(
                data, pl.DataFrame
            ):
                return pl.DataFrame(data)

        # Convert to whatever framework we have

        if DependencyManager.has_pandas():
            import pandas as pd

            return pd.DataFrame(data)  # type: ignore[arg-type]

        if DependencyManager.has_polars():
            import polars as pl

            return pl.DataFrame(data)

        raise ValueError("Requires pandas or polars to be installed.")

    def download_as(self, args: DownloadAsArgs) -> str:
        # download selected rows if there are any, otherwise use all rows
        data: TableData = self._value if len(self._value) > 0 else self._data

        df = self._as_data_frame(data)
        ext = args.format
        if ext == "csv":
            return mo_data.csv(df).url
        elif ext == "json":
            return mo_data.json(df).url
        else:
            raise ValueError("format must be one of 'csv' or 'json'.")


def _as_row_major(data: TableData | dict[str, list[JSONType]]) -> TableData:
    if not isinstance(data, dict):
        return data

    if DependencyManager.has_pyarrow():
        import pyarrow as pa  # type: ignore

        columns = [pa.array(column) for column in data.values()]
        names = list(data.keys())
        return pa.Table.from_arrays(columns, names)

    # reshape colunn major
    #   { "col1": [1, 2, 3], "col2": [4, 5, 6], ... }
    # into row major
    #   [ {"col1": 1, "col2": 4}, {"col1": 2, "col2": 5 }, ...]
    column_values = data.values()
    column_names = list(data.keys())
    return [
        {key: value for key, value in zip(column_names, row_values)}
        for row_values in zip(*column_values)
    ]


# TODO: more narrow return type
def _normalize_data(data: TableData) -> JSONType:
    # Handle pandas
    if DependencyManager.has_pandas():
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            vf = mo_data.csv(data)
            return vf.url

    # Handle polars
    if DependencyManager.has_polars():
        import polars as pl

        if isinstance(data, pl.DataFrame):
            vf = mo_data.csv(data)
            return vf.url

    # Assert that data is a list
    if not isinstance(data, (list, tuple, dict)):
        raise ValueError("data must be a list, tuple, or dict.")

    # Handle empty data
    if len(data) == 0:
        return []

    if DependencyManager.has_pyarrow():
        import pyarrow as pa

        if isinstance(data, pa.Table):
            vf = mo_data.csv(table)
            return vf.url

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
