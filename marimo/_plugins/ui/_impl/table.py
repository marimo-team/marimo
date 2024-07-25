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
from marimo._data.models import NonNestedLiteral
from marimo._output.mime import MIME
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.dataframes.transforms.apply import (
    get_handler_for_dataframe,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    Condition,
    FilterRowsTransform,
    TransformType,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    TableManager,
)
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._plugins.ui._impl.utils.dataframe import ListOrTuple, TableData
from marimo._runtime.functions import EmptyArgs, Function

LOGGER = _loggers.marimo_logger()


if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa  # ignore


@dataclass
class DownloadAsArgs:
    format: Literal["csv", "json"]


@dataclass
class ColumnSummary:
    column: str
    nulls: Optional[int]
    # int, float, datetime
    min: Optional[NonNestedLiteral]
    max: Optional[NonNestedLiteral]
    # str
    unique: Optional[int]
    # bool
    true: Optional[NonNestedLiteral] = None
    false: Optional[NonNestedLiteral] = None


@dataclass
class ColumnSummaries:
    summaries: List[ColumnSummary]


@dataclass
class SearchTableArgs:
    query: Optional[str] = None
    sort: Optional[SortArgs] = None
    filters: Optional[List[Condition]] = None


@dataclass
class SortArgs:
    by: ColumnName
    descending: bool


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
            {"first_name": "Michael", "last_name": "Scott"},
            {"first_name": "Dwight", "last_name": "Schrute"},
        ],
        label="Users",
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
        label="Dataframe",
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
    - `selection`: 'single' or 'multi' to enable row selection, or `None` to
        disable
    - `page_size`: the number of rows to show per page.
      defaults to 10
    - `show_column_summaries`: whether to show column summaries
    - `format_mapping`: a mapping from column names to formatting strings or functions
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
        show_column_summaries: bool = True,
        format_mapping: Optional[Dict[str, str | Callable]] = None,
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
        self._format_mapping = format_mapping or {}
        # Holds the original data
        self._manager = get_table_manager(data)
        # Holds the data after filtering (sort, search, limit etc.)
        self._filtered_manager = self._manager
        # Holds the data after selection and filtering
        self._selected_manager: Optional[TableManager[Any]] = None

        if (
            total_cols := self._manager.get_num_columns()
        ) > TableManager.DEFAULT_COL_LIMIT:
            raise ValueError(
                f"Your table has {total_cols} columns, "
                "which is greater than the maximum allowed columns of "
                f"{TableManager.DEFAULT_COL_LIMIT} for mo.ui.table(). "
                "If this is a problem, please open a GitHub issue: "
                "https://github.com/marimo-team/marimo/issues"
            )

        totalRows = self._manager.get_num_rows(force=True) or 0
        hasMore = totalRows > TableManager.DEFAULT_ROW_LIMIT
        if hasMore:
            self._filtered_manager = self._filtered_manager.limit(
                TableManager.DEFAULT_ROW_LIMIT
            )
        # get the formatted data
        self._formatted_data = self._apply_formatting(
            self._filtered_manager.data
        )
        # get the formatted manager
        self._formatted_manager = get_table_manager(self._formatted_data)

        # pagination defaults to True if there are more than 10 rows
        if pagination is None:
            pagination = totalRows > 10

        # field_types = self._manager.get_field_types()
        field_types = self._formatted_manager.get_field_types()

        super().__init__(
            component_name=table._name,
            label=label,
            initial_value=[],
            args={
                "data": self._formatted_manager.to_data(),
                "has-more": hasMore,
                "total-rows": totalRows,
                "pagination": pagination,
                "page-size": page_size,
                "field-types": field_types if field_types else None,
                "selection": (
                    selection if self._manager.supports_selection() else None
                ),
                "show-filters": self._manager.supports_filters(),
                "show-download": self._manager.supports_download(),
                "show-column-summaries": show_column_summaries,
                "row-headers": self._manager.get_row_headers(),
            },
            on_change=on_change,
            functions=(
                Function(
                    name=self.download_as.__name__,
                    arg_cls=DownloadAsArgs,
                    function=self.download_as,
                ),
                Function(
                    name=self.get_column_summaries.__name__,
                    arg_cls=EmptyArgs,
                    function=self.get_column_summaries,
                ),
                Function(
                    name=self.search.__name__,
                    arg_cls=SearchTableArgs,
                    function=self.search,
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
        self._selected_manager = self._filtered_manager.select_rows(indices)
        self._has_any_selection = len(indices) > 0
        # apply formatting to the selected data
        return self._apply_formatting(
            self._selected_manager.data  # type: ignore[no-any-return]
        )

    def download_as(self, args: DownloadAsArgs) -> str:
        # download selected rows if there are any, otherwise use all rows
        # not apply formatting here, raw data is downloaded
        manager = (
            self._selected_manager
            if self._selected_manager and self._has_any_selection
            else self._filtered_manager
        )

        ext = args.format
        if ext == "csv":
            return mo_data.csv(manager.to_csv()).url
        elif ext == "json":
            return mo_data.json(manager.to_json()).url
        else:
            raise ValueError("format must be one of 'csv' or 'json'.")

    def get_column_summaries(self, args: EmptyArgs) -> ColumnSummaries:
        del args
        summaries: List[ColumnSummary] = []
        for column in self._filtered_manager.get_column_names():
            summary = self._filtered_manager.get_summary(column)
            summaries.append(
                ColumnSummary(
                    column=column,
                    nulls=summary.nulls,
                    min=summary.min,
                    max=summary.max,
                    unique=summary.unique,
                    true=summary.true,
                    false=summary.false,
                )
            )

        return ColumnSummaries(summaries)

    def search(self, args: SearchTableArgs) -> Union[JSONType, str]:
        # Start with the original manager, then filter
        result = self._manager

        # If no query or sort, return nothing
        # The frontend will just show the original data
        if not args.query and not args.sort and not args.filters:
            self._filtered_manager = self._manager
            return []

        if args.filters:
            handler = get_handler_for_dataframe(self._manager.data)
            data = handler.handle_filter_rows(
                result.data,
                FilterRowsTransform(
                    type=TransformType.FILTER_ROWS,
                    where=args.filters,
                    operation="keep_rows",
                ),
            )
            result = get_table_manager(data)
        if args.query:
            result = result.search(args.query)
        if args.sort:
            result = result.sort_values(args.sort.by, args.sort.descending)
        # Save the manager to be used for selection
        self._filtered_manager = result
        return result.limit(TableManager.DEFAULT_ROW_LIMIT).to_data()

    def _apply_formatting(self, data: TableData) -> TableData:
        # Apply formatting to the given data based on the format mapping.
        import pandas as pd
        import polars as pl
        import pyarrow as pa

        if not self._format_mapping:
            return data

        if isinstance(data, list | tuple):
            if all(isinstance(item, dict) for item in data):
                return [self._format_row(row) for row in data]
            return [self._format_value("", item) for item in data]

        if isinstance(data, dict):
            return {
                col: self._format_column(col, values)
                for col, values in data.items()
            }

        if isinstance(data, pd.DataFrame):
            data_copy = data.copy()
            for col in data_copy.columns:
                if col in self._format_mapping:
                    data_copy[col] = data_copy[col].apply(
                        lambda x, col=col: self._format_value(col, x)
                    )
            return data_copy

        if isinstance(data, pl.DataFrame):
            data_copy = data.clone()
            for col in data_copy.columns:
                if col in self._format_mapping:
                    formatted_col = pl.Series(
                        col,
                        [self._format_value(col, x) for x in data_copy[col]],
                    )
                    data_copy = data_copy.with_columns(formatted_col)
            return data_copy

        if isinstance(data, pa.Table):
            data_copy = data
            for col in data_copy.column_names:
                if col in self._format_mapping:
                    # Get the column index
                    col_index = data_copy.schema.get_field_index(col)
                    # Apply the transformation to each element in the column
                    transformed_column = pa.array(
                        [
                            self._format_value(col, value.as_py())
                            for value in data_copy[col_index]
                        ],
                        type=data_copy.schema.field(col_index).type,
                    )
                    # Replace the column in the copy of the table
                    data_copy = data_copy.set_column(
                        col_index, col, transformed_column
                    )
            return data_copy

        return data

    def _format_row(self, row: Dict[str, JSONType]) -> Dict[str, JSONType]:
        # Apply formatting to each value in a row dictionary
        return {
            col: self._format_value(col, value) for col, value in row.items()
        }

    def _format_column(
        self, col: str, values: List[JSONType]
    ) -> List[JSONType]:
        # Apply formatting to each value in a column list
        return [self._format_value(col, value) for value in values]

    def _format_value(self, col: str, value: JSONType) -> JSONType:
        # Apply formatting logic based on column and value
        if col in self._format_mapping:
            formatter = self._format_mapping[col]
            if isinstance(formatter, str):
                return formatter.format(value)
            if callable(formatter):
                return formatter(value)
        return value
