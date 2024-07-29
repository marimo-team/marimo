# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Union,
    cast,
)

from marimo._data.models import ColumnSummary
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_column,
    format_row,
)
from marimo._plugins.ui._impl.tables.pandas_table import (
    PandasTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.pyarrow_table import (
    PyArrowTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    TableManager,
)

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

    def apply_formatting(self, format_mapping: FormatMapping) -> JsonTableData:
        if isinstance(self.data, dict) and all(
            isinstance(value, (list, tuple)) for value in self.data.values()
        ):
            return {
                col: format_column(col, values, format_mapping)  # type: ignore
                for col, values in self.data.items()
            }
        if isinstance(self.data, (list, tuple)) and all(
            isinstance(item, dict) for item in self.data
        ):
            return [
                format_row(row, format_mapping)  # type: ignore
                for row in self.data
            ]
        return self.data

    def supports_filters(self) -> bool:
        return False

    def to_data(
        self, format_mapping: Optional[FormatMapping] = None
    ) -> JSONType:
        return (
            self._normalize_data(self.apply_formatting(format_mapping))
            if format_mapping
            else self._normalize_data(self.data)
        )

    def to_csv(self, format_mapping: Optional[FormatMapping] = None) -> bytes:
        return self._as_table_manager().to_csv(format_mapping)

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

    def search(self, query: str) -> DefaultTableManager:
        query = query.lower()
        if isinstance(self.data, dict):
            mask: List[bool] = [
                any(
                    query in str(self.data[key][row]).lower()
                    for key in self.data.keys()
                )
                for row in range(self.get_num_rows() or 0)
            ]
            results: JsonTableData = {
                key: [value[i] for i, match in enumerate(mask) if match]
                for key, value in self.data.items()
            }
            return DefaultTableManager(results)
        return DefaultTableManager(
            [
                row
                for row in self._normalize_data(self.data)
                if any(query in str(v).lower() for v in row.values())
            ]
        )

    def get_row_headers(self) -> list[str]:
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

    def get_num_rows(self, force: bool = True) -> int:
        del force
        if isinstance(self.data, dict):
            return len(next(iter(self.data.values()), []))
        return len(self.data)

    def get_num_columns(self) -> int:
        return len(self.data) if isinstance(self.data, dict) else 1

    def get_column_names(self) -> List[str]:
        if isinstance(self.data, dict):
            return list(self.data.keys())
        first = next(iter(self.data), None)
        return list(first.keys()) if isinstance(first, dict) else ["value"]

    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        return sorted(
            self._as_table_manager().get_unique_column_values(column)
        )

    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> DefaultTableManager:
        normalized = self._normalize_data(self.data)
        try:
            data = sorted(normalized, key=lambda x: x[by], reverse=descending)
        except TypeError:
            # Handle when all values are not comparable
            data = sorted(
                normalized, key=lambda x: str(x[by]), reverse=descending
            )
        return DefaultTableManager(data)

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
                dict(zip(column_names, row_values))
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
        if not isinstance(data[0], dict):
            if not isinstance(data[0], (str, int, float, bool, type(None))):
                raise ValueError(
                    "data must be a sequence of JSON-serializable types, or a "
                    "sequence of dicts."
                )

            # we're going to assume that data has the right shape, after
            # having checked just the first entry
            casted = cast(List[Union[str, int, float, bool, MIME, None]], data)
            return [{"value": datum} for datum in casted]
        # Sequence of dicts
        return cast(List[Dict[str, Any]], data)
