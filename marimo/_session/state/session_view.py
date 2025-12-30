# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal, Optional

from marimo._data.models import DataSourceConnection, DataTable
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import (
    CellNotification,
    DatasetsNotification,
    DataSourceConnectionsNotification,
    InstallingPackageAlertNotification,
    InterruptedNotification,
    NotificationMessage,
    SQLTableListPreviewNotification,
    SQLTablePreviewNotification,
    StartupLogsNotification,
    UIElementMessageNotification,
    UpdateCellCodesNotification,
    UpdateCellIdsNotification,
    VariablesNotification,
    VariableValue,
    VariableValuesNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._runtime.commands import (
    CommandMessage,
    CreateNotebookCommand,
    ExecuteCellCommand,
    ExecuteCellsCommand,
    SyncGraphCommand,
    UpdateUIElementCommand,
)
from marimo._sql.connection_utils import (
    update_table_in_connection,
    update_table_list_in_connection,
)
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE
from marimo._types.ids import CellId_t, WidgetModelId
from marimo._utils.lists import as_list

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
    """A representation of a session state for replay and serialization.

    Of note, a SessionView stores:
    * the last-seen notebook-order of Cell IDs
    * a mapping from cell IDs to their last seen notification of interest,
      such as an output, status, or console output
    * various other state needed for replay

    A notebook session can be hydrated from a serialized SessionView,
    for example on notebook startup when auto-instantiate is off, or
    on reconnection via a replay.
    """

    def __init__(self) -> None:
        # Last seen notebook-order of cell IDs
        self.cell_ids: Optional[UpdateCellIdsNotification] = None
        # A mapping from cell (IDs) to their last seen notification
        self.cell_notifications: dict[CellId_t, CellNotification] = {}
        # The most recent datasets notification.
        self.datasets = DatasetsNotification(tables=[])
        # The most recent data-connectors notification
        self.data_connectors = DataSourceConnectionsNotification(
            connections=[]
        )
        # The most recent Variables notification.
        self.variable_notifications: VariablesNotification = (
            VariablesNotification(variables=[])
        )
        # Map of variable name to value.
        self.variable_values: dict[str, VariableValue] = {}
        # Map of object id to value.
        self.ui_values: dict[str, Any] = {}
        # Map of cell id to the last code that was executed in that cell.
        self.last_executed_code: dict[CellId_t, str] = {}
        # Map of cell id to the last cell execution time
        self.last_execution_time: dict[CellId_t, float] = {}
        # Any stale code that was read from a file-watcher
        self.stale_code: Optional[UpdateCellCodesNotification] = None
        # Model messages
        self.model_messages: dict[
            WidgetModelId, list[UIElementMessageNotification]
        ] = {}

        # Startup logs for startup command - only one at a time
        self.startup_logs: Optional[StartupLogsNotification] = None

        # Package installation logs - accumulated per package
        self.package_logs: dict[
            str, str
        ] = {}  # package name -> accumulated logs

        # Auto-saving
        self.auto_export_state = AutoExportState()

    def _add_ui_value(self, name: str, value: Any) -> None:
        self.ui_values[name] = value

    def _add_last_run_code(self, req: ExecuteCellCommand) -> None:
        self.last_executed_code[req.cell_id] = req.code

    def add_raw_notification(self, raw_notification: KernelMessage) -> None:
        self._touch()
        # Type ignore because NotificationMessage is a Union, not a class
        self.add_notification(deserialize_kernel_message(raw_notification))  # type: ignore[arg-type]

    def add_control_request(self, request: CommandMessage) -> None:
        self._touch()

        if isinstance(request, UpdateUIElementCommand):
            for object_id, value in request.ids_and_values:
                self._add_ui_value(object_id, value)
        elif isinstance(request, (ExecuteCellsCommand, SyncGraphCommand)):
            for execution_request in request.execution_requests:
                self._add_last_run_code(execution_request)
        elif isinstance(request, CreateNotebookCommand):
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
        for cell_notif in self.cell_notifications.values():
            console_outputs: list[CellOutput] = as_list(cell_notif.console)
            for cell_output in console_outputs:
                if cell_output.channel == CellChannel.STDIN:
                    cell_output.channel = CellChannel.STDOUT
                    cell_output.data = f"{cell_output.data} {stdin}\n"
                    return

    def add_notification(self, notification: NotificationMessage) -> None:
        """Add a notification to the session view."""
        self._touch()
        self.auto_export_state.mark_all_stale()

        if isinstance(notification, CellNotification):
            previous = self.cell_notifications.get(notification.cell_id)
            self.cell_notifications[notification.cell_id] = (
                merge_cell_notification(previous, notification)
            )
            if not previous:
                return
            if (
                previous.status == "queued"
                and notification.status == "running"
            ):
                self.save_execution_time(notification, "start")
            if previous.status == "running" and notification.status == "idle":
                self.save_execution_time(notification, "end")

        elif isinstance(notification, VariablesNotification):
            self.variable_notifications = notification

            # Set of variable names that are in scope.
            variable_names: set[str] = set(
                [v.name for v in self.variable_notifications.variables]
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
            self.datasets = DatasetsNotification(
                tables=list(next_tables.values())
            )

            # Remove any data source connections that are no longer in scope.
            # Keep internal connections if they exist as these are not defined in variables
            next_connections: dict[str, DataSourceConnection] = {}
            for connection in self.data_connectors.connections:
                if (
                    connection.name in variable_names
                    or connection.name == INTERNAL_DUCKDB_ENGINE
                ):
                    next_connections[connection.name] = connection
            self.data_connectors = DataSourceConnectionsNotification(
                connections=list(next_connections.values())
            )

        elif isinstance(notification, VariableValuesNotification):
            for value in notification.variables:
                self.variable_values[value.name] = value

        elif isinstance(notification, InterruptedNotification):
            # Resolve stdin
            self.add_stdin("")
        elif isinstance(notification, DatasetsNotification):
            # Merge datasets, dedupe by table name and keep the latest.
            # If clear_channel is set, clear those tables
            prev_tables = self.datasets.tables
            if notification.clear_channel is not None:
                prev_tables = [
                    t
                    for t in prev_tables
                    if t.source_type != notification.clear_channel
                ]

            tables = {t.name: t for t in prev_tables}
            for table in notification.tables:
                tables[table.name] = table
            self.datasets = DatasetsNotification(tables=list(tables.values()))

        elif isinstance(notification, DataSourceConnectionsNotification):
            # Update data source connections, dedupe by name and keep the latest
            prev_connections = self.data_connectors.connections
            connections = {c.name: c for c in prev_connections}

            for c in notification.connections:
                connections[c.name] = c

            self.data_connectors = DataSourceConnectionsNotification(
                connections=list(connections.values())
            )

        elif isinstance(notification, SQLTablePreviewNotification):
            sql_table_preview = notification
            sql_metadata = sql_table_preview.metadata
            table_preview_connections = self.data_connectors.connections
            if sql_table_preview.table is not None:
                update_table_in_connection(
                    table_preview_connections,
                    sql_metadata,
                    sql_table_preview.table,
                )

        elif isinstance(notification, SQLTableListPreviewNotification):
            sql_table_list_preview = notification
            sql_metadata = sql_table_list_preview.metadata
            table_list_connections = self.data_connectors.connections
            update_table_list_in_connection(
                table_list_connections,
                sql_metadata,
                sql_table_list_preview.tables,
            )

        elif isinstance(notification, UpdateCellIdsNotification):
            self.cell_ids = notification

        elif (
            isinstance(notification, UpdateCellCodesNotification)
            and notification.code_is_stale
        ):
            self.stale_code = notification

        elif isinstance(notification, UIElementMessageNotification):
            if notification.model_id is None:
                return
            messages = self.model_messages.get(notification.model_id, [])
            messages.append(notification)
            # TODO: cleanup/merge previous 'update' messages
            self.model_messages[notification.model_id] = messages

        elif isinstance(notification, StartupLogsNotification):
            prev = self.startup_logs.content if self.startup_logs else ""
            self.startup_logs = StartupLogsNotification(
                content=prev + notification.content,
                status=notification.status,
            )

        elif isinstance(notification, InstallingPackageAlertNotification):
            # Handle streaming logs if present
            if notification.logs and notification.log_status:
                for package_name, new_content in notification.logs.items():
                    if notification.log_status == "start":
                        # Start new log for this package
                        self.package_logs[package_name] = new_content
                    elif notification.log_status == "append":
                        # Append to existing log
                        prev_content = self.package_logs.get(package_name, "")
                        self.package_logs[package_name] = (
                            prev_content + new_content
                        )
                    elif notification.log_status == "done":
                        # Append final content and mark as done
                        prev_content = self.package_logs.get(package_name, "")
                        self.package_logs[package_name] = (
                            prev_content + new_content
                        )
                        # We could clean up completed logs here if desired,
                        # but for now keep them for replay purposes

    def get_cell_outputs(
        self, ids: list[CellId_t]
    ) -> dict[CellId_t, CellOutput]:
        """Get the outputs for the given cell ids."""
        outputs: dict[CellId_t, CellOutput] = {}
        for cell_id in ids:
            cell_notif = self.cell_notifications.get(cell_id)
            if cell_notif is not None and cell_notif.output is not None:
                outputs[cell_id] = cell_notif.output
        return outputs

    def get_cell_console_outputs(
        self, ids: list[CellId_t]
    ) -> dict[CellId_t, list[CellOutput]]:
        """Get the console outputs for the given cell ids."""
        outputs: dict[CellId_t, list[CellOutput]] = {}
        for cell_id in ids:
            cell_notif = self.cell_notifications.get(cell_id)
            if cell_notif is not None and cell_notif.console:
                outputs[cell_id] = as_list(cell_notif.console)
        return outputs

    def save_execution_time(
        self, notification: NotificationMessage, event: Literal["start", "end"]
    ) -> None:
        """Updates execution time for given cell."""
        if not isinstance(notification, CellNotification):
            return
        cell_id = notification.cell_id

        if event == "start":
            time_elapsed = notification.timestamp
        elif event == "end":
            start = self.last_execution_time.get(cell_id)
            start = start if start else 0
            time_elapsed = time.time() - start
            time_elapsed = round(time_elapsed * 1000)

        self.last_execution_time[cell_id] = time_elapsed

    @property
    def notifications(self) -> list[NotificationMessage]:
        all_notifications: list[NotificationMessage] = []
        if self.cell_ids:
            all_notifications.append(self.cell_ids)
        if self.variable_notifications.variables:
            all_notifications.append(self.variable_notifications)
        if self.variable_values:
            all_notifications.append(
                VariableValuesNotification(
                    variables=list(self.variable_values.values())
                )
            )
        if self.datasets.tables:
            all_notifications.append(self.datasets)
        if self.data_connectors.connections:
            all_notifications.append(self.data_connectors)
        all_notifications.extend(self.cell_notifications.values())
        if self.stale_code:
            all_notifications.append(self.stale_code)
        if self.model_messages:
            for messages in self.model_messages.values():
                all_notifications.extend(messages)
        # Only include startup logs if they are in progress (not done)
        if self.startup_logs and self.startup_logs.status != "done":
            all_notifications.append(self.startup_logs)
        return all_notifications

    def is_empty(self) -> bool:
        return all(
            notif.output is None and notif.console is None
            for notif in self.cell_notifications.values()
        )

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


def _merge_consecutive_console_outputs(
    console: list[CellOutput],
) -> list[CellOutput]:
    """Merge consecutive text/plain outputs with the same channel."""
    if not console:
        return console

    merged: list[CellOutput] = []

    for output in console:
        # Check if we can merge with the last output
        if (
            merged
            and merged[-1].mimetype == "text/plain"
            and output.mimetype == "text/plain"
            and merged[-1].channel == output.channel
            and isinstance(merged[-1].data, str)
            and isinstance(output.data, str)
        ):
            # Merge by concatenating the data
            merged[-1] = CellOutput(
                channel=merged[-1].channel,
                mimetype=merged[-1].mimetype,
                data=merged[-1].data + output.data,
                timestamp=merged[-1].timestamp,
            )
        else:
            merged.append(output)

    return merged


def merge_cell_notification(
    previous: Optional[CellNotification],
    current: CellNotification,
) -> CellNotification:
    """Merge two cell notifications."""
    if previous is None:
        return current

    assert previous.cell_id == current.cell_id

    if current.status is None:
        current.status = previous.status

    # If we went from queued to running, clear the console.
    if current.status == "running" and previous.status == "queued":
        current.console = []
    else:
        combined_console: list[CellOutput] = as_list(previous.console)
        combined_console.extend(as_list(current.console))
        current.console = _merge_consecutive_console_outputs(combined_console)

    # If we went from running to running, use the previous timestamp.
    if current.status == "running" and previous.status == "running":
        current.timestamp = previous.timestamp

    if current.output is None:
        current.output = previous.output

    return current
