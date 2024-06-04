# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Sequence,
    Union,
    cast,
)

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._impl.tables.pandas_table import (
    PandasTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.pyarrow_table import (
    PyArrowTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager

JsonTableData = Union[
    Sequence[Union[str, int, float, bool, MIME, None]],
    Sequence[JSONType],
    List[JSONType],
    Dict[str, Sequence[Union[str, int, float, bool, MIME, None]]],
]


class DefaultTableManager(TableManager[JsonTableData]):
    type = "dictionary"

    def __init__(self, data: JsonTableData):
        self.data = data

    def supports_download(self) -> bool:
        # If we have pandas/polars/pyarrow, we can convert to CSV or JSON
        return (
            DependencyManager.has_pandas()
            or DependencyManager.has_polars()
            or DependencyManager.has_pyarrow()
        )

    def to_data(self) -> JSONType:
        return self._normalize_data(self.data)

    def to_csv(self) -> bytes:
        return self._as_table_manager().to_csv()

    def to_json(self) -> bytes:
        return self._as_table_manager().to_json()

    def select_rows(self, indices: List[int]) -> DefaultTableManager:
        # Column major data
        if isinstance(self.data, dict):
            new_data: Dict[Any, Any] = {
                key: [value[i] for i in indices]
                for key, value in self.data.items()
            }
            return DefaultTableManager(new_data)
        # Row major data
        return DefaultTableManager([self.data[i] for i in indices])

    def select_columns(self, columns: List[str]) -> DefaultTableManager:
        # Column major data
        if isinstance(self.data, dict):
            new_data: Dict[str, Any] = {
                key: value
                for key, value in self.data.items()
                if key in columns
            }
            return DefaultTableManager(new_data)
        # Row major data
        return DefaultTableManager(
            [
                {key: row[key] for key in columns}
                for row in self._normalize_data(self.data)
            ]
        )

    def limit(self, num: int) -> DefaultTableManager:
        if num < 0:
            raise ValueError("Limit must be a positive integer")
        if isinstance(self.data, dict):
            return DefaultTableManager(
                {key: value[:num] for key, value in self.data.items()}
            )
        return DefaultTableManager(self.data[:num])

    def get_row_headers(self) -> list[tuple[str, list[str | int | float]]]:
        return []

    def _as_table_manager(self) -> TableManager[Any]:
        if DependencyManager.has_pandas():
            import pandas as pd

            return PandasTableManagerFactory.create()(pd.DataFrame(self.data))
        if DependencyManager.has_polars():
            import polars as pl

            return PolarsTableManagerFactory.create()(pl.DataFrame(self.data))
        if DependencyManager.has_pyarrow():
            import pyarrow as pa

            if isinstance(self.data, dict):
                return PyArrowTableManagerFactory.create()(
                    pa.Table.from_pydict(self.data)
                )
            return PyArrowTableManagerFactory.create()(
                pa.Table.from_pylist(self._normalize_data(self.data))
            )

        raise ValueError("No supported table libraries found.")

    def get_summary(self, column: str) -> ColumnSummary:
        del column
        return ColumnSummary()

    def get_num_rows(self) -> int:
        if isinstance(self.data, dict):
            return len(next(iter(self.data.values()), []))
        return len(self.data)

    def get_num_columns(self) -> int:
        if isinstance(self.data, dict):
            return len(self.data)
        return 1

    def get_column_names(self) -> List[str]:
        if isinstance(self.data, dict):
            return list(self.data.keys())
        first = next(iter(self.data), None)
        if isinstance(first, dict):
            return list(first.keys())
        return ["value"]

    @staticmethod
    def is_type(value: Any) -> bool:
        return isinstance(value, (list, tuple, dict))

    @staticmethod
    def _normalize_data(data: JsonTableData) -> list[dict[str, Any]]:
        # If it is a dict of lists (column major),
        # convert to list of dicts (row major)
        if isinstance(data, dict) and all(
            isinstance(value, (list, tuple)) for value in data.values()
        ):
            # reshape column major
            #   { "col1": [1, 2, 3], "col2": [4, 5, 6], ... }
            # into row major
            #   [ {"col1": 1, "col2": 4}, {"col1": 2, "col2": 5 }, ...]
            column_values = data.values()
            column_names = list(data.keys())
            return [
                {key: value for key, value in zip(column_names, row_values)}
                for row_values in zip(*column_values)
            ]

        # Assert that data is a list
        if not isinstance(data, (list, tuple)):
            raise ValueError(
                "data must be a list or tuple or a dict of lists."
            )

        # Handle empty data
        if len(data) == 0:
            return []

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
        return cast(List[Dict[str, Any]], data)
