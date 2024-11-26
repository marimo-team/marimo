# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from typing import (
    Any,
    Generic,
    Optional,
    Tuple,
    TypeVar,
)

import marimo._output.data.data as mo_data
from marimo._data.models import ColumnSummary, DataType, ExternalDataType
from marimo._plugins.core.web_component import JSONType
from marimo._plugins.ui._impl.tables.format import FormatMapping

T = TypeVar("T")

ColumnName = str
FieldType = DataType
FieldTypes = list[Tuple[ColumnName, Tuple[FieldType, ExternalDataType]]]


class TableManager(abc.ABC, Generic[T]):
    # Upper limit for column summaries
    # The only sets the default to show column summaries,
    # but it can be overridden by the user
    DEFAULT_SUMMARY_CHARTS_COLUMN_LIMIT = 40
    # Upper limit for frontend table component to show column summary charts
    # to ensure browser performance
    DEFAULT_SUMMARY_CHARTS_ROW_LIMIT = 20_000
    # Upper limit for column summaries to avoid hanging up the kernel
    # Note: Keep this value in sync with DataTablePlugin's banner text
    DEFAULT_SUMMARY_STATS_ROW_LIMIT = 1_000_000

    type: str = ""

    def __init__(self, data: T) -> None:
        self.data = data

    def to_data(
        self,
        format_mapping: Optional[FormatMapping] = None,
    ) -> JSONType:
        """
        The best way to represent the data in a table as JSON.

        By default, this method calls `to_csv` and returns the result as
        a string.
        """
        return mo_data.csv(self.to_csv(format_mapping)).url

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
        raise NotImplementedError

    @abc.abstractmethod
    def supports_filters(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> TableManager[Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def to_csv(
        self,
        format_mapping: Optional[FormatMapping] = None,
    ) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def to_json(self) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    def select_rows(self, indices: list[int]) -> TableManager[Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def select_columns(self, columns: list[str]) -> TableManager[Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_row_headers(self) -> list[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_field_type(
        self, column_name: str
    ) -> Tuple[FieldType, ExternalDataType]:
        raise NotImplementedError

    def get_field_types(self) -> FieldTypes:
        return [
            (column_name, self.get_field_type(column_name))
            for column_name in self.get_column_names()
        ]

    @abc.abstractmethod
    def take(self, count: int, offset: int) -> TableManager[Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def search(self, query: str) -> TableManager[Any]:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def is_type(value: Any) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def get_summary(self, column: str) -> ColumnSummary:
        raise NotImplementedError

    @abc.abstractmethod
    def get_num_rows(self, force: bool = True) -> Optional[int]:
        # This can be expensive to compute,
        # so we allow optionals
        raise NotImplementedError

    @abc.abstractmethod
    def get_num_columns(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def get_column_names(self) -> list[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        raise NotImplementedError

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
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def create() -> type[TableManager[Any]]:
        raise NotImplementedError
