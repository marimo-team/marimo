from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.shared_types import CellVariableValue
from marimo._ai._tools.tools.tables_and_variables import (
    ColumnInfo,
    DataTableMetadata,
    GetTablesAndVariables,
    TablesAndVariablesOutput,
)
from marimo._messaging.ops import VariableValue


@dataclass
class MockDataset:
    name: str
    source_type: str
    num_rows: int
    num_columns: int
    columns: list[ColumnInfo]
    primary_keys: list[str] | None = None
    indexes: list[str] | None = None


@dataclass
class MockDatasets:
    tables: list[MockDataset] = field(default_factory=list)


@dataclass
class MockSessionView:
    datasets: MockDatasets
    variable_values: dict[str, VariableValue] = field(default_factory=dict)


@dataclass
class MockSession:
    session_view: MockSessionView


@pytest.fixture
def tool() -> GetTablesAndVariables:
    """Create a GetTablesAndVariables tool instance."""
    return GetTablesAndVariables(ToolContext())


@pytest.fixture
def sample_columns() -> list[ColumnInfo]:
    """Sample column information for testing."""
    return [
        ColumnInfo("id", "int", "INTEGER", [1, 2, 3]),
        ColumnInfo("name", "str", "VARCHAR", ["Alice", "Bob"]),
        ColumnInfo("email", "str", "VARCHAR", ["alice@example.com"]),
    ]


@pytest.fixture
def sample_tables(sample_columns: list[ColumnInfo]) -> list[MockDataset]:
    """Sample table data for testing."""
    return [
        MockDataset(
            name="users",
            source_type="database",
            num_rows=100,
            num_columns=3,
            columns=sample_columns,
            primary_keys=["id"],
            indexes=["idx_name"],
        ),
        MockDataset(
            name="orders",
            source_type="csv",
            num_rows=50,
            num_columns=2,
            columns=[
                ColumnInfo("order_id", "int", "INTEGER", [1, 2]),
                ColumnInfo("user_id", "int", "INTEGER", [1, 2]),
            ],
        ),
    ]


@pytest.fixture
def sample_variables() -> dict[str, VariableValue]:
    """Sample variable data for testing."""
    return {
        "x": VariableValue("x", 42, "int"),
        "y": VariableValue("y", "hello", "str"),
        "df": VariableValue("df", None, "DataFrame"),
        "my_list": VariableValue("my_list", [1, 2, 3], "list"),
    }


@pytest.fixture
def sample_session(
    sample_tables: list[MockDataset],
    sample_variables: dict[str, VariableValue],
) -> MockSession:
    """Sample session with tables and variables."""
    return MockSession(
        MockSessionView(
            datasets=MockDatasets(tables=sample_tables),
            variable_values=sample_variables,
        )
    )


def test_get_tables_and_variables_empty_list(
    tool: GetTablesAndVariables, sample_session: MockSession
):
    """Test _get_tables_and_variables with empty variable names list (return all)."""
    result = tool._get_tables_and_variables(sample_session, [])

    assert isinstance(result, TablesAndVariablesOutput)
    assert len(result.tables) == 2
    assert len(result.variables) == 4

    # Check tables
    assert "users" in result.tables
    assert "orders" in result.tables

    users_table = result.tables["users"]
    assert users_table.source == "database"
    assert users_table.num_rows == 100
    assert users_table.num_columns == 3
    assert users_table.primary_keys == ["id"]
    assert users_table.indexes == ["idx_name"]
    assert len(users_table.columns) == 3

    # Check variables
    assert "x" in result.variables
    assert "y" in result.variables
    assert "df" in result.variables
    assert "my_list" in result.variables

    x_var = result.variables["x"]
    assert x_var.name == "x"
    assert x_var.value == 42
    assert x_var.data_type == "int"


def test_get_tables_and_variables_specific_variables(
    tool: GetTablesAndVariables, sample_session: MockSession
):
    """Test _get_tables_and_variables with specific variable names."""
    result = tool._get_tables_and_variables(
        sample_session, ["users", "x", "y"]
    )

    assert isinstance(result, TablesAndVariablesOutput)
    assert len(result.tables) == 1  # Only "users" table
    assert len(result.variables) == 2  # Only "x" and "y" variables

    # Check that only requested items are returned
    assert "users" in result.tables
    assert "orders" not in result.tables

    assert "x" in result.variables
    assert "y" in result.variables
    assert "df" not in result.variables
    assert "my_list" not in result.variables


def test_get_tables_and_variables_nonexistent_variables(
    tool: GetTablesAndVariables, sample_session: MockSession
):
    """Test _get_tables_and_variables with non-existent variable names."""
    result = tool._get_tables_and_variables(
        sample_session, ["nonexistent_table", "nonexistent_var"]
    )

    assert isinstance(result, TablesAndVariablesOutput)
    assert len(result.tables) == 0
    assert len(result.variables) == 0


def test_get_tables_and_variables_mixed_existing_nonexistent(
    tool: GetTablesAndVariables, sample_session: MockSession
):
    """Test _get_tables_and_variables with mix of existing and non-existent variables."""
    result = tool._get_tables_and_variables(
        sample_session, ["users", "nonexistent_table", "x", "nonexistent_var"]
    )

    assert isinstance(result, TablesAndVariablesOutput)
    assert len(result.tables) == 1  # Only "users" table exists
    assert len(result.variables) == 1  # Only "x" variable exists

    assert "users" in result.tables
    assert "x" in result.variables


def test_data_table_metadata_structure(
    tool: GetTablesAndVariables, sample_session: MockSession
):
    """Test that DataTableMetadata is properly structured."""
    result = tool._get_tables_and_variables(sample_session, ["users"])

    users_table = result.tables["users"]
    assert isinstance(users_table, DataTableMetadata)
    assert users_table.source == "database"
    assert users_table.num_rows == 100
    assert users_table.num_columns == 3
    assert users_table.primary_keys == ["id"]
    assert users_table.indexes == ["idx_name"]

    # Check column structure
    assert len(users_table.columns) == 3
    id_column = users_table.columns[0]
    assert isinstance(id_column, ColumnInfo)
    assert id_column.name == "id"
    assert id_column.data_type == "int"
    assert id_column.external_type == "INTEGER"
    assert id_column.sample_values == [1, 2, 3]


def test_cell_variable_value_structure(
    tool: GetTablesAndVariables, sample_session: MockSession
):
    """Test that CellVariableValue is properly structured."""
    result = tool._get_tables_and_variables(sample_session, ["x", "my_list"])

    x_var = result.variables["x"]
    assert isinstance(x_var, CellVariableValue)
    assert x_var.name == "x"
    assert x_var.value == 42
    assert x_var.data_type == "int"

    list_var = result.variables["my_list"]
    assert isinstance(list_var, CellVariableValue)
    assert list_var.name == "my_list"
    assert list_var.value == [1, 2, 3]
    assert list_var.data_type == "list"


def test_empty_session(tool: GetTablesAndVariables):
    """Test _get_tables_and_variables with empty session (no tables or variables)."""
    empty_session = MockSession(
        MockSessionView(datasets=MockDatasets(tables=[]), variable_values={})
    )
    result = tool._get_tables_and_variables(empty_session, [])

    assert isinstance(result, TablesAndVariablesOutput)
    assert len(result.tables) == 0
    assert len(result.variables) == 0


def test_table_with_no_primary_keys_or_indexes(tool: GetTablesAndVariables):
    """Test table with no primary keys or indexes."""
    table_without_keys = MockDataset(
        name="simple_table",
        source_type="json",
        num_rows=10,
        num_columns=2,
        columns=[
            ColumnInfo("col1", "str", "TEXT", ["a", "b"]),
            ColumnInfo("col2", "int", "INTEGER", [1, 2]),
        ],
        primary_keys=None,
        indexes=None,
    )

    session = MockSession(
        MockSessionView(
            datasets=MockDatasets(tables=[table_without_keys]),
            variable_values={},
        )
    )

    result = tool._get_tables_and_variables(session, ["simple_table"])

    simple_table = result.tables["simple_table"]
    assert simple_table.primary_keys is None
    assert simple_table.indexes is None


def test_variable_with_none_value(tool: GetTablesAndVariables):
    """Test variable with None value."""
    variables_with_none = {
        "none_var": VariableValue("none_var", None, "NoneType"),
    }

    session = MockSession(
        MockSessionView(
            datasets=MockDatasets(tables=[]),
            variable_values=variables_with_none,
        )
    )

    result = tool._get_tables_and_variables(session, ["none_var"])

    none_var = result.variables["none_var"]
    assert none_var.name == "none_var"
    assert none_var.value is None
    assert none_var.data_type == "NoneType"


def test_filtering_logic_separate_tables_and_variables(
    tool: GetTablesAndVariables, sample_session: MockSession
):
    """Test that filtering works correctly for both tables and variables separately."""
    # Request only table names (no matching variables)
    result = tool._get_tables_and_variables(
        sample_session, ["users", "orders"]
    )

    assert len(result.tables) == 2
    assert len(result.variables) == 0

    # Request only variable names (no matching tables)
    result = tool._get_tables_and_variables(sample_session, ["x", "y"])

    assert len(result.tables) == 0
    assert len(result.variables) == 2
