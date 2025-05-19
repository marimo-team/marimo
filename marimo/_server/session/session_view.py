# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal, Optional

from marimo._data.models import DataSourceConnection, DataTable
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import (
    CellOp,
    Datasets,
    DataSourceConnections,
    Interrupted,
    MessageOperation,
    SendUIElementMessage,
    UpdateCellCodes,
    UpdateCellIdsRequest,
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
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE
from marimo._types.ids import CellId_t, WidgetModelId
from marimo._utils.lists import as_list
from marimo._utils.parse_dataclass import parse_raw

ExportType = Literal["html", "md", "ipynb", "session"]


@dataclass
class AutoExportState:
    html: bool = False
    md: bool = False
    ipynb: bool = False
    session: bool = False

    def mark_all_stale(self) -> None:
        self.html = False
        self.md = False
        self.ipynb = False
        self.session = False

    def is_stale(self, export_type: ExportType) -> bool:
        return not getattr(self, export_type)

    def mark_exported(self, export_type: ExportType) -> None:
        setattr(self, export_type, True)


class SessionView:
    """
    This stores the current view of the session.

    Which are the cell's outputs, status, and console.
    """

    def __init__(self) -> None:
        # Last seen cell IDs
        self.cell_ids: Optional[UpdateCellIdsRequest] = None
        # List of operations we care about keeping track of.
        self.cell_operations: dict[CellId_t, CellOp] = {}
        # The most recent datasets operation.
        self.datasets = Datasets(tables=[])
        # The most recent data-connectors operation
        self.data_connectors = DataSourceConnections(connections=[])
        # The most recent Variables operation.
        self.variable_operations: Variables = Variables(variables=[])
        # Map of variable name to value.
        self.variable_values: dict[str, VariableValue] = {}
        # Map of object id to value.
        self.ui_values: dict[str, Any] = {}
        # Map of cell id to the last code that was executed in that cell.
        self.last_executed_code: dict[CellId_t, str] = {}
        # Map of cell id to the last cell execution time
        self.last_execution_time: dict[CellId_t, float] = {}
        # Any stale code that was read from a file-watcher
        self.stale_code: Optional[UpdateCellCodes] = None
        # Model messages
        self.model_messages: dict[
            WidgetModelId, list[SendUIElementMessage]
        ] = {}

        # Auto-saving
        self.auto_export_state = AutoExportState()

    def _add_ui_value(self, name: str, value: Any) -> None:
        self.ui_values[name] = value

    def _add_last_run_code(self, req: ExecutionRequest) -> None:
        self.last_executed_code[req.cell_id] = req.code

    def add_raw_operation(self, raw_operation: Any) -> None:
        self._touch()

        # parse_raw only accepts a dataclass, so we wrap MessageOperation in a
        # dataclass.
        @dataclass
        class _Container:
            operation: MessageOperation

        operation = parse_raw({"operation": raw_operation}, _Container)
        self.add_operation(operation.operation)

    def add_control_request(self, request: ControlRequest) -> None:
        self._touch()

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
        self._touch()

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
        self._touch()
        self.auto_export_state.mark_all_stale()

        """Add an operation to the session view."""

        if isinstance(operation, CellOp):
            previous = self.cell_operations.get(operation.cell_id)
            self.cell_operations[operation.cell_id] = merge_cell_operation(
                previous, operation
            )
            if not previous:
                return
            if previous.status == "queued" and operation.status == "running":
                self.save_execution_time(operation, "start")
            if previous.status == "running" and operation.status == "idle":
                self.save_execution_time(operation, "end")

        elif isinstance(operation, Variables):
            self.variable_operations = operation

            # Set of variable names that are in scope.
            variable_names: set[str] = set(
                [v.name for v in self.variable_operations.variables]
            )

            # Remove any variable values that are no longer in scope.
            next_values: dict[str, VariableValue] = {}
            for name, value in self.variable_values.items():
                if name in variable_names:
                    next_values[name] = value
            self.variable_values = next_values

            # Remove any table values that are no longer in scope.
            next_tables: dict[str, DataTable] = {}
            for table in self.datasets.tables:
                # If it's connected to an engine, then the engine variable must still exist
                # If it's connected to a variable, then the variable must still exist
                # Otherwise, we include it
                if table.engine is not None:
                    if table.engine in variable_names:
                        next_tables[table.name] = table
                elif table.variable_name is not None:
                    if table.variable_name in variable_names:
                        next_tables[table.name] = table
                else:
                    next_tables[table.name] = table
            self.datasets = Datasets(tables=list(next_tables.values()))

            # Remove any data source connections that are no longer in scope.
            # Keep internal connections if they exist as these are not defined in variables
            next_connections: dict[str, DataSourceConnection] = {}
            for connection in self.data_connectors.connections:
                if (
                    connection.name in variable_names
                    or connection.name == INTERNAL_DUCKDB_ENGINE
                ):
                    next_connections[connection.name] = connection
            self.data_connectors = DataSourceConnections(
                connections=list(next_connections.values())
            )

        elif isinstance(operation, VariableValues):
            for value in operation.variables:
                self.variable_values[value.name] = value

        elif isinstance(operation, Interrupted):
            # Resolve stdin
            self.add_stdin("")
        elif isinstance(operation, Datasets):
            # Merge datasets, dedupe by table name and keep the latest.
            # If clear_channel is set, clear those tables
            prev_tables = self.datasets.tables
            if operation.clear_channel is not None:
                prev_tables = [
                    t
                    for t in prev_tables
                    if t.source_type != operation.clear_channel
                ]

            tables = {t.name: t for t in prev_tables}
            for table in operation.tables:
                tables[table.name] = table
            self.datasets = Datasets(tables=list(tables.values()))

        elif isinstance(operation, DataSourceConnections):
            # Update data source connections, dedupe by name and keep the latest
            prev_connections = self.data_connectors.connections
            connections = {c.name: c for c in prev_connections}

            for c in operation.connections:
                connections[c.name] = c

            self.data_connectors = DataSourceConnections(
                connections=list(connections.values())
            )

        elif isinstance(operation, UpdateCellIdsRequest):
            self.cell_ids = operation

        elif (
            isinstance(operation, UpdateCellCodes) and operation.code_is_stale
        ):
            self.stale_code = operation

        elif isinstance(operation, SendUIElementMessage):
            if operation.model_id is None:
                return
            messages = self.model_messages.get(operation.model_id, [])
            messages.append(operation)
            # TODO: cleanup/merge previous 'update' messages
            self.model_messages[operation.model_id] = messages

    def get_cell_outputs(
        self, ids: list[CellId_t]
    ) -> dict[CellId_t, CellOutput]:
        """Get the outputs for the given cell ids."""
        outputs: dict[CellId_t, CellOutput] = {}
        for cell_id in ids:
            cell_op = self.cell_operations.get(cell_id)
            if cell_op is not None and cell_op.output is not None:
                outputs[cell_id] = cell_op.output
        return outputs

    def get_cell_console_outputs(
        self, ids: list[CellId_t]
    ) -> dict[CellId_t, list[CellOutput]]:
        """Get the console outputs for the given cell ids."""
        outputs: dict[CellId_t, list[CellOutput]] = {}
        for cell_id in ids:
            cell_op = self.cell_operations.get(cell_id)
            if cell_op is not None and cell_op.console:
                outputs[cell_id] = as_list(cell_op.console)
        return outputs

    def save_execution_time(
        self, operation: MessageOperation, event: Literal["start", "end"]
    ) -> None:
        """Updates execution time for given cell."""
        if not isinstance(operation, CellOp):
            return
        cell_id = operation.cell_id

        if event == "start":
            time_elapsed = operation.timestamp
        elif event == "end":
            start = self.last_execution_time.get(cell_id)
            start = start if start else 0
            time_elapsed = time.time() - start
            time_elapsed = round(time_elapsed * 1000)

        self.last_execution_time[cell_id] = time_elapsed

    @property
    def operations(self) -> list[MessageOperation]:
        all_ops: list[MessageOperation] = []
        if self.cell_ids:
            all_ops.append(self.cell_ids)
        if self.variable_operations.variables:
            all_ops.append(self.variable_operations)
        if self.variable_values:
            all_ops.append(
                VariableValues(variables=list(self.variable_values.values()))
            )
        if self.datasets.tables:
            all_ops.append(self.datasets)
        if self.data_connectors.connections:
            all_ops.append(self.data_connectors)
        all_ops.extend(self.cell_operations.values())
        if self.stale_code:
            all_ops.append(self.stale_code)
        if self.model_messages:
            for messages in self.model_messages.values():
                all_ops.extend(messages)
        return all_ops

    def mark_auto_export_html(self) -> None:
        self.auto_export_state.mark_exported("html")

    def mark_auto_export_md(self) -> None:
        self.auto_export_state.mark_exported("md")

    def mark_auto_export_ipynb(self) -> None:
        self.auto_export_state.mark_exported("ipynb")

    def mark_auto_export_session(self) -> None:
        self.auto_export_state.mark_exported("session")

    def needs_export(self, export_type: ExportType) -> bool:
        return self.auto_export_state.is_stale(export_type)

    def _touch(self) -> None:
        self.auto_export_state.mark_all_stale()


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
