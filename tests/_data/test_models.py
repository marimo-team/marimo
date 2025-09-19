from typing import Any

import msgspec

from marimo._data.models import (
    BinValue,
    ColumnStats,
    Database,
    DataSourceConnection,
    DataTable,
    DataTableColumn,
    Schema,
    ValueCount,
)
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._utils.keyed_list import KeyedList


def assert_serde_roundtrip(obj: Any, my_type: type[msgspec.Struct]) -> None:
    assert encode_json_bytes(obj) == encode_json_bytes(
        msgspec.json.decode(encode_json_bytes(obj), type=my_type)
    )


def test_data_table_column_post_init() -> None:
    column = DataTableColumn(
        name=123,
        type="string",
        external_type="string",
        sample_values=[],
    )
    assert column.name == "123"
    assert_serde_roundtrip(column, DataTableColumn)


def test_data_table_creation() -> None:
    col = DataTableColumn(
        name="foo",
        type="string",
        external_type="varchar",
        sample_values=["a", "b"],
    )
    table = DataTable(
        source_type="local",
        source="pandas",
        name="my_table",
        num_rows=2,
        num_columns=1,
        variable_name=None,
        columns=KeyedList([col], key="name"),
    )
    assert table.name == "my_table"
    assert table.columns["foo"].type == "string"
    assert_serde_roundtrip(table, DataTable)


def test_schema_and_database_creation() -> None:
    col = DataTableColumn(
        name="bar",
        type="integer",
        external_type="int64",
        sample_values=[1, 2],
    )
    table = DataTable(
        source_type="local",
        source="pandas",
        name="numbers",
        num_rows=2,
        num_columns=1,
        variable_name=None,
        columns=KeyedList([col], key="name"),
    )
    schema = Schema(
        name="public",
        tables=KeyedList([table], key="name"),
    )
    db = Database(
        name="testdb",
        dialect="sqlite",
        schemas=KeyedList([schema], key="name"),
    )
    assert db.name == "testdb"
    assert db.schemas["public"].tables["numbers"].name == "numbers"
    assert_serde_roundtrip(db, Database)


def test_column_stats_and_bin_value() -> None:
    stats = ColumnStats(
        total=10,
        nulls=1,
        unique=9,
        min=1,
        max=10,
        mean=5.5,
        median=5,
        std=2.5,
        true=None,
        false=None,
        p5=1,
        p25=3,
        p75=8,
        p95=10,
    )
    assert stats.total == 10
    bin_value = BinValue(bin_start=0, bin_end=10, count=5)
    assert bin_value.count == 5
    assert_serde_roundtrip(stats, ColumnStats)


def test_value_count() -> None:
    vc = ValueCount(value="foo", count=42)
    assert vc.value == "foo"
    assert vc.count == 42
    assert_serde_roundtrip(vc, ValueCount)


def test_data_source_connection() -> None:
    db = Database(
        name="db",
        dialect="sqlite",
        schemas=KeyedList([], key="name"),
    )
    conn = DataSourceConnection(
        source="sqlite",
        dialect="sqlite",
        name="engine",
        display_name="SQLite (engine)",
        databases=[db],
        default_database="db",
        default_schema="main",
    )
    assert conn.display_name.startswith("SQLite")
    assert conn.default_database == "db"
    assert_serde_roundtrip(conn, DataSourceConnection)
