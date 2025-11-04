# Copyright 2025 Marimo. All rights reserved.

import time
from typing import Callable

import pytest

from marimo._data.models import (
    Database,
    DataSourceConnection,
    DataTable,
    DataTableColumn,
    Schema,
)
from marimo._messaging.ops import SQLMetadata
from marimo._sql.connection_utils import (
    update_table_in_connection,
    update_table_list_in_connection,
)

TIME_THRESHOLD_SECONDS = 0.1


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


class TestPerformance:
    """Performance tests for connection utils."""

    def _measure_performance(
        self,
        func: Callable[[], None],
        iterations: int = 1000,
    ) -> tuple[float, float]:
        """Measure average and total execution time.

        Returns:
            Tuple of (average_time_ms, total_time_ms)
        """
        start = time.perf_counter()
        for _ in range(iterations):
            func()
        total_time = (time.perf_counter() - start) * 1000  # Convert to ms
        avg_time = total_time / iterations
        return avg_time, total_time

    def test_performance_small_hierarchy(self) -> None:
        """Benchmark with small hierarchy (typical real-world case)."""
        # 2 connections, 3 databases each, 5 schemas each, 20 tables each
        connections = create_test_connections(
            num_connections=2,
            num_databases_per_conn=3,
            num_schemas_per_db=5,
            num_tables_per_schema=20,
        )

        sql_metadata = SQLMetadata(
            connection="connection_1",
            database="database_2",
            schema="schema_4",
        )

        updated_table = create_test_table("table_19")
        updated_table.num_rows = 999

        def update_func() -> None:
            update_table_in_connection(
                connections, sql_metadata, updated_table
            )

        avg_time, total_time = self._measure_performance(
            update_func, iterations=1000
        )

        print(
            f"\nSmall hierarchy (2x3x5x20 = 600 tables): "
            f"{avg_time:.4f}ms avg, {total_time:.2f}ms total"
        )

        # Assert reasonable performance: < 0.1ms per operation
        assert avg_time < 0.1, f"Performance too slow: {avg_time:.4f}ms"

    def test_performance_medium_hierarchy(self) -> None:
        """Benchmark with medium hierarchy."""
        # 5 connections, 5 databases each, 10 schemas each, 50 tables each
        connections = create_test_connections(
            num_connections=5,
            num_databases_per_conn=5,
            num_schemas_per_db=10,
            num_tables_per_schema=50,
        )

        sql_metadata = SQLMetadata(
            connection="connection_4",
            database="database_4",
            schema="schema_9",
        )

        updated_table = create_test_table("table_49")
        updated_table.num_rows = 999

        def update_func() -> None:
            update_table_in_connection(
                connections, sql_metadata, updated_table
            )

        avg_time, total_time = self._measure_performance(
            update_func, iterations=1000
        )

        print(
            f"\nMedium hierarchy (5x5x10x50 = 12,500 tables): "
            f"{avg_time:.4f}ms avg, {total_time:.2f}ms total"
        )

        # Assert reasonable performance: < 0.5ms per operation
        assert avg_time < TIME_THRESHOLD_SECONDS, (
            f"Performance too slow: {avg_time:.4f}ms"
        )

    def test_performance_large_hierarchy(self) -> None:
        """Benchmark with large hierarchy (stress test)."""
        # 10 connections, 10 databases each, 10 schemas each, 100 tables each
        connections = create_test_connections(
            num_connections=10,
            num_databases_per_conn=10,
            num_schemas_per_db=10,
            num_tables_per_schema=100,
        )

        sql_metadata = SQLMetadata(
            connection="connection_9",
            database="database_9",
            schema="schema_9",
        )

        updated_table = create_test_table("table_99")
        updated_table.num_rows = 999

        def update_func() -> None:
            update_table_in_connection(
                connections, sql_metadata, updated_table
            )

        avg_time, total_time = self._measure_performance(
            update_func, iterations=1000
        )

        print(
            f"\nLarge hierarchy (10x10x10x100 = 100,000 tables): "
            f"{avg_time:.4f}ms avg, {total_time:.2f}ms total"
        )

        # Assert reasonable performance: < 1ms per operation
        assert avg_time < TIME_THRESHOLD_SECONDS, (
            f"Performance too slow: {avg_time:.4f}ms"
        )

    def test_performance_worst_case_early_exit(self) -> None:
        """Benchmark best case: early exit on first connection."""
        connections = create_test_connections(
            num_connections=10,
            num_databases_per_conn=10,
            num_schemas_per_db=10,
            num_tables_per_schema=100,
        )

        sql_metadata = SQLMetadata(
            connection="connection_0",
            database="database_0",
            schema="schema_0",
        )

        updated_table = create_test_table("table_0")
        updated_table.num_rows = 999

        def update_func() -> None:
            update_table_in_connection(
                connections, sql_metadata, updated_table
            )

        avg_time, total_time = self._measure_performance(
            update_func, iterations=1000
        )

        print(
            f"\nBest case (early exit): "
            f"{avg_time:.4f}ms avg, {total_time:.2f}ms total"
        )

        # Early exit should be very fast
        assert avg_time < 0.1, f"Performance too slow: {avg_time:.4f}ms"

    def test_performance_update_table_list(self) -> None:
        """Benchmark update_table_list_in_connection."""
        connections = create_test_connections(
            num_connections=5,
            num_databases_per_conn=5,
            num_schemas_per_db=10,
            num_tables_per_schema=50,
        )

        sql_metadata = SQLMetadata(
            connection="connection_4",
            database="database_4",
            schema="schema_9",
        )

        new_tables = [create_test_table(f"new_table_{i}") for i in range(50)]

        def update_func() -> None:
            update_table_list_in_connection(
                connections, sql_metadata, new_tables
            )

        avg_time, total_time = self._measure_performance(
            update_func, iterations=1000
        )

        print(
            f"\nUpdate table list (5x5x10x50 = 12,500 tables): "
            f"{avg_time:.4f}ms avg, {total_time:.2f}ms total"
        )

        # Should be fast since we're just replacing a list reference
        assert avg_time < TIME_THRESHOLD_SECONDS, (
            f"Performance too slow: {avg_time:.4f}ms"
        )

    @pytest.mark.skip(
        reason="Only run manually for detailed profiling analysis"
    )
    def test_profile_with_cprofile(self) -> None:
        """Profile the function with cProfile for detailed analysis."""
        import cProfile
        import pstats

        connections = create_test_connections(
            num_connections=10,
            num_databases_per_conn=10,
            num_schemas_per_db=10,
            num_tables_per_schema=100,
        )

        sql_metadata = SQLMetadata(
            connection="connection_9",
            database="database_9",
            schema="schema_9",
        )

        updated_table = create_test_table("table_99")

        profiler = cProfile.Profile()
        profiler.enable()

        for _ in range(10000):
            update_table_in_connection(
                connections, sql_metadata, updated_table
            )

        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.strip_dirs()
        stats.sort_stats("cumulative")
        print("\n" + "=" * 80)
        print("cProfile Results (top 20):")
        print("=" * 80)
        stats.print_stats(20)
