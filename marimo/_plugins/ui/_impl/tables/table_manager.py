# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
)

from marimo._data.models import (
    BinValue,
    ColumnStats,
    DataType,
    ExternalDataType,
)
from marimo._plugins.ui._impl.tables.format import FormatMapping

if TYPE_CHECKING:
    from marimo._plugins.ui._impl.table import SortArgs

T = TypeVar("T")

ColumnName = str
RowId = str
FieldType = DataType
FieldTypes = list[tuple[ColumnName, tuple[FieldType, ExternalDataType]]]


class TableCoordinate(NamedTuple):
    """Identifies a single cell in a table by row ID and column name."""

    row_id: Union[int, str]
    column_name: str


@dataclass
class TableCell:
    """Represents a single cell value at a specific row and column."""

    row: Union[int, str]
    column: str
    value: Any | None

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to cell values."""
        if key not in ["row", "column", "value"]:
            raise KeyError(f"Invalid key: {key}")
        return getattr(self, key)


class TableManager(abc.ABC, Generic[T]):
    """Abstract base class defining the interface for all table backend managers."""

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
        """Return whether the table supports file download."""
        return True

    def supports_selection(self) -> bool:
        """Return whether the table supports row selection."""
        return True

    def supports_altair(self) -> bool:
        """Return whether the table data can be passed to Altair for charting."""
        return True

    @abc.abstractmethod
    def apply_formatting(
        self, format_mapping: Optional[FormatMapping]
    ) -> TableManager[Any]:
        """Apply a format mapping to the table and return the formatted manager."""
        pass

    @abc.abstractmethod
    def supports_filters(self) -> bool:
        """Return whether the table backend supports column filtering."""
        pass

    @abc.abstractmethod
    def sort_values(self, by: list[SortArgs]) -> TableManager[Any]:
        """Return a new manager with rows sorted according to the given sort arguments."""
        pass

    @abc.abstractmethod
    def to_csv_str(
        self,
        format_mapping: Optional[FormatMapping] = None,
        separator: str | None = None,
    ) -> str:
        """Serialize the table to a CSV-formatted string."""
        pass

    def to_csv(
        self,
        format_mapping: Optional[FormatMapping] = None,
        encoding: str | None = "utf-8",
        separator: str | None = None,
    ) -> bytes:
        """Serialize the table to CSV bytes using the given encoding."""
        resolved_encoding = encoding or "utf-8"
        return self.to_csv_str(format_mapping, separator=separator).encode(
            resolved_encoding
        )

    def to_arrow_ipc(self) -> bytes:
        """Serialize the table to Arrow IPC format bytes."""
        raise NotImplementedError("Arrow format not supported")

    @abc.abstractmethod
    def to_json_str(
        self,
        format_mapping: Optional[FormatMapping] = None,
        strict_json: bool = False,
        ensure_ascii: bool = True,
    ) -> str:
        """Serialize the table to a JSON-formatted string."""
        pass

    def to_json(
        self,
        format_mapping: Optional[FormatMapping] = None,
        strict_json: bool = False,  # Whether the result should be strictly JSON compliant (eg. nan -> null)
        encoding: str | None = "utf-8",
        ensure_ascii: bool = True,
    ) -> bytes:
        """Serialize the table to JSON bytes using the given encoding."""
        resolved_encoding = encoding or "utf-8"
        return self.to_json_str(
            format_mapping=format_mapping,
            strict_json=strict_json,
            ensure_ascii=ensure_ascii,
        ).encode(resolved_encoding)

    @abc.abstractmethod
    def to_parquet(self) -> bytes:
        """Serialize the table to Parquet format bytes."""
        raise NotImplementedError

    @abc.abstractmethod
    def select_rows(self, indices: list[int]) -> TableManager[Any]:
        """Return a new manager containing only the rows at the given indices."""
        pass

    @abc.abstractmethod
    def select_columns(self, columns: list[str]) -> TableManager[Any]:
        """Return a new manager containing only the specified columns."""
        pass

    @abc.abstractmethod
    def select_cells(self, cells: list[TableCoordinate]) -> list[TableCell]:
        """Return the cell values at the given row/column coordinates."""
        pass

    @abc.abstractmethod
    def drop_columns(self, columns: list[str]) -> TableManager[Any]:
        """Return a new manager with the specified columns removed."""
        pass

    @abc.abstractmethod
    def get_row_headers(self) -> FieldTypes:
        """Return field type information for the row-header columns."""
        pass

    @abc.abstractmethod
    def get_field_type(
        self, column_name: str
    ) -> tuple[FieldType, ExternalDataType]:
        """Return the marimo field type and external type string for a column."""
        pass

    def get_field_types(self) -> FieldTypes:
        """Return field type information for all columns, converting names to strings."""
        # Some column names may be non-string (sqlalchemy quoted names), so we convert them to strings
        return [
            (str(column_name), self.get_field_type(column_name))
            for column_name in self.get_column_names()
        ]

    @abc.abstractmethod
    def take(self, count: int, offset: int) -> TableManager[Any]:
        """Return a new manager with at most `count` rows starting at `offset`."""
        pass

    @abc.abstractmethod
    def search(self, query: str) -> TableManager[Any]:
        """Return a new manager with rows that match the search query."""
        pass

    @staticmethod
    @abc.abstractmethod
    def is_type(value: Any) -> bool:
        """Return True if the given value is a type handled by this manager."""
        pass

    @abc.abstractmethod
    def get_stats(self, column: str) -> ColumnStats:
        """Return summary statistics for the given column."""
        pass

    @abc.abstractmethod
    def get_bin_values(
        self, column: ColumnName, num_bins: int
    ) -> list[BinValue]:
        """Return histogram bin values for the given column."""
        pass

    @abc.abstractmethod
    def get_num_rows(self, force: bool = True) -> Optional[int]:
        """Return the number of rows, or None if unknown without forcing collection."""
        # This can be expensive to compute,
        # so we allow optionals
        pass

    @abc.abstractmethod
    def get_num_columns(self) -> int:
        """Return the number of columns in the table."""
        pass

    @abc.abstractmethod
    def get_column_names(self) -> list[str]:
        """Return the list of column names in the table."""
        pass

    @abc.abstractmethod
    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        """Return the unique values present in the given column."""
        pass

    @abc.abstractmethod
    def get_sample_values(self, column: str) -> list[Any]:
        """Return a small sample of representative values from the given column."""
        pass

    @abc.abstractmethod
    def calculate_top_k_rows(
        self, column: ColumnName, k: int
    ) -> list[tuple[Any, int]]:
        """Return the top-k most frequent values and their counts for the given column."""
        pass

    def __repr__(self) -> str:
        rows = self.get_num_rows(force=False)
        columns = self.get_num_columns()
        if rows is None:
            return f"{self.type}: {columns:,} columns"
        return f"{self.type}: {rows:,} rows x {columns:,} columns"


class TableManagerFactory(abc.ABC):
    """Abstract factory for creating TableManager instances for a specific package."""

    @staticmethod
    @abc.abstractmethod
    def package_name() -> str:
        """Return the name of the package this factory supports."""
        pass

    @staticmethod
    @abc.abstractmethod
    def create() -> type[TableManager[Any]]:
        """Return the TableManager class for this factory's package."""
        pass
