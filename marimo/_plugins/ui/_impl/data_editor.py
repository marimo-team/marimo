# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import datetime
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Literal,
    TypedDict,
    Union,
    cast,
)

import narwhals.stable.v2 as nw
from narwhals.typing import IntoDataFrame

import marimo._output.data.data as mo_data
from marimo import _loggers
from marimo._data.models import DataType
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from marimo._utils.assert_never import log_never
from marimo._utils.deprecated import deprecated

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from narwhals.dtypes import DType
    from typing_extensions import TypeIs


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


class RemoveColumnEdit(TypedDict):
    columnIdx: int
    type: Literal["remove"]


class RenameColumnEdit(TypedDict):
    columnIdx: int
    newName: str
    type: Literal["rename"]


class _RequiredInsertColumnEdit(TypedDict):
    columnIdx: int
    newName: str
    type: Literal["insert"]


class InsertColumnEdit(_RequiredInsertColumnEdit, total=False):
    dataType: DataType


ColumnEdit = RemoveColumnEdit | RenameColumnEdit | InsertColumnEdit


class RowEdit(TypedDict):
    """A typed dictionary representing a row removal.

    Attributes:
        rowIdx (int): The index of the row being removed.
        type (Literal["remove"]): The type of edit.
    """

    rowIdx: int
    type: Literal["remove"]


class DataEdits(TypedDict):
    """A typed dictionary containing a list of edits.

    Attributes:
        edits (List[PositionalEdit | RowEdit | ColumnEdit]): List of individual cell edits, row edits, or column edits.
    """

    edits: list[PositionalEdit | RowEdit | ColumnEdit]


RowOrientedData = list[dict[str, Any]]
ColumnOrientedData = dict[str, list[Any]]
Scalar = str | int | float | bool | None
ScalarData = list[Scalar]
_DEFAULT_SCALAR_COLUMN = "value"
_TYPE_INFERENCE_SAMPLE_SIZE = 10
_MAX_SAFE_INTEGER = Decimal(2**53 - 1)


def _dtype_from_data_type(data_type: DataType | None) -> DType | None:
    if data_type == "string":
        return nw.String()
    if data_type == "boolean":
        return nw.Boolean()
    if data_type == "integer":
        return nw.Int64()
    if data_type == "number":
        return nw.Float64()
    if data_type == "date":
        return nw.Date()
    if data_type == "datetime":
        return nw.Datetime()
    if data_type == "time":
        return nw.Time()
    return None


def _convert_to_integer(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Cannot convert {value!r} to integer") from error
    if (
        not decimal_value.is_finite()
        or decimal_value != decimal_value.to_integral_value()
    ):
        raise ValueError(
            f"Cannot convert non-integral value {value!r} to integer"
        )
    return int(decimal_value)


def _sample_indices(length: int) -> Sequence[int]:
    if length <= _TYPE_INFERENCE_SAMPLE_SIZE:
        return range(length)
    return [
        *(
            index * length // _TYPE_INFERENCE_SAMPLE_SIZE
            for index in range(_TYPE_INFERENCE_SAMPLE_SIZE - 1)
        ),
        length - 1,
    ]


def _infer_conversion_examples_from_rows(
    data: RowOrientedData,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for row_idx in _sample_indices(len(data)):
        values.update(
            (column, value)
            for column, value in data[row_idx].items()
            if value is not None
        )
    return values


def _infer_conversion_examples_from_columns(
    data: ColumnOrientedData,
    row_count: int,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for row_idx in _sample_indices(row_count):
        for column, column_values in data.items():
            if (
                row_idx < len(column_values)
                and column_values[row_idx] is not None
            ):
                values[column] = column_values[row_idx]
    return values


@dataclass
class _EditableTable:
    data: RowOrientedData | ColumnOrientedData
    column_names: list[str]
    row_count: int
    conversion_examples: dict[str, Any]
    dtypes: dict[str, DType]

    @classmethod
    def from_rows(
        cls,
        data: RowOrientedData,
        schema: nw.Schema | None,
        column_names: Sequence[str] | None,
    ) -> _EditableTable:
        column_order: list[str] = []
        column_set: set[str] = set()
        for row in data:
            for column in row:
                if column not in column_set:
                    column_order.append(column)
                    column_set.add(column)

        fallback_columns = (
            column_names
            if column_names is not None
            else schema.keys()
            if schema is not None
            else ()
        )
        for column in fallback_columns:
            if column not in column_set:
                column_order.append(column)
                column_set.add(column)

        dtypes = dict(schema.items()) if schema is not None else {}
        return cls(
            data,
            column_order,
            len(data),
            _infer_conversion_examples_from_rows(data),
            dtypes,
        )

    @classmethod
    def from_columns(
        cls,
        data: ColumnOrientedData,
        schema: nw.Schema | None,
    ) -> _EditableTable:
        column_order = list(data)
        if schema is not None:
            column_order.extend(
                column for column in schema if column not in data
            )
        dtypes = dict(schema.items()) if schema is not None else {}
        row_count = max((len(values) for values in data.values()), default=0)
        return cls(
            data,
            column_order,
            row_count,
            _infer_conversion_examples_from_columns(data, row_count),
            dtypes,
        )

    def apply(self, edits: DataEdits) -> None:
        for edit in edits["edits"]:
            if is_positional_edit(edit):
                self._apply_positional_edit(edit)
            elif is_row_edit(edit):
                self._apply_row_edit(edit)
            elif is_column_edit(edit):
                self._apply_column_edit(edit)
            else:
                log_never(edit)

    def _materialize_columns(self) -> None:
        if isinstance(self.data, list):
            return
        for column in self.column_names:
            values = self.data.setdefault(column, [])
            values.extend([None] * (self.row_count - len(values)))

    def _get_cell_value(self, row_idx: int, column: str) -> Any:
        if row_idx >= self.row_count:
            return None
        if isinstance(self.data, list):
            return self.data[row_idx].get(column)
        values = self.data.get(column, [])
        return values[row_idx] if row_idx < len(values) else None

    def _apply_positional_edit(self, edit: PositionalEdit) -> None:
        column_id = edit["columnId"]
        row_idx = edit["rowIdx"]
        if row_idx < 0:
            return
        if column_id not in self.column_names:
            self.column_names.append(column_id)
            self.conversion_examples[column_id] = None
            if isinstance(self.data, list):
                for row in self.data:
                    row[column_id] = None
        if isinstance(self.data, dict) and column_id not in self.data:
            self.data[column_id] = [None] * self.row_count
        self._materialize_columns()

        if row_idx >= self.row_count:
            new_row_count = row_idx + 1
            if isinstance(self.data, list):
                self.data.extend(
                    dict.fromkeys(self.column_names)
                    for _ in range(new_row_count - self.row_count)
                )
            else:
                for values in self.data.values():
                    values.extend([None] * (new_row_count - len(values)))
            self.row_count = new_row_count

        dtype = self.dtypes.get(column_id)
        conversion_value = (
            self._get_cell_value(row_idx, column_id)
            if dtype is not None
            else self.conversion_examples.get(column_id)
        )
        converted_value = _convert_value(
            edit["value"],
            conversion_value,
            dtype,
        )
        if isinstance(self.data, list):
            self.data[row_idx][column_id] = converted_value
        else:
            values = self.data[column_id]
            values.extend([None] * (row_idx - len(values) + 1))
            values[row_idx] = converted_value

    def _apply_row_edit(self, edit: RowEdit) -> None:
        row_idx = edit["rowIdx"]
        if edit["type"] != "remove" or not 0 <= row_idx < self.row_count:
            return
        if isinstance(self.data, list):
            self.data.pop(row_idx)
        else:
            for values in self.data.values():
                if row_idx < len(values):
                    values.pop(row_idx)
        self.row_count -= 1

    def _apply_column_edit(self, edit: ColumnEdit) -> None:
        new_column_name = cast(str | None, edit.get("newName"))
        _validate_column_edit(edit, len(self.column_names), new_column_name)

        column_idx = edit["columnIdx"]
        edit_type = edit["type"]
        if edit_type == "insert":
            assert new_column_name is not None
            if new_column_name in self.column_names:
                raise ValueError(f"Column {new_column_name} already exists")

            self._materialize_columns()
            self.column_names.insert(column_idx, new_column_name)
            if isinstance(self.data, list):
                for row_idx, row in enumerate(self.data):
                    self.data[row_idx] = {
                        column: None
                        if column == new_column_name
                        else row[column]
                        for column in self.column_names
                        if column == new_column_name or column in row
                    }
            else:
                items = list(self.data.items())
                items.insert(
                    column_idx,
                    (new_column_name, [None] * self.row_count),
                )
                self.data.clear()
                self.data.update(items)
            self.conversion_examples[new_column_name] = None
            dtype = _dtype_from_data_type(
                cast(DataType | None, edit.get("dataType"))
            )
            if dtype is None:
                self.dtypes.pop(new_column_name, None)
            else:
                self.dtypes[new_column_name] = dtype
            return

        old_name = self.column_names[column_idx]
        if edit_type == "remove":
            self._materialize_columns()
            self.column_names.pop(column_idx)
            if isinstance(self.data, list):
                for row in self.data:
                    row.pop(old_name, None)
            else:
                self.data.pop(old_name, None)
            self.conversion_examples.pop(old_name, None)
            self.dtypes.pop(old_name, None)
            return

        assert edit_type == "rename"
        assert new_column_name is not None
        if old_name == new_column_name:
            return
        if new_column_name in self.column_names:
            raise ValueError(f"Column {new_column_name} already exists")

        self._materialize_columns()
        self.column_names[column_idx] = new_column_name
        if isinstance(self.data, list):
            for row_idx, row in enumerate(self.data):
                self.data[row_idx] = {
                    new_column_name if column == old_name else column: value
                    for column, value in row.items()
                }
        else:
            renamed_columns = {
                new_column_name if column == old_name else column: values
                for column, values in self.data.items()
            }
            self.data.clear()
            self.data.update(renamed_columns)
        self.conversion_examples[new_column_name] = (
            self.conversion_examples.pop(old_name, None)
        )
        dtype = self.dtypes.pop(old_name, None)
        if dtype is not None:
            self.dtypes[new_column_name] = dtype


@deprecated(
    "mo.ui.experimental_data_editor is deprecated. Use mo.ui.data_editor instead"
)
def experimental_data_editor(
    *args: Any,
    **kwargs: Any,
) -> data_editor:
    return data_editor(*args, **kwargs)


# Use Union[] instead of X | Y in class base — see altair_transformer.py
# for rationale.
@mddoc
class data_editor(
    UIElement[
        DataEdits,
        Union[
            ScalarData,
            RowOrientedData,
            ColumnOrientedData,
            IntoDataFrame,
        ],
    ]
):
    """A data editor component for editing tabular data.

    This component is experimental and intentionally limited in features,
    if you have any feature requests, please file an issue at
    https://github.com/marimo-team/marimo/issues.

    The data can be supplied as:
    1. an eager dataframe (e.g., Polars, Pandas, PyArrow)
    2. a list of scalar values, displayed in a column named `value`
    3. a list of dicts, with one dict for each row, keyed by column names
    4. a dict of lists, with each list representing a column

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
        value (ScalarData | RowOrientedData | ColumnOrientedData | IntoDataFrame): The current state of the edited data.
        data (ScalarData | RowOrientedData | ColumnOrientedData | IntoDataFrame): The original data passed to the editor.

    Args:
        data (ScalarData | RowOrientedData | ColumnOrientedData | IntoDataFrame): The data to be edited.
            Can be a dataframe, a list of scalars, a list of dicts, or a dict of lists.
        label (str): Markdown label for the element.
        on_change (Optional[Callable]): Optional callback to run when this element's value changes.
        editable_columns (Union[list[str], Literal["all"]]): A list of column names to be editable.
            If "all", all columns are editable. Pass an empty list to make all columns read-only. Defaults to "all".

    Deprecated:
        pagination (bool): Whether to enable pagination.
        page_size (int): The number of rows to display per page.
        column_sizing_mode (Literal["auto", "fit"]): The column sizing mode for the table.
    """

    _name: Final[str] = "marimo-data-editor"

    def __init__(
        self,
        data: ScalarData
        | RowOrientedData
        | ColumnOrientedData
        | IntoDataFrame,
        *,
        label: str = "",
        on_change: Callable[
            [
                ScalarData
                | RowOrientedData
                | ColumnOrientedData
                | IntoDataFrame
            ],
            None,
        ]
        | None = None,
        editable_columns: list[str] | Literal["all"] = "all",
        column_sizing_mode: Literal["auto", "fit"] | None = None,
        pagination: bool | None = None,
        page_size: int | None = None,
    ) -> None:
        # These attributes are deprecated, but we keep them for backwards compatibility
        if pagination:
            LOGGER.warning(
                "pagination is deprecated and will be removed in a future version"
            )
        if page_size:
            LOGGER.warning(
                "page_size is deprecated and will be removed in a future version"
            )
        if column_sizing_mode:
            LOGGER.warning("column_sizing_mode is deprecated")

        table_manager = get_table_manager(data)

        self._data = data
        self._edits: DataEdits | None = None
        column_names = table_manager.get_column_names()
        self._column_names = column_names
        field_types = table_manager.get_field_types()

        if isinstance(editable_columns, list):
            for col in editable_columns:
                if col not in column_names:
                    raise ValueError(f"Column {col} is not in the data")
        elif editable_columns is None:
            editable_columns = []

        super().__init__(
            component_name=data_editor._name,
            label=label,
            initial_value={"edits": []},
            args={
                "data": mo_data.csv(table_manager.to_csv()).url,
                "field-types": field_types or None,
                "column-names": column_names,
                "editable-columns": editable_columns,
                "column-sizing-mode": "auto",
            },
            on_change=on_change,
        )

    @property
    def data(
        self,
    ) -> ScalarData | RowOrientedData | ColumnOrientedData | IntoDataFrame:
        return self._data

    def _convert_value(
        self, value: DataEdits
    ) -> ScalarData | RowOrientedData | ColumnOrientedData | IntoDataFrame:
        self._edits = value
        # list/dict edit paths mutate in place, so deepcopy first.
        # The dataframe path constructs a new native frame via narwhals
        # without mutating the input — and not all dataframes are picklable
        # (e.g., DuckDBPyRelation), so skip the deepcopy in that case.
        data = self._data
        if isinstance(data, (list, dict)):
            data = deepcopy(data)
        return apply_edits(data, value, column_names=self._column_names)

    def __hash__(self) -> int:
        return id(self)


def apply_edits(
    data: ScalarData | RowOrientedData | ColumnOrientedData | IntoDataFrame,
    edits: DataEdits,
    schema: nw.Schema | None = None,
    *,
    column_names: Sequence[str] | None = None,
) -> ScalarData | RowOrientedData | ColumnOrientedData | IntoDataFrame:
    if len(edits["edits"]) == 0:
        return data
    if isinstance(data, list):
        return _apply_edits_list(data, edits, schema, column_names)
    elif isinstance(data, dict):
        table = _EditableTable.from_columns(data, schema)
        table.apply(edits)
        return data

    try:
        return _apply_edits_dataframe(data, edits, schema)
    except Exception as e:
        raise ValueError(
            f"Data editor does not support this type of data: {type(data)}"
        ) from e


def _apply_edits_list(
    data: ScalarData | RowOrientedData,
    edits: DataEdits,
    schema: nw.Schema | None,
    column_names: Sequence[str] | None,
) -> ScalarData | RowOrientedData:
    is_empty_scalar_data = (
        not data
        and schema is None
        and list(column_names or ()) == [_DEFAULT_SCALAR_COLUMN]
    )
    if not is_empty_scalar_data and all(isinstance(row, dict) for row in data):
        rows = cast(RowOrientedData, data)
        table = _EditableTable.from_rows(rows, schema, column_names)
        table.apply(edits)
        return rows

    if any(isinstance(row, dict) for row in data):
        raise ValueError(
            "Row-oriented data must contain either only dictionaries or "
            "only scalar values"
        )

    scalar_column = (
        column_names[0]
        if column_names is not None and len(column_names) == 1
        else _DEFAULT_SCALAR_COLUMN
    )
    rows = [{scalar_column: value} for value in data]
    table = _EditableTable.from_rows(rows, schema, [scalar_column])
    table.apply(edits)

    if table.column_names == [scalar_column]:
        return [cast(Scalar, row[scalar_column]) for row in rows]
    return rows


def _apply_edits_dataframe(
    native_df: IntoDataFrame, edits: DataEdits, schema: nw.Schema | None
) -> IntoDataFrame:
    df = nw.from_native(native_df, eager_only=True)
    column_oriented = df.to_dict(as_series=False)
    schema = schema or cast(nw.Schema, df.schema)

    # TODO: We should try to find more performant methods of bulk edits for dataframes
    table = _EditableTable.from_columns(column_oriented, schema)
    table.apply(edits)
    new_native_df = nw.from_dict(
        column_oriented, backend=nw.get_native_namespace(df)
    ).to_native()
    return new_native_df  # type: ignore[no-any-return]


def _convert_list(value: Any) -> list[Any]:
    if not isinstance(value, str):
        return value if isinstance(value, list) else [value]

    try:
        parsed = ast.literal_eval(value)
        return parsed if isinstance(parsed, list) else list(parsed)
    except (TypeError, ValueError, SyntaxError):
        return value.split(",")


def _convert_by_dtype(value: Any, dtype: DType) -> tuple[bool, Any]:
    if dtype == nw.Datetime:
        return True, datetime.datetime.fromisoformat(value)
    if dtype == nw.Date:
        return True, datetime.date.fromisoformat(value)
    if dtype == nw.Time:
        return True, datetime.time.fromisoformat(value)
    if dtype == nw.Duration:
        return True, datetime.timedelta(microseconds=float(value))
    if hasattr(dtype, "is_float") and dtype.is_float():
        return True, float(value)
    if hasattr(dtype, "is_integer") and dtype.is_integer():
        return True, _convert_to_integer(value)
    if dtype == nw.String or dtype == nw.Enum or dtype == nw.Categorical:
        return True, str(value)
    if dtype == nw.Boolean:
        return True, bool(value)
    if dtype == nw.List:
        return True, _convert_list(value)
    return False, value


def _convert_like(value: Any, example: Any) -> Any:
    if example is None:
        return value
    if isinstance(example, bool):
        return bool(value)
    if isinstance(example, int):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return float(value)
        if decimal_value.is_finite() and (
            decimal_value == decimal_value.to_integral_value()
        ):
            return int(decimal_value)
        if (
            not decimal_value.is_finite()
            or abs(decimal_value) <= _MAX_SAFE_INTEGER
        ):
            return float(value)
        return value
    if isinstance(example, float):
        return float(value)
    if isinstance(example, str):
        return str(value)
    if isinstance(example, datetime.timedelta):
        return datetime.timedelta(microseconds=float(value))
    if isinstance(example, datetime.datetime):
        return datetime.datetime.fromisoformat(value)
    if isinstance(example, datetime.date):
        return datetime.date.fromisoformat(value)
    if isinstance(example, list):
        return _convert_list(value)
    return value


def _convert_value(
    value: Any,
    original_value: Any,
    dtype: DType | None = None,
) -> Any:
    if value is None:
        return None

    if dtype is not None:
        try:
            handled, converted = _convert_by_dtype(value, dtype)
        except ValueError as error:
            LOGGER.error(str(error))
            return original_value
        if handled:
            return converted
        # Some pandas extension dtypes map to nw.Unknown. Using the example
        # preserves a numeric column instead of coercing it to object.
        LOGGER.debug("Unhandled dtype %s; coercing from example", dtype)

    try:
        return _convert_like(value, original_value)
    except ValueError as error:
        LOGGER.error(str(error))
        return original_value if dtype is not None else value


def is_positional_edit(
    edit: PositionalEdit | RowEdit | ColumnEdit,
) -> TypeIs[PositionalEdit]:
    """Check if edit is a PositionalEdit and return it typed."""
    return "rowIdx" in edit and "columnId" in edit and "value" in edit


def is_row_edit(
    edit: PositionalEdit | RowEdit | ColumnEdit,
) -> TypeIs[RowEdit]:
    """Check if edit is a RowEdit and return it typed."""
    return "rowIdx" in edit and "type" in edit


def is_column_edit(
    edit: PositionalEdit | RowEdit | ColumnEdit,
) -> TypeIs[ColumnEdit]:
    """Check if edit is a ColumnEdit and return it typed."""
    return "columnIdx" in edit and "type" in edit


def _validate_column_edit(
    edit: ColumnEdit,
    column_count: int,
    new_column_name: str | None,
) -> None:
    """Validate column edit parameters."""
    column_idx = edit["columnIdx"]
    edit_type = edit["type"]

    if edit_type in ("insert", "rename") and new_column_name is None:
        raise ValueError(
            "New column name is required for insert/rename operations"
        )

    max_index = column_count if edit_type == "insert" else column_count - 1
    if column_idx < 0 or column_idx > max_index:
        raise ValueError(f"Column index {column_idx} is out of bounds")
