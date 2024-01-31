# Copyright 2024 Marimo. All rights reserved.

from typing import Any
from unittest.mock import patch

from marimo._ast.cell import CellId_t, CellStatusType
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import (
    CellOp,
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


def test_ui_values():
    session_view = SessionView()
    session_view.add_request(SetUIElementValueRequest([("test_ui", 123)]))
    assert "test_ui" in session_view.ui_values
    assert session_view.ui_values["test_ui"] == 123

    # Can add multiple values
    # and can overwrite values
    session_view.add_request(
        SetUIElementValueRequest([("test_ui2", 456), ("test_ui", 789)])
    )
    assert "test_ui2" in session_view.ui_values
    assert "test_ui" in session_view.ui_values
    assert session_view.ui_values["test_ui2"] == 456
    assert session_view.ui_values["test_ui"] == 789

    # Can add from CreationRequest
    session_view.add_request(
        CreationRequest(
            execution_requests=(),
            set_ui_element_value_request=SetUIElementValueRequest(
                [("test_ui3", 101112)]
            ),
        )
    )
    assert "test_ui3" in session_view.ui_values


def test_last_run_code():
    session_view = SessionView()
    session_view.add_request(
        ExecuteMultipleRequest(
            execution_requests=(
                ExecutionRequest(cell_id=cell_id, code="print('hello')"),
            )
        )
    )
    assert session_view.last_executed_code[cell_id] == "print('hello')"

    # Can overwrite values and add multiple
    session_view.add_request(
        ExecuteMultipleRequest(
            execution_requests=(
                ExecutionRequest(cell_id=cell_id, code="print('hello world')"),
                ExecutionRequest(
                    cell_id="cell_2", code="print('hello world')"
                ),
            )
        )
    )
    assert session_view.last_executed_code[cell_id] == "print('hello world')"
    assert session_view.last_executed_code["cell_2"] == "print('hello world')"

    # Can add from CreationRequest
    session_view.add_request(
        CreationRequest(
            execution_requests=(
                ExecutionRequest(cell_id=cell_id, code="print('hello')"),
            ),
            set_ui_element_value_request=SetUIElementValueRequest([]),
        )
    )
    assert session_view.last_executed_code[cell_id] == "print('hello')"


def test_add_variables():
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
    assert session_view.variable_values["var2"].value == "hello"


def test_add_cell_op():
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
