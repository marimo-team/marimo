# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Literal,
    Optional,
    Union,
    cast,
)

from narwhals.typing import IntoDataFrame

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._data.models import BinValue, ColumnStats, ValueCount
from marimo._data.preview_column import get_column_preview_dataset
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import ColumnPreview
from marimo._output.mime import MIME
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.charts.altair_transformer import _to_marimo_arrow
from marimo._plugins.ui._impl.dataframes.transforms.apply import (
    apply_transforms_to_df,
)
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    Condition,
    FilterRowsTransform,
    TransformType,
)
from marimo._plugins.ui._impl.tables.selection import (
    INDEX_COLUMN_NAME,
    add_selection_column,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldTypes,
    RowId,
    TableCell,
    TableCoordinate,
    TableManager,
)
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._plugins.ui._impl.utils.dataframe import (
    ListOrTuple,
    TableData,
    download_as,
)
from marimo._plugins.validators import (
    validate_no_integer_columns,
    validate_page_size,
)
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._runtime.context.utils import get_mode
from marimo._runtime.functions import EmptyArgs, Function
from marimo._utils.hashable import is_hashable
from marimo._utils.narwhals_utils import (
    can_narwhalify_lazyframe,
    unwrap_narwhals_dataframe,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narwhals.typing import IntoLazyFrame

LOGGER = _loggers.marimo_logger()


class TableSearchError(Exception):
    def __init__(self, error: str):
        self.error = error
        super().__init__(error)


@dataclass
class DownloadAsArgs:
    format: Literal["csv", "json", "parquet"]


@dataclass
class ColumnSummariesArgs: ...


@dataclass
class ColumnSummaries:
    # If precomputed aggregations fail, we fallback to chart data
    data: Union[JSONType, str]
    stats: dict[ColumnName, ColumnStats]
    bin_values: dict[ColumnName, list[BinValue]]
    value_counts: dict[ColumnName, list[ValueCount]]
    show_charts: bool
    # Disabled because of too many columns/rows
    # This will show a banner in the frontend
    is_disabled: Optional[bool] = None


ShowColumnSummaries = Union[bool, Literal["stats", "chart"]]
CHART_MAX_ROWS_STRING_VALUE_COUNTS = 20_000

DEFAULT_MAX_COLUMNS = 50

MaxColumnsNotProvided = Literal["inherit"]
MAX_COLUMNS_NOT_PROVIDED: MaxColumnsNotProvided = "inherit"

MaxColumnsType = Union[int, None, MaxColumnsNotProvided]


@dataclass(frozen=True)
class SortArgs:
    by: ColumnName
    descending: bool


@dataclass(frozen=True)
class SearchTableArgs:
    page_size: int
    page_number: int
    query: Optional[str] = None
    sort: Optional[list[SortArgs]] = None
    filters: Optional[list[Condition]] = None
    limit: Optional[int] = None
    max_columns: Optional[Union[int, MaxColumnsNotProvided]] = (
        MAX_COLUMNS_NOT_PROVIDED
    )


CellStyles = dict[RowId, dict[ColumnName, dict[str, Any]]]


@dataclass(frozen=True)
class SearchTableResponse:
    data: str
    total_rows: Union[int, Literal["too_many"]]
    cell_styles: Optional[CellStyles] = None
    # Mapping of rowId -> columnName -> hover text (plain string or None to suppress)
    cell_hover_texts: Optional[
        dict[RowId, dict[ColumnName, Optional[str]]]
    ] = None


@dataclass
class GetRowIdsResponse:
    row_ids: list[int]
    all_rows: bool
    error: Optional[str] = None


@dataclass
class GetDataUrlResponse:
    data_url: Union[str, object]
    format: Literal["csv", "json", "arrow"]


@dataclass
class CalculateTopKRowsArgs:
    column: ColumnName
    k: int


@dataclass
class CalculateTopKRowsResponse:
    data: list[tuple[str, int]]


@dataclass
class PreviewColumnArgs:
    column: ColumnName


def get_default_table_page_size() -> int:
    """Get the default number of rows to display in a table."""
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return 10
    else:
        return ctx.marimo_config["display"]["default_table_page_size"]


def get_default_table_max_columns() -> int:
    """Get the default maximum number of columns to display in a table."""
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return DEFAULT_MAX_COLUMNS
    else:
        return ctx.marimo_config["display"]["default_table_max_columns"]


@mddoc
class table(
    UIElement[
        Union[list[str], list[int], list[dict[str, Any]]],
        Union[list[JSONType], IntoDataFrame, list[TableCell]],
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

        Create a table with conditional cell formatting:

        ```python
        import random


        # rowId and columnName are strings.
        def style_cell(_rowId, _columnName, value):
            # Apply inline styling to the visible individual cells.
            return {
                "backgroundColor": "lightcoral"
                if value < 4
                else "cornflowerblue",
                "color": "white",
                "fontStyle": "italic",
            }


        table = mo.ui.table(
            data=[random.randint(0, 10) for x in range(200)],
            style_cell=style_cell,
        )
        table
        ```

        Create a table with per-cell hover text (plain text only):

        ```python
        import random


        # rowId and columnName are strings.
        def hover_cell(rowId, columnName, value):
            # Compute a short plain-text title for the visible individual cells.
            return f"Row {rowId} — {columnName}: {value}"


        table = mo.ui.table(
            data=[random.randint(0, 10) for _ in range(200)],
            hover_template=hover_cell,
        )
        table
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
        selection (Literal["single", "multi", "single-cell", "multi-cell"], optional): 'single' or 'multi' to enable row selection,
            'single-cell' or 'multi-cell' to enable cell selection
            or None to disable. Defaults to "multi".
        initial_selection (Union[List[int], List[tuple[str, str]], optional): Indices of the rows you want selected by default.
        page_size (int, optional): The number of rows to show per page. Defaults to 10.
        show_column_summaries (Union[bool, Literal["stats", "chart"]], optional): Whether to show column summaries.
            Defaults to True when the table has less than 40 columns and at least 10 rows, False otherwise.
            If "stats", only show stats. If "chart", only show charts.
        show_data_types (bool, optional): Whether to show data types of columns in the table header.
            Defaults to True.
        show_download (bool, optional): Whether to show the download button.
            Defaults to True for dataframes, False otherwise.
        format_mapping (Dict[str, Union[str, Callable[..., Any]]], optional): A mapping from
            column names to formatting strings or functions.
        freeze_columns_left (Sequence[str], optional): List of column names to freeze on the left.
        freeze_columns_right (Sequence[str], optional): List of column names to freeze on the right.
        text_justify_columns (Dict[str, Literal["left", "center", "right"]], optional):
            Dictionary of column names to text justification options: left, center, right.
        wrapped_columns (List[str], optional): List of column names to wrap.
        header_tooltip (Dict[str, str], optional): Mapping from column names to tooltip text on the column header.
        label (str, optional): Markdown label for the element. Defaults to "".
        on_change (Callable[[Union[List[JSONType], Dict[str, List[JSONType]], IntoDataFrame, List[TableCell]]], None], optional):
            Optional callback to run when this element's value changes.
        style_cell (Callable[[str, str, Any], Dict[str, Any]], optional): A function that takes the row id, column name and value and returns a dictionary of CSS styles.
        hover_template (Union[str, Callable[[str, str, Any], str]], optional):
            Either a string template applied at the row level, or a callable
            that computes plain-text hover titles for individual visible cells.
            When a callable is provided, values are computed per page in Python
            and passed to the frontend; native HTML `title` is used for display.
            Plain text only is supported.
        max_columns (int, optional): Maximum number of columns to display. Defaults to the
            configured default_table_max_columns (50 by default). Set to None to show all columns.
        max_height (int, optional): Maximum height of the table body in pixels. When set,
            the table becomes vertically scrollable and the header will be made sticky
            in the UI to remain visible while scrolling. Defaults to None.
        label (str, optional): A descriptive name for the table. Defaults to "".
    """

    _name: Final[str] = "marimo-table"

    @staticmethod
    def lazy(
        data: IntoLazyFrame,
        *,
        page_size: Optional[int] = None,
        preload: bool = False,
    ) -> table:
        """
        Create a table from a Polars LazyFrame.

        This won't load the data into memory until requested by the user.
        Once requested, only the first 10 rows will be loaded.

        Pagination and selection are not supported for lazy tables.

        Args:
            data (IntoLazyFrame): The data to display.
            page_size (int, optional): The number of rows to show per page.
            preload (bool, optional): Whether to load the first page of data
                without user confirmation. Defaults to False.
        """

        if not can_narwhalify_lazyframe(data):
            raise ValueError(
                "data must be a Polars LazyFrame, Ibis Table, or DuckDBRelation. Got: "
                + type(data).__name__
            )

        if page_size is None:
            page_size = get_default_table_page_size()

        return table(
            data=data,
            pagination=False,
            selection=None,
            initial_selection=None,
            page_size=page_size,
            show_column_summaries=False,
            show_download=False,
            format_mapping=None,
            freeze_columns_left=None,
            freeze_columns_right=None,
            text_justify_columns=None,
            wrapped_columns=None,
            label="",
            on_change=None,
            style_cell=None,
            max_columns=MAX_COLUMNS_NOT_PROVIDED,
            _internal_column_charts_row_limit=None,
            _internal_summary_row_limit=None,
            _internal_total_rows="too_many",
            _internal_lazy=True,
            _internal_preload=preload,
        )

    def __init__(
        self,
        data: Union[
            ListOrTuple[Union[str, int, float, bool, MIME, None]],
            ListOrTuple[dict[str, JSONType]],
            dict[str, ListOrTuple[JSONType]],
            IntoDataFrame,
        ],
        pagination: Optional[bool] = None,
        selection: Optional[
            Literal["single", "multi", "single-cell", "multi-cell"]
        ] = "multi",
        initial_selection: Optional[
            Union[list[int], list[tuple[str, str]]]
        ] = None,
        page_size: Optional[int] = None,
        show_column_summaries: Optional[ShowColumnSummaries] = None,
        show_data_types: bool = True,
        format_mapping: Optional[
            dict[str, Union[str, Callable[..., Any]]]
        ] = None,
        freeze_columns_left: Optional[Sequence[str]] = None,
        freeze_columns_right: Optional[Sequence[str]] = None,
        text_justify_columns: Optional[
            dict[str, Literal["left", "center", "right"]]
        ] = None,
        wrapped_columns: Optional[list[str]] = None,
        header_tooltip: Optional[dict[str, str]] = None,
        show_download: bool = True,
        max_columns: MaxColumnsType = MAX_COLUMNS_NOT_PROVIDED,
        *,
        label: str = "",
        on_change: Optional[
            Callable[
                [
                    Union[
                        list[JSONType],
                        dict[str, ListOrTuple[JSONType]],
                        IntoDataFrame,
                        list[TableCell],
                    ]
                ],
                None,
            ]
        ] = None,
        style_cell: Optional[Callable[[str, str, Any], dict[str, Any]]] = None,
        hover_template: Optional[
            Union[str, Callable[[str, str, Any], str]]
        ] = None,
        max_height: Optional[int] = None,
        # The _internal_* arguments are for overriding and unit tests
        # table should take the value unconditionally
        _internal_column_charts_row_limit: Optional[int] = None,
        _internal_summary_row_limit: Optional[int] = None,
        _internal_total_rows: Optional[Union[int, Literal["too_many"]]] = None,
        _internal_lazy: bool = False,
        _internal_preload: bool = False,
    ) -> None:
        if page_size is None:
            page_size = self.default_page_size

        validate_no_integer_columns(data)
        validate_page_size(page_size)
        self._lazy = _internal_lazy
        self._page_size = page_size
        self._max_columns: Optional[int] = None
        max_columns_arg: Union[int, str]

        has_stable_row_id = False
        if selection is not None:
            data, has_stable_row_id = add_selection_column(data)
        self._has_stable_row_id = has_stable_row_id

        # The original data passed in
        self._data = data
        # Holds the original data
        self._manager = get_table_manager(data)

        # Handle max_columns: use config default if not provided, None means "all"
        if max_columns == MAX_COLUMNS_NOT_PROVIDED:
            self._max_columns = get_default_table_max_columns()
            max_columns_arg = self._max_columns
        elif max_columns is None:
            self._max_columns = None
            max_columns_arg = "all"
        else:
            self._max_columns = max_columns
            max_columns_arg = max_columns

        if _internal_total_rows is not None:
            total_rows = _internal_total_rows
        else:
            num_rows = self._manager.get_num_rows(force=True)
            total_rows = num_rows if num_rows is not None else "too_many"

        # Set the default value for show_column_summaries,
        # if it is not set by the user
        if show_column_summaries is None:
            # cast to bool --- comparison come back as a NumPy bool
            show_column_summaries = bool(
                (
                    self._manager.get_num_columns()
                    <= TableManager.DEFAULT_SUMMARY_CHARTS_COLUMN_LIMIT
                )
                and (
                    total_rows == "too_many"
                    or total_rows
                    >= TableManager.DEFAULT_SUMMARY_CHARTS_MINIMUM_ROWS
                )
            )
        self._show_column_summaries: ShowColumnSummaries = (
            show_column_summaries
        )

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

        app_mode = get_mode()
        # Some panels are not as useful in non-edit mode and require an external dependency
        show_column_explorer = app_mode == "edit" or app_mode == "run"
        show_chart_builder = app_mode == "edit"

        show_page_size_selector = True
        if (isinstance(total_rows, int) and total_rows <= 5) or _internal_lazy:
            show_page_size_selector = False

        # Holds the data after user searching from original data
        # (searching operations include query, sort, filter, etc.)
        self._searched_manager = self._manager
        # Holds the data after user selecting from the component
        self._selected_manager: Optional[
            Union[TableManager[Any], list[TableCell]]
        ] = None

        self._selection = selection
        self._has_any_selection = False
        # Either a list of int (for selection "single" or "multiple")
        # Or a list of dict (for selection "single-cell" or "multi-cell")
        initial_value: list[Any] = []
        if initial_selection and self._manager.supports_selection():
            if (selection in ["single", "single-cell"]) and len(
                initial_selection
            ) > 1:
                raise ValueError(
                    "For single selection mode, initial_selection can only contain one row index"
                )
            try:
                if selection in ["single-cell", "multi-cell"]:
                    coordinates: list[TableCoordinate] = []
                    for v in initial_selection:
                        if not isinstance(v, tuple) or len(v) != 2:
                            raise TypeError(
                                "initial_selection must be a list of tuples for cell selection"
                            )
                        coordinates.append(
                            TableCoordinate(row_id=v[0], column_name=v[1])
                        )
                    if coordinates:
                        self._selected_manager = (
                            self._searched_manager.select_cells(coordinates)
                        )
                else:
                    indexes: list[int] = []
                    for v in initial_selection:
                        if not isinstance(v, int):
                            raise TypeError(
                                "initial_selection must be a list of integers for row selection"
                            )
                        indexes.append(v)
                    self._selected_manager = (
                        self._searched_manager.select_rows(indexes)
                    )
            except IndexError as e:
                raise IndexError(
                    "initial_selection contains invalid row indices"
                ) from e

            initial_value = (
                initial_selection
                if all(isinstance(v, int) for v in initial_selection)
                else [
                    {"rowId": v[0], "columnName": v[1]}
                    for v in initial_selection
                    if isinstance(v, tuple)
                ]
            )
            self._has_any_selection = True

        # We will need this when calling table manager's to_json_str()
        self._format_mapping = format_mapping

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

        self._style_cell = style_cell
        # Store hover callable vs string template separately
        self._hover_cell: Optional[Callable[[str, str, Any], str]] = None
        self._hover_template: Optional[str] = None
        if isinstance(hover_template, str):
            self._hover_template = hover_template
        elif callable(hover_template):
            self._hover_cell = hover_template

        search_result_styles: Optional[CellStyles] = None
        search_result_hover_texts: Optional[
            dict[RowId, dict[ColumnName, Optional[str]]]
        ] = None
        search_result_data: JSONType = []
        field_types: Optional[FieldTypes] = None
        num_columns = 0

        if not _internal_lazy:
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
            search_result_styles = search_result.cell_styles
            search_result_data = search_result.data
            search_result_hover_texts = search_result.cell_hover_texts

            # Validate column configurations
            column_names_set = set(self._manager.get_column_names())
            num_columns = len(column_names_set)
            _validate_frozen_columns(
                freeze_columns_left, freeze_columns_right, column_names_set
            )
            _validate_column_formatting(
                text_justify_columns, wrapped_columns, column_names_set
            )
            _validate_header_tooltip(header_tooltip, column_names_set)

            field_types = self._manager.get_field_types()

        super().__init__(
            component_name=table._name,
            label=label,
            initial_value=initial_value,
            args={
                "data": search_result_data,
                "total-rows": total_rows,
                "total-columns": num_columns,
                "max-columns": max_columns_arg,
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
                "show-data-types": show_data_types,
                "show-page-size-selector": show_page_size_selector,
                "show-column-explorer": show_column_explorer,
                "show-chart-builder": show_chart_builder,
                "row-headers": self._manager.get_row_headers(),
                "freeze-columns-left": freeze_columns_left,
                "freeze-columns-right": freeze_columns_right,
                "text-justify-columns": text_justify_columns,
                "wrapped-columns": wrapped_columns,
                "header-tooltip": header_tooltip,
                "has-stable-row-id": self._has_stable_row_id,
                "cell-styles": search_result_styles,
                "hover-template": self._hover_template,
                "cell-hover-texts": search_result_hover_texts,
                "lazy": _internal_lazy,
                "preload": _internal_preload,
                "max-height": int(max_height)
                if max_height is not None
                else None,
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
                    arg_cls=ColumnSummariesArgs,
                    function=self._get_column_summaries,
                ),
                Function(
                    name="search",
                    arg_cls=SearchTableArgs,
                    function=self._search,
                ),
                Function(
                    name="get_row_ids",
                    arg_cls=EmptyArgs,
                    function=self._get_row_ids,
                ),
                Function(
                    name="get_data_url",
                    arg_cls=EmptyArgs,
                    function=self._get_data_url,
                ),
                Function(
                    name="calculate_top_k_rows",
                    arg_cls=CalculateTopKRowsArgs,
                    function=self._calculate_top_k_rows,
                ),
                Function(
                    name="preview_column",
                    arg_cls=PreviewColumnArgs,
                    function=self._preview_column,
                ),
            ),
        )

    @property
    def data(self) -> TableData:
        """Get the original table data.

        Returns:
            TableData: The original data passed to the table constructor, in its
                original format (list, dict, dataframe, etc.).
        """
        return self._data

    def _get_banner_text(self) -> str:
        if self._lazy:
            return f"Previewing only the first {self._page_size} rows."

        total_columns = self._manager.get_num_columns()
        if self._max_columns is not None and total_columns > self._max_columns:
            return (
                f"Only showing {self._max_columns} of {total_columns} columns."
            )
        return ""

    def _convert_value(
        self, value: Union[list[int], list[str], list[dict[str, Any]]]
    ) -> Union[list[JSONType], IntoDataFrame, list[TableCell]]:
        if self._selection is None:
            return cast(list[JSONType], None)

        if self._selection in ["single-cell", "multi-cell"]:
            coordinates = [
                TableCoordinate(row_id=v["rowId"], column_name=v["columnName"])
                for v in value
                if isinstance(v, dict) and "rowId" in v and "columnName" in v
            ]
            self._has_any_selection = len(coordinates) > 0
            return self._searched_manager.select_cells(coordinates)  # type: ignore
        else:
            indices = [
                int(v)
                for v in value
                if isinstance(v, int) or isinstance(v, str)
            ]
            self._has_any_selection = len(indices) > 0
            if self._has_stable_row_id:
                # Search across the original data
                self._selected_manager = self._manager.select_rows(
                    indices
                ).drop_columns([INDEX_COLUMN_NAME])
            else:
                self._selected_manager = self._searched_manager.select_rows(
                    indices
                )
            return unwrap_narwhals_dataframe(self._selected_manager.data)  # type: ignore[no-any-return]

    def _download_as(self, args: DownloadAsArgs) -> str:
        """Download the table data in the specified format.

        For cell-selection modes ("single-cell"/"multi-cell"), selection is
        ignored and the current searched/filtered view is downloaded. For
        row-selection modes, downloads selected rows if any, otherwise the
        current searched/filtered view. Raw data is downloaded without any
        formatting applied.

        Args:
            args (DownloadAsArgs): Arguments specifying the download format.
                format must be one of 'csv' or 'json'.

        Returns:
            str: URL to download the data file.

        Raises:
            ValueError: If format is not 'csv' or 'json'.
        """
        # For cell-selection modes, ignore selection and download from the
        # searched/filtered view. For row-selection modes, preserve existing
        # behavior: download selected rows if any, otherwise the searched view.
        manager_candidate: Union[TableManager[Any], list[TableCell]]
        if self._selection in ["single-cell", "multi-cell"]:
            LOGGER.info(
                "Cell selection downloads aren't supported; downloading all data."
            )
            manager_candidate = self._searched_manager
        else:
            manager_candidate = (
                self._selected_manager
                if self._selected_manager and self._has_any_selection
                else self._searched_manager
            )

        # Remove the selection column before downloading
        if isinstance(manager_candidate, TableManager):
            return download_as(
                manager_candidate, args.format, drop_marimo_index=True
            )
        else:
            raise NotImplementedError(
                "Download is not supported for this table format."
            )

    def _get_column_summaries(
        self, args: ColumnSummariesArgs
    ) -> ColumnSummaries:
        """Get statistical summaries for each column in the table.

        Calculates summaries like null counts, min/max values, unique counts, etc.
        for each column. Summaries are only calculated if the total number of rows
        is below the column summary row limit.

        Args:
            args (ColumnSummariesArgs): Arguments specifying whether to precompute
                the column summaries and bin values.

        Returns:
            ColumnSummaries: Object containing column summaries and chart data.
                If summaries are disabled or row limit is exceeded, returns empty
                summaries with is_disabled flag set appropriately.
        """
        del args

        show_column_summaries = self._show_column_summaries

        if not show_column_summaries:
            return ColumnSummaries(
                data=None,
                stats={},
                bin_values={},
                value_counts={},
                # This is not 'disabled' because of too many rows
                # so we don't want to display the banner
                is_disabled=False,
                show_charts=False,
            )

        total_rows = self._searched_manager.get_num_rows(force=True) or 0

        # Avoid expensive column summaries calculation by setting a upper limit
        # if we are above the limit, we hide the column summaries
        if total_rows > self._column_summary_row_limit:
            return ColumnSummaries(
                data=None,
                stats={},
                bin_values={},
                value_counts={},
                is_disabled=True,
                show_charts=False,
            )

        # If we are above the limit to show charts,
        # or if we are in stats-only mode,
        # we don't show charts
        show_charts = (
            self._show_column_summaries != "stats"
            and total_rows <= self._column_charts_row_limit
        )

        # Get column stats if not chart-only mode
        should_get_stats = show_column_summaries != "chart"
        stats: dict[ColumnName, ColumnStats] = {}

        chart_data = None
        bin_values: dict[ColumnName, list[BinValue]] = {}
        value_counts: dict[ColumnName, list[ValueCount]] = {}
        data = self._searched_manager

        DEFAULT_BIN_SIZE = 9
        DEFAULT_VALUE_COUNTS_SIZE = 15

        bin_aggregation_failed = False
        cols_to_drop = []

        for column in self._manager.get_column_names():
            statistic = None
            if should_get_stats:
                try:
                    statistic = self._searched_manager.get_stats(column)
                    stats[column] = statistic
                except BaseException:
                    # Catch-all: some libraries like Polars have bugs and raise
                    # BaseExceptions, which shouldn't crash the kernel
                    LOGGER.warning("Failed to get stats for column %s", column)

            if show_charts:
                if not should_get_stats:
                    LOGGER.warning(
                        "Unable to compute stats for column, may not be computed correctly"
                    )

                (column_type, external_type) = self._manager.get_field_type(
                    column
                )
                # For boolean columns, we can drop the column since we use stats
                if column_type == "boolean" or column_type == "unknown":
                    cols_to_drop.append(column)

                # Handle columns with all nulls first
                # These get empty bins regardless of type
                if statistic and statistic.nulls == total_rows:
                    try:
                        bin_values[column] = []
                        cols_to_drop.append(column)
                        continue
                    except BaseException as e:
                        LOGGER.warning(
                            "Failed to drop all-null column %s: %s", column, e
                        )
                        continue

                # For now, we only compute value counts for categorical columns and small tables
                external_type = external_type.lower()
                categorical_type = (
                    "cat" in external_type or "enum" in external_type
                )
                if column_type == "string" and categorical_type:
                    try:
                        val_counts = self._get_value_counts(
                            column, DEFAULT_VALUE_COUNTS_SIZE, total_rows
                        )
                        if len(val_counts) > 0:
                            value_counts[column] = val_counts
                            cols_to_drop.append(column)
                        continue
                    except BaseException as e:
                        LOGGER.warning(
                            "Failed to get value counts for column %s: %s",
                            column,
                            e,
                        )

                # Bin values are only supported for numeric and temporal columns
                if column_type not in [
                    "integer",
                    "number",
                    "date",
                    "datetime",
                    "time",
                ]:
                    continue

                try:
                    # get_bin_values is marked unstable
                    # https://narwhals-dev.github.io/narwhals/api-reference/series/#narwhals.series.Series.hist
                    bins = data.get_bin_values(column, DEFAULT_BIN_SIZE)
                    bin_values[column] = bins
                    if len(bins) > 0:
                        cols_to_drop.append(column)
                    continue
                except BaseException as e:
                    bin_aggregation_failed = True
                    LOGGER.warning(
                        "Failed to get bin values for column %s: %s", column, e
                    )

        should_fallback = show_charts and bin_aggregation_failed
        if should_fallback:
            LOGGER.debug("Bin aggregation failed, falling back to chart data")
            data = data.drop_columns(cols_to_drop)
            chart_data, _ = self._to_chart_data_url(data)

        return ColumnSummaries(
            data=chart_data,
            stats=stats,
            bin_values=bin_values,
            value_counts=value_counts,
            show_charts=show_charts,
            is_disabled=False,
        )

    def _get_value_counts(
        self, column: ColumnName, size: int, total_rows: int
    ) -> list[ValueCount]:
        """Get value counts for a column. The last item will be 'others' with the count of remaining
        unique values. If there are only unique values, we return 'unique values' instead.

        Args:
            column (ColumnName): The column to get value counts for.
            size (int): The number of value counts to return.
            total_rows (int): The total number of rows in the table.

        Returns:
            list[ValueCount]: The value counts.
        """
        if size <= 0 or total_rows <= 0:
            LOGGER.warning("Total rows and size is not valid")
            return []

        top_k_rows = self._searched_manager.calculate_top_k_rows(column, size)
        if len(top_k_rows) == 0:
            return []

        all_unique = top_k_rows[0][1] == 1
        if all_unique:
            return [ValueCount(value="unique values", count=total_rows)]

        value_counts = []

        if len(top_k_rows) == size:
            # reserve 1 for others
            top_k_rows = top_k_rows[:-1]

        sum_count = 0
        for value, count in top_k_rows:
            sum_count += count
            value = str(value) if value is not None else "null"
            value_counts.append(ValueCount(value=value, count=count))

        remaining = total_rows - sum_count
        if remaining > 0:
            unique_count = ValueCount(value="others", count=remaining)
            if len(value_counts) == size:
                value_counts[-1] = unique_count
            else:
                value_counts.append(unique_count)

        return value_counts

    @classmethod
    def _to_chart_data_url(
        cls, table_manager: TableManager[Any]
    ) -> tuple[str, Literal["csv", "json", "arrow"]]:
        """
        Get the data for the column summaries.

        Arrow is preferred (less memory and faster)
        fallback to CSV (more compact than JSON)

        We return a URL instead of the data directly
        so the browser can cache requests
        """
        if DependencyManager.pyarrow.has():
            try:
                data_url = mo_data.arrow(table_manager.to_arrow_ipc()).url
                return data_url, "arrow"
            except NotImplementedError:
                LOGGER.debug(
                    "Arrow export not implemented, falling back to CSV."
                )
            except Exception as e:
                LOGGER.error("Unexpected error exporting Arrow: %s", e)

        # Try CSV
        try:
            data_url = mo_data.csv(table_manager.to_csv({})).url
            return data_url, "csv"
        except (ValueError, NotImplementedError):
            LOGGER.debug("CSV export failed, falling back to JSON.")
        except Exception as e:
            LOGGER.error("Unexpected error exporting CSV: %s", e)

        # Fallback to JSON
        try:
            data_url = mo_data.json(
                table_manager.to_json({}, ensure_ascii=True)
            ).url
            return data_url, "json"
        except Exception as e:
            LOGGER.error(
                "Failed to export table data as Arrow, CSV, or JSON: %s", e
            )
            raise

    def _get_data_url(self, args: EmptyArgs) -> GetDataUrlResponse:
        """Get the data URL for the entire table. Used for charting."""
        del args

        if DependencyManager.altair.has():
            result = _to_marimo_arrow(self._searched_manager.data)
            return GetDataUrlResponse(
                data_url=result["url"],
                format=result["format"]["type"],
            )

        url, data_format = self._to_chart_data_url(self._searched_manager)
        return GetDataUrlResponse(
            data_url=url,
            format=data_format,
        )

    @functools.lru_cache(maxsize=1)  # noqa: B019
    def _apply_filters_query_sort_cached(
        self,
        filters: Optional[tuple[Condition, ...]],
        query: Optional[str],
        sort: Optional[tuple[SortArgs, ...]],
    ) -> TableManager[Any]:
        """Cached version that expects hashable arguments."""
        return self._apply_filters_query_sort(
            list(filters) if filters else None,
            query,
            list(sort) if sort else None,
        )

    def _apply_filters_query_sort(
        self,
        filters: Optional[list[Condition]],
        query: Optional[str],
        sort: Optional[list[SortArgs]],
    ) -> TableManager[Any]:
        result = self._manager

        if filters:
            # Filter out conditions for columns that don't exist
            existing_columns = set(result.get_column_names())
            valid_filters = [
                condition
                for condition in filters
                if condition.column_id in existing_columns
            ]

            if valid_filters:
                data = apply_transforms_to_df(
                    result.data,
                    FilterRowsTransform(
                        type=TransformType.FILTER_ROWS,
                        where=valid_filters,
                        operation="keep_rows",
                    ),
                )
                result = get_table_manager(data)

        if query:
            result = result.search(query)

        if sort:
            existing_columns = set(result.get_column_names())
            valid_sort = [s for s in sort if s.by in existing_columns]
            if valid_sort:
                result = result.sort_values(valid_sort)

        return result

    def _calculate_top_k_rows(
        self, args: CalculateTopKRowsArgs
    ) -> CalculateTopKRowsResponse:
        """Calculate the top k rows in the table, grouped by column.
        Returns a table of the top k rows, grouped by column with the count.
        """
        column, k = args.column, args.k
        try:
            data = self._searched_manager.calculate_top_k_rows(column, k)
            return CalculateTopKRowsResponse(data=data)
        # Some libs will panic like Polars, which are only caught with BaseException
        except BaseException as e:
            LOGGER.error("Failed to calculate top k rows: %s", e)
            return CalculateTopKRowsResponse(data=[])

    def _preview_column(self, args: PreviewColumnArgs) -> ColumnPreview:
        """Preview a column of a dataset."""
        column = args.column

        # We use a placeholder for table names
        column_preview = get_column_preview_dataset(
            self._searched_manager, "_df", column
        )
        return column_preview

    def _style_cells(
        self,
        skip: int,
        take: int,
        total_rows: Union[int, Literal["too_many"]],
        descending: bool = False,
    ) -> Optional[CellStyles]:
        """Calculate the styling of the cells in the table."""
        if self._style_cell is None:
            return None

        def do_style_cell(row: str, col: str) -> dict[str, Any]:
            selected_cells = self._searched_manager.select_cells(
                [TableCoordinate(row_id=row, column_name=col)]
            )
            if not selected_cells or self._style_cell is None:
                return {}
            return self._style_cell(row, col, selected_cells[0].value)

        columns = self._searched_manager.get_column_names()
        response = self._get_row_ids(EmptyArgs())

        # Clamp the take to the total number of rows
        if total_rows != "too_many" and skip + take > total_rows:
            take = total_rows - skip

        # Determine row range
        row_ids: Union[list[int], range]
        if response.all_rows or response.error:
            row_ids = range(skip, skip + take)
            if descending and total_rows != "too_many":
                row_ids = range(
                    total_rows - 1 - skip, total_rows - 1 - skip - take, -1
                )
        else:
            row_ids = response.row_ids[skip : skip + take]

        return {
            str(row): {col: do_style_cell(str(row), col) for col in columns}
            for row in row_ids
        }

    def _hover_cells(
        self,
        skip: int,
        take: int,
        total_rows: Union[int, Literal["too_many"]],
        descending: bool = False,
    ) -> Optional[dict[RowId, dict[ColumnName, Optional[str]]]]:
        """Calculate hover text for cells in the table (plain strings or None)."""
        if self._hover_cell is None:
            return None

        def do_hover_cell(row: str, col: str) -> Optional[str]:
            selected_cells = self._searched_manager.select_cells(
                [TableCoordinate(row_id=row, column_name=col)]
            )
            if not selected_cells or self._hover_cell is None:
                return None
            try:
                value = selected_cells[0].value
                result = self._hover_cell(row, col, value)
                return str(result) if result is not None else None
            except BaseException as e:
                LOGGER.warning(
                    "Failed to compute hover text for %s:%s: %s", row, col, e
                )
                return None

        columns = self._searched_manager.get_column_names()
        response = self._get_row_ids(EmptyArgs())

        # Clamp the take to the total number of rows
        if total_rows != "too_many" and skip + take > total_rows:
            take = total_rows - skip

        # Determine row range
        row_ids: Union[list[int], range]
        if response.all_rows or response.error:
            row_ids = range(skip, skip + take)
            if descending and total_rows != "too_many":
                row_ids = range(
                    total_rows - 1 - skip, total_rows - 1 - skip - take, -1
                )
        else:
            row_ids = response.row_ids[skip : skip + take]

        return {
            str(row): {col: do_hover_cell(str(row), col) for col in columns}
            for row in row_ids
        }

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
                - max_columns: Optional max number of columns. None means show all columns,
                  MAX_COLUMNS_NOT_PROVIDED means use the table's max_columns setting.

        Returns:
            SearchTableResponse: Response containing:
                - data: Filtered and formatted table data for the requested page
                - total_rows: Total number of rows after applying filters
                - cell_styles: User defined styling information for each cell in the page
                - cell_hover_texts: User defined hover text for each cell in the page
        """
        offset = args.page_number * args.page_size
        max_columns = args.max_columns
        if max_columns == MAX_COLUMNS_NOT_PROVIDED:
            max_columns = self._max_columns

        def clamp_rows_and_columns(manager: TableManager[Any]) -> str:
            # Limit to page and column clamping for the frontend
            data = manager.take(args.page_size, offset)
            column_names = data.get_column_names()

            # Do not clamp if max_columns is None
            if max_columns is not None and len(column_names) > max_columns:
                data = data.select_columns(column_names[:max_columns])

            try:
                return data.to_json_str(self._format_mapping)
            except BaseException as e:
                # Catch and re-raise the error as a non-BaseException
                # to avoid crashing the kernel
                raise TableSearchError(str(e)) from e

        # If no query or sort, return nothing
        # The frontend will just show the original data
        total_rows: Union[int, Literal["too_many"]]
        if not args.query and not args.sort and not args.filters:
            self._searched_manager = self._manager
            if self._lazy:
                total_rows = "too_many"
            else:
                total_rows = self._manager.get_num_rows(force=True) or 0

            return SearchTableResponse(
                data=clamp_rows_and_columns(self._manager),
                total_rows=total_rows,
                cell_styles=self._style_cells(
                    offset, args.page_size, total_rows
                ),
                cell_hover_texts=self._hover_cells(
                    offset, args.page_size, total_rows
                ),
            )

        filter_function = (
            self._apply_filters_query_sort_cached
            if is_hashable(args.filters, args.query, args.sort)
            else self._apply_filters_query_sort
        )
        result = filter_function(
            tuple(args.filters) if args.filters else None,  # type: ignore
            args.query,
            tuple(args.sort) if args.sort else None,  # type: ignore
        )

        # Save the manager to be used for selection
        self._searched_manager = result

        descending = False

        if self._lazy:
            total_rows = "too_many"
        else:
            total_rows = result.get_num_rows(force=True) or 0

        if args.sort and (self._style_cell or self._hover_cell):
            for element in args.sort:
                if element.descending:
                    descending = True

        return SearchTableResponse(
            data=clamp_rows_and_columns(result),
            total_rows=total_rows,
            cell_styles=self._style_cells(
                offset, args.page_size, total_rows, descending
            ),
            cell_hover_texts=self._hover_cells(
                offset, args.page_size, total_rows, descending
            ),
        )

    def _get_row_ids(self, args: EmptyArgs) -> GetRowIdsResponse:
        """Get row IDs of a table. If searched, return searched rows else all_rows flag is True.

        Args:
            args (EmptyArgs): Empty arguments

        Returns:
            GetRowIdsResponse: Response containing:
                - row_ids: List of row IDs
                - all_rows: Whether all rows are selected
        """
        del args

        total_rows = self._manager.get_num_rows()
        num_rows_searched = self._searched_manager.get_num_rows()

        if total_rows is None or num_rows_searched is None:
            return GetRowIdsResponse(
                row_ids=[],
                all_rows=False,
                error="Failed to get row IDs: number of rows is unknown",
            )

        # If no search has been applied, return with all_rows=True to avoid passing row IDs
        if total_rows == num_rows_searched:
            return GetRowIdsResponse(row_ids=[], all_rows=True)

        if num_rows_searched > 1_000_000:
            return GetRowIdsResponse(
                row_ids=[],
                all_rows=False,
                error="Select all with search is not supported for large datasets. Please filter to less than 1,000,000 rows",
            )

        # For dictionary or list data, return sequential indices
        if isinstance(self.data, dict) or isinstance(self.data, list):
            return GetRowIdsResponse(
                row_ids=list(range(num_rows_searched)),
                all_rows=False,
            )

        # For dataframes
        try:
            row_ids = self._searched_manager.data[INDEX_COLUMN_NAME].to_list()
            return GetRowIdsResponse(row_ids=row_ids, all_rows=False)
        except Exception as e:
            return GetRowIdsResponse(
                row_ids=[],
                all_rows=False,
                error=f"Failed to get row IDs: {str(e)}",
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

    @functools.cached_property
    def default_page_size(self) -> int:
        return get_default_table_page_size()

    def __hash__(self) -> int:
        return id(self)


def _validate_frozen_columns(
    freeze_columns_left: Optional[Sequence[str]],
    freeze_columns_right: Optional[Sequence[str]],
    column_names_set: set[str],
) -> None:
    """Validate frozen column configurations.

    Validates that:
    1. The same column is not frozen on both sides
    2. All frozen columns exist in the table
    """

    freeze_columns_left_set = (
        set(freeze_columns_left) if freeze_columns_left else None
    )
    freeze_columns_right_set = (
        set(freeze_columns_right) if freeze_columns_right else None
    )

    # Convert sequences to sets for O(1) lookups
    if freeze_columns_left_set and freeze_columns_right_set:
        if not freeze_columns_left_set.isdisjoint(freeze_columns_right_set):
            raise ValueError("The same column cannot be frozen on both sides.")

    # Check all frozen columns exist
    if freeze_columns_left_set:
        invalid = freeze_columns_left_set - column_names_set
        if invalid:
            raise ValueError(
                f"Column '{next(iter(invalid))}' not found in table."
            )

    if freeze_columns_right_set:
        invalid = freeze_columns_right_set - column_names_set
        if invalid:
            raise ValueError(
                f"Column '{next(iter(invalid))}' not found in table."
            )


def _validate_column_formatting(
    text_justify_columns: Optional[
        dict[str, Literal["left", "center", "right"]]
    ],
    wrapped_columns: Optional[list[str]],
    column_names_set: set[str],
) -> None:
    """Validate text justification and wrapped column configurations.

    Validates that:
    1. All columns specified in text_justify_columns exist in the table
    2. All justification values are valid ('left', 'center', 'right')
    3. All columns specified in wrapped_columns exist in the table
    """
    if text_justify_columns:
        valid_justifications = {"left", "center", "right"}
        for column, justify in text_justify_columns.items():
            if column not in column_names_set:
                raise ValueError(f"Column '{column}' not found in table.")
            if justify not in valid_justifications:
                raise ValueError(
                    f"Invalid justification '{justify}' for column '{column}'. "
                    f"Must be one of: {', '.join(valid_justifications)}."
                )

    if wrapped_columns:
        wrapped_columns_set = set(wrapped_columns)
        invalid = wrapped_columns_set - column_names_set
        if invalid:
            raise ValueError(
                f"Column '{next(iter(invalid))}' not found in table."
            )


def _validate_header_tooltip(
    header_tooltip: Optional[dict[str, str]],
    column_names_set: set[str],
) -> None:
    """Validate header tooltip mapping.

    Ensures all specified columns exist in the table.
    """
    if header_tooltip:
        invalid = set(header_tooltip.keys()) - column_names_set
        if invalid:
            raise ValueError(
                f"Column '{next(iter(invalid))}' not found in table."
            )
