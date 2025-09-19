# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from dataclasses import dataclass

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.datasource import (
    GetDatabaseTables,
    GetDatabaseTablesArgs,
    TableDetails,
)
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._messaging.ops import DataSourceConnections


@dataclass
class MockDataSourceConnection:
    name: str
    dialect: str
    databases: list[Database]


@dataclass
class MockSessionView:
    data_connectors: DataSourceConnections


@dataclass
class MockSession:
    session_view: MockSessionView


@pytest.fixture
def tool() -> GetDatabaseTables:
    """Create a GetDatabaseTables tool instance."""
    return GetDatabaseTables(ToolContext())


@pytest.fixture
def sample_table() -> DataTable:
    """Sample table for testing."""
    return DataTable(
        source_type="connection",
        source="postgresql",
        name="users",
        num_rows=100,
        num_columns=3,
        variable_name=None,
        columns=[
            DataTableColumn("id", "int", "INTEGER", [1, 2, 3]),
            DataTableColumn("name", "str", "VARCHAR", ["Alice", "Bob"]),
            DataTableColumn("email", "str", "VARCHAR", ["alice@example.com"]),
        ],
    )


@pytest.fixture
def sample_schema(sample_table: DataTable) -> Schema:
    """Sample schema for testing."""
    return Schema(
        name="public",
        tables=[sample_table],
    )


@pytest.fixture
def sample_database(sample_schema: Schema) -> Database:
    """Sample database for testing."""
    return Database(
        name="test_db",
        dialect="postgresql",
        schemas=[sample_schema],
    )


@pytest.fixture
def sample_connection(sample_database: Database) -> MockDataSourceConnection:
    """Sample connection for testing."""
    return MockDataSourceConnection(
        name="postgres_conn",
        dialect="postgresql",
        databases=[sample_database],
    )


@pytest.fixture
def sample_session(sample_connection: MockDataSourceConnection) -> MockSession:
    """Sample session with data connectors."""
    return MockSession(
        session_view=MockSessionView(
            data_connectors=DataSourceConnections(
                connections=[sample_connection]
            )
        )
    )


@pytest.fixture
def multi_table_session() -> MockSession:
    """Session with multiple tables for testing filtering."""
    tables = [
        DataTable(
            source_type="connection",
            source="mysql",
            name="users",
            num_rows=100,
            num_columns=2,
            variable_name=None,
            columns=[
                DataTableColumn("id", "int", "INTEGER", [1, 2]),
                DataTableColumn("name", "str", "VARCHAR", ["Alice"]),
            ],
        ),
        DataTable(
            source_type="connection",
            source="mysql",
            name="orders",
            num_rows=50,
            num_columns=2,
            variable_name=None,
            columns=[
                DataTableColumn("order_id", "int", "INTEGER", [1]),
                DataTableColumn("user_id", "int", "INTEGER", [1]),
            ],
        ),
        DataTable(
            source_type="connection",
            source="mysql",
            name="products",
            num_rows=25,
            num_columns=2,
            variable_name=None,
            columns=[
                DataTableColumn("product_id", "int", "INTEGER", [1]),
                DataTableColumn("name", "str", "VARCHAR", ["Widget"]),
            ],
        ),
    ]

    schema = Schema(name="public", tables=tables)
    database = Database(name="ecommerce", dialect="mysql", schemas=[schema])
    connection = MockDataSourceConnection(
        name="mysql_conn", dialect="mysql", databases=[database]
    )

    return MockSession(
        session_view=MockSessionView(
            data_connectors=DataSourceConnections(connections=[connection])
        )
    )


def test_get_tables_no_query(
    tool: GetDatabaseTables, sample_session: MockSession
):
    """Test getting all tables when no query is provided."""

    # Mock the session
    def mock_get_session(_session_id):
        return sample_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query=None,
    )

    result = tool.handle(args)

    assert isinstance(result, tool.Output)
    assert len(result.tables) == 1

    table_detail = result.tables[0]
    assert isinstance(table_detail, TableDetails)
    assert table_detail.connection == "postgres_conn"
    assert table_detail.database == "test_db"
    assert table_detail.schema == "public"
    assert table_detail.table.name == "users"


def test_get_tables_with_simple_query(
    tool: GetDatabaseTables, multi_table_session: MockSession
):
    """Test getting tables with simple text query."""

    # Mock the session
    def mock_get_session(_session_id):
        return multi_table_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query="user",
    )

    result = tool.handle(args)

    assert isinstance(result, tool.Output)
    assert len(result.tables) == 1  # Only "users" table matches "user"

    table_names = {td.table.name for td in result.tables}
    assert "users" in table_names
    assert "orders" not in table_names  # "orders" doesn't contain "user"
    assert "products" not in table_names


def test_get_tables_with_regex_query(
    tool: GetDatabaseTables, multi_table_session: MockSession
):
    """Test getting tables with regex query."""

    # Mock the session
    def mock_get_session(_session_id):
        return multi_table_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query="^user.*",
    )

    result = tool.handle(args)

    assert isinstance(result, tool.Output)
    assert len(result.tables) == 1

    table_detail = result.tables[0]
    assert table_detail.table.name == "users"


def test_get_tables_with_schema_match(
    tool: GetDatabaseTables, multi_table_session: MockSession
):
    """Test getting tables by schema name match."""

    # Mock the session
    def mock_get_session(_session_id):
        return multi_table_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query="pub",
    )

    result = tool.handle(args)

    assert isinstance(result, tool.Output)
    assert len(result.tables) == 3  # All tables in public schema

    table_names = {td.table.name for td in result.tables}
    assert "users" in table_names
    assert "orders" in table_names
    assert "products" in table_names


def test_get_tables_empty_connections(tool: GetDatabaseTables):
    """Test getting tables when no connections exist."""
    empty_session = MockSession(
        session_view=MockSessionView(
            data_connectors=DataSourceConnections(connections=[])
        )
    )

    # Mock the session
    def mock_get_session(_session_id):
        return empty_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query=None,
    )

    with pytest.raises(ToolExecutionError) as e:
        tool.handle(args)
    assert e.value.code == "NO_DATABASES_FOUND"


def test_get_tables_no_matches(
    tool: GetDatabaseTables, sample_session: MockSession
):
    """Test getting tables when query matches nothing."""

    # Mock the session
    def mock_get_session(_session_id):
        return sample_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query="nonexistent",
    )

    result = tool.handle(args)

    assert isinstance(result, tool.Output)
    assert len(result.tables) == 0


def test_table_details_structure(
    tool: GetDatabaseTables, sample_session: MockSession
):
    """Test that TableDetails is properly structured."""

    # Mock the session
    def mock_get_session(_session_id):
        return sample_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query=None,
    )

    result = tool.handle(args)

    table_detail = result.tables[0]
    assert isinstance(table_detail, TableDetails)
    assert table_detail.connection == "postgres_conn"
    assert table_detail.database == "test_db"
    assert table_detail.schema == "public"
    assert isinstance(table_detail.table, DataTable)
    assert table_detail.table.name == "users"
    assert len(table_detail.table.columns) == 3


def test_multiple_connections(tool: GetDatabaseTables):
    """Test with multiple connections."""
    # Create two connections with different databases
    table1 = DataTable(
        source_type="connection",
        source="postgresql",
        name="table1",
        num_rows=10,
        num_columns=0,
        variable_name=None,
        columns=[],
    )
    table2 = DataTable(
        source_type="connection",
        source="mysql",
        name="table2",
        num_rows=20,
        num_columns=0,
        variable_name=None,
        columns=[],
    )

    schema1 = Schema(name="schema1", tables=[table1])
    schema2 = Schema(name="schema2", tables=[table2])

    db1 = Database(name="db1", dialect="postgresql", schemas=[schema1])
    db2 = Database(name="db2", dialect="mysql", schemas=[schema2])

    conn1 = MockDataSourceConnection(
        name="conn1", dialect="postgresql", databases=[db1]
    )
    conn2 = MockDataSourceConnection(
        name="conn2", dialect="mysql", databases=[db2]
    )

    multi_conn_session = MockSession(
        session_view=MockSessionView(
            data_connectors=DataSourceConnections(connections=[conn1, conn2])
        )
    )

    # Mock the session
    def mock_get_session(_session_id):
        return multi_conn_session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query=None,
    )

    result = tool.handle(args)

    assert isinstance(result, tool.Output)
    assert len(result.tables) == 2

    connections = {td.connection for td in result.tables}
    assert "conn1" in connections
    assert "conn2" in connections

    databases = {td.database for td in result.tables}
    assert "db1" in databases
    assert "db2" in databases


def test_query_matches_multiple_levels(tool: GetDatabaseTables):
    """Test query that matches at different levels (schema and table)."""
    # Create tables with overlapping names
    user_table = DataTable(
        source_type="connection",
        source="postgresql",
        name="user",
        num_rows=5,
        num_columns=0,
        variable_name=None,
        columns=[],
    )
    user_schema_table = DataTable(
        source_type="connection",
        source="postgresql",
        name="orders",
        num_rows=10,
        num_columns=0,
        variable_name=None,
        columns=[],
    )

    user_schema = Schema(name="user", tables=[user_table])
    public_schema = Schema(name="public", tables=[user_schema_table])

    database = Database(
        name="testdb",
        dialect="postgresql",
        schemas=[user_schema, public_schema],
    )

    connection = MockDataSourceConnection(
        name="conn", dialect="postgresql", databases=[database]
    )

    session = MockSession(
        session_view=MockSessionView(
            data_connectors=DataSourceConnections(connections=[connection])
        )
    )

    # Mock the session
    def mock_get_session(_session_id):
        return session

    tool.context.get_session = mock_get_session

    args = GetDatabaseTablesArgs(
        session_id="test_session",
        query="user",
    )

    result = tool.handle(args)

    assert isinstance(result, tool.Output)
    assert len(result.tables) == 1  # Only the "user" table matches "user"

    table_names = {td.table.name for td in result.tables}
    assert "user" in table_names
    # The "orders" table is in the "public" schema, not the "user" schema
    # So it won't be included when query matches "user"
    assert "orders" not in table_names


def test_query_no_duplicates(tool: GetDatabaseTables):
    """Test that schema-level matching doesn't create duplicates with table-level matching."""
    # Create a schema that matches the query AND has tables that also match
    schema1 = Schema(
        name="users",  # This will match query "user"
        tables=[
            DataTable(
                source_type="connection",
                source="postgresql",
                name="user_profiles",  # This would also match "user"
                num_rows=10,
                num_columns=0,
                variable_name=None,
                columns=[],
            ),
            DataTable(
                source_type="connection",
                source="postgresql",
                name="user_settings",  # This would also match "user"
                num_rows=20,
                num_columns=0,
                variable_name=None,
                columns=[],
            ),
        ],
    )

    # Create another schema that doesn't match but has tables that do
    schema2 = Schema(
        name="products",  # This won't match "user"
        tables=[
            DataTable(
                source_type="connection",
                source="postgresql",
                name="user_reviews",  # This would match "user"
                num_rows=5,
                num_columns=0,
                variable_name=None,
                columns=[],
            ),
        ],
    )

    database = Database(
        name="test_db",
        dialect="postgresql",
        schemas=[schema1, schema2],
    )

    connection = MockDataSourceConnection(
        name="test_conn",
        dialect="postgresql",
        databases=[database],
    )

    session = MockSession(
        session_view=MockSessionView(
            data_connectors=DataSourceConnections(connections=[connection])
        )
    )

    # Query that matches both schema name and individual table names
    result = tool._get_tables(session, query="user")

    # Should get all tables from the matching schema (2 tables)
    # plus the matching table from the non-matching schema (1 table)
    # Total: 3 tables, no duplicates
    assert len(result.tables) == 3

    # Verify no duplicates by checking unique combinations
    table_identifiers = [
        (t.connection, t.database, t.schema, t.table.name)
        for t in result.tables
    ]
    assert len(table_identifiers) == len(set(table_identifiers)), (
        "Found duplicate tables"
    )

    # Verify we got the expected tables
    table_names = [t.table.name for t in result.tables]
    assert "user_profiles" in table_names
    assert "user_settings" in table_names
    assert "user_reviews" in table_names
