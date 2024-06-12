# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from marimo._ast.cell import CellId_t, CellStatusType
from marimo._data.models import DataTable, DataTableColumn
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import (
    CellOp,
    Datasets,
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
from marimo._utils.parse_dataclass import parse_raw

cell_id: CellId_t = "cell_1"

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

initial_status = "running"
updated_status: CellStatusType = "running"


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
        )
    )
    assert "test_ui3" in session_view.ui_values


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
                        source="Local",
                        name="table1",
                        columns=[DataTableColumn(name="col1", type="boolean")],
                        num_rows=1,
                        num_columns=1,
                        variable_name="df1",
                    ),
                    DataTable(
                        source="Local",
                        name="table2",
                        columns=[DataTableColumn(name="col2", type="integer")],
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
                        source="Local",
                        name="table2",
                        columns=[
                            DataTableColumn(name="new_col", type="boolean")
                        ],
                        num_rows=20,
                        num_columns=20,
                        variable_name="df2",
                    ),
                    DataTable(
                        source="Local",
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
