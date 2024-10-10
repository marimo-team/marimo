# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    List,
    Optional,
    TypedDict,
    Union,
)

import narwhals.stable.v1 as nw
from narwhals.typing import IntoDataFrame

import marimo._output.data.data as mo_data
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.tables.utils import get_table_manager


@dataclass
class DataEditorValue:
    # Row-oriented data
    data: List[Dict[str, Any]]


class PositionalEdit(TypedDict):
    rowIdx: int
    columnId: str
    value: Any


class DataEdits(TypedDict):
    edits: List[PositionalEdit]


RowOrientedData = List[Dict[str, Any]]
ColumnOrientedData = Dict[str, List[Any]]


@mddoc
class data_editor(
    UIElement[
        DataEdits,
        Union[RowOrientedData, ColumnOrientedData, IntoDataFrame],
    ]
):
    """
    **[EXPERIMENTAL]**

    This component is experimental and intentionally limited in features,
    if you have any feature requests, please file an issue at
    https://github.com/marimo-team/marimo/issues.

    A data editor component for editing tabular data.

    The data can be supplied as:
    1. a Pandas, Polars, or Pyarrow DataFrame
    2. a list of dicts, with one dict for each row, keyed by column names
    3. a dict of lists, with each list representing a column

    **Examples.**

    Create a data editor from a Pandas dataframe:

    ```python
    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
    editor = mo.ui.experimental_data_editor(data=df, label="Edit Data")
    ```

    Create a data editor from a list of dicts:

    ```python
    data = [{"A": 1, "B": "a"}, {"A": 2, "B": "b"}, {"A": 3, "B": "c"}]
    editor = mo.ui.experimental_data_editor(data=data, label="Edit Data")
    ```

    Create a data editor from a dict of lists:

    ```python
    data = {"A": [1, 2, 3], "B": ["a", "b", "c"]}
    editor = mo.ui.experimental_data_editor(data=data, label="Edit Data")
    ```

    **Attributes.**

    - `value`: the current state of the edited data
    - `data`: the original data passed to the editor

    **Initialization Args.**

    - `data`: The data to be edited. Can be a Pandas dataframe,
        a list of dicts, or a dict of lists.
    - `label`: markdown label for the element
    - `on_change`: optional callback to run when this element's value changes
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
    ) -> None:
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
) -> Union[RowOrientedData, ColumnOrientedData, IntoDataFrame]:
    if len(edits["edits"]) == 0:
        return data
    # If row-oriented, apply edits to the data
    if isinstance(data, list):
        return _apply_edits_row_oriented(data, edits)
    # If column-oriented, apply edits to the data
    elif isinstance(data, dict):
        return _apply_edits_column_oriented(data, edits)

    # narwhalify
    try:
        return _apply_edits_dataframe(data, edits)  # type: ignore[no-any-return]
    except Exception as e:
        raise ValueError(
            f"Data editor does not support this type of data: {type(data)}"
        ) from e


def _apply_edits_column_oriented(
    data: ColumnOrientedData,
    edits: DataEdits,
) -> ColumnOrientedData:
    for edit in edits["edits"]:
        column = data[edit["columnId"]]
        if edit["rowIdx"] >= len(column):
            # Extend the column with None values up to the new row index
            column.extend([None] * (edit["rowIdx"] - len(column) + 1))
        column[edit["rowIdx"]] = edit["value"]

    return data


def _apply_edits_row_oriented(
    data: RowOrientedData,
    edits: DataEdits,
) -> RowOrientedData:
    for edit in edits["edits"]:
        if edit["rowIdx"] >= len(data):
            # Create a new row with None values for all columns
            new_row = {col: None for col in data[0].keys()}
            data.append(new_row)
        data[edit["rowIdx"]][edit["columnId"]] = edit["value"]

    return data


@nw.narwhalify
def _apply_edits_dataframe(
    df: nw.DataFrame[Any], edits: DataEdits
) -> nw.DataFrame[Any]:
    column_oriented = df.to_dict(as_series=False)
    new_data = _apply_edits_column_oriented(column_oriented, edits)
    native_namespace = nw.get_native_namespace(df)
    return nw.from_dict(new_data, native_namespace=native_namespace)
