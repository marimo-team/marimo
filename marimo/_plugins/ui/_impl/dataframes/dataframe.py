# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Final,
    List,
    Optional,
    Union,
)

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._impl.dataframes.handlers import TransformsContainer
from marimo._plugins.ui._impl.dataframes.transforms import Transformations
from marimo._plugins.ui._impl.tables.pandas_table import (
    PandasTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import ColumnName

if TYPE_CHECKING:
    import pandas as pd

from dataclasses import dataclass

import marimo._output.data.data as mo_data
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.functions import EmptyArgs, Function
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class GetDataFrameResponse:
    url: str
    has_more: bool
    total_rows: int
    row_headers: List[tuple[str, List[str | int | float]]]


@dataclass
class GetColumnValuesArgs:
    column: str


@dataclass
class GetColumnValuesResponse:
    values: List[str | int | float]
    too_many_values: bool


@dataclass
class SortValuesArgs:
    by: ColumnName
    descending: bool


class ColumnNotFound(Exception):
    def __init__(self, column: str):
        self.column = column
        super().__init__(f"Column {column} does not exist")


class GetDataFrameError(Exception):
    def __init__(self, error: str):
        self.error = error
        super().__init__(error)


@mddoc
class dataframe(UIElement[Dict[str, Any], "pd.DataFrame"]):
    """
    Run transformations on a DataFrame or series.
    Currently only Pandas DataFrames are supported.

    For Polars DataFrames, you can convert to a Pandas DataFrame.
    However the returned DataFrame will still be a Pandas DataFrame,
    so you will need to convert back to a Polars DataFrame if you want.

    **Example.**

    ```python
    dataframe = mo.ui.dataframe(data)
    ```

    ```python
    dataframe = mo.ui.dataframe(polars_df.to_pandas())
    ```

    **Attributes.**

    - `value`: the transformed DataFrame or series

    **Initialization Args.**

    - `df`: the DataFrame or series to transform
    - `page_size`: the number of rows to show in the table
    """

    _name: Final[str] = "marimo-dataframe"

    # Only get the first 100 (for performance reasons)
    # Could make this configurable in the arguments later if desired.
    DISPLAY_LIMIT = 100

    def __init__(
        self,
        df: pd.DataFrame,
        on_change: Optional[Callable[[pd.DataFrame], None]] = None,
        page_size: Optional[int] = 5,
    ) -> None:
        DependencyManager.require_pandas("to use the dataframe plugin")
        import pandas as pd

        if not isinstance(df, pd.DataFrame):
            raise ValueError(
                "Dataframe plugin only supports Pandas DataFrames"
            )

        # HACK: this is a hack to get the name of the variable that was passed
        dataframe_name = "df"
        try:
            frame = inspect.currentframe()
            if frame is not None and frame.f_back is not None:
                for (
                    var_name,
                    var_value,
                ) in frame.f_back.f_locals.items():
                    if var_value is df:
                        dataframe_name = var_name
                        break
        except Exception:
            pass

        self._data = df
        self._manager = PandasTableManagerFactory.create()(df)
        self._transform_container = TransformsContainer(df)
        self._error: Optional[str] = None

        super().__init__(
            component_name=dataframe._name,
            initial_value={
                "transforms": [],
            },
            on_change=on_change,
            label="",
            args={
                "columns": self._get_column_types(),
                "dataframe-name": dataframe_name,
                "total": len(df),
                "page-size": page_size,
            },
            functions=(
                Function(
                    name=self.get_dataframe.__name__,
                    arg_cls=EmptyArgs,
                    function=self.get_dataframe,
                ),
                Function(
                    name=self.get_column_values.__name__,
                    arg_cls=GetColumnValuesArgs,
                    function=self.get_column_values,
                ),
                Function(
                    name=self.sort_values.__name__,
                    arg_cls=SortValuesArgs,
                    function=self.sort_values,
                ),
            ),
        )

    def _get_column_types(self) -> List[List[Union[str, int]]]:
        return [[name, dtype] for name, dtype in self._data.dtypes.items()]  # type: ignore

    def get_dataframe(self, _args: EmptyArgs) -> GetDataFrameResponse:
        if self._error is not None:
            raise GetDataFrameError(self._error)

        manager = PandasTableManagerFactory.create()(
            self._value.head(self.DISPLAY_LIMIT)
        )
        url = mo_data.csv(manager.to_csv()).url
        total_rows = len(self._value)
        return GetDataFrameResponse(
            url=url,
            total_rows=total_rows,
            has_more=total_rows > self.DISPLAY_LIMIT,
            row_headers=manager.get_row_headers(),
        )

    def get_column_values(
        self, args: GetColumnValuesArgs
    ) -> GetColumnValuesResponse:
        """Get all the unique values in a column."""
        LIMIT = 500

        if args.column not in self._data.columns:
            raise ColumnNotFound(args.column)

        # We get the unique values from the original dataframe, not the
        # transformed one
        unique_values = self._data[args.column].unique().tolist()
        if len(unique_values) <= LIMIT:
            return GetColumnValuesResponse(
                values=list(sorted(unique_values, key=str)),
                too_many_values=False,
            )
        else:
            return GetColumnValuesResponse(
                values=[],
                too_many_values=True,
            )

    def _convert_value(self, value: Dict[str, Any]) -> pd.DataFrame:
        if value is None:
            self._error = None
            return self._data

        try:
            transformations = parse_raw(value, Transformations)
            result = self._transform_container.apply(transformations)
            self._error = None
            return result
        except Exception as e:
            error = "Error applying dataframe transform: %s\n\n" % str(e)
            sys.stderr.write(error)
            self._error = error
            return self._data

    def sort_values(self, args: SortValuesArgs) -> Union[JSONType, str]:
        return (
            self._manager.sort_values(args.by, args.descending)
            .limit(self.DISPLAY_LIMIT)
            .to_data()
        )
