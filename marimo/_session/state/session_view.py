# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, replace
from itertools import groupby
from typing import Any, Literal, TypeVar, cast

import msgspec

from marimo import _loggers
from marimo._data.models import DataSourceConnection, DataTable
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.mimetypes import KnownMimeType, MimeBundleTuple
from marimo._messaging.notification import (
    BreakpointsNotification,
    CallbackOutputNotification,
    CellNotification,
    ConsoleInputsClearedNotification,
    DatasetsNotification,
    DataSourceConnectionsNotification,
    EnvironmentOperationNotification,
    EnvironmentState,
    EnvironmentStateNotification,
    EsmSpec,
    ExecutionNotification,
    InterruptedNotification,
    ModelClose,
    ModelLifecycleNotification,
    ModelOpen,
    ModelUpdate,
    NotificationMessage,
    PdbInputNotification,
    PdbOutputNotification,
    SQLSchemaListPreviewNotification,
    SQLTableListPreviewNotification,
    SQLTablePreviewNotification,
    StartupLogsNotification,
    StartupProgressNotification,
    StorageNamespacesNotification,
    UIElementMessageNotification,
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
    ModelCommand,
    ModelUpdateMessage,
    SetBreakpointsCommand,
    SyncGraphCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.layout.layout import LayoutConfig
from marimo._session.state.environment import (
    reduce_environment_state,
)
from marimo._sql.connection_utils import (
    update_schema_list_in_connection,
    update_table_in_connection,
    update_table_list_in_connection,
)
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE
from marimo._types.ids import CellId_t, UIElementId, WidgetModelId
from marimo._utils.code import hash_code
from marimo._utils.lists import as_list

LOGGER = _loggers.marimo_logger()

ExportType = Literal["html", "md", "ipynb", "session"]
MIMEBUNDLE_TYPE: KnownMimeType = "application/vnd.marimo+mimebundle"


BufferPath = tuple[str | int, ...]


@dataclass
class ModelReplayState:
    """Aggregated snapshot of a widget model's current state.

    Internally uses a dict for buffers (path → bytes) so merging
    updates is a simple dict operation. Converted back to the wire
    format (parallel lists) on replay via `to_notification()`.
    """

    model_id: WidgetModelId
    state: dict[str, Any]
    buffers: dict[BufferPath, bytes]
    esm_spec: EsmSpec | None = None

    @staticmethod
    def from_open(model_id: WidgetModelId, msg: ModelOpen) -> ModelReplayState:
        buffers = {
            tuple(p): b
            for p, b in zip(msg.buffer_paths, msg.buffers, strict=False)
        }
        return ModelReplayState(
            model_id=model_id,
            state=dict(msg.state),
            buffers=buffers,
            esm_spec=msg.esm_spec,
        )

    def apply_update(self, msg: ModelUpdate) -> None:
        """Merge an update into this snapshot (mutates in place)."""
        # Drop buffers whose root key is being overridden
        updated_keys = set(msg.state.keys())
        self.buffers = {
            path: buf
            for path, buf in self.buffers.items()
            if path[0] not in updated_keys
        }
        # Merge new state and buffers
        self.state.update(msg.state)
        for path, buf in zip(msg.buffer_paths, msg.buffers, strict=False):
            self.buffers[tuple(path)] = buf
        # A spec on an update is a hot reload; late joiners must replay
        # the current code, not the original open's.
        if msg.esm_spec is not None:
            self.esm_spec = msg.esm_spec

    def to_notification(self) -> ModelLifecycleNotification:
        paths = list(self.buffers.keys())
        bufs = list(self.buffers.values())
        return ModelLifecycleNotification(
            model_id=self.model_id,
            message=ModelOpen(
                state=dict(self.state),
                buffer_paths=[list(p) for p in paths],
                buffers=bufs,
                esm_spec=self.esm_spec,
            ),
        )


@dataclass
class AutoExportState:
    html: bool = False
    md: bool = False
    ipynb: bool = False
    session: bool = False
    generation: int = 0

    def mark_all_stale(self) -> None:
        self.generation += 1
        self.html = False
        self.md = False
        self.ipynb = False
        self.session = False

    def is_stale(self, export_type: ExportType) -> bool:
        return not getattr(self, export_type)

    def mark_exported(
        self, export_type: ExportType, *, generation: int | None = None
    ) -> bool:
        if generation is not None and generation != self.generation:
            return False
        setattr(self, export_type, True)
        return True


_CommandOutput = TypeVar(
    "_CommandOutput", PdbOutputNotification, CallbackOutputNotification
)

SnapshotScope = Literal["full", "editor", "host"]


@dataclass(frozen=True)
class _CommandEntry:
    output: CellOutput
    after_seq: int | None
    # The session also retains rows that have no host item sequence.
    console_offset: int


@dataclass(frozen=True)
class _OutputOwner:
    execution_id: str | None
    code_hash: str | None
    awaiting_plan: bool = False


@dataclass(frozen=True)
class CellExport:
    code_hash: str | None
    output: CellOutput | None
    console: list[CellOutput]


class SessionView:
    """A representation of a session state for replay and serialization.

    Of note, a SessionView stores:
    * a mapping from cell IDs to their last seen notification of interest,
      such as an output, status, or console output
    * various other state needed for replay

    A notebook session can be hydrated from a serialized SessionView,
    for example on notebook startup when auto-instantiate is off, or
    on reconnection via a replay.
    """

    def __init__(self) -> None:
        # A mapping from cell (IDs) to their last seen notification
        self.cell_notifications: dict[CellId_t, CellNotification] = {}
        self._output_owners: dict[CellId_t, _OutputOwner] = {}
        self._previous_output_hashes: dict[CellId_t, str | None] = {}
        self._cleared_inputs: dict[
            CellId_t, ConsoleInputsClearedNotification
        ] = {}
        self._console_positions: dict[CellId_t, int] = {}
        self._command_output: dict[
            tuple[
                CellId_t,
                type[PdbOutputNotification | CallbackOutputNotification],
            ],
            list[_CommandEntry],
        ] = {}
        # The most recent datasets notification.
        self.datasets = DatasetsNotification(tables=[])
        # The most recent data-connectors notification
        self.data_connectors = DataSourceConnectionsNotification(
            connections=[]
        )
        # The most recent external storage namespaces notification
        self.external_storage_namespaces = StorageNamespacesNotification(
            namespaces=[]
        )
        # The most recent Variables notification.
        self.variable_notifications: VariablesNotification = (
            VariablesNotification(variables=[])
        )
        # Map of variable name to value.
        self.variable_values: dict[str, VariableValue] = {}
        # Map of object id to value.
        self.ui_values: dict[str, Any] = {}
        self.breakpoints = BreakpointsNotification(breakpoints={})
        self.pending_pdb_input: PdbInputNotification | None = None
        # Map of cell id to the last code that was executed in that cell.
        self.last_executed_code: dict[CellId_t, str] = {}
        # Map of cell id to the last cell execution time
        self.last_execution_time: dict[CellId_t, float] = {}
        # Aggregated model state — one snapshot per live model.
        # Updates merge in; close removes the entry.
        self.model_states: dict[WidgetModelId, ModelReplayState] = {}
        # UI element messages
        self.ui_element_messages: dict[
            UIElementId, list[UIElementMessageNotification]
        ] = {}

        # Startup logs for startup command - only one at a time
        self.startup_logs: StartupLogsNotification | None = None
        self.startup_progress: StartupProgressNotification | None = None

        self._environment_states: dict[
            Literal["kernel", "server"], EnvironmentState
        ] = {
            "kernel": EnvironmentState(restart_required=False, operations=[]),
            "server": EnvironmentState(restart_required=False, operations=[]),
        }

        # Server-side missing-package alerts already sent this session.
        # NOT reset by _touch() — once alerted we don't re-alert.
        self.notified_server_packages: set[str] = set()

        # Auto-saving
        self.auto_export_state = AutoExportState()
        self._auto_export_html_layout: LayoutConfig | None = None

    def _add_ui_value(self, name: str, value: Any) -> None:
        self.ui_values[name] = value

    def _add_last_run_code(self, req: ExecuteCellCommand) -> None:
        cell = self.cell_notifications.get(req.cell_id)
        if cell is not None:
            owner = self._output_owners.get(req.cell_id)
            if owner is None:
                previous = self.last_executed_code.get(req.cell_id)
                owner = _OutputOwner(
                    None, hash_code(previous) if previous is not None else None
                )
            self._output_owners[req.cell_id] = replace(
                owner, awaiting_plan=True
            )
            self._retain_previous_output(cell)
        self.last_executed_code[req.cell_id] = req.code

    def add_raw_notification(self, raw_notification: KernelMessage) -> None:
        # Type ignore because NotificationMessage is a Union, not a class
        self.add_notification(deserialize_kernel_message(raw_notification))  # type: ignore[arg-type]

    def add_control_request(self, request: CommandMessage) -> None:
        self._touch()

        if isinstance(request, UpdateUIElementCommand):
            for object_id, value in request.ids_and_values:
                self._add_ui_value(object_id, value)
        elif isinstance(request, SetBreakpointsCommand):
            self.breakpoints = BreakpointsNotification(
                breakpoints=request.breakpoints
            )
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
        elif isinstance(request, ModelCommand):
            self._apply_model_command(request)

    def _apply_model_command(self, request: ModelCommand) -> None:
        """Merge a client's model write into replay state.

        The kernel does not echo client writes back (see
        `_create_model_message` in `marimo._plugins.ui._impl.comm`), so
        the command itself is the only record of frontend-driven trait
        changes for reconnect replay.
        """
        message = request.message
        if not isinstance(message, ModelUpdateMessage):
            # Custom messages are ephemeral — never replayed.
            return
        view = self.model_states.get(request.model_id)
        if view is None:
            return
        # Clients may write widget state, never code or style: replayed
        # state reaches future viewers. Mirrors the kernel-side filter
        # in MarimoCommManager.receive_comm_message.
        state = {
            k: v for k, v in message.state.items() if k not in ("_esm", "_css")
        }
        view.apply_update(
            ModelUpdate(
                state=state,
                buffer_paths=message.buffer_paths,
                buffers=request.buffers,
            )
        )

    def add_stdin(self, stdin: str, *, input_id: str | None = None) -> None:
        self._touch()

        """Add a stdin request to the session view."""
        # Find the first cell that is waiting for stdin.
        for cell_notif in self.cell_notifications.values():
            console_outputs: list[CellOutput] = as_list(cell_notif.console)
            for cell_output in console_outputs:
                if input_id is not None and cell_output.input_id != input_id:
                    continue
                if cell_output.channel == CellChannel.STDIN:
                    cell_output.channel = CellChannel.STDOUT
                    if cell_output.mimetype == "text/password":
                        # This state is reused for replay, exports, and caches.
                        cell_output.data = f"{cell_output.data}\n"
                        cell_output.mimetype = "text/plain"
                    else:
                        cell_output.data = f"{cell_output.data} {stdin}\n"
                    return

    def add_notification(self, notification: NotificationMessage) -> None:
        """Add a notification to the session view."""
        self._touch()

        if isinstance(notification, ExecutionNotification):
            self._observe_execution(notification)
        elif isinstance(notification, CellNotification):
            owner = self.current_execution_id(notification.cell_id)
            if (
                owner is not None
                and notification.execution_id is not None
                and owner != notification.execution_id
            ):
                return
            if notification.status == "running" or notification.console == []:
                self._clear_command_output(notification.cell_id)
            previous = self.cell_notifications.get(notification.cell_id)
            if (
                notification.console == []
                and previous is not None
                and notification.execution_id is not None
            ):
                self._clear_console_inputs(
                    notification.cell_id, notification.execution_id, previous
                )
            if notification.output is not None:
                self._previous_output_hashes.pop(notification.cell_id, None)
            elif notification.cell_id in self._previous_output_hashes:
                # The merged status and displayed value have different owners.
                notification = msgspec.structs.replace(
                    notification, run_id=None, execution_id=None
                )
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

        elif isinstance(
            notification, (PdbOutputNotification, CallbackOutputNotification)
        ):
            if (
                isinstance(notification, CallbackOutputNotification)
                and notification.clears_cell_console
            ):
                self._clear_command_output(notification.cell_id)
                cell = self.cell_notifications.get(notification.cell_id)
                if cell is not None:
                    owner = self.current_execution_id(notification.cell_id)
                    if owner is not None:
                        self._clear_console_inputs(
                            notification.cell_id, owner, cell
                        )
                    cell.console = _pending_inputs(cell.console)
            key = (notification.cell_id, type(notification))
            entries = self._command_output.setdefault(key, [])
            if notification.replace or not notification.entries:
                entries.clear()
            command = self.position_command_output(notification)
            positions = command.after_seq
            cell = self.cell_notifications.get(notification.cell_id)
            offset = len(as_list(cell.console)) if cell is not None else 0
            entries.extend(
                _CommandEntry(
                    entry,
                    None if positions is msgspec.UNSET else positions[i],
                    offset,
                )
                for i, entry in enumerate(command.entries)
            )

        elif isinstance(notification, PdbInputNotification):
            self.pending_pdb_input = (
                notification if notification.input_id is not None else None
            )

        elif isinstance(notification, VariablesNotification):
            self.variable_notifications = notification

            # Set of variable names that are in scope.
            variable_names: set[str] = {
                v.name for v in self.variable_notifications.variables
            }

            # Remove any variable values that are no longer in scope.
            next_values: dict[str, VariableValue] = {
                name: value
                for name, value in self.variable_values.items()
                if name in variable_names
            }
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

            # Remove any external storage namespaces that are no longer in scope.
            next_namespaces = [
                ns
                for ns in self.external_storage_namespaces.namespaces
                if ns.name in variable_names
            ]
            self.external_storage_namespaces = StorageNamespacesNotification(
                namespaces=next_namespaces
            )

        elif isinstance(notification, VariableValuesNotification):
            for removed in notification.removed:
                value = self.variable_values.get(removed.name)
                if (
                    value is not None
                    and value.execution_id == removed.execution_id
                ):
                    del self.variable_values[removed.name]
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

        elif isinstance(notification, StorageNamespacesNotification):
            # Merge external storage namespaces, dedupe by name and keep the latest
            prev_namespaces = self.external_storage_namespaces.namespaces
            namespaces_by_name = {ns.name: ns for ns in prev_namespaces}
            for ns in notification.namespaces:
                namespaces_by_name[ns.name] = ns
            self.external_storage_namespaces = StorageNamespacesNotification(
                namespaces=list(namespaces_by_name.values())
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

        elif isinstance(notification, SQLSchemaListPreviewNotification):
            sql_schema_list_preview = notification
            sql_db_metadata = sql_schema_list_preview.metadata
            schema_list_connections = self.data_connectors.connections
            if sql_schema_list_preview.schemas is not None:
                update_schema_list_in_connection(
                    schema_list_connections,
                    sql_db_metadata,
                    sql_schema_list_preview.schemas,
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

        elif isinstance(notification, UIElementMessageNotification):
            # TODO: Consider reducing to a single message per element
            # (similar to ModelReplayState) instead of keeping the full
            # history. Currently the only user is chat streaming
            # ("stream_chunk" messages) which are ephemeral and don't
            # need replay at all.
            ui_element_id = notification.ui_element
            if ui_element_id not in self.ui_element_messages:
                self.ui_element_messages[ui_element_id] = []
            self.ui_element_messages[ui_element_id].append(notification)

        elif isinstance(notification, ModelLifecycleNotification):
            model_id = notification.model_id
            msg = notification.message
            if isinstance(msg, ModelOpen):
                self.model_states[model_id] = ModelReplayState.from_open(
                    model_id, msg
                )
            elif isinstance(msg, ModelUpdate):
                view = self.model_states.get(model_id)
                if view is not None:
                    view.apply_update(msg)
            elif isinstance(msg, ModelClose):
                self.model_states.pop(model_id, None)
            # ModelCustom is ephemeral — skip for replay

        elif isinstance(notification, StartupProgressNotification):
            previous_progress = self.startup_progress
            logs = notification.logs
            if (
                notification.log_mode == "append"
                and previous_progress is not None
                and previous_progress.phase == notification.phase
            ):
                logs = previous_progress.logs + logs
            self.startup_progress = StartupProgressNotification(
                phase=notification.phase, logs=logs, log_mode="replace"
            )

        elif isinstance(notification, StartupLogsNotification):
            prev = self.startup_logs.content if self.startup_logs else ""
            self.startup_logs = StartupLogsNotification(
                content=prev + notification.content,
                status=notification.status,
            )

        elif isinstance(notification, EnvironmentOperationNotification):
            self._environment_states[notification.source] = (
                reduce_environment_state(
                    self._environment_states[notification.source],
                    notification,
                )
            )

    def get_environment_state(
        self, source: Literal["kernel", "server"]
    ) -> EnvironmentState:
        """Snapshot a target environment's attempts and restart requirement."""
        return copy.deepcopy(self._environment_states[source])

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

    def _retain_previous_output(self, cell: CellNotification) -> None:
        if cell.output is None or cell.cell_id in self._previous_output_hashes:
            return
        owner = self._output_owners.get(cell.cell_id)
        self._previous_output_hashes[cell.cell_id] = (
            owner.code_hash if owner is not None else None
        )

    def _observe_execution(self, notification: ExecutionNotification) -> None:
        cell_id = notification.cell_id
        owner = self.current_execution_id(cell_id)
        cell = self.cell_notifications.get(cell_id)
        if (
            notification.phase == "planned"
            and owner != notification.execution_id
        ):
            self._console_positions[cell_id] = -1
            self._cleared_inputs.pop(cell_id, None)
            if cell is not None:
                self._retain_previous_output(cell)
                self.cell_notifications[cell_id] = msgspec.structs.replace(
                    cell,
                    execution_id=(
                        cell.execution_id
                        if cell.output is not None
                        else notification.execution_id
                    ),
                    console=None,
                )
            self._output_owners[cell_id] = _OutputOwner(
                notification.execution_id,
                hash_code(notification.code)
                if notification.code is not None
                else notification.code_hash,
            )
        elif (
            notification.phase == "completed"
            and owner == notification.execution_id
            and cell is not None
        ):
            for entry in as_list(cell.console):
                if entry.channel == CellChannel.STDIN:
                    entry.channel = CellChannel.STDOUT
                    entry.mimetype = "text/plain"

    def _clear_command_output(self, cell_id: CellId_t) -> None:
        for kind in (PdbOutputNotification, CallbackOutputNotification):
            if entries := self._command_output.get((cell_id, kind)):
                entries.clear()

    def _clear_console_inputs(
        self, cell_id: CellId_t, execution_id: str, previous: CellNotification
    ) -> None:
        ids = [
            entry.input_id
            for entry in as_list(previous.console)
            if isinstance(entry.input_id, str)
            and entry.channel != CellChannel.STDIN
        ]
        if ids:
            cleared = self.cleared_console_inputs(cell_id, execution_id)
            self._cleared_inputs[cell_id] = ConsoleInputsClearedNotification(
                cell_id,
                execution_id,
                [*(cleared.input_ids if cleared else []), *ids],
            )

    def current_execution_id(self, cell_id: CellId_t) -> str | None:
        owner = self._output_owners.get(cell_id)
        return owner.execution_id if owner is not None else None

    def restore_cell_outputs(
        self,
        cells: dict[CellId_t, CellNotification],
        hashes: dict[str, CellId_t],
    ) -> None:
        self.cell_notifications = cells
        self._output_owners = {
            cell_id: _OutputOwner(None, code_hash)
            for code_hash, cell_id in hashes.items()
            if cell_id in cells
        }
        self._previous_output_hashes.clear()

    def outputs_for_export(
        self, cell_id: CellId_t, code: str | None, *, for_display: bool
    ) -> CellExport:
        """Select the value and console for the source written to the artifact."""
        code_hash = hash_code(code) if code else None
        owner = self._output_owners.get(cell_id)
        if code is None and owner is not None and owner.execution_id is None:
            # A reopened cache still has its original hash before any submission.
            code_hash = owner.code_hash
        if owner is None:
            # Legacy producers emit cell updates without an execution plan.
            submitted = self.last_executed_code.get(cell_id)
            matches = submitted is None or hash_code(submitted) == code_hash
        else:
            matches = (
                code_hash is not None
                and owner.code_hash == code_hash
                and (for_display or not owner.awaiting_plan)
            )

        output = self.current_execution_output(cell_id) if matches else None
        if (
            for_display
            and code_hash is not None
            and self._previous_output_hashes.get(cell_id) == code_hash
        ):
            output = self.cell_notifications[cell_id].output
        console = (
            self.cell_console(cell_id, include_callbacks=for_display)
            if matches
            else []
        )
        if cell_id not in self.cell_notifications and not console:
            code_hash = None
        return CellExport(code_hash, output, console)

    def current_execution_output(self, cell_id: CellId_t) -> CellOutput | None:
        """Return only output produced by the current execution."""
        cell = self.cell_notifications.get(cell_id)
        if cell is None or cell_id in self._previous_output_hashes:
            return None
        return cell.output

    def cleared_console_inputs(
        self, cell_id: CellId_t, execution_id: str | None = None
    ) -> ConsoleInputsClearedNotification | None:
        """Return the input rows hidden by this execution's console clears."""
        cleared = self._cleared_inputs.get(cell_id)
        return (
            cleared
            if cleared
            and (execution_id is None or cleared.execution_id == execution_id)
            else None
        )

    def has_cell_console_output(self, cell_id: CellId_t) -> bool:
        """Whether the cell has public console output, including callback writes."""
        cell = self.cell_notifications.get(cell_id)
        return bool(
            (cell is not None and cell.console)
            or self._command_output.get((cell_id, CallbackOutputNotification))
        )

    def cell_console(
        self, cell_id: CellId_t, *, include_callbacks: bool
    ) -> list[CellOutput]:
        cell = self.cell_notifications.get(cell_id)
        entries = as_list(cell.console) if cell is not None else []
        if include_callbacks and (
            callbacks := self._command_output.get(
                (cell_id, CallbackOutputNotification)
            )
        ):
            combined: list[CellOutput] = []
            start = 0
            for callback in callbacks:
                combined.extend(entries[start : callback.console_offset])
                combined.append(callback.output)
                start = callback.console_offset
            combined.extend(entries[start:])
            if any(callback.after_seq is None for callback in callbacks):
                # Unpositioned writes can arrive in separately buffered batches.
                combined.sort(key=lambda entry: entry.timestamp)
            entries = combined
        return _merge_consecutive_console_outputs(entries)

    def get_cell_console_outputs(
        self, ids: list[CellId_t]
    ) -> dict[CellId_t, list[CellOutput]]:
        """Return each cell's console, including its widget and function callbacks."""
        return {
            cell_id: entries
            for cell_id in ids
            if (entries := self.cell_console(cell_id, include_callbacks=True))
        }

    def update_cell_outputs(
        self, cell_id_to_output: dict[CellId_t, MimeBundleTuple]
    ) -> None:
        self._touch()  # Mark all auto-export states as stale

        for cell_id, output in cell_id_to_output.items():
            cell_notif = self.cell_notifications.get(cell_id)
            if cell_notif is None:
                LOGGER.warning(f"Cell {cell_id} not found in session view")
                continue

            mimetype, data = output
            new_mimebundle = {mimetype: data}

            if cell_notif.output is None:
                cell_notif.output = CellOutput(
                    channel=CellChannel.OUTPUT, mimetype=mimetype, data=data
                )
            elif isinstance(cell_notif.output.data, list):
                LOGGER.debug(
                    "Skipping list of errors output, should not have rich elements"
                )
                continue
            elif cell_notif.output.mimetype == MIMEBUNDLE_TYPE:
                if not isinstance(cell_notif.output.data, dict):
                    LOGGER.warning(
                        "Existing output is a mimebundle for cell %s, but data is not a dict (type=%s)",
                        cell_id,
                        type(cell_notif.output.data).__name__,
                    )
                    continue
                cell_notif.output.data = cast(
                    dict[str, Any],
                    {
                        **cell_notif.output.data,
                        **new_mimebundle,
                    },
                )
            else:
                # We form a new mimebundle including the existing output
                mimebundle = {
                    cell_notif.output.mimetype: cell_notif.output.data
                }
                cell_notif.output.mimetype = MIMEBUNDLE_TYPE
                cell_notif.output.data = cast(
                    dict[str, Any], {**mimebundle, **new_mimebundle}
                )

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

    def record_console_position(
        self, cell_id: CellId_t, execution_id: str, seq: int
    ) -> None:
        """Remember where private command writes fit among this execution's items."""
        if self.current_execution_id(cell_id) == execution_id:
            self._console_positions[cell_id] = seq

    def position_command_output(
        self, command: PdbOutputNotification | CallbackOutputNotification
    ) -> PdbOutputNotification | CallbackOutputNotification:
        if (
            command.replace
            or command.after_seq is not msgspec.UNSET
            or not command.entries
        ):
            return command
        position = self._console_positions.get(command.cell_id)
        if position is None:
            return command
        return msgspec.structs.replace(
            command, after_seq=[position] * len(command.entries)
        )

    @staticmethod
    def _command_snapshot(
        kind: type[_CommandOutput],
        cell_id: CellId_t,
        entries: list[_CommandEntry],
    ) -> _CommandOutput:
        positions = [
            entry.after_seq for entry in entries if entry.after_seq is not None
        ]
        return kind(
            cell_id,
            [entry.output for entry in entries],
            replace=True,
            after_seq=positions
            if positions and len(positions) == len(entries)
            else msgspec.UNSET,
        )

    def debugger_notifications(
        self,
    ) -> list[PdbOutputNotification | PdbInputNotification]:
        """Private state a consumer gains when it takes over the editor."""
        notifications: list[PdbOutputNotification | PdbInputNotification] = [
            self._command_snapshot(PdbOutputNotification, cell_id, entries)
            for (cell_id, kind), entries in self._command_output.items()
            if kind is PdbOutputNotification
        ]
        if self.pending_pdb_input is not None:
            notifications.append(self.pending_pdb_input)
        return notifications

    def snapshot_notifications(
        self, *, scope: SnapshotScope = "full"
    ) -> list[NotificationMessage]:
        """Copy retained notifications for a connecting client.

        The editor snapshot carries command transcripts and debugger state.
        Only a full session snapshot includes kernel cell updates.
        """
        notifications: list[NotificationMessage] = [
            EnvironmentStateNotification(source=source, state=state)
            for source, state in self._environment_states.items()
        ]
        if self.startup_progress is not None:
            notifications.append(self.startup_progress)
        notifications.extend(self._notebook_notifications(scope))
        return copy.deepcopy(notifications)

    def _notebook_notifications(
        self, scope: SnapshotScope
    ) -> list[NotificationMessage]:
        all_notifications: list[NotificationMessage] = [self.breakpoints]
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
        if self.external_storage_namespaces.namespaces:
            all_notifications.append(self.external_storage_namespaces)

        # Model messages must come before cell notifications to ensure
        # the model exists before the view tries to use it.
        for state in self.model_states.values():
            all_notifications.append(state.to_notification())

        if self.ui_element_messages:
            for ui_messages in self.ui_element_messages.values():
                all_notifications.extend(ui_messages)

        if scope == "full":
            all_notifications.extend(
                msgspec.structs.replace(
                    cell,
                    console=_merge_consecutive_console_outputs(cell.console),
                )
                if isinstance(cell.console, list)
                else cell
                for cell in self.cell_notifications.values()
            )
        if scope != "host":
            all_notifications.extend(self._cleared_inputs.values())
            all_notifications.extend(
                self._command_snapshot(
                    CallbackOutputNotification, cell_id, entries
                )
                for (cell_id, kind), entries in self._command_output.items()
                if kind is CallbackOutputNotification
            )
            all_notifications.extend(self.debugger_notifications())
        # Only include startup logs if they are in progress (not done)
        if self.startup_logs and self.startup_logs.status != "done":
            all_notifications.append(self.startup_logs)
        return all_notifications

    def get_model_notifications(self) -> list[ModelLifecycleNotification]:
        """Return model-open notifications for all live widget models.

        Used to embed model state in static HTML exports so anywidgets
        can render without a running kernel.
        """
        return [
            state.to_notification() for state in self.model_states.values()
        ]

    def is_empty(self) -> bool:
        if any(
            entries
            for (_, kind), entries in self._command_output.items()
            if kind is CallbackOutputNotification
        ):
            return False
        return all(
            notif.output is None and notif.console is None
            for notif in self.cell_notifications.values()
        )

    def mark_auto_export_html(
        self,
        layout: LayoutConfig | None = None,
        *,
        generation: int | None = None,
    ) -> bool:
        if not self.auto_export_state.mark_exported(
            "html", generation=generation
        ):
            return False
        self._auto_export_html_layout = copy.deepcopy(layout)
        return True

    def needs_auto_export_html(self, layout: LayoutConfig | None) -> bool:
        return self.needs_export("html") or (
            layout != self._auto_export_html_layout
        )

    def mark_auto_export_md(self, *, generation: int | None = None) -> bool:
        return self.auto_export_state.mark_exported(
            "md", generation=generation
        )

    def mark_auto_export_ipynb(self, *, generation: int | None = None) -> bool:
        return self.auto_export_state.mark_exported(
            "ipynb", generation=generation
        )

    def mark_auto_export_session(self) -> None:
        self.auto_export_state.mark_exported("session")

    def needs_export(self, export_type: ExportType) -> bool:
        return self.auto_export_state.is_stale(export_type)

    @property
    def auto_export_generation(self) -> int:
        return self.auto_export_state.generation

    def _touch(self) -> None:
        self.auto_export_state.mark_all_stale()


def _merge_consecutive_console_outputs(
    console: list[CellOutput],
) -> list[CellOutput]:
    """Merge consecutive text/plain outputs with the same channel."""
    merged: list[CellOutput] = []
    for (_, mimetype, _, text), group in groupby(
        console,
        key=lambda entry: (
            entry.channel,
            entry.mimetype,
            entry.input_id,
            isinstance(entry.data, str),
        ),
    ):
        entries = list(group)
        if mimetype == "text/plain" and text and len(entries) > 1:
            merged.append(
                msgspec.structs.replace(
                    entries[0],
                    data="".join(cast(str, entry.data) for entry in entries),
                )
            )
        else:
            merged.extend(entries)
    return merged


def _pending_inputs(
    console: CellOutput | list[CellOutput] | None,
) -> list[CellOutput]:
    return [
        entry
        for entry in as_list(console)
        if entry.channel == CellChannel.STDIN
    ]


def merge_cell_notification(
    previous: CellNotification | None,
    current: CellNotification,
) -> CellNotification:
    """Merge two cell notifications."""
    if previous is None:
        return current

    assert previous.cell_id == current.cell_id

    if current.status is None:
        current.status = previous.status

    # Reset the console on an explicit empty list (the `[]` clears contract,
    # e.g. mo.output.clear_console()) or on queued -> running. Otherwise stale
    # console output would persist in the session view.
    explicit_clear = isinstance(current.console, list) and not current.console
    queued_to_running = (
        current.status == "running" and previous.status == "queued"
    )
    if queued_to_running:
        current.console = []
    elif explicit_clear:
        current.console = _pending_inputs(previous.console)
    else:
        combined_console: list[CellOutput] = as_list(previous.console)
        # Keep write boundaries until export can interleave callback output.
        # An input split across writes must still accept one reply.
        for entry in as_list(current.console):
            if (
                combined_console
                and entry.channel == CellChannel.STDIN
                and combined_console[-1].channel == CellChannel.STDIN
            ):
                combined_console[-1:] = _merge_consecutive_console_outputs(
                    [combined_console[-1], entry]
                )
            else:
                combined_console.append(entry)
        current.console = combined_console

    # If we went from running to running, use the previous timestamp.
    if current.status == "running" and previous.status == "running":
        current.timestamp = previous.timestamp

    if current.output is None:
        current.output = previous.output

    return current
