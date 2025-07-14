# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import datetime
from copy import deepcopy
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Final,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
)

import narwhals.stable.v1 as nw
from narwhals.typing import IntoDataFrame

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._utils.deprecated import deprecated

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from narwhals.dtypes import DType
    from typing_extensions import TypeIs


@dataclass
class DataEditorValue:
    """A dataclass representing the value of a data editor.

    Attributes:
        data (List[Dict[str, Any]]): Row-oriented data as a list of dictionaries.
    """

    data: list[dict[str, Any]]


class PositionalEdit(TypedDict):
    """A typed dictionary representing a single edit in the data editor.

    Attributes:
        rowIdx (int): The index of the row being edited.
        columnId (str): The ID of the column being edited.
        value (Any): The new value for the cell.
    """

    rowIdx: int
    columnId: str
    value: Any


class ColumnEdit(TypedDict):
    """A typed dictionary representing a bulk edit of a column.

    Attributes:
        columnIdx (int): The index of the column being edited.
        If insert/remove, this is the index of the column to be edited. If rename, this is the index of the column to be renamed.
        newName (Optional[str]): The new name of the column.
        type (Literal["insert", "remove", "rename"]): The type of edit.
    """

    columnIdx: int
    newName: Optional[str]
    type: Literal["insert", "remove", "rename"]


class RowEdit(TypedDict):
    """A typed dictionary representing a bulk edit of a row.

    Attributes:
        rowIdx (int): The index of the row being edited.
        type (Literal["insert", "remove"]): The type of edit.

    Note: Insert is already handled with positional edits, so we can focus on 'remove' here
    """

    rowIdx: int
    type: Literal["insert", "remove"]


class DataEdits(TypedDict):
    """A typed dictionary containing a list of edits.

    Attributes:
        edits (List[PositionalEdit | RowEdit | ColumnEdit]): List of individual cell edits, row edits, or column edits.
    """

    edits: list[Union[PositionalEdit, RowEdit, ColumnEdit]]


RowOrientedData = list[dict[str, Any]]
ColumnOrientedData = dict[str, list[Any]]


@deprecated(
    "mo.ui.experimental_data_editor is deprecated. Use mo.ui.data_editor instead"
)
def experimental_data_editor(
    *args: Any,
    **kwargs: Any,
) -> data_editor:
    return data_editor(*args, **kwargs)


@mddoc
class data_editor(
    UIElement[
        DataEdits,
        Union[RowOrientedData, ColumnOrientedData, IntoDataFrame],
    ]
):
    """A data editor component for editing tabular data.

    This component is experimental and intentionally limited in features,
    if you have any feature requests, please file an issue at
    https://github.com/marimo-team/marimo/issues.

    The data can be supplied as:
    1. a Pandas, Polars, or Pyarrow DataFrame
    2. a list of dicts, with one dict for each row, keyed by column names
    3. a dict of lists, with each list representing a column

    Examples:
        Create a data editor from a Pandas dataframe:

        ```python
        import pandas as pd

        df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        editor = mo.ui.data_editor(data=df, label="Edit Data")
        ```

        Create a data editor from a list of dicts:

        ```python
        data = [{"A": 1, "B": "a"}, {"A": 2, "B": "a"}, {"A": 3, "B": "c"}]
        editor = mo.ui.data_editor(data=data, label="Edit Data")
        ```

        Create a data editor from a dict of lists:

        ```python
        data = {"A": [1, 2, 3], "B": ["a", "b", "c"]}
        editor = mo.ui.data_editor(data=data, label="Edit Data")
        ```

    Attributes:
        value (Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]): The current state of the edited data.
        data (Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]): The original data passed to the editor.

    Args:
        data (Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]): The data to be edited.
            Can be a Pandas dataframe, a list of dicts, or a dict of lists.
        label (str): Markdown label for the element.
        on_change (Optional[Callable]): Optional callback to run when this element's value changes.
        column_sizing_mode (Literal["auto", "fit"]): The column sizing mode for the table.
            `auto` will size columns based on the content, `fit` will size columns to fit the view.

    Deprecated:
        pagination (bool): Whether to enable pagination.
        page_size (int): The number of rows to display per page.
    """

    _name: Final[str] = "marimo-data-editor"

    def __init__(
        self,
        data: Union[RowOrientedData, ColumnOrientedData, IntoDataFrame],
        *,
        pagination: bool = True,  # Deprecated, TODO: Remove
        page_size: int = 50,  # Deprecated
        label: str = "",
        on_change: Optional[
            Callable[
                [Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]],
                None,
            ]
        ] = None,
        column_sizing_mode: Literal["auto", "fit"] = "auto",
    ) -> None:
        del pagination, page_size
        table_manager = get_table_manager(data)

        self._data = data
        self._edits: DataEdits | None = None
        field_types = table_manager.get_field_types()

        super().__init__(
            component_name=data_editor._name,
            label=label,
            initial_value={"edits": []},
            args={
                "data": mo_data.csv(table_manager.to_csv()).url,
                "field-types": field_types or None,
                "column-sizing-mode": column_sizing_mode,
            },
            on_change=on_change,
        )

    @property
    def data(
        self,
    ) -> Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]:
        return self._data

    def _convert_value(
        self, value: DataEdits
    ) -> Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]:
        self._edits = value
        return apply_edits(deepcopy(self._data), value)

    def __hash__(self) -> int:
        return id(self)


def apply_edits(
    data: Union[RowOrientedData, ColumnOrientedData, IntoDataFrame],
    edits: DataEdits,
    schema: Optional[nw.Schema] = None,
) -> Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]:
    if len(edits["edits"]) == 0:
        return data
    # If row-oriented, apply edits to the data
    if isinstance(data, list):
        return _apply_edits_row_oriented(data, edits, schema)
    # If column-oriented, apply edits to the data
    elif isinstance(data, dict):
        return _apply_edits_column_oriented(data, edits, schema)

    try:
        return _apply_edits_dataframe(data, edits, schema)
    except Exception as e:
        raise ValueError(
            f"Data editor does not support this type of data: {type(data)}"
        ) from e


def _apply_edits_column_oriented(
    data: ColumnOrientedData,
    edits: DataEdits,
    schema: Optional[nw.Schema] = None,
) -> ColumnOrientedData:
    for edit in edits["edits"]:
        if is_positional_edit(edit):
            _apply_positional_edit_column_oriented(data, edit, schema)
        elif is_row_edit(edit):
            _apply_row_edit_column_oriented(data, edit)
        elif is_column_edit(edit):
            _apply_column_edit_column_oriented(data, edit)

    return data


def _apply_edits_row_oriented(
    data: RowOrientedData,
    edits: DataEdits,
    schema: Optional[nw.Schema] = None,
) -> RowOrientedData:
    for edit in edits["edits"]:
        if is_positional_edit(edit):
            _apply_positional_edit_row_oriented(data, edit, schema)
        elif is_row_edit(edit):
            _apply_row_edit_row_oriented(data, edit)
        elif is_column_edit(edit):
            _apply_column_edit_row_oriented(data, edit)

    return data


def _apply_edits_dataframe(
    native_df: IntoDataFrame, edits: DataEdits, schema: Optional[nw.Schema]
) -> IntoDataFrame:
    df = nw.from_native(native_df, eager_or_interchange_only=True)
    column_oriented = df.to_dict(as_series=False)
    schema = schema or cast(nw.Schema, df.schema)

    # TODO: We should try to find more performant methods of bulk edits for dataframes
    new_data = _apply_edits_column_oriented(column_oriented, edits, schema)
    new_native_df = nw.from_dict(
        new_data, backend=nw.get_native_namespace(df)
    ).to_native()
    return new_native_df  # type: ignore[no-any-return]


def _convert_value(
    value: Any,
    original_value: Any,
    dtype: Optional[DType] = None,
) -> Any:
    try:
        # None is a valid value for all dtypes
        if value is None:
            return None

        if dtype is not None:
            if dtype == nw.Datetime:
                return datetime.datetime.fromisoformat(value)
            elif dtype == nw.Date:
                return datetime.date.fromisoformat(value)
            elif dtype == nw.Duration:
                return datetime.timedelta(microseconds=float(value))
            elif dtype == nw.Float32:
                return float(value)
            elif dtype == nw.Float64:
                return float(value)
            elif dtype == nw.Int16:
                return int(value)
            elif dtype == nw.Int32:
                return int(value)
            elif dtype == nw.Int64:
                return int(value)
            elif dtype == nw.UInt16:
                return int(value)
            elif dtype == nw.UInt32:
                return int(value)
            elif dtype == nw.UInt64:
                return int(value)
            elif dtype == nw.String:
                return str(value)
            elif dtype == nw.Enum:
                return str(value)
            elif dtype == nw.Categorical:
                return str(value)
            elif dtype == nw.Boolean:
                return bool(value)
            elif dtype == nw.List:
                # Handle list conversion
                if isinstance(value, str):
                    # Attempt to parse string as a list
                    try:
                        return list(ast.literal_eval(value))
                    except (ValueError, SyntaxError):
                        # If parsing fails, split the string
                        return value.split(",")
                elif isinstance(value, list):
                    return value  # type: ignore
                else:
                    # If it's not a string or list, wrap it in a list
                    return [value]
            else:
                LOGGER.warning(f"Unsupported dtype: {dtype}")
                return str(value)

        if original_value is None:
            return value

        # Try to convert the value to the original type
        original_type: Any = type(original_value)

        if isinstance(original_value, (int, float)):
            return original_type(value)
        elif isinstance(original_value, str):
            return str(value)
        # The more specific time checks are handled first to avoid parent classes matching
        elif isinstance(original_value, (datetime.timedelta)):
            return datetime.timedelta(microseconds=float(value))
        elif isinstance(original_value, (datetime.datetime)):
            return datetime.datetime.fromisoformat(value)
        elif isinstance(original_value, (datetime.date)):
            return datetime.date.fromisoformat(value)
        elif isinstance(original_value, list):
            # Handle list conversion
            if isinstance(value, str):
                # Attempt to parse string as a list
                try:
                    return list(ast.literal_eval(value))
                except (ValueError, SyntaxError):
                    # If parsing fails, split the string
                    return list(value.split(","))
            elif isinstance(value, list):
                return value  # type: ignore[return-value]
            else:
                # If it's not a string or list, wrap it in a list
                return [value]
        else:
            return value
    except ValueError as e:
        LOGGER.error(str(e))
        # If conversion fails, return the original value
        return original_value  # type: ignore[return-value]


def is_positional_edit(
    edit: Union[PositionalEdit, RowEdit, ColumnEdit],
) -> TypeIs[PositionalEdit]:
    """Check if edit is a PositionalEdit and return it typed."""
    return "rowIdx" in edit and "columnId" in edit and "value" in edit


def is_row_edit(
    edit: Union[PositionalEdit, RowEdit, ColumnEdit],
) -> TypeIs[RowEdit]:
    """Check if edit is a RowEdit and return it typed."""
    return "rowIdx" in edit and "type" in edit


def is_column_edit(
    edit: Union[PositionalEdit, RowEdit, ColumnEdit],
) -> TypeIs[ColumnEdit]:
    """Check if edit is a ColumnEdit and return it typed."""
    return "columnIdx" in edit and "type" in edit


def _apply_positional_edit_column_oriented(
    data: ColumnOrientedData,
    edit: PositionalEdit,
    schema: Optional[nw.Schema] = None,
) -> None:
    """Apply a positional edit to column-oriented data."""
    column = data[edit["columnId"]]
    if edit["rowIdx"] >= len(column):
        # Extend the column with None values up to the new row index
        column.extend([None] * (edit["rowIdx"] - len(column) + 1))
    dtype = schema.get(edit["columnId"]) if schema else None
    column[edit["rowIdx"]] = _convert_value(
        edit["value"], column[0] if column else None, dtype
    )


def _apply_positional_edit_row_oriented(
    data: RowOrientedData,
    edit: PositionalEdit,
    schema: Optional[nw.Schema] = None,
) -> None:
    """Apply a positional edit to row-oriented data."""
    if edit["rowIdx"] >= len(data):
        # Create a new row with None values for all columns
        new_row = {col: None for col in data[0].keys()}
        data.append(new_row)
    original_value = data[0][edit["columnId"]] if data else None
    dtype = schema.get(edit["columnId"]) if schema else None
    data[edit["rowIdx"]][edit["columnId"]] = _convert_value(
        edit["value"], original_value, dtype
    )


def _apply_row_edit_column_oriented(
    data: ColumnOrientedData,
    edit: RowEdit,
) -> None:
    """Apply a row edit to column-oriented data."""
    if edit["type"] == "remove":
        rowIdx = edit["rowIdx"]
        for column in data.values():
            if not _is_valid_index(rowIdx, len(column)):
                continue
            del column[rowIdx]


def _apply_row_edit_row_oriented(
    data: RowOrientedData,
    edit: RowEdit,
) -> None:
    """Apply a row edit to row-oriented data."""
    rowIdx = edit["rowIdx"]
    if not _is_valid_index(rowIdx, len(data)):
        return
    if edit["type"] == "remove":
        data.pop(rowIdx)


def _validate_column_edit(
    edit: ColumnEdit,
    data_length: int,
    new_column_name: Optional[str],
) -> None:
    """Validate column edit parameters."""
    column_idx = edit["columnIdx"]
    edit_type = edit["type"]

    if column_idx < 0 or column_idx > data_length:
        raise ValueError(f"Column index {column_idx} is out of bounds")

    if edit_type in ("insert", "rename") and new_column_name is None:
        raise ValueError(
            "New column name is required for insert/rename operations"
        )


def _apply_column_edit_column_oriented(
    data: ColumnOrientedData,
    edit: ColumnEdit,
) -> None:
    """Apply a column edit to column-oriented data."""
    column_order = list(data.keys())
    new_column_name = edit.get("newName")

    column_idx = edit["columnIdx"]
    edit_type = edit["type"]

    _validate_column_edit(edit, len(data), new_column_name)

    column_idx = edit["columnIdx"]
    edit_type = edit["type"]

    if edit_type == "insert":
        assert new_column_name is not None

        data_length = len(data[column_order[0]]) if column_order else 0

        if column_idx == len(column_order):
            # Add new column at the end
            data[new_column_name] = [None] * data_length
        else:
            # Insert new column at specific index
            column_data = data.copy()
            data.clear()
            for idx, key in enumerate(column_order):
                if idx == column_idx:
                    data[new_column_name] = [None] * data_length
                data[key] = column_data[key]
        return

    # Find column by index
    column_id = None
    for idx, key in enumerate(column_order):
        if idx == column_idx:
            column_id = key
            break

    if column_id is None:
        raise ValueError(f"Column index {column_idx} not found")

    if edit_type == "rename":
        assert new_column_name is not None

        column_data = data.copy()
        data.clear()
        for key in column_order:
            if key == column_id:
                data[new_column_name] = column_data[key]
            else:
                data[key] = column_data[key]
    elif edit_type == "remove":
        del data[column_id]


def _apply_column_edit_row_oriented(
    data: RowOrientedData,
    edit: ColumnEdit,
) -> None:
    """Apply a column edit to row-oriented data."""
    if not data:
        return

    column_order = list(data[0].keys())
    new_column_name = edit.get("newName")

    _validate_column_edit(edit, len(data[0]) + 1, new_column_name)

    column_idx = edit["columnIdx"]
    edit_type = edit["type"]

    if edit_type == "insert":
        assert new_column_name is not None

        if column_idx < len(column_order):
            new_column_order = (
                column_order[:column_idx]
                + [new_column_name]
                + column_order[column_idx:]
            )
        else:
            new_column_order = column_order + [new_column_name]

        for row_idx, row in enumerate(data):
            new_row = {
                column: row.get(column, None) for column in new_column_order
            }
            data[row_idx] = new_row
        return

    # Find column by index
    column_id = None
    for idx, column in enumerate(data[0]):
        if idx == column_idx:
            column_id = column
            break

    if column_id is None:
        raise ValueError(f"Column index {column_idx} not found")

    if edit_type == "remove":
        for d in data:
            del d[column_id]
    elif edit_type == "rename":
        assert new_column_name is not None

        # Get the column name at the specified index
        column_name = list(data[0].keys())[column_idx]

        for row in data:
            new_row = {}
            for key in row.keys():
                if key == column_name:
                    new_row[new_column_name] = row[key]
                else:
                    new_row[key] = row[key]
            row.clear()
            row.update(new_row)


def _is_valid_index(index: int, length: int) -> bool:
    return index >= 0 and index < length
