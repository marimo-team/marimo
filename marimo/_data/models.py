from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TCH003
from typing import List, Literal, Optional, Union

DataType = Literal["string", "boolean", "integer", "number", "date", "unknown"]


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

    source: str
    name: str
    num_rows: Optional[int]
    num_columns: Optional[int]
    variable_name: Optional[str]
    columns: List[DataTableColumn]


@dataclass
class ColumnSummary:
    """
    Represents a summary of a column in a data table.

    """

    total: Optional[int] = None
    nulls: Optional[int] = None
    unique: Optional[int] = None
    min: Optional[Union[float, datetime]] = None
    max: Optional[Union[float, datetime]] = None
    mean: Optional[Union[float, datetime]] = None
    median: Optional[Union[float, datetime]] = None
    std: Optional[float] = None
    true: Optional[int] = None
    false: Optional[int] = None
    p5: Optional[Union[float, datetime]] = None
    p25: Optional[Union[float, datetime]] = None
    # p50 is the median
    p75: Optional[Union[float, datetime]] = None
    p95: Optional[Union[float, datetime]] = None
