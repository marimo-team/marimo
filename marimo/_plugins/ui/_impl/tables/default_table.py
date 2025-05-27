# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
import json
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Optional, Union, cast

from marimo._data.models import ColumnStats, ExternalDataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.mime import MIME
from marimo._plugins.core.json_encoder import WebComponentEncoder
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
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    FieldTypes,
    TableCell,
    TableCoordinate,
    TableManager,
)

JsonTableData = Union[
    Sequence[Union[str, int, float, bool, MIME, None]],
    Sequence[JSONType],
    list[JSONType],
    dict[str, Sequence[Union[str, int, float, bool, MIME, None]]],
    dict[str, JSONType],
]

# For non-column-oriented data, we use "key" and "value" as the column names
KEY = "key"
VALUE = "value"


class DefaultTableManager(TableManager[JsonTableData]):
    type = "dictionary"

    def __init__(self, data: JsonTableData):
        self.data = data
        self.is_column_oriented = _is_column_oriented(data)

    def supports_download(self) -> bool:
        # If we have pandas/polars/pyarrow, we can convert to CSV or JSON
        return (
            DependencyManager.pandas.has()
            or DependencyManager.polars.has()
            or DependencyManager.pyarrow.has()
        )

    def apply_formatting(
        self, format_mapping: Optional[FormatMapping]
    ) -> TableManager[JsonTableData]:
        if not format_mapping:
            return self

        if isinstance(self.data, dict) and self.is_column_oriented:
            return DefaultTableManager(
                {
                    col: format_column(col, values, format_mapping)  # type: ignore
                    for col, values in self.data.items()
                }
            )
        if isinstance(self.data, (list, tuple)) and all(
            isinstance(item, dict) for item in self.data
        ):
            return DefaultTableManager(
                [
                    format_row(row, format_mapping)  # type: ignore
                    for row in self.data
                ]
            )
        return self

    def supports_filters(self) -> bool:
        return False

    def to_csv_str(
        self, format_mapping: Optional[FormatMapping] = None
    ) -> str:
        if isinstance(self.data, dict) and not self.is_column_oriented:
            return DefaultTableManager(
                self._normalize_data(self.data)
            ).to_csv_str(format_mapping)

        return self._as_table_manager().to_csv_str(format_mapping)

    def to_json_str(
        self, format_mapping: Optional[FormatMapping] = None
    ) -> str:
        return json.dumps(
            self._normalize_data(self.apply_formatting(format_mapping).data),
            cls=WebComponentEncoder,
        )

    def to_parquet(self) -> bytes:
        if isinstance(self.data, dict) and not self.is_column_oriented:
            return DefaultTableManager(
                self._normalize_data(self.data)
            ).to_parquet()
        return self._as_table_manager().to_parquet()

    def select_rows(self, indices: list[int]) -> DefaultTableManager:
        if isinstance(self.data, dict):
            # Column major data
            if self.is_column_oriented:
                new_data: dict[Any, Any] = {
                    key: [cast(list[JSONType], value)[i] for i in indices]
                    for key, value in self.data.items()
                }
                return DefaultTableManager(new_data)
            else:
                return DefaultTableManager(
                    self._normalize_data(self.data)
                ).select_rows(indices)
        # Row major data
        return DefaultTableManager([self.data[i] for i in indices])

    def select_columns(self, columns: list[str]) -> DefaultTableManager:
        column_set = set(columns)
        # Column major data
        if isinstance(self.data, dict):
            new_data: dict[str, Any] = {
                key: value
                for key, value in self.data.items()
                if key in column_set
            }
            return DefaultTableManager(new_data)
        # Row major data
        return DefaultTableManager(
            [
                {key: row[key] for key in column_set}
                for row in self._normalize_data(self.data)
            ]
        )

    def select_cells(self, cells: list[TableCoordinate]) -> list[TableCell]:
        if not cells:
            return []

        selected_cells: list[TableCell] = []
        if (
            self.is_column_oriented
            and isinstance(self.data, dict)
            and all(isinstance(v, list) for v in self.data.values())
        ):
            for row_id, column_name in cells:
                column = self.data[column_name]
                if isinstance(column, Sequence):
                    selected_cells.append(
                        TableCell(
                            row=row_id,
                            column=column_name,
                            value=column[int(row_id)],
                        )
                    )
        elif isinstance(self.data, dict):
            rows_of_dict = list(self.data.items())
            for row_id, column_name in cells:
                value = (
                    rows_of_dict[int(row_id)][0]
                    if column_name == "key"
                    else rows_of_dict[int(row_id)][1]
                )
                selected_cells.append(
                    TableCell(row=row_id, column=column_name, value=value)
                )
        elif isinstance(self.data, list):
            rows_of_list = self.data
            for row_id, column_name in cells:
                row_index = int(row_id)
                if row_index < 0 or row_index > len(rows_of_list) - 1:
                    continue

                row = rows_of_list[row_index]
                if isinstance(row, dict) and column_name in row:
                    selected_cells.append(
                        TableCell(
                            row=row_id,
                            column=column_name,
                            value=row[column_name],
                        )
                    )
                elif not isinstance(row, list) and column_name == "value":
                    selected_cells.append(
                        TableCell(row=row_id, column=column_name, value=row)
                    )

        return selected_cells

    def drop_columns(self, columns: list[str]) -> DefaultTableManager:
        return self.select_columns(
            list(set(self.get_column_names()) - set(columns))
        )

    def take(self, count: int, offset: int) -> DefaultTableManager:
        if count < 0:
            raise ValueError("Count must be a positive integer")
        if offset < 0:
            raise ValueError("Offset must be a non-negative integer")

        if isinstance(self.data, dict):
            if self.is_column_oriented:
                return DefaultTableManager(
                    cast(
                        JsonTableData,
                        {
                            key: cast(list[Any], value)[
                                offset : offset + count
                            ]
                            for key, value in self.data.items()
                        },
                    )
                )
            return DefaultTableManager(
                self._normalize_data(self.data)[offset : offset + count]
            )
        return DefaultTableManager(self.data[offset : offset + count])

    def search(self, query: str) -> DefaultTableManager:
        query = query.lower()
        if isinstance(self.data, dict) and self.is_column_oriented:
            mask: list[bool] = [
                any(
                    query in str(cast(list[Any], self.data[key])[row]).lower()
                    for key in self.data.keys()
                )
                for row in range(self.get_num_rows() or 0)
            ]
            results = {
                key: [
                    cast(list[Any], value)[i]
                    for i, match in enumerate(mask)
                    if match
                ]
                for key, value in self.data.items()
            }
            return DefaultTableManager(cast(JsonTableData, results))
        return DefaultTableManager(
            [
                row
                for row in self._normalize_data(self.data)
                if any(query in str(v).lower() for v in row.values())
            ]
        )

    def get_row_headers(self) -> list[str]:
        return []

    @functools.lru_cache(maxsize=5)  # noqa: B019
    def calculate_top_k_rows(
        self, column: ColumnName, k: int
    ) -> list[tuple[Any, int]]:
        column_names = self.get_column_names()
        if column not in column_names:
            raise ValueError(f"Column {column} not found in table.")

        grouped: dict[str, int] = defaultdict(int)
        if isinstance(self.data, dict):
            if self.is_column_oriented:
                # Handle column-oriented data
                for value in cast(list[Any], self.data[column]):
                    grouped[value] += 1
            else:
                # In this case, the data is a dict of key-value pairs
                # where the key is the row identifier and the value is the data
                for key, value in self.data.items():
                    if column == KEY:
                        grouped[key] += 1
                    elif column == VALUE:
                        grouped[value] += 1
        else:
            # Handle row-oriented data
            for row in self.data:
                if isinstance(row, dict) and column in row:
                    grouped[row[column]] += 1

        sorted_grouped = sorted(
            grouped.items(), key=lambda x: x[1], reverse=True
        )
        top_k = sorted_grouped[:k]

        return [(value, count) for value, count in top_k]

    def get_field_type(
        self, column_name: str
    ) -> tuple[FieldType, ExternalDataType]:
        del column_name
        return ("unknown", "object")

    # By default, don't provide any field types
    # so the frontend can infer them
    def get_field_types(self) -> FieldTypes:
        return []

    def _as_table_manager(self) -> TableManager[Any]:
        if DependencyManager.pandas.has():
            import pandas as pd

            return PandasTableManagerFactory.create()(pd.DataFrame(self.data))
        if DependencyManager.polars.has():
            import polars as pl

            if isinstance(self.data, dict) and not self.is_column_oriented:
                return PolarsTableManagerFactory.create()(
                    pl.DataFrame(self._normalize_data(self.data))
                )

            return PolarsTableManagerFactory.create()(
                pl.DataFrame(cast(Any, self.data))
            )

        raise ValueError("No supported table libraries found.")

    def get_stats(self, column: str) -> ColumnStats:
        del column
        return ColumnStats()

    def get_num_rows(self, force: bool = True) -> int:
        del force
        if isinstance(self.data, dict):
            if self.is_column_oriented:
                first = next(iter(self.data.values()), None)
                return len(cast(list[Any], first))
            else:
                return len(self.data)
        return len(self.data)

    def get_num_columns(self) -> int:
        return len(self.data) if isinstance(self.data, dict) else 1

    def get_column_names(self) -> list[str]:
        if isinstance(self.data, dict):
            if not self.is_column_oriented:
                return [KEY, VALUE]
            return list(self.data.keys())
        first = next(iter(self.data), None)
        return list(first.keys()) if isinstance(first, dict) else ["value"]

    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        return sorted(
            self._as_table_manager().get_unique_column_values(column)
        )

    def get_sample_values(self, column: str) -> list[Any]:
        return self._as_table_manager().get_sample_values(column)

    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> DefaultTableManager:
        if isinstance(self.data, dict) and self.is_column_oriented:
            # For column-oriented data, extract the sort column and get sorted indices
            sort_column = cast(list[Any], self.data[by])
            try:
                sorted_indices = sorted(
                    range(len(sort_column)),
                    key=lambda i: sort_column[i],
                    reverse=descending,
                )
            except TypeError:
                # Handle when values are not comparable
                def sort_func_str(i: int) -> tuple[bool, str] | str:
                    # For ascending, generate a tuple of (is_none, value)
                    # (True, None) will be for None values
                    # (False, x) will be for other values.
                    # As False < True, None values will be sorted to the end.

                    # For descending, (is_not_none, value) tuple
                    # (False, None) will be for None values.
                    # (True, x) will be for other values.
                    # As True > False, other values come before None values
                    if descending:
                        return (
                            sort_column[i] is not None,
                            str(sort_column[i]),
                        )
                    else:
                        return str(sort_column[i])

                sorted_indices = sorted(
                    range(len(sort_column)),
                    key=sort_func_str,
                    reverse=descending,
                )
            # Apply sorted indices to each column while maintaining column orientation
            return DefaultTableManager(
                cast(
                    JsonTableData,
                    {
                        col: [
                            cast(list[Any], values)[i] for i in sorted_indices
                        ]
                        for col, values in self.data.items()
                    },
                )
            )

        # For row-major data, continue with existing logic
        normalized = self._normalize_data(self.data)
        try:

            def sort_func_col(x: dict[str, Any]) -> tuple[bool, Any]:
                is_none = x[by] is not None if descending else x[by] is None
                return (is_none, x[by])

            data = sorted(normalized, key=sort_func_col, reverse=descending)
        except TypeError:
            # Handle when all values are not comparable
            def sort_func_col_str(x: dict[str, Any]) -> tuple[bool, str]:
                is_none = x[by] is not None if descending else x[by] is None
                return (is_none, str(x[by]))

            data = sorted(
                normalized, key=sort_func_col_str, reverse=descending
            )
        return DefaultTableManager(data)

    @staticmethod
    def is_type(value: Any) -> bool:
        return isinstance(value, (list, tuple, dict))

    @staticmethod
    def _normalize_data(data: JsonTableData) -> list[dict[str, Any]]:
        # If it is a dict of lists (column major),
        # convert to list of dicts (row major)
        if isinstance(data, dict) and _is_column_oriented(data):
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

        # If its a dictionary, convert to key-value pairs
        if isinstance(data, dict):
            return [{KEY: key, VALUE: value} for key, value in data.items()]

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
            casted = cast(list[Union[str, int, float, bool, MIME, None]], data)
            return [{"value": datum} for datum in casted]
        # Sequence of dicts
        return cast(list[dict[str, Any]], data)


def _is_column_oriented(data: JsonTableData) -> bool:
    return isinstance(data, dict) and all(
        isinstance(value, (list, tuple)) for value in data.values()
    )
