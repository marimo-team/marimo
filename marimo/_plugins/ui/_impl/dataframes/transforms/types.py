# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Generic,
    Literal,
    Optional,
    TypeVar,
    Union,
)

from narwhals.typing import IntoDataFrame, IntoLazyFrame

# Could be a DataFrame from pandas, polars, pyarrow, DataFrameProtocol, etc.
DataFrameType = Union[IntoDataFrame, IntoLazyFrame]

ColumnId = str
ColumnIds = list[ColumnId]
NumpyDataType = str
Operator = Literal[
    "==",
    "!=",
    "<",
    ">",
    "<",
    "<=",
    ">=",
    "is_true",
    "is_false",
    "is_null",
    "is_not_null",
    "equals",
    "does_not_equal",
    "contains",
    "regex",
    "starts_with",
    "ends_with",
    "in",
    "not_in",
]
Aggregation = Literal[
    "count",
    "sum",
    "mean",
    "median",
    "min",
    "max",
]
UniqueKeep = Literal["first", "last", "none", "any"]


class TransformType(Enum):
    """Enumeration of supported dataframe transform operations."""

    AGGREGATE = "aggregate"
    COLUMN_CONVERSION = "column_conversion"
    FILTER_ROWS = "filter_rows"
    GROUP_BY = "group_by"
    RENAME_COLUMN = "rename_column"
    SELECT_COLUMNS = "select_columns"
    SORT_COLUMN = "sort_column"
    SHUFFLE_ROWS = "shuffle_rows"
    SAMPLE_ROWS = "sample_rows"
    EXPLODE_COLUMNS = "explode_columns"
    EXPAND_DICT = "expand_dict"
    UNIQUE = "unique"
    PIVOT = "pivot"


@dataclass(frozen=True)
class Condition:
    """A single filter condition applied to a column with an operator and optional value."""

    column_id: ColumnId
    operator: Operator
    value: Optional[Any] = None

    def __hash__(self) -> int:
        return hash((self.column_id, self.operator, self.value))

    def __post_init__(self) -> None:
        if self.operator == "in" or self.operator == "not_in":
            if isinstance(self.value, list):
                # Hack to convert to tuple for frozen dataclass
                # Only tuples can be hashed
                object.__setattr__(self, "value", tuple(self.value))
            elif isinstance(self.value, tuple):
                pass
            else:
                raise ValueError(
                    "value must be a list or tuple for 'in' or 'not_in' operator"
                )


@dataclass
class ColumnConversionTransform:
    """Transform that casts a column to a specified data type."""

    type: Literal[TransformType.COLUMN_CONVERSION]
    column_id: ColumnId
    data_type: NumpyDataType
    errors: Literal["ignore", "raise"]


@dataclass
class RenameColumnTransform:
    """Transform that renames a column to a new name."""

    type: Literal[TransformType.RENAME_COLUMN]
    column_id: ColumnId
    new_column_id: ColumnId


@dataclass
class SortColumnTransform:
    """Transform that sorts a dataframe by a column in ascending or descending order."""

    type: Literal[TransformType.SORT_COLUMN]
    column_id: ColumnId
    ascending: bool
    na_position: Literal["first", "last"]


@dataclass
class FilterRowsTransform:
    """Transform that keeps or removes rows matching a set of conditions."""

    type: Literal[TransformType.FILTER_ROWS]
    operation: Literal["keep_rows", "remove_rows"]
    where: list[Condition]


@dataclass
class GroupByTransform:
    """Transform that groups rows by columns and applies an aggregation function."""

    type: Literal[TransformType.GROUP_BY]
    column_ids: ColumnIds
    drop_na: bool
    aggregation: Aggregation
    aggregation_column_ids: ColumnIds


@dataclass
class AggregateTransform:
    """Transform that applies one or more aggregation functions across specified columns."""

    type: Literal[TransformType.AGGREGATE]
    column_ids: ColumnIds
    aggregations: list[Aggregation]


@dataclass
class SelectColumnsTransform:
    """Transform that retains only the specified columns in the dataframe."""

    type: Literal[TransformType.SELECT_COLUMNS]
    column_ids: ColumnIds


@dataclass
class ShuffleRowsTransform:
    """Transform that randomly shuffles all rows using the given seed."""

    type: Literal[TransformType.SHUFFLE_ROWS]
    seed: int


@dataclass
class SampleRowsTransform:
    """Transform that randomly samples a fixed number of rows, with optional replacement."""

    type: Literal[TransformType.SAMPLE_ROWS]
    n: int
    replace: bool
    seed: int


@dataclass
class ExplodeColumnsTransform:
    """Transform that explodes list-like column values into separate rows."""

    type: Literal[TransformType.EXPLODE_COLUMNS]
    column_ids: ColumnIds


@dataclass
class ExpandDictTransform:
    """Transform that expands a dict-valued column into one column per key."""

    type: Literal[TransformType.EXPAND_DICT]
    column_id: ColumnId


@dataclass
class UniqueTransform:
    """Transform that removes duplicate rows based on specified columns and a keep strategy."""

    type: Literal[TransformType.UNIQUE]
    column_ids: ColumnIds
    keep: UniqueKeep


@dataclass
class PivotTransform:
    """Transform that pivots columns into a wide-format table using an aggregation function."""

    type: Literal[TransformType.PIVOT]
    column_ids: ColumnIds
    index_column_ids: ColumnIds
    value_column_ids: ColumnIds
    aggregation: Aggregation


Transform = Union[
    AggregateTransform,
    ColumnConversionTransform,
    FilterRowsTransform,
    PivotTransform,
    GroupByTransform,
    RenameColumnTransform,
    SelectColumnsTransform,
    SortColumnTransform,
    ShuffleRowsTransform,
    SampleRowsTransform,
    ExplodeColumnsTransform,
    ExpandDictTransform,
    UniqueTransform,
]


@dataclass
class Transformations:
    """An ordered list of transforms to apply sequentially to a dataframe."""

    transforms: list[Transform]


T = TypeVar("T")


class TransformHandler(abc.ABC, Generic[T]):
    """Abstract base class that defines handlers for each supported dataframe transform type."""

    @staticmethod
    @abc.abstractmethod
    def handle_column_conversion(
        df: T, transform: ColumnConversionTransform
    ) -> T:
        """Apply a column type-conversion transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_rename_column(df: T, transform: RenameColumnTransform) -> T:
        """Apply a column rename transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_sort_column(df: T, transform: SortColumnTransform) -> T:
        """Apply a column sort transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_filter_rows(df: T, transform: FilterRowsTransform) -> T:
        """Apply a row filter transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_group_by(df: T, transform: GroupByTransform) -> T:
        """Apply a group-by transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_aggregate(df: T, transform: AggregateTransform) -> T:
        """Apply an aggregate transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_select_columns(df: T, transform: SelectColumnsTransform) -> T:
        """Apply a select-columns transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_shuffle_rows(df: T, transform: ShuffleRowsTransform) -> T:
        """Apply a row shuffle transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_sample_rows(df: T, transform: SampleRowsTransform) -> T:
        """Apply a row sampling transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_explode_columns(df: T, transform: ExplodeColumnsTransform) -> T:
        """Apply a column explode transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_expand_dict(df: T, transform: ExpandDictTransform) -> T:
        """Apply a dict-expansion transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_unique(df: T, transform: UniqueTransform) -> T:
        """Apply a unique-rows transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_pivot(df: T, transform: PivotTransform) -> T:
        """Apply a pivot transform to the dataframe."""
        raise NotImplementedError

    @staticmethod
    def as_python_code(
        df: T, df_name: str, columns: list[str], transforms: list[Transform]
    ) -> str | None:
        """Return a Python code string representing the applied transforms, or None if unsupported."""
        del df_name, transforms, columns, df
        return None

    @staticmethod
    def as_sql_code(transformed_df: T) -> str | None:
        """Return a SQL string representing the transformed dataframe, or None if unsupported."""
        del transformed_df
        return None
