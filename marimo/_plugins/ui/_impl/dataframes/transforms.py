# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Literal, Union

ColumnId = str
ColumnIds = List[ColumnId]
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
    "is_nan",
    "is_not_nan",
    "equals",
    "does_not_equal",
    "contains",
    "regex",
    "starts_with",
    "ends_with",
    "in",
]
Aggregation = Literal[
    "count",
    "sum",
    "mean",
    "median",
    "min",
    "max",
]


class TransformType(Enum):
    AGGREGATE = "aggregate"
    COLUMN_CONVERSION = "column_conversion"
    FILTER_ROWS = "filter_rows"
    GROUP_BY = "group_by"
    RENAME_COLUMN = "rename_column"
    SELECT_COLUMNS = "select_columns"
    SORT_COLUMN = "sort_column"


@dataclass
class Condition:
    column_id: ColumnId
    operator: Operator
    value: Any


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
    where: List[Condition]


@dataclass
class GroupByTransform:
    type: Literal[TransformType.GROUP_BY]
    column_ids: ColumnIds
    drop_na: bool
    aggregation: Aggregation


@dataclass
class AggregateTransform:
    type: Literal[TransformType.AGGREGATE]
    column_ids: ColumnIds
    aggregations: List[Aggregation]


@dataclass
class SelectColumnsTransform:
    type: Literal[TransformType.SELECT_COLUMNS]
    column_ids: ColumnIds


Transform = Union[
    AggregateTransform,
    ColumnConversionTransform,
    FilterRowsTransform,
    GroupByTransform,
    RenameColumnTransform,
    SelectColumnsTransform,
    SortColumnTransform,
]


@dataclass
class Transformations:
    transforms: List[Transform]
