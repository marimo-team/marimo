# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from packages/host-protocol.
# Regenerate with `make host-protocol-codegen`.
"""Wrap records in their events."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from msgspec import UNSET, UnsetType

from marimo._core import protocol

if TYPE_CHECKING:
    from datetime import datetime

Body: TypeAlias = (
    protocol.Analysis
    | protocol.Attachment
    | protocol.Cell
    | protocol.Console
    | protocol.Custom
    | protocol.Document
    | protocol.Execution
    | protocol.Host
    | protocol.Input
    | protocol.Notebook
    | protocol.Output
    | protocol.Project
    | protocol.Run
    | protocol.Runtime
    | protocol.Variable
)
SnapshotBody: TypeAlias = (
    protocol.Analysis
    | protocol.Attachment
    | protocol.Cell
    | protocol.Console
    | protocol.Document
    | protocol.Execution
    | protocol.Host
    | protocol.Input
    | protocol.Notebook
    | protocol.Output
    | protocol.Project
    | protocol.Run
    | protocol.Runtime
    | protocol.Variable
)
RecordEvent: TypeAlias = (
    protocol.AnalysisEvent
    | protocol.AttachmentEvent
    | protocol.CellEvent
    | protocol.ConsoleEvent
    | protocol.CustomEvent
    | protocol.DocumentEvent
    | protocol.ExecutionEvent
    | protocol.HostEvent
    | protocol.InputEvent
    | protocol.NotebookEvent
    | protocol.OutputEvent
    | protocol.ProjectEvent
    | protocol.RunEvent
    | protocol.RuntimeEvent
    | protocol.VariableEvent
)
RemovableBody: TypeAlias = (
    protocol.Attachment
    | protocol.Cell
    | protocol.Console
    | protocol.Execution
    | protocol.Notebook
    | protocol.Output
    | protocol.Project
    | protocol.Run
    | protocol.Runtime
    | protocol.Variable
)
RemovalEvent: TypeAlias = (
    protocol.AttachmentRemovedEvent
    | protocol.CellRemovedEvent
    | protocol.ConsoleRemovedEvent
    | protocol.ExecutionRemovedEvent
    | protocol.NotebookRemovedEvent
    | protocol.OutputRemovedEvent
    | protocol.ProjectRemovedEvent
    | protocol.RunRemovedEvent
    | protocol.RuntimeRemovedEvent
    | protocol.VariableRemovedEvent
)


def record(
    value: Body,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> RecordEvent:
    """Wrap a record without copying it; occurrences require a timestamp."""
    match value:
        case protocol.Analysis():
            return protocol.AnalysisEvent(
                protocol.AnalysisMessage(
                    analysis=value, request_id=request_id, time=time
                )
            )
        case protocol.Attachment():
            return protocol.AttachmentEvent(
                protocol.AttachmentMessage(
                    attachment=value, request_id=request_id, time=time
                )
            )
        case protocol.Cell():
            return protocol.CellEvent(
                protocol.CellMessage(
                    cell=value, request_id=request_id, time=time
                )
            )
        case protocol.Console():
            return protocol.ConsoleEvent(
                protocol.ConsoleMessage(
                    console=value, request_id=request_id, time=time
                )
            )
        case protocol.Custom():
            if isinstance(time, UnsetType):
                raise ValueError("CustomEvent requires an emission time")
            return protocol.CustomEvent(
                protocol.CustomMessage(
                    custom=value, request_id=request_id, time=time
                )
            )
        case protocol.Document():
            return protocol.DocumentEvent(
                protocol.DocumentMessage(
                    document=value, request_id=request_id, time=time
                )
            )
        case protocol.Execution():
            return protocol.ExecutionEvent(
                protocol.ExecutionMessage(
                    execution=value, request_id=request_id, time=time
                )
            )
        case protocol.Host():
            return protocol.HostEvent(
                protocol.HostMessage(
                    host=value, request_id=request_id, time=time
                )
            )
        case protocol.Input():
            return protocol.InputEvent(
                protocol.InputMessage(
                    input=value, request_id=request_id, time=time
                )
            )
        case protocol.Notebook():
            return protocol.NotebookEvent(
                protocol.NotebookMessage(
                    notebook=value, request_id=request_id, time=time
                )
            )
        case protocol.Output():
            return protocol.OutputEvent(
                protocol.OutputMessage(
                    output=value, request_id=request_id, time=time
                )
            )
        case protocol.Project():
            return protocol.ProjectEvent(
                protocol.ProjectMessage(
                    project=value, request_id=request_id, time=time
                )
            )
        case protocol.Run():
            return protocol.RunEvent(
                protocol.RunMessage(
                    run=value, request_id=request_id, time=time
                )
            )
        case protocol.Runtime():
            return protocol.RuntimeEvent(
                protocol.RuntimeMessage(
                    runtime=value, request_id=request_id, time=time
                )
            )
        case protocol.Variable():
            return protocol.VariableEvent(
                protocol.VariableMessage(
                    variable=value, request_id=request_id, time=time
                )
            )
    raise TypeError(f"Unsupported record type: {type(value)}")


def removed(
    record_type: type[RemovableBody],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> RemovalEvent:
    """Construct the removal envelope for a supported record type."""
    if record_type is protocol.Attachment:
        return protocol.AttachmentRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.AttachmentId(object_id),
                request_id=request_id,
                time=time,
            )
        )
    if record_type is protocol.Cell:
        return protocol.CellRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.CellId(object_id), request_id=request_id, time=time
            )
        )
    if record_type is protocol.Console:
        return protocol.ConsoleRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.ItemId(object_id), request_id=request_id, time=time
            )
        )
    if record_type is protocol.Execution:
        return protocol.ExecutionRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.ExecutionId(object_id),
                request_id=request_id,
                time=time,
            )
        )
    if record_type is protocol.Notebook:
        return protocol.NotebookRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.NotebookId(object_id),
                request_id=request_id,
                time=time,
            )
        )
    if record_type is protocol.Output:
        return protocol.OutputRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.ItemId(object_id), request_id=request_id, time=time
            )
        )
    if record_type is protocol.Project:
        return protocol.ProjectRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.ProjectId(object_id),
                request_id=request_id,
                time=time,
            )
        )
    if record_type is protocol.Run:
        return protocol.RunRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.RunId(object_id), request_id=request_id, time=time
            )
        )
    if record_type is protocol.Runtime:
        return protocol.RuntimeRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.RuntimeId(object_id),
                request_id=request_id,
                time=time,
            )
        )
    if record_type is protocol.Variable:
        return protocol.VariableRemovedEvent(
            protocol.RemovedMessage(
                id=protocol.ItemId(object_id), request_id=request_id, time=time
            )
        )
    raise TypeError(f"No removal event for {record_type}")
