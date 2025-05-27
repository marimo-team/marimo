# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import datetime
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
from marimo._plugins.validators import validate_page_size
from marimo._utils.deprecated import deprecated

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from narwhals.dtypes import DType


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


class DataEdits(TypedDict):
    """A typed dictionary containing a list of positional edits.

    Attributes:
        edits (List[PositionalEdit]): List of individual cell edits.
    """

    edits: list[PositionalEdit]


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
        pagination (Optional[bool]): Whether to use pagination, enabled by default.
        page_size (Optional[int]): Page size if pagination is in use, 50 by default.
    """

    _name: Final[str] = "marimo-data-editor"

    LIMIT: Final[int] = 1000

    def __init__(
        self,
        data: Union[RowOrientedData, ColumnOrientedData, IntoDataFrame],
        *,
        pagination: bool = True,
        page_size: int = 50,
        label: str = "",
        on_change: Optional[
            Callable[
                [Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]],
                None,
            ]
        ] = None,
        column_sizing_mode: Literal["auto", "fit"] = "auto",
    ) -> None:
        validate_page_size(page_size)
        table_manager = get_table_manager(data)

        size = table_manager.get_num_rows()
        if size is None or size > self.LIMIT:
            raise ValueError(
                f"Data editor supports a maximum of {self.LIMIT} rows."
            )

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
                "pagination": pagination,
                "page-size": page_size,
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
        return apply_edits(self._data, value)

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
        column = data[edit["columnId"]]
        if edit["rowIdx"] >= len(column):
            # Extend the column with None values up to the new row index
            column.extend([None] * (edit["rowIdx"] - len(column) + 1))
        dtype = schema.get(edit["columnId"]) if schema else None
        column[edit["rowIdx"]] = _convert_value(
            edit["value"], column[0] if column else None, dtype
        )

    return data


def _apply_edits_row_oriented(
    data: RowOrientedData,
    edits: DataEdits,
    schema: Optional[nw.Schema] = None,
) -> RowOrientedData:
    for edit in edits["edits"]:
        if edit["rowIdx"] >= len(data):
            # Create a new row with None values for all columns
            new_row = {col: None for col in data[0].keys()}
            data.append(new_row)
        original_value = data[0][edit["columnId"]] if data else None
        dtype = schema.get(edit["columnId"]) if schema else None
        data[edit["rowIdx"]][edit["columnId"]] = _convert_value(
            edit["value"], original_value, dtype
        )

    return data


def _apply_edits_dataframe(
    native_df: IntoDataFrame, edits: DataEdits, schema: Optional[nw.Schema]
) -> IntoDataFrame:
    df = nw.from_native(native_df, eager_or_interchange_only=True)
    column_oriented = df.to_dict(as_series=False)
    schema = schema or cast(nw.Schema, df.schema)
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
        elif isinstance(original_value, (datetime.date)):
            return datetime.date.fromisoformat(value)
        elif isinstance(original_value, (datetime.datetime)):
            return datetime.datetime.fromisoformat(value)
        elif isinstance(original_value, (datetime.timedelta)):
            return datetime.timedelta(microseconds=float(value))
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
