# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from marimo._ast.cell import RuntimeStateType
from marimo._data.models import DataTable, DataTableColumn
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import (
    CellOp,
    Datasets,
    DataSourceConnection,
    DataSourceConnections,
    SendUIElementMessage,
    UpdateCellCodes,
    UpdateCellIdsRequest,
    VariableDeclaration,
    Variables,
    VariableValue,
    VariableValues,
    serialize,
)
from marimo._runtime.requests import (
    CreationRequest,
    ExecuteMultipleRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._server.session.session_view import SessionView
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE
from marimo._types.ids import CellId_t, WidgetModelId
from marimo._utils.parse_dataclass import parse_raw

cell_id = CellId_t("cell_1")

initial_output = CellOutput(
    channel=CellChannel.OUTPUT,
    data="Initial output",
    mimetype="text/plain",
)
updated_output = CellOutput(
    channel=CellChannel.OUTPUT,
    data="Updated output",
    mimetype="text/plain",
)

initial_status: RuntimeStateType = "running"
updated_status: RuntimeStateType = "running"


def test_cell_ids() -> None:
    session_view = SessionView()
    assert session_view.cell_ids is None

    session_view.add_operation(
        UpdateCellIdsRequest(
            cell_ids=[cell_id],
        )
    )
    operation = session_view.operations[0]
    assert isinstance(operation, UpdateCellIdsRequest)
    assert operation.cell_ids == [cell_id]


def test_session_view_cell_op() -> None:
    session_view = SessionView()

    # Create initial CellOp
    initial_cell_op = CellOp(
        cell_id=cell_id, output=initial_output, status=initial_status
    )
    session_view.add_operation(initial_cell_op)

    # Add updated CellOp to SessionView
    updated_cell_op = CellOp(
        cell_id=cell_id, output=updated_output, status=updated_status
    )
    session_view.add_operation(updated_cell_op)

    assert session_view.cell_operations[cell_id].output == updated_output
    assert session_view.cell_operations[cell_id].status == updated_status


# Test adding Variables to SessionView
def test_session_view_variables() -> None:
    session_view = SessionView()

    # Create Variables operation
    variables_op = Variables(
        variables=[
            VariableDeclaration(name="var1", declared_by=[], used_by=[])
        ]
    )
    session_view.add_operation(variables_op)

    # Check if the Variables operation was added correctly
    assert session_view.variable_operations == variables_op


# Test adding VariableValues to SessionView
def test_session_view_variable_values() -> None:
    session_view = SessionView()
    # Create Variables operation
    variables_op = Variables(
        variables=[
            VariableDeclaration(
                name="var1", declared_by=[cell_id], used_by=[]
            ),
            VariableDeclaration(
                name="var2", declared_by=[cell_id], used_by=[]
            ),
        ]
    )
    session_view.add_operation(variables_op)

    # Create VariableValues operation
    variable_values_op = VariableValues(
        variables=[
            VariableValue(name="var1", value=1),
            VariableValue(name="var2", value="hello"),
        ]
    )
    session_view.add_operation(variable_values_op)

    variables_names = session_view.variable_values.keys()
    assert list(variables_names) == ["var1", "var2"]

    # Add new Variable operation without the previous variables
    variables_op = Variables(
        variables=[
            VariableDeclaration(
                name="var2", declared_by=[cell_id], used_by=[]
            ),
            VariableDeclaration(
                name="var3", declared_by=[cell_id], used_by=[]
            ),
        ]
    )
    session_view.add_operation(variables_op)

    variables_names = session_view.variable_values.keys()
    # var1 was removed, var2 was not changed, var3 has no value yet
    assert list(variables_names) == ["var2"]


def test_ui_values() -> None:
    session_view = SessionView()
    session_view.add_control_request(
        SetUIElementValueRequest.from_ids_and_values([("test_ui", 123)])
    )
    assert "test_ui" in session_view.ui_values
    assert session_view.ui_values["test_ui"] == 123

    # Can add multiple values
    # and can overwrite values
    session_view.add_control_request(
        SetUIElementValueRequest.from_ids_and_values(
            [("test_ui2", 456), ("test_ui", 789)]
        )
    )
    assert "test_ui2" in session_view.ui_values
    assert "test_ui" in session_view.ui_values
    assert session_view.ui_values["test_ui2"] == 456
    assert session_view.ui_values["test_ui"] == 789

    # Can add from CreationRequest
    session_view.add_control_request(
        CreationRequest(
            execution_requests=(),
            set_ui_element_value_request=SetUIElementValueRequest.from_ids_and_values(
                [("test_ui3", 101112)]
            ),
            auto_run=True,
        )
    )
    assert "test_ui3" in session_view.ui_values


def test_model_message_values() -> None:
    session_view = SessionView()
    model_id = WidgetModelId("test_model")
    model_id2 = WidgetModelId("test_model2")

    session_view.add_operation(
        SendUIElementMessage(
            model_id=model_id,
            message={"key": "value"},
            ui_element=None,
        )
    )
    assert model_id in session_view.model_messages
    assert session_view.model_messages[model_id][0].message == {"key": "value"}

    # Can add to existing model
    session_view.add_operation(
        SendUIElementMessage(
            model_id=model_id,
            message={"key": "new_value"},
            ui_element=None,
        )
    )
    assert len(session_view.model_messages[model_id]) == 2
    assert session_view.model_messages[model_id][1].message == {
        "key": "new_value"
    }

    # Can add multiple models
    session_view.add_operation(
        SendUIElementMessage(
            model_id=model_id2,
            message={"key2": "value2"},
            ui_element=None,
        )
    )
    assert model_id2 in session_view.model_messages
    assert session_view.model_messages[model_id2][0].message == {
        "key2": "value2"
    }


def test_last_run_code() -> None:
    session_view = SessionView()
    session_view.add_control_request(
        ExecuteMultipleRequest(
            cell_ids=[cell_id],
            codes=["print('hello')"],
        )
    )
    assert session_view.last_executed_code[cell_id] == "print('hello')"

    # Can overwrite values and add multiple
    session_view.add_control_request(
        ExecuteMultipleRequest(
            cell_ids=[cell_id, "cell_2"],
            codes=["print('hello world')", "print('hello world')"],
        )
    )
    assert session_view.last_executed_code[cell_id] == "print('hello world')"
    assert session_view.last_executed_code["cell_2"] == "print('hello world')"

    # Can add from CreationRequest
    session_view.add_control_request(
        CreationRequest(
            execution_requests=(
                ExecutionRequest(cell_id=cell_id, code="print('hello')"),
            ),
            set_ui_element_value_request=SetUIElementValueRequest.from_ids_and_values(
                []
            ),
            auto_run=True,
        )
    )
    assert session_view.last_executed_code[cell_id] == "print('hello')"


def test_serialize_parse_variable_value() -> None:
    original = VariableValue(name="var1", value=1)
    serialized = serialize(original)
    assert serialized == {"datatype": "int", "name": "var1", "value": "1"}
    parsed = parse_raw(serialized, VariableValue)
    assert parsed == original


def test_add_variables() -> None:
    session_view = SessionView()

    session_view.add_raw_operation(
        serialize(
            Variables(
                variables=[
                    VariableDeclaration(
                        name="var1", declared_by=[cell_id], used_by=[]
                    ),
                    VariableDeclaration(
                        name="var2", declared_by=[cell_id], used_by=[]
                    ),
                ]
            )
        )
    )
    session_view.add_raw_operation(
        serialize(
            VariableValues(
                variables=[
                    VariableValue(name="var1", value=1),
                    VariableValue(name="var2", value="hello"),
                ]
            )
        )
    )

    assert session_view.variable_operations.variables[0].name == "var1"
    assert session_view.variable_operations.variables[1].name == "var2"
    assert session_view.variable_values["var1"].value == "1"
    assert session_view.variable_values["var1"].datatype == "int"
    assert session_view.variable_values["var2"].value == "hello"
    assert session_view.variable_values["var2"].datatype == "str"


def test_add_datasets() -> None:
    session_view = SessionView()

    session_view.add_raw_operation(
        serialize(
            Datasets(
                tables=[
                    DataTable(
                        source_type="local",
                        source="df",
                        name="table1",
                        columns=[
                            DataTableColumn(
                                name="col1",
                                type="boolean",
                                external_type="BOOL",
                                sample_values=["true", "false"],
                            )
                        ],
                        num_rows=1,
                        num_columns=1,
                        variable_name="df1",
                    ),
                    DataTable(
                        source_type="local",
                        source="df",
                        name="table2",
                        columns=[
                            DataTableColumn(
                                name="col2",
                                type="integer",
                                external_type="INT",
                                sample_values=["1", "2"],
                            )
                        ],
                        num_rows=2,
                        num_columns=2,
                        variable_name="df2",
                    ),
                ]
            )
        )
    )

    assert session_view.datasets.tables[0].name == "table1"
    assert session_view.datasets.tables[1].name == "table2"
    assert session_view.datasets.tables[0].variable_name == "df1"
    assert session_view.datasets.tables[1].variable_name == "df2"

    # Can add a new table and overwrite an existing table

    session_view.add_raw_operation(
        serialize(
            Datasets(
                tables=[
                    DataTable(
                        source_type="local",
                        source="df",
                        name="table2",
                        columns=[
                            DataTableColumn(
                                name="new_col",
                                type="boolean",
                                external_type="BOOL",
                                sample_values=["true", "false"],
                            )
                        ],
                        num_rows=20,
                        num_columns=20,
                        variable_name="df2",
                    ),
                    DataTable(
                        source_type="local",
                        source="df",
                        name="table3",
                        columns=[],
                        num_rows=3,
                        num_columns=3,
                        variable_name="df3",
                    ),
                ]
            )
        )
    )

    assert session_view.datasets.tables[0].name == "table1"
    # Updated
    assert session_view.datasets.tables[1].name == "table2"
    assert session_view.datasets.tables[1].columns[0].name == "new_col"
    assert session_view.datasets.tables[1].num_rows == 20
    # Added
    assert session_view.datasets.tables[2].name == "table3"
    assert session_view.datasets.tables[2].variable_name == "df3"

    # Can filter out tables from new variables
    session_view.add_raw_operation(
        serialize(
            Variables(
                variables=[
                    VariableDeclaration(
                        name="df2", declared_by=[cell_id], used_by=[]
                    ),
                ]
            )
        )
    )

    assert len(session_view.datasets.tables) == 1
    assert session_view.datasets.tables[0].name == "table2"


def test_add_datasets_clear_channel() -> None:
    session_view = SessionView()
    session_view.add_raw_operation(
        serialize(
            Datasets(
                tables=[
                    DataTable(
                        source_type="duckdb",
                        source="db",
                        name="db.table1",
                        columns=[],
                        num_rows=1,
                        num_columns=1,
                        variable_name=None,
                    ),
                    DataTable(
                        source_type="local",
                        source="memory",
                        name="df1",
                        columns=[],
                        num_rows=1,
                        num_columns=1,
                        variable_name="df1",
                    ),
                ],
                clear_channel="duckdb",
            )
        )
    )

    assert len(session_view.datasets.tables) == 2
    names = [t.name for t in session_view.datasets.tables]
    assert "db.table1" in names
    assert "df1" in names

    session_view.add_raw_operation(
        serialize(
            Datasets(
                tables=[
                    DataTable(
                        source_type="local",
                        source="db",
                        name="db.table2",
                        columns=[],
                        num_rows=1,
                        num_columns=1,
                        variable_name=None,
                    )
                ],
                clear_channel="duckdb",
            )
        )
    )

    assert len(session_view.datasets.tables) == 2
    names = [t.name for t in session_view.datasets.tables]
    assert "db.table1" not in names
    assert "df1" in names
    assert "db.table2" in names


def test_add_data_source_connections() -> None:
    session_view = SessionView()

    # Add initial connections
    session_view.add_raw_operation(
        serialize(
            DataSourceConnections(
                connections=[
                    DataSourceConnection(
                        source="duckdb",
                        dialect="duckdb",
                        name="db1",
                        display_name="duckdb (db1)",
                    ),
                    DataSourceConnection(
                        source="sqlalchemy",
                        dialect="postgresql",
                        name="pg1",
                        display_name="postgresql (pg1)",
                    ),
                    DataSourceConnection(
                        source="duckdb",
                        dialect="default",
                        name=INTERNAL_DUCKDB_ENGINE,
                        display_name="duckdb internal",
                    ),
                ]
            )
        )
    )

    assert len(session_view.data_connectors.connections) == 3
    names = [c.name for c in session_view.data_connectors.connections]
    assert "db1" in names
    assert "pg1" in names
    assert INTERNAL_DUCKDB_ENGINE in names

    # Add new connection and update existing
    session_view.add_raw_operation(
        serialize(
            DataSourceConnections(
                connections=[
                    DataSourceConnection(
                        source="duckdb",
                        dialect="duckdb",
                        name="db1",
                        display_name="duckdb (db1_updated)",
                    ),
                    DataSourceConnection(
                        source="sqlalchemy",
                        dialect="mysql",
                        name="mysql1",
                        display_name="mysql (mysql1)",
                    ),
                ]
            )
        )
    )

    assert len(session_view.data_connectors.connections) == 4
    conns = {c.name: c for c in session_view.data_connectors.connections}

    # Check updated connection
    assert "db1" in conns
    assert conns["db1"].display_name == "duckdb (db1_updated)"

    # Check new connection replaced old one
    assert "mysql1" in conns
    assert conns["mysql1"].dialect == "mysql"
    # Check existing connection
    assert "pg1" in conns
    assert INTERNAL_DUCKDB_ENGINE in names

    # Check connectors in operations
    assert session_view.data_connectors in session_view.operations

    # Filter out connections from variables
    session_view.add_raw_operation(
        serialize(
            Variables(
                variables=[
                    VariableDeclaration(
                        name="mysql1", declared_by=[cell_id], used_by=[]
                    ),
                ]
            )
        )
    )
    assert len(session_view.data_connectors.connections) == 2
    session_view_names = [
        c.name for c in session_view.data_connectors.connections
    ]
    assert "mysql1" in session_view_names
    assert INTERNAL_DUCKDB_ENGINE in session_view_names


def test_add_cell_op() -> None:
    session_view = SessionView()
    session_view.add_raw_operation(
        serialize(
            CellOp(
                cell_id=cell_id, output=initial_output, status=initial_status
            )
        )
    )

    assert session_view.cell_operations[cell_id].output == initial_output
    assert session_view.cell_operations[cell_id].status == initial_status


# patch time
@patch("time.time", return_value=123)
def test_combine_console_outputs(time_mock: Any) -> None:
    del time_mock
    session_view = SessionView()
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=CellOutput.stdout("one"),
            status="running",
        )
    )
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=CellOutput.stdout("two"),
            status="running",
        )
    )

    assert session_view.cell_operations[cell_id].console == [
        CellOutput.stdout("one"),
        CellOutput.stdout("two"),
    ]

    # Moves to queued
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=None,
            status="queued",
        )
    )

    assert session_view.cell_operations[cell_id].console == [
        CellOutput.stdout("one"),
        CellOutput.stdout("two"),
    ]

    # Moves to running clears console
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=None,
            status="running",
        )
    )
    assert session_view.cell_operations[cell_id].console == []

    # Write again
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=CellOutput.stdout("three"),
            status="running",
        )
    )
    assert session_view.cell_operations[cell_id].console == [
        CellOutput.stdout("three")
    ]


@patch("time.time", return_value=123)
def test_stdin(time_mock: Any) -> None:
    del time_mock
    session_view = SessionView()
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=CellOutput.stdout("Hello"),
            status="running",
        )
    )
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=CellOutput.stdin("What is your name?"),
            status="running",
        )
    )

    assert session_view.cell_operations[cell_id].console == [
        CellOutput.stdout("Hello"),
        CellOutput.stdin("What is your name?"),
    ]

    session_view.add_stdin("marimo")

    assert session_view.cell_operations[cell_id].console == [
        CellOutput.stdout("Hello"),
        CellOutput.stdout("What is your name? marimo\n"),
    ]


@patch("time.time", return_value=123)
def test_get_cell_outputs(time_mock: Any) -> None:
    del time_mock
    cell_2_id = "cell_2"
    session_view = SessionView()
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            output=initial_output,
            status=initial_status,
        ),
    )
    session_view.add_operation(
        CellOp(
            cell_id=cell_2_id,
            output=None,
            status=updated_status,
        ),
    )

    assert session_view.get_cell_outputs([cell_id]) == {
        cell_id: initial_output
    }
    assert session_view.get_cell_outputs([cell_id, cell_2_id]) == {
        cell_id: initial_output
    }

    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            output=updated_output,
            status=updated_status,
        )
    )
    session_view.add_operation(
        CellOp(
            cell_id=cell_2_id,
            output=updated_output,
            status=updated_status,
        )
    )

    assert session_view.get_cell_outputs([cell_id, cell_2_id]) == {
        cell_id: updated_output,
        cell_2_id: updated_output,
    }


@patch("time.time", return_value=123)
def test_get_cell_console_outputs(time_mock: Any) -> None:
    del time_mock
    cell_2_id = "cell_2"
    session_view = SessionView()
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=[CellOutput.stdout("one")],
            status=initial_status,
        )
    )
    session_view.add_operation(
        CellOp(
            cell_id=cell_2_id,
            console=None,
            status=updated_status,
        )
    )

    assert session_view.get_cell_console_outputs([cell_id]) == {
        cell_id: [CellOutput.stdout("one")]
    }
    assert session_view.get_cell_console_outputs([cell_id, cell_2_id]) == {
        cell_id: [CellOutput.stdout("one")],
    }

    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            console=[CellOutput.stdout("two")],
            status=updated_status,
        )
    )
    session_view.add_operation(
        CellOp(
            cell_id=cell_2_id,
            console=[CellOutput.stdout("two")],
            status=updated_status,
        )
    )

    assert session_view.get_cell_console_outputs([cell_id, cell_2_id]) == {
        cell_id: [CellOutput.stdout("one"), CellOutput.stdout("two")],
        cell_2_id: [CellOutput.stdout("two")],
    }


def test_mark_auto_export():
    session_view = SessionView()
    assert session_view.needs_export("html")
    assert session_view.needs_export("md")

    session_view.mark_auto_export_html()
    assert not session_view.needs_export("html")

    session_view.mark_auto_export_md()
    assert not session_view.needs_export("md")

    session_view._touch()
    assert session_view.needs_export("html")
    assert session_view.needs_export("md")

    session_view.mark_auto_export_html()
    session_view.mark_auto_export_md()
    session_view.add_operation(
        CellOp(
            cell_id=cell_id,
            output=initial_output,
            status=initial_status,
        ),
    )
    assert session_view.needs_export("html")
    assert session_view.needs_export("md")

    session_view.mark_auto_export_session()
    assert not session_view.needs_export("session")

    session_view._touch()
    assert session_view.needs_export("session")


def test_stale_code() -> None:
    """Test that stale code is properly tracked and included in operations."""
    session_view = SessionView()
    assert session_view.stale_code is None

    # Add stale code operation
    stale_code_op = UpdateCellCodes(
        cell_ids=["cell1"],
        codes=["print('hello')"],
        code_is_stale=True,
    )
    session_view.add_operation(stale_code_op)

    # Verify stale code is tracked
    assert session_view.stale_code == stale_code_op
    assert session_view.stale_code in session_view.operations

    # Add non-stale code operation
    non_stale_code_op = UpdateCellCodes(
        cell_ids=["cell2"],
        codes=["print('world')"],
        code_is_stale=False,
    )
    session_view.add_operation(non_stale_code_op)

    # Verify non-stale code doesn't affect stale_code tracking
    assert session_view.stale_code == stale_code_op
    assert session_view.stale_code in session_view.operations

    # Update stale code
    new_stale_code_op = UpdateCellCodes(
        cell_ids=["cell3"],
        codes=["print('updated')"],
        code_is_stale=True,
    )
    session_view.add_operation(new_stale_code_op)

    # Verify stale code is updated
    assert session_view.stale_code == new_stale_code_op
    assert session_view.stale_code in session_view.operations
    assert stale_code_op not in session_view.operations


def test_dataset_filter_by_engine_and_variable() -> None:
    session_view = SessionView()

    # Initially add three tables: one with an engine, one with a variable name, and one with neither
    session_view.add_raw_operation(
        serialize(
            Datasets(
                tables=[
                    DataTable(
                        source_type="connection",
                        source="duckdb",
                        name="table_with_engine",
                        columns=[],
                        num_rows=1,
                        num_columns=1,
                        engine="some_engine",
                        variable_name=None,
                    ),
                    DataTable(
                        source_type="local",
                        source="df",
                        name="table_with_var",
                        columns=[],
                        num_rows=1,
                        num_columns=1,
                        engine=None,
                        variable_name="some_var",
                    ),
                    DataTable(
                        source_type="local",
                        source="df",
                        name="table_none",
                        columns=[],
                        num_rows=1,
                        num_columns=1,
                        engine=None,
                        variable_name=None,
                    ),
                ]
            )
        )
    )
    # Confirm all three are present before filtering
    assert len(session_view.datasets.tables) == 3

    # Step 1: Add operation of all variables
    session_view.add_operation(
        Variables(
            variables=[
                VariableDeclaration(
                    name="some_engine", declared_by=[], used_by=[]
                ),
                VariableDeclaration(
                    name="some_var", declared_by=[], used_by=[]
                ),
            ]
        )
    )
    assert len(session_view.datasets.tables) == 3

    # Step 2: Only "some_engine" is in scope => keep table_with_engine + table_none
    session_view.add_operation(
        Variables(
            variables=[
                VariableDeclaration(
                    name="some_engine", declared_by=[], used_by=[]
                )
            ]
        )
    )
    table_names = [t.name for t in session_view.datasets.tables]
    assert "table_with_engine" in table_names
    assert "table_with_var" not in table_names
    assert "table_none" in table_names

    # Step 3: No variables => only table with neither engine nor variable_name is kept
    session_view.add_operation(Variables(variables=[]))
    table_names = [t.name for t in session_view.datasets.tables]
    assert table_names == ["table_none"]
