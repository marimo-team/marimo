# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta  # noqa: TCH003
from decimal import Decimal
from typing import List, Literal, Optional, Union

DataType = Literal["string", "boolean", "integer", "number", "date", "unknown"]
# This is the data type based on the source library
# e.g. polars, pandas, numpy, etc.
ExternalDataType = str


@dataclass
class DataTableColumn:
    """
    Represents a column in a data table.

    Attributes:
        name (str): The name of the column.
        type (DataType): The data type of the column.
    """

    name: str
    type: DataType
    external_type: ExternalDataType


DataTableSource = Literal["local", "duckdb"]


@dataclass
class DataTable:
    """
    Represents a data table.

    Attributes:
        source (str): The source of the data table.
        name (str): The name of the data table.
        num_rows (Optional[int]): The number of rows in the data table.
        num_columns (Optional[int]): The number of columns in the data table.
        variable_name (Optional[str]): The variable name associated with
        the data table.
        columns (List[DataTableColumn]): The list of columns in the data table.
    """

    source_type: DataTableSource
    source: str
    name: str
    num_rows: Optional[int]
    num_columns: Optional[int]
    variable_name: Optional[str]
    columns: List[DataTableColumn]


NumericLiteral = Union[int, float, Decimal]
TemporalLiteral = Union[date, time, datetime, timedelta]
NonNestedLiteral = Union[NumericLiteral, TemporalLiteral, str, bool, bytes]


@dataclass
class ColumnSummary:
    """
    Represents a summary of a column in a data table.

    """

    total: Optional[int] = None
    nulls: Optional[int] = None
    unique: Optional[int] = None
    min: Optional[NonNestedLiteral] = None
    max: Optional[NonNestedLiteral] = None
    mean: Optional[NonNestedLiteral] = None
    median: Optional[NonNestedLiteral] = None
    std: Optional[NonNestedLiteral] = None
    true: Optional[int] = None
    false: Optional[int] = None
    p5: Optional[NonNestedLiteral] = None
    p25: Optional[NonNestedLiteral] = None
    # p50 is the median
    p75: Optional[NonNestedLiteral] = None
    p95: Optional[NonNestedLiteral] = None
