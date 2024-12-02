from __future__ import annotations

from typing import Any

import pytest

from marimo._data.get_datasets import (
    get_datasets_from_duckdb,
    get_datasets_from_variables,
    has_updates_to_datasource,
)
from marimo._data.models import DataTable, DataTableColumn
from marimo._dependencies.dependencies import DependencyManager
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.duckdb.has()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_has_updates_to_datasource() -> None:
    assert has_updates_to_datasource("hello") is False
    assert has_updates_to_datasource("ATTACH 'marimo.db'") is True
    assert has_updates_to_datasource("DETACH marimo") is True
    assert has_updates_to_datasource("CREATE TABLE cars (name TEXT)") is True


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_datasets() -> None:
    assert get_datasets_from_duckdb() == []

    import duckdb

    duckdb.execute("""
        CREATE TABLE all_types (
            col_boolean BOOLEAN,
            col_tinyint TINYINT,
            col_smallint SMALLINT,
            col_integer INTEGER,
            col_bigint BIGINT,
            col_hugeint HUGEINT,
            col_utinyint UTINYINT,
            col_usmallint USMALLINT,
            col_uinteger UINTEGER,
            col_ubigint UBIGINT,
            col_float FLOAT,
            col_double DOUBLE,
            col_decimal DECIMAL(18,3),
            col_varchar VARCHAR,
            col_date DATE,
            col_time TIME,
            col_timestamp TIMESTAMP,
            col_interval INTERVAL,
            col_blob BLOB,
            col_bit BIT,
            col_uuid UUID,
            col_json JSON
        )
    """)
    assert get_datasets_from_duckdb() == [
        DataTable(
            name="memory.main.all_types",
            source_type="duckdb",
            source="memory",
            num_rows=None,
            num_columns=22,
            variable_name=None,
            columns=[
                DataTableColumn(
                    name="col_boolean",
                    type="boolean",
                    external_type="BOOLEAN",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_tinyint",
                    type="integer",
                    external_type="TINYINT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_smallint",
                    type="integer",
                    external_type="SMALLINT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_integer",
                    type="integer",
                    external_type="INTEGER",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_bigint",
                    type="integer",
                    external_type="BIGINT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_hugeint",
                    type="integer",
                    external_type="HUGEINT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_utinyint",
                    type="integer",
                    external_type="UTINYINT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_usmallint",
                    type="integer",
                    external_type="USMALLINT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_uinteger",
                    type="integer",
                    external_type="UINTEGER",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_ubigint",
                    type="integer",
                    external_type="UBIGINT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_float",
                    type="number",
                    external_type="FLOAT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_double",
                    type="number",
                    external_type="DOUBLE",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_decimal",
                    type="number",
                    external_type="DECIMAL(18,3)",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_varchar",
                    type="string",
                    external_type="VARCHAR",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_date",
                    type="date",
                    external_type="DATE",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_time",
                    type="time",
                    external_type="TIME",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_timestamp",
                    type="datetime",
                    external_type="TIMESTAMP",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_interval",
                    type="datetime",
                    external_type="INTERVAL",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_blob",
                    type="string",
                    external_type="BLOB",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_bit",
                    type="string",
                    external_type="BIT",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_uuid",
                    type="string",
                    external_type="UUID",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="col_json",
                    type="unknown",
                    external_type="JSON",
                    sample_values=[],
                ),
            ],
        )
    ]


@pytest.mark.parametrize(
    "df",
    create_dataframes({"A": [1, 2, 3], "B": ["a", "a", "a"]}),
)
def test_get_datasets_from_variables(df: Any) -> None:
    datatests = get_datasets_from_variables([("my_df", df), ("non_df", 123)])
    # We don't compare these values
    external_type1 = datatests[0].columns[0].external_type
    external_type2 = datatests[0].columns[1].external_type

    rows = datatests[0].num_rows
    assert rows is None or rows == 3

    assert datatests == [
        DataTable(
            name="my_df",
            source_type="local",
            source="memory",
            num_rows=rows,
            num_columns=2,
            variable_name="my_df",
            columns=[
                DataTableColumn(
                    name="A",
                    type="integer",
                    external_type=external_type1,
                    sample_values=[],
                ),
                DataTableColumn(
                    name="B",
                    type="string",
                    external_type=external_type2,
                    sample_values=[],
                ),
            ],
        )
    ]
