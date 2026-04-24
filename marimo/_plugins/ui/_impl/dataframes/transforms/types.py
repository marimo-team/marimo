# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import abc
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Literal, TypeVar, Union

from narwhals.typing import IntoDataFrame, IntoLazyFrame

# Could be a DataFrame from pandas, polars, pyarrow, DataFrameProtocol, etc.
# Use Union[] instead of X | Y — see altair_transformer.py for rationale.
DataFrameType = Union[IntoDataFrame, IntoLazyFrame]

ColumnId = str
ColumnIds = list[ColumnId]
NumpyDataType = str
Operator = Literal[
    "==",
    "!=",
    "<",
    ">",
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
    "between",
    "is_empty",
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
class RangeValue:
    min: int | float | str
    max: int | float | str


@dataclass(frozen=True)
class FilterCondition:
    column_id: ColumnId
    operator: Operator
    type: Literal["condition"] = "condition"
    value: Any | None = None
    negate: bool = False

    def __hash__(self) -> int:
        return hash(
            (self.type, self.column_id, self.operator, self.value, self.negate)
        )

    def __post_init__(self) -> None:
        if self.operator == "between" and isinstance(self.value, dict):
            if "min" not in self.value or "max" not in self.value:
                raise ValueError(
                    "value must be a dict with 'min' and 'max' keys for 'between' operator"
                )

            object.__setattr__(
                self,
                "value",
                RangeValue(
                    min=self.value["min"],
                    max=self.value["max"],
                ),
            )
        if self.operator == "between" and isinstance(self.value, RangeValue):
            # Only compare when both ends are comparable primitives —
            # strings vs. numbers would raise TypeError. The frontend
            # surfaces this as a dict; we accept RangeValue for programmatic
            # construction and still want a cheap sanity check.
            if (
                isinstance(self.value.min, (int, float))
                and isinstance(self.value.max, (int, float))
                and self.value.min > self.value.max
            ):
                raise ValueError(
                    "'between' filter requires min <= max, got "
                    f"min={self.value.min!r}, max={self.value.max!r}"
                )
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


@dataclass(frozen=True)
class FilterGroup:
    children: tuple[FilterCondition | FilterGroup, ...]
    type: Literal["group"] = "group"
    operator: Literal["and", "or"] = "and"
    negate: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.children, list):
            object.__setattr__(self, "children", tuple(self.children))
        # The operator is declared as Literal["and", "or"] but Python
        # doesn't enforce literals at runtime. A bogus value here would
        # silently fall through the downstream "and" combiner path and
        # produce wrong rows, so reject early.
        if self.operator not in ("and", "or"):
            raise ValueError(
                "FilterGroup.operator must be 'and' or 'or', "
                f"got {self.operator!r}"
            )


DTYPE_OPERATORS: dict[str, frozenset[Operator]] = {
    "number": frozenset(
        {
            "==",
            "!=",
            "<",
            ">",
            "<=",
            ">=",
            "is_null",
            "is_not_null",
            "in",
            "not_in",
            "between",
        }
    ),
    "boolean": frozenset({"is_true", "is_false", "is_null", "is_not_null"}),
    "str": frozenset(
        {
            "equals",
            "does_not_equal",
            "contains",
            "regex",
            "starts_with",
            "ends_with",
            "is_null",
            "is_not_null",
            "in",
            "not_in",
            "is_empty",
        }
    ),
    "temporal": frozenset(
        {"==", "!=", "<", ">", "<=", ">=", "is_null", "is_not_null", "between"}
    ),
}


def conditions_to_filter_group(
    conditions: list[FilterCondition],
) -> FilterGroup:
    return FilterGroup(
        type="group",
        operator="and",
        children=tuple(conditions),
        negate=False,
    )


def validate_operator_for_dtype(operator: Operator, dtype: str) -> bool:
    allowed = DTYPE_OPERATORS.get(dtype, frozenset())
    if not allowed:
        # unknown data type, allow all operators
        return True
    return operator in allowed


@dataclass
class ColumnConversionTransform:
    type: Literal[TransformType.COLUMN_CONVERSION]
    column_id: ColumnId
    data_type: NumpyDataType
    errors: Literal["ignore", "raise"]


@dataclass
class RenameColumnTransform:
    type: Literal[TransformType.RENAME_COLUMN]
    column_id: ColumnId
    new_column_id: ColumnId


@dataclass
class SortColumnTransform:
    type: Literal[TransformType.SORT_COLUMN]
    column_id: ColumnId
    ascending: bool
    na_position: Literal["first", "last"]


@dataclass
class FilterRowsTransform:
    type: Literal[TransformType.FILTER_ROWS]
    operation: Literal["keep_rows", "remove_rows"]
    where: FilterGroup


@dataclass
class GroupByTransform:
    type: Literal[TransformType.GROUP_BY]
    column_ids: ColumnIds
    drop_na: bool
    aggregation: Aggregation
    aggregation_column_ids: ColumnIds


@dataclass
class AggregateTransform:
    type: Literal[TransformType.AGGREGATE]
    column_ids: ColumnIds
    aggregations: list[Aggregation]


@dataclass
class SelectColumnsTransform:
    type: Literal[TransformType.SELECT_COLUMNS]
    column_ids: ColumnIds


@dataclass
class ShuffleRowsTransform:
    type: Literal[TransformType.SHUFFLE_ROWS]
    seed: int


@dataclass
class SampleRowsTransform:
    type: Literal[TransformType.SAMPLE_ROWS]
    n: int
    replace: bool
    seed: int


@dataclass
class ExplodeColumnsTransform:
    type: Literal[TransformType.EXPLODE_COLUMNS]
    column_ids: ColumnIds


@dataclass
class ExpandDictTransform:
    type: Literal[TransformType.EXPAND_DICT]
    column_id: ColumnId


@dataclass
class UniqueTransform:
    type: Literal[TransformType.UNIQUE]
    column_ids: ColumnIds
    keep: UniqueKeep


@dataclass
class PivotTransform:
    type: Literal[TransformType.PIVOT]
    column_ids: ColumnIds
    index_column_ids: ColumnIds
    value_column_ids: ColumnIds
    aggregation: Aggregation


Transform = (
    AggregateTransform
    | ColumnConversionTransform
    | FilterRowsTransform
    | PivotTransform
    | GroupByTransform
    | RenameColumnTransform
    | SelectColumnsTransform
    | SortColumnTransform
    | ShuffleRowsTransform
    | SampleRowsTransform
    | ExplodeColumnsTransform
    | ExpandDictTransform
    | UniqueTransform
)


@dataclass
class Transformations:
    transforms: list[Transform]


T = TypeVar("T")


class TransformHandler(abc.ABC, Generic[T]):
    @staticmethod
    @abc.abstractmethod
    def handle_column_conversion(
        df: T, transform: ColumnConversionTransform
    ) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_rename_column(df: T, transform: RenameColumnTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_sort_column(df: T, transform: SortColumnTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_filter_rows(df: T, transform: FilterRowsTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_group_by(df: T, transform: GroupByTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_aggregate(df: T, transform: AggregateTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_select_columns(df: T, transform: SelectColumnsTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_shuffle_rows(df: T, transform: ShuffleRowsTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_sample_rows(df: T, transform: SampleRowsTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_explode_columns(df: T, transform: ExplodeColumnsTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_expand_dict(df: T, transform: ExpandDictTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_unique(df: T, transform: UniqueTransform) -> T:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def handle_pivot(df: T, transform: PivotTransform) -> T:
        raise NotImplementedError

    @staticmethod
    def as_python_code(
        df: T, df_name: str, columns: list[str], transforms: list[Transform]
    ) -> str | None:
        del df_name, transforms, columns, df
        return None

    @staticmethod
    def as_sql_code(transformed_df: T) -> str | None:
        del transformed_df
        return None
