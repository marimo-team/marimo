# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

from marimo._ast.cell import CellId_t
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.ops import (
    CellOp,
    MessageOperation,
    Variables,
    VariableValue,
    VariableValues,
)
from marimo._runtime.requests import Request, SetUIElementValueRequest
from marimo._utils.parse_dataclass import parse_raw


class SessionView:
    """
    This stores the current view of the session.

    Which are the cell's outputs, status, and console.
    """

    def __init__(self) -> None:
        # List of operations we care about keeping track of.
        self.cell_operations: dict[CellId_t, CellOp] = {}
        self.variable_operations: Variables = Variables(variables=[])
        self.variable_values: dict[str, VariableValue] = {}
        self.ui_values: dict[str, Any] = {}

    def add_ui_value(self, name: str, value: Any) -> None:
        self.ui_values[name] = value

    def add_raw_operation(self, raw_operation: Any) -> None:
        # parse_raw only accepts a dataclass, so we wrap MessageOperation in a
        # dataclass.
        @dataclass
        class _Container:
            operation: MessageOperation

        operation = parse_raw({"operation": raw_operation}, _Container)
        self.add_operation(operation.operation)

    def add_request(self, request: Request) -> None:
        if isinstance(request, SetUIElementValueRequest):
            for object_id, value in request.ids_and_values:
                self.add_ui_value(object_id, value)
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
    if not value:
        return []
    return value if isinstance(value, list) else [value]
