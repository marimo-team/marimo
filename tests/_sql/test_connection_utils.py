# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.models import (
    Database,
    DataSourceConnection,
    DataTable,
    DataTableColumn,
    Schema,
)
from marimo._messaging.notification import SQLDatabaseMetadata, SQLMetadata
from marimo._sql.connection_utils import (
    _find_schema_by_path,
    update_schema_list_in_connection,
    update_table_in_connection,
    update_table_list_in_connection,
)


def create_test_table(name: str = "test_table") -> DataTable:
    """Create a test DataTable."""
    return DataTable(
        source_type="connection",
        source="postgres",
        name=name,
        num_rows=100,
        num_columns=3,
        variable_name=None,
        columns=[
            DataTableColumn(
                name="id",
                type="integer",
                external_type="INT",
                sample_values=[1, 2, 3],
            ),
            DataTableColumn(
                name="name",
                type="string",
                external_type="VARCHAR",
                sample_values=["Alice", "Bob", "Charlie"],
            ),
            DataTableColumn(
                name="age",
                type="integer",
                external_type="INT",
                sample_values=[25, 30, 35],
            ),
        ],
    )


def create_test_connections(
    num_connections: int = 1,
    num_databases_per_conn: int = 1,
    num_schemas_per_db: int = 1,
    num_tables_per_schema: int = 1,
) -> list[DataSourceConnection]:
    """Create test data source connections with a hierarchical structure."""
    connections = []
    for conn_idx in range(num_connections):
        databases = []
        for db_idx in range(num_databases_per_conn):
            schemas = []
            for schema_idx in range(num_schemas_per_db):
                tables = [
                    create_test_table(f"table_{table_idx}")
                    for table_idx in range(num_tables_per_schema)
                ]
                schemas.append(
                    Schema(name=f"schema_{schema_idx}", tables=tables)
                )
            databases.append(
                Database(
                    name=f"database_{db_idx}",
                    dialect="postgresql",
                    schemas=schemas,
                )
            )
        connections.append(
            DataSourceConnection(
                source="postgres",
                dialect="postgresql",
                name=f"connection_{conn_idx}",
                display_name=f"PostgreSQL (connection_{conn_idx})",
                databases=databases,
            )
        )
    return connections


class TestUpdateTableInConnection:
    """Tests for update_table_in_connection function."""

    def test_update_existing_table(self) -> None:
        """Test updating an existing table in the hierarchy."""
        connections = create_test_connections(
            num_connections=2,
            num_databases_per_conn=2,
            num_schemas_per_db=2,
            num_tables_per_schema=3,
        )

        sql_metadata = SQLMetadata(
            connection="connection_1",
            database="database_1",
            schema="schema_1",
        )

        # Create updated table
        updated_table = create_test_table("table_2")
        updated_table.num_rows = 500  # Changed value

        update_table_in_connection(connections, sql_metadata, updated_table)

        # Verify the update
        target_schema = connections[1].databases[1].schemas[1]
        updated = target_schema.tables[2]
        assert updated.name == "table_2"
        assert updated.num_rows == 500

    def test_update_nonexistent_connection(self) -> None:
        """Test updating a table in a non-existent connection."""
        connections = create_test_connections()

        sql_metadata = SQLMetadata(
            connection="nonexistent",
            database="database_0",
            schema="schema_0",
        )

        updated_table = create_test_table()
        original_table = connections[0].databases[0].schemas[0].tables[0]
        original_rows = original_table.num_rows

        update_table_in_connection(connections, sql_metadata, updated_table)

        # Verify nothing changed
        assert original_table.num_rows == original_rows

    def test_update_nonexistent_database(self) -> None:
        """Test updating a table in a non-existent database."""
        connections = create_test_connections()

        sql_metadata = SQLMetadata(
            connection="connection_0",
            database="nonexistent",
            schema="schema_0",
        )

        updated_table = create_test_table()
        original_table = connections[0].databases[0].schemas[0].tables[0]
        original_rows = original_table.num_rows

        update_table_in_connection(connections, sql_metadata, updated_table)

        # Verify nothing changed
        assert original_table.num_rows == original_rows

    def test_update_nonexistent_schema(self) -> None:
        """Test updating a table in a non-existent schema."""
        connections = create_test_connections()

        sql_metadata = SQLMetadata(
            connection="connection_0",
            database="database_0",
            schema="nonexistent",
        )

        updated_table = create_test_table()
        original_table = connections[0].databases[0].schemas[0].tables[0]
        original_rows = original_table.num_rows

        update_table_in_connection(connections, sql_metadata, updated_table)

        # Verify nothing changed
        assert original_table.num_rows == original_rows

    def test_update_nonexistent_table(self) -> None:
        """Test updating a non-existent table."""
        connections = create_test_connections(num_tables_per_schema=2)

        sql_metadata = SQLMetadata(
            connection="connection_0",
            database="database_0",
            schema="schema_0",
        )

        updated_table = create_test_table("nonexistent_table")
        original_tables = connections[0].databases[0].schemas[0].tables[:]

        update_table_in_connection(connections, sql_metadata, updated_table)

        # Verify nothing changed
        assert connections[0].databases[0].schemas[0].tables == original_tables


class TestUpdateSchemaListInConnection:
    """Tests for update_schema_list_in_connection function."""

    def test_update_schema_list(self) -> None:
        """Test updating a schema list in the hierarchy."""
        connections = create_test_connections(num_schemas_per_db=3)

        sql_db_metadata = SQLDatabaseMetadata(
            connection="connection_0",
            database="database_0",
        )

        # Create new schema list
        new_schemas = [
            Schema(name=f"new_schema_{i}", tables=[]) for i in range(5)
        ]

        update_schema_list_in_connection(
            connections, sql_db_metadata, new_schemas
        )

        # Verify the update
        target_database = connections[0].databases[0]
        assert len(target_database.schemas) == 5
        assert target_database.schemas[0].name == "new_schema_0"
        assert target_database.schemas[4].name == "new_schema_4"

    def test_update_schema_list_nonexistent_connection(self) -> None:
        """Test updating a schema list in a non-existent connection."""
        connections = create_test_connections(num_schemas_per_db=3)

        sql_db_metadata = SQLDatabaseMetadata(
            connection="nonexistent",
            database="database_0",
        )

        new_schemas = [
            Schema(name=f"new_schema_{i}", tables=[]) for i in range(5)
        ]
        original_count = len(connections[0].databases[0].schemas)

        update_schema_list_in_connection(
            connections, sql_db_metadata, new_schemas
        )

        # Verify nothing changed
        assert len(connections[0].databases[0].schemas) == original_count


class TestUpdateTableListInConnection:
    """Tests for update_table_list_in_connection function."""

    def test_update_table_list(self) -> None:
        """Test updating a table list in the hierarchy."""
        connections = create_test_connections(num_tables_per_schema=3)

        sql_metadata = SQLMetadata(
            connection="connection_0",
            database="database_0",
            schema="schema_0",
        )

        # Create new table list
        new_tables = [create_test_table(f"new_table_{i}") for i in range(5)]

        update_table_list_in_connection(connections, sql_metadata, new_tables)

        # Verify the update
        target_schema = connections[0].databases[0].schemas[0]
        assert len(target_schema.tables) == 5
        assert target_schema.tables[0].name == "new_table_0"
        assert target_schema.tables[4].name == "new_table_4"

    def test_update_table_list_nonexistent_connection(self) -> None:
        """Test updating a table list in a non-existent connection."""
        connections = create_test_connections(num_tables_per_schema=3)

        sql_metadata = SQLMetadata(
            connection="nonexistent",
            database="database_0",
            schema="schema_0",
        )

        new_tables = [create_test_table(f"new_table_{i}") for i in range(5)]
        original_count = len(connections[0].databases[0].schemas[0].tables)

        update_table_list_in_connection(connections, sql_metadata, new_tables)

        # Verify nothing changed
        assert (
            len(connections[0].databases[0].schemas[0].tables)
            == original_count
        )


def _create_nested_connection() -> list[DataSourceConnection]:
    """Connection with a top-level namespace ("top") holding a recursive
    sub-namespace tree: top -> nested -> deep."""
    deep = Schema(
        name="deep",
        tables=[],
        tables_resolved=False,
        child_schemas=[],
        child_schemas_resolved=False,
    )
    nested = Schema(
        name="nested",
        tables=[create_test_table("table4")],
        tables_resolved=True,
        child_schemas=[deep],
        child_schemas_resolved=True,
    )
    top = Database(
        name="top",
        dialect="iceberg",
        schemas=[
            Schema(name="", tables=[], tables_resolved=True),
            nested,
        ],
    )
    return [
        DataSourceConnection(
            source="iceberg",
            dialect="iceberg",
            name="my_iceberg",
            display_name="iceberg (my_iceberg)",
            databases=[top],
        )
    ]


class TestFindSchemaByPath:
    def test_finds_top_level(self) -> None:
        connections = _create_nested_connection()
        schemas = connections[0].databases[0].schemas
        found = _find_schema_by_path(schemas, ["nested"])
        assert found is not None
        assert found.name == "nested"

    def test_descends_into_nested(self) -> None:
        connections = _create_nested_connection()
        schemas = connections[0].databases[0].schemas
        found = _find_schema_by_path(schemas, ["nested", "deep"])
        assert found is not None
        assert found.name == "deep"

    def test_missing_path_returns_none(self) -> None:
        connections = _create_nested_connection()
        schemas = connections[0].databases[0].schemas
        assert _find_schema_by_path(schemas, ["nested", "missing"]) is None
        assert _find_schema_by_path(schemas, []) is None


class TestNestedNamespaceUpdates:
    def test_update_child_schema_list_at_path(self) -> None:
        """Resolving child namespaces of a nested namespace updates the right
        node in-place."""
        connections = _create_nested_connection()
        sql_db_metadata = SQLDatabaseMetadata(
            connection="my_iceberg",
            database="top",
            schema_path=["nested"],
        )
        new_children = [Schema(name="deep", tables=[])]

        update_schema_list_in_connection(
            connections, sql_db_metadata, new_children
        )

        nested = _find_schema_by_path(
            connections[0].databases[0].schemas, ["nested"]
        )
        assert nested is not None
        assert [s.name for s in nested.child_schemas] == ["deep"]
        assert nested.child_schemas_resolved is True

    def test_update_table_list_at_nested_path(self) -> None:
        """Resolving tables of a deeply nested namespace targets that schema."""
        connections = _create_nested_connection()
        sql_metadata = SQLMetadata(
            connection="my_iceberg",
            database="top",
            schema="deep",
            schema_path=["nested", "deep"],
        )
        new_tables = [create_test_table("table5")]

        update_table_list_in_connection(connections, sql_metadata, new_tables)

        deep = _find_schema_by_path(
            connections[0].databases[0].schemas, ["nested", "deep"]
        )
        assert deep is not None
        assert [t.name for t in deep.tables] == ["table5"]
        assert deep.tables_resolved is True

    def test_update_table_at_nested_path(self) -> None:
        """A single-table update descends the namespace path."""
        connections = _create_nested_connection()
        sql_metadata = SQLMetadata(
            connection="my_iceberg",
            database="top",
            schema="nested",
            schema_path=["nested"],
        )
        updated = create_test_table("table4")
        updated.num_rows = 999

        update_table_in_connection(connections, sql_metadata, updated)

        nested = _find_schema_by_path(
            connections[0].databases[0].schemas, ["nested"]
        )
        assert nested is not None
        assert nested.tables[0].num_rows == 999
