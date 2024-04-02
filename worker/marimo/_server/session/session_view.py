# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

from marimo._ast.cell import CellId_t
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import (
    CellOp,
    Interrupted,
    MessageOperation,
    Variables,
    VariableValue,
    VariableValues,
)
from marimo._runtime.requests import (
    ControlRequest,
    CreationRequest,
    ExecuteMultipleRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._utils.parse_dataclass import parse_raw


class SessionView:
    """
    This stores the current view of the session.

    Which are the cell's outputs, status, and console.
    """

    def __init__(self) -> None:
        # List of operations we care about keeping track of.
        self.cell_operations: dict[CellId_t, CellOp] = {}
        # The most recent Variables operation.
        self.variable_operations: Variables = Variables(variables=[])
        # Map of variable name to value.
        self.variable_values: dict[str, VariableValue] = {}
        # Map of object id to value.
        self.ui_values: dict[str, Any] = {}
        # Map of cell id to the last code that was executed in that cell.
        self.last_executed_code: dict[CellId_t, str] = {}

    def _add_ui_value(self, name: str, value: Any) -> None:
        self.ui_values[name] = value

    def _add_last_run_code(self, req: ExecutionRequest) -> None:
        self.last_executed_code[req.cell_id] = req.code

    def add_raw_operation(self, raw_operation: Any) -> None:
        # parse_raw only accepts a dataclass, so we wrap MessageOperation in a
        # dataclass.
        @dataclass
        class _Container:
            operation: MessageOperation

        operation = parse_raw({"operation": raw_operation}, _Container)
        self.add_operation(operation.operation)

    def add_control_request(self, request: ControlRequest) -> None:
        if isinstance(request, SetUIElementValueRequest):
            for object_id, value in request.ids_and_values:
                self._add_ui_value(object_id, value)
        elif isinstance(request, ExecuteMultipleRequest):
            for execution_request in request.execution_requests:
                self._add_last_run_code(execution_request)
        elif isinstance(request, CreationRequest):
            for (
                object_id,
                value,
            ) in request.set_ui_element_value_request.ids_and_values:
                self._add_ui_value(object_id, value)
            for execution_request in request.execution_requests:
                self._add_last_run_code(execution_request)

    def add_stdin(self, stdin: str) -> None:
        """Add a stdin request to the session view."""
        # Find the first cell that is waiting for stdin.
        for cell_op in self.cell_operations.values():
            console_ops: list[CellOutput] = as_list(cell_op.console)
            for cell_output in console_ops:
                if cell_output.channel == CellChannel.STDIN:
                    cell_output.channel = CellChannel.STDOUT
                    cell_output.data = f"{cell_output.data} {stdin}\n"
                    return

    def add_operation(self, operation: MessageOperation) -> None:
        """Add an operation to the session view."""

        if isinstance(operation, CellOp):
            previous = self.cell_operations.get(operation.cell_id)
            self.cell_operations[operation.cell_id] = merge_cell_operation(
                previous, operation
            )
        elif isinstance(operation, Variables):
            self.variable_operations = operation

            # Remove any variable values that are no longer in scope.
            names: set[str] = set(
                [v.name for v in self.variable_operations.variables]
            )
            next_values: dict[str, VariableValue] = {}
            for name, value in self.variable_values.items():
                if name in names:
                    next_values[name] = value
            self.variable_values = next_values

        elif isinstance(operation, VariableValues):
            for value in operation.variables:
                self.variable_values[value.name] = value

        elif isinstance(operation, Interrupted):
            # Resolve stdin
            self.add_stdin("")

    @property
    def operations(self) -> list[MessageOperation]:
        all_ops: list[MessageOperation] = [
            self.variable_operations,
            VariableValues(variables=list(self.variable_values.values())),
        ]
        all_ops.extend(self.cell_operations.values())
        return all_ops


def merge_cell_operation(
    previous: Optional[CellOp],
    next_: CellOp,
) -> CellOp:
    """Merge two cell operations."""
    if previous is None:
        return next_

    assert previous.cell_id == next_.cell_id

    if next_.status is None:
        next_.status = previous.status

    # If we went from queued to running, clear the console.
    if next_.status == "running" and previous.status == "queued":
        next_.console = []
    else:
        combined_console: list[CellOutput] = as_list(previous.console)
        combined_console.extend(as_list(next_.console))
        next_.console = combined_console

    # If we went from running to running, use the previous timestamp.
    if next_.status == "running" and previous.status == "running":
        next_.timestamp = previous.timestamp

    if next_.output is None:
        next_.output = previous.output

    return next_


def as_list(value: Union[Any, Optional[Any], list[Any]]) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
