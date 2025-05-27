# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta  # noqa: TCH003
from decimal import Decimal
from typing import Any, Literal, Optional, Union

from marimo._types.ids import VariableName

DataType = Literal[
    "string",
    "boolean",
    "integer",
    "number",
    "date",
    "datetime",
    "time",
    "unknown",
]
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
        external_type (ExternalDataType): The raw data type of the column.
        sample_values (List[Any]): The sample values of the column.
    """

    name: str
    type: DataType
    external_type: ExternalDataType
    sample_values: list[Any]


# Local -> Python dataframes
# DuckDB -> DuckDB tables using the global in-memory DuckDB instance
# Connection -> SQL tables using a named data source connection (e.g. SQLAlchemy, or a custom DuckDB connection)
# Catalog -> Data catalog (e.g. iceberg)
DataTableSource = Literal["local", "duckdb", "connection", "catalog"]
DataTableType = Literal["table", "view"]


@dataclass
class DataTable:
    """
    Represents a data table.

    Attributes:
        source_type (DataTableSource): Type of data source ('local', 'duckdb', 'connection').
        source (str): Can be dialect, or source db name.
        name (str): Name of the data table.
        num_rows (Optional[int]): Total number of rows in the table, if known.
        num_columns (Optional[int]): Total number of columns in the table, if known.
        variable_name (Optional[VariableName]): Variable name referencing this table in code.
        columns (List[DataTableColumn]): List of column definitions and metadata.
        engine (Optional[VariableName]): Database engine or connection handler, if any.
        type (DataTableType): Table type, either 'table' or 'view'. Defaults to 'table'.
        primary_keys (Optional[List[str]]): Column names used as primary keys, if any.
        indexes (Optional[List[str]]): Column names used as indexes, if any.
    """

    source_type: DataTableSource
    source: str
    name: str
    num_rows: Optional[int]
    num_columns: Optional[int]
    variable_name: Optional[VariableName]
    columns: list[DataTableColumn]
    engine: Optional[VariableName] = None
    type: DataTableType = "table"
    primary_keys: Optional[list[str]] = None
    indexes: Optional[list[str]] = None


@dataclass
class Schema:
    name: str
    tables: list[DataTable] = field(default_factory=list)


@dataclass
class Database:
    """
    Represents a collection of schemas.

    Attributes:
        name (str): The name of the database
        dialect (str): The dialect of the database
        schemas (List[Schema]): List of schemas in the database
        engine (Optional[VariableName]): Database engine or connection handler, if any.
    """

    name: str
    dialect: str
    schemas: list[Schema] = field(default_factory=list)
    engine: Optional[VariableName] = None


NumericLiteral = Union[int, float, Decimal]
TemporalLiteral = Union[date, time, datetime, timedelta]
NonNestedLiteral = Union[NumericLiteral, TemporalLiteral, str, bool, bytes]


@dataclass
class ColumnStats:
    """
    Represents stats for a column in a data table.

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


@dataclass
class DataSourceConnection:
    """
    Represents a data source connection.

    Attributes:
        source (str): The source of the data source connection. E.g 'postgres'.
        dialect (str): The dialect of the data source connection. E.g 'postgresql'.
        name (str): The name of the data source connection. E.g 'engine'.
        display_name (str): The display name of the data source connection. E.g 'PostgresQL (engine)'.
        databases (List[Database]): The databases in the data source connection.
        default_database (Optional[str]): The default database in the data source connection.
        default_schema (Optional[str]): The default schema in the data source connection.
    """

    source: str
    dialect: str
    name: str
    display_name: str
    databases: list[Database] = field(default_factory=list)
    default_database: Optional[str] = None
    default_schema: Optional[str] = None
