# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Generic, NamedTuple, Optional, TypeVar, Union

from marimo._data.models import ColumnStats, DataType, ExternalDataType
from marimo._plugins.ui._impl.tables.format import FormatMapping

T = TypeVar("T")

ColumnName = str
RowId = str
FieldType = DataType
FieldTypes = list[tuple[ColumnName, tuple[FieldType, ExternalDataType]]]


class TableCoordinate(NamedTuple):
    row_id: Union[int, str]
    column_name: str


@dataclass
class TableCell:
    row: Union[int, str]
    column: str
    value: Any | None

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to cell values."""
        if key not in ["row", "column", "value"]:
            raise KeyError(f"Invalid key: {key}")
        return getattr(self, key)


class TableManager(abc.ABC, Generic[T]):
    # Upper limit for column summaries
    # The only sets the default to show column summaries,
    # but it can be overridden by the user
    DEFAULT_SUMMARY_CHARTS_COLUMN_LIMIT = 40
    # Upper limit for frontend table component to show column summary charts
    # to ensure browser performance
    DEFAULT_SUMMARY_CHARTS_ROW_LIMIT = 20_000
    # Lower limit for frontend to show column summary charts, since for
    # very small tables column summaries just take up space.
    DEFAULT_SUMMARY_CHARTS_MINIMUM_ROWS = 11
    # Upper limit for column summaries to avoid hanging up the kernel
    # Note: Keep this value in sync with DataTablePlugin's banner text
    DEFAULT_SUMMARY_STATS_ROW_LIMIT = 1_000_000

    type: str = ""

    def __init__(self, data: T) -> None:
        self.data = data

    def supports_download(self) -> bool:
        return True

    def supports_selection(self) -> bool:
        return True

    def supports_altair(self) -> bool:
        return True

    @abc.abstractmethod
    def apply_formatting(
        self, format_mapping: Optional[FormatMapping]
    ) -> TableManager[Any]:
        pass

    @abc.abstractmethod
    def supports_filters(self) -> bool:
        pass

    @abc.abstractmethod
    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> TableManager[Any]:
        pass

    @abc.abstractmethod
    def to_csv_str(
        self,
        format_mapping: Optional[FormatMapping] = None,
    ) -> str:
        pass

    def to_csv(
        self,
        format_mapping: Optional[FormatMapping] = None,
    ) -> bytes:
        return self.to_csv_str(format_mapping).encode("utf-8")

    def to_arrow_ipc(self) -> bytes:
        raise NotImplementedError("Arrow format not supported")

    @abc.abstractmethod
    def to_json_str(
        self, format_mapping: Optional[FormatMapping] = None
    ) -> str:
        pass

    def to_json(self, format_mapping: Optional[FormatMapping] = None) -> bytes:
        return self.to_json_str(format_mapping).encode("utf-8")

    @abc.abstractmethod
    def to_parquet(self) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def select_rows(self, indices: list[int]) -> TableManager[Any]:
        pass

    @abc.abstractmethod
    def select_columns(self, columns: list[str]) -> TableManager[Any]:
        pass

    @abc.abstractmethod
    def select_cells(self, cells: list[TableCoordinate]) -> list[TableCell]:
        pass

    @abc.abstractmethod
    def drop_columns(self, columns: list[str]) -> TableManager[Any]:
        pass

    @abc.abstractmethod
    def get_row_headers(self) -> list[str]:
        pass

    @abc.abstractmethod
    def get_field_type(
        self, column_name: str
    ) -> tuple[FieldType, ExternalDataType]:
        pass

    def get_field_types(self) -> FieldTypes:
        return [
            (column_name, self.get_field_type(column_name))
            for column_name in self.get_column_names()
        ]

    @abc.abstractmethod
    def take(self, count: int, offset: int) -> TableManager[Any]:
        pass

    @abc.abstractmethod
    def search(self, query: str) -> TableManager[Any]:
        pass

    @staticmethod
    @abc.abstractmethod
    def is_type(value: Any) -> bool:
        pass

    @abc.abstractmethod
    def get_stats(self, column: str) -> ColumnStats:
        pass

    @abc.abstractmethod
    def get_num_rows(self, force: bool = True) -> Optional[int]:
        # This can be expensive to compute,
        # so we allow optionals
        pass

    @abc.abstractmethod
    def get_num_columns(self) -> int:
        pass

    @abc.abstractmethod
    def get_column_names(self) -> list[str]:
        pass

    @abc.abstractmethod
    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        pass

    @abc.abstractmethod
    def get_sample_values(self, column: str) -> list[Any]:
        pass

    @abc.abstractmethod
    def calculate_top_k_rows(
        self, column: ColumnName, k: int
    ) -> list[tuple[Any, int]]:
        pass

    def __repr__(self) -> str:
        rows = self.get_num_rows(force=False)
        columns = self.get_num_columns()
        if rows is None:
            return f"{self.type}: {columns:,} columns"
        return f"{self.type}: {rows:,} rows x {columns:,} columns"


class TableManagerFactory(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def package_name() -> str:
        pass

    @staticmethod
    @abc.abstractmethod
    def create() -> type[TableManager[Any]]:
        pass
