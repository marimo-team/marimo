# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    List,
    Literal,
    Optional,
    Sequence,
    Union,
)

from narwhals.typing import IntoDataFrame

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
from marimo._plugins.validators import (
    validate_no_integer_columns,
    validate_page_size,
)
from marimo._runtime.functions import EmptyArgs, Function
from marimo._utils.narwhals_utils import unwrap_narwhals_dataframe

LOGGER = _loggers.marimo_logger()


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
    data: Union[JSONType, str]
    summaries: List[ColumnSummary]
    # Disabled because of too many columns/rows
    # This will show a banner in the frontend
    is_disabled: Optional[bool] = None


@dataclass(frozen=True)
class SearchTableArgs:
    page_size: int
    page_number: int
    query: Optional[str] = None
    sort: Optional[SortArgs] = None
    filters: Optional[List[Condition]] = None
    limit: Optional[int] = None


@dataclass(frozen=True)
class SearchTableResponse:
    data: Union[JSONType, str]
    total_rows: int


@dataclass(frozen=True)
class SortArgs:
    by: ColumnName
    descending: bool


@mddoc
class table(
    UIElement[
        Union[List[str], List[int]], Union[List[JSONType], IntoDataFrame]
    ]
):
    """A table component with selectable rows.

    Get the selected rows with `table.value`. The table data can be supplied as:

    1. a list of dicts, with one dict for each row, keyed by column names;
    2. a list of values, representing a table with a single column;
    3. a Pandas dataframe; or
    4. a Polars dataframe; or
    5. an Ibis dataframe; or
    6. a PyArrow table.

    Examples:
        Create a table from a list of dicts, one for each row:

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

        ```python
        table = mo.ui.table(
            data=[
                {"first_name": "Michael", "last_name": "Scott"},
                {"first_name": "Dwight", "last_name": "Schrute"},
            ],
            label="Users",
        )
        ```

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

        Create a table with format mapping:

        ```python
        # format_mapping is a dict keyed by column names,
        # with values as formatting functions or strings
        def format_name(name):
            return name.upper()


        table = mo.ui.table(
            data=[
                {"first_name": "Michael", "last_name": "Scott", "age": 45},
                {"first_name": "Dwight", "last_name": "Schrute", "age": 40},
            ],
            format_mapping={
                "first_name": format_name,  # Use callable to format first names
                "age": "{:.1f}".format,  # Use string format for age
            },
            label="Format Mapping",
        )
        ```

        In each case, access the table data with `table.value`.

    Attributes:
        value (Union[List[JSONType], IntoDataFrame]): The selected rows, in the same format
            as the original data, or None if no selection.
        data (Union[List[JSONType], IntoDataFrame]): The original table data.

    Args:
        data (Union[List[Union[str, int, float, bool, MIME, None]], List[Dict[str, JSONType]], Dict[str, List[JSONType]], IntoDataFrame]):
            Values can be primitives (`str`, `int`, `float`, `bool`, or `None`) or marimo elements:
            e.g. `mo.ui.button(...)`, `mo.md(...)`, `mo.as_html(...)`, etc. Data can be passed in many ways:
            - as dataframes: a pandas dataframe, a polars dataframe
            - as rows: a list of dicts, where each dict represents a row in the table
            - as columns: a dict keyed by column names, where the value of each entry is a list representing a column
            - as a single column: a list of values
        pagination (bool, optional): Whether to paginate; if False, all rows will be shown.
            Defaults to True when above 10 rows, False otherwise.
        selection (Literal["single", "multi"], optional): 'single' or 'multi' to enable row selection,
            or None to disable. Defaults to "multi".
        initial_selection (List[int], optional): Indices of the rows you want selected by default.
        page_size (int, optional): The number of rows to show per page. Defaults to 10.
        show_column_summaries (Union[bool, Literal["stats", "chart"]], optional): Whether to show column summaries.
            Defaults to True when the table has less than 40 columns, False otherwise.
            If "stats", only show stats. If "chart", only show charts.
        show_download (bool, optional): Whether to show the download button.
            Defaults to True for dataframes, False otherwise.
        format_mapping (Dict[str, Union[str, Callable[..., Any]]], optional): A mapping from
            column names to formatting strings or functions.
        freeze_columns_left (Sequence[str], optional): List of column names to freeze on the left.
        freeze_columns_right (Sequence[str], optional): List of column names to freeze on the right.
        text_justify_columns (Dict[str, Literal["left", "center", "right"]], optional):
            Dictionary of column names to text justification options: left, center, right.
        wrapped_columns (List[str], optional): List of column names to wrap.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[Union[List[JSONType], Dict[str, List[JSONType]], IntoDataFrame]], None], optional):
            Optional callback to run when this element's value changes.
        max_columns (int, optional): Maximum number of columns to display. Defaults to 50.
            Set to None to show all columns.
    """

    _name: Final[str] = "marimo-table"

    def __init__(
        self,
        data: Union[
            ListOrTuple[Union[str, int, float, bool, MIME, None]],
            ListOrTuple[Dict[str, JSONType]],
            Dict[str, ListOrTuple[JSONType]],
            "IntoDataFrame",
        ],
        pagination: Optional[bool] = None,
        selection: Optional[Literal["single", "multi"]] = "multi",
        initial_selection: Optional[List[int]] = None,
        page_size: int = 10,
        show_column_summaries: Optional[
            Union[bool, Literal["stats", "chart"]]
        ] = None,
        format_mapping: Optional[
            Dict[str, Union[str, Callable[..., Any]]]
        ] = None,
        freeze_columns_left: Optional[Sequence[str]] = None,
        freeze_columns_right: Optional[Sequence[str]] = None,
        text_justify_columns: Optional[
            Dict[str, Literal["left", "center", "right"]]
        ] = None,
        wrapped_columns: Optional[List[str]] = None,
        show_download: bool = True,
        max_columns: Optional[int] = 50,
        *,
        label: str = "",
        on_change: Optional[
            Callable[
                [
                    Union[
                        List[JSONType],
                        Dict[str, ListOrTuple[JSONType]],
                        "IntoDataFrame",
                    ]
                ],
                None,
            ]
        ] = None,
        # The _internal_* arguments are for overriding and unit tests
        # table should take the value unconditionally
        _internal_column_charts_row_limit: Optional[int] = None,
        _internal_summary_row_limit: Optional[int] = None,
        _internal_total_rows: Optional[Union[int, Literal["too_many"]]] = None,
    ) -> None:
        validate_no_integer_columns(data)
        validate_page_size(page_size)

        # The original data passed in
        self._data = data
        # Holds the original data
        self._manager = get_table_manager(data)
        self._max_columns = max_columns

        # Set the default value for show_column_summaries,
        # if it is not set by the user
        if show_column_summaries is None:
            show_column_summaries = (
                self._manager.get_num_columns()
                <= TableManager.DEFAULT_SUMMARY_CHARTS_COLUMN_LIMIT
            )
        self._show_column_summaries = show_column_summaries

        if _internal_column_charts_row_limit is not None:
            self._column_charts_row_limit = _internal_column_charts_row_limit
        else:
            self._column_charts_row_limit = (
                TableManager.DEFAULT_SUMMARY_CHARTS_ROW_LIMIT
            )

        if _internal_summary_row_limit is not None:
            self._column_summary_row_limit = _internal_summary_row_limit
        else:
            self._column_summary_row_limit = (
                TableManager.DEFAULT_SUMMARY_STATS_ROW_LIMIT
            )

        # Holds the data after user searching from original data
        # (searching operations include query, sort, filter, etc.)
        self._searched_manager = self._manager
        # Holds the data after user selecting from the component
        self._selected_manager: Optional[TableManager[Any]] = None

        initial_value = []
        if initial_selection and self._manager.supports_selection():
            if selection == "single" and len(initial_selection) > 1:
                raise ValueError(
                    "For single selection mode, initial_selection can only contain one row index"
                )
            try:
                self._selected_manager = self._searched_manager.select_rows(
                    initial_selection
                )
            except IndexError as e:
                raise IndexError(
                    "initial_selection contains invalid row indices"
                ) from e
            initial_value = initial_selection
            self._has_any_selection = True

        # We will need this when calling table manager's to_data()
        self._format_mapping = format_mapping

        field_types = self._manager.get_field_types()

        if _internal_total_rows is not None:
            total_rows = _internal_total_rows
        else:
            num_rows = self._manager.get_num_rows(force=True)
            total_rows = num_rows if num_rows is not None else "too_many"

        if pagination is False and total_rows != "too_many":
            page_size = total_rows
        # pagination defaults to True if there are more than page_size rows
        if pagination is None:
            if total_rows == "too_many":
                pagination = True
            elif total_rows > page_size:
                pagination = True
            else:
                pagination = False

        # Search first page
        search_result = self._search(
            SearchTableArgs(
                page_size=page_size,
                page_number=0,
                query=None,
                sort=None,
                filters=None,
            )
        )

        # Validate frozen columns
        if (
            freeze_columns_left is not None
            and freeze_columns_right is not None
        ):
            for column in freeze_columns_left:
                if column not in freeze_columns_right:
                    continue
                raise ValueError(
                    "The same column cannot be frozen on both sides."
                )
        else:
            column_names = self._manager.get_column_names()
            if freeze_columns_left is not None:
                for column in freeze_columns_left:
                    if column not in column_names:
                        raise ValueError(
                            f"Column '{column}' not found in table."
                        )
            if freeze_columns_right is not None:
                for column in freeze_columns_right:
                    if column not in column_names:
                        raise ValueError(
                            f"Column '{column}' not found in table."
                        )

        if text_justify_columns:
            valid_justifications = {"left", "center", "right"}
            column_names = self._manager.get_column_names()

            for column, justify in text_justify_columns.items():
                if column not in column_names:
                    raise ValueError(f"Column '{column}' not found in table.")
                if justify not in valid_justifications:
                    raise ValueError(
                        f"Invalid justification '{justify}' for column '{column}'. "
                        f"Must be one of: {', '.join(valid_justifications)}."
                    )

        if wrapped_columns:
            column_names = self._manager.get_column_names()
            for column in wrapped_columns:
                if column not in column_names:
                    raise ValueError(f"Column '{column}' not found in table.")

        # Clamp field types to max columns
        if (
            self._max_columns is not None
            and len(field_types) > self._max_columns
        ):
            field_types = field_types[: self._max_columns]

        super().__init__(
            component_name=table._name,
            label=label,
            initial_value=initial_value,
            args={
                "data": search_result.data,
                "total-rows": total_rows,
                "total-columns": self._manager.get_num_columns(),
                "banner-text": self._get_banner_text(),
                "pagination": pagination,
                "page-size": page_size,
                "field-types": field_types or None,
                "selection": (
                    selection if self._manager.supports_selection() else None
                ),
                "show-filters": self._manager.supports_filters(),
                "show-download": show_download
                and self._manager.supports_download(),
                "show-column-summaries": show_column_summaries,
                "row-headers": self._manager.get_row_headers(),
                "freeze-columns-left": freeze_columns_left,
                "freeze-columns-right": freeze_columns_right,
                "text-justify-columns": text_justify_columns,
                "wrapped-columns": wrapped_columns,
            },
            on_change=on_change,
            functions=(
                Function(
                    name="download_as",
                    arg_cls=DownloadAsArgs,
                    function=self._download_as,
                ),
                Function(
                    name="get_column_summaries",
                    arg_cls=EmptyArgs,
                    function=self._get_column_summaries,
                ),
                Function(
                    name="search",
                    arg_cls=SearchTableArgs,
                    function=self._search,
                ),
            ),
        )

    @property
    def data(
        self,
    ) -> TableData:
        """Get the original table data.

        Returns:
            TableData: The original data passed to the table constructor, in its
                original format (list, dict, dataframe, etc.).
        """
        return self._data

    def _get_banner_text(self) -> str:
        total_columns = self._manager.get_num_columns()
        if self._max_columns is not None and total_columns > self._max_columns:
            return (
                f"Only showing {self._max_columns} of {total_columns} columns."
            )
        return ""

    def _convert_value(
        self, value: Union[List[int] | List[str]]
    ) -> Union[List[JSONType], "IntoDataFrame"]:
        indices = [int(v) for v in value]
        self._selected_manager = self._searched_manager.select_rows(indices)
        self._has_any_selection = len(indices) > 0
        return unwrap_narwhals_dataframe(self._selected_manager.data)  # type: ignore[no-any-return]

    def _download_as(self, args: DownloadAsArgs) -> str:
        """Download the table data in the specified format.

        Downloads selected rows if there are any, otherwise downloads all rows.
        Raw data is downloaded without any formatting applied.

        Args:
            args (DownloadAsArgs): Arguments specifying the download format.
                format must be one of 'csv' or 'json'.

        Returns:
            str: URL to download the data file.

        Raises:
            ValueError: If format is not 'csv' or 'json'.
        """
        manager = (
            self._selected_manager
            if self._selected_manager and self._has_any_selection
            else self._searched_manager
        )

        ext = args.format
        if ext == "csv":
            return mo_data.csv(manager.to_csv()).url
        elif ext == "json":
            return mo_data.json(manager.to_json()).url
        else:
            raise ValueError("format must be one of 'csv' or 'json'.")

    def _get_column_summaries(self, args: EmptyArgs) -> ColumnSummaries:
        """Get statistical summaries for each column in the table.

        Calculates summaries like null counts, min/max values, unique counts, etc.
        for each column. Summaries are only calculated if the total number of rows
        is below the column summary row limit.

        Args:
            args (EmptyArgs): Empty arguments object (unused).

        Returns:
            ColumnSummaries: Object containing column summaries and chart data.
                If summaries are disabled or row limit is exceeded, returns empty
                summaries with is_disabled flag set appropriately.
        """
        del args
        if not self._show_column_summaries:
            return ColumnSummaries(
                data=None,
                summaries=[],
                # This is not 'disabled' because of too many rows
                # so we don't want to display the banner
                is_disabled=False,
            )

        total_rows = self._searched_manager.get_num_rows(force=True) or 0

        # Avoid expensive column summaries calculation by setting a upper limit
        # if we are above the limit, we hide the column summaries
        if total_rows > self._column_summary_row_limit:
            return ColumnSummaries(
                data=None,
                summaries=[],
                is_disabled=True,
            )

        # Get column summaries if not chart-only mode
        summaries: List[ColumnSummary] = []
        if self._show_column_summaries != "chart":
            for column in self._manager.get_column_names():
                try:
                    summary = self._searched_manager.get_summary(column)
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
                except BaseException:
                    # Catch-all: some libraries like Polars have bugs and raise
                    # BaseExceptions, which shouldn't crash the kernel
                    LOGGER.warning(
                        "Failed to get summary for column %s", column
                    )

        # If we are above the limit to show charts,
        # or if we are in stats-only mode,
        # we don't return the chart data
        chart_data = None
        if (
            self._show_column_summaries != "stats"
            and total_rows <= self._column_charts_row_limit
        ):
            chart_data = self._searched_manager.to_data({})

        return ColumnSummaries(
            data=chart_data,
            summaries=summaries,
            is_disabled=False,
        )

    @functools.lru_cache(maxsize=1)  # noqa: B019
    def _apply_filters_query_sort(
        self,
        filters: Optional[List[Condition]],
        query: Optional[str],
        sort: Optional[SortArgs],
    ) -> TableManager[Any]:
        result = self._manager

        if filters:
            data = unwrap_narwhals_dataframe(result.data)
            handler = get_handler_for_dataframe(data)
            data = handler.handle_filter_rows(
                data,
                FilterRowsTransform(
                    type=TransformType.FILTER_ROWS,
                    where=filters,
                    operation="keep_rows",
                ),
            )
            result = get_table_manager(data)

        if query:
            result = result.search(query)

        if sort and sort.by in result.get_column_names():
            result = result.sort_values(sort.by, sort.descending)

        return result

    def _search(self, args: SearchTableArgs) -> SearchTableResponse:
        """Search and filter the table data.

        Applies filters, search query, and sorting to the table data. Returns
        paginated results based on the specified page size and number.

        Args:
            args (SearchTableArgs): Search arguments containing:
                - page_size: Number of rows per page
                - page_number: Zero-based page index
                - query: Optional search query string
                - sort: Optional sorting configuration
                - filters: Optional list of filter conditions
                - limit: Optional row limit

        Returns:
            SearchTableResponse: Response containing:
                - data: Filtered and formatted table data for the requested page
                - total_rows: Total number of rows after applying filters
        """
        offset = args.page_number * args.page_size

        def clamp_rows_and_columns(manager: TableManager[Any]) -> JSONType:
            # Limit to page and column clamping for the frontend
            data = manager.take(args.page_size, offset)
            column_names = data.get_column_names()
            if (
                self._max_columns is not None
                and len(column_names) > self._max_columns
            ):
                data = data.select_columns(column_names[: self._max_columns])
            return data.to_data(self._format_mapping)

        # If no query or sort, return nothing
        # The frontend will just show the original data
        if not args.query and not args.sort and not args.filters:
            self._searched_manager = self._manager
            return SearchTableResponse(
                data=clamp_rows_and_columns(self._manager),
                total_rows=self._manager.get_num_rows(force=True) or 0,
            )

        # Apply filters, query, and functools.sort using the cached method
        result = self._apply_filters_query_sort(
            tuple(args.filters) if args.filters else None,
            args.query,
            args.sort,
        )

        # Save the manager to be used for selection
        self._searched_manager = result

        return SearchTableResponse(
            data=clamp_rows_and_columns(result),
            total_rows=result.get_num_rows(force=True) or 0,
        )

    def _repr_markdown_(self) -> str:
        """Return a markdown representation of the table.

        Generates a markdown or HTML representation of the table data,
        useful for rendering in the GitHub viewer.

        Returns:
            str: HTML representation of the table if available,
                otherwise string representation.
        """
        df = self.data
        if hasattr(df, "_repr_html_"):
            return df._repr_html_()  # type: ignore[attr-defined,no-any-return]
        return str(df)

    def __hash__(self) -> int:
        return id(self)
