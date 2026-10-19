# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from protocols/host/openapi.yaml.
# Regenerate with `make host-protocol-codegen`.
"""Typed envelope adapters. Payload ownership stays with the caller."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, overload

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
    | protocol.Display
    | protocol.Document
    | protocol.Execution
    | protocol.Host
    | protocol.Notebook
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
    | protocol.Display
    | protocol.Document
    | protocol.Execution
    | protocol.Host
    | protocol.Notebook
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
    | protocol.DisplayEvent
    | protocol.DocumentEvent
    | protocol.ExecutionEvent
    | protocol.HostEvent
    | protocol.NotebookEvent
    | protocol.ProjectEvent
    | protocol.RunEvent
    | protocol.RuntimeEvent
    | protocol.VariableEvent
)
RemovableBody: TypeAlias = (
    protocol.Attachment
    | protocol.Cell
    | protocol.Console
    | protocol.Display
    | protocol.Execution
    | protocol.Notebook
    | protocol.Project
    | protocol.Run
    | protocol.Runtime
    | protocol.Variable
)
RemovalEvent: TypeAlias = (
    protocol.AttachmentRemovedEvent
    | protocol.CellRemovedEvent
    | protocol.ConsoleRemovedEvent
    | protocol.DisplayRemovedEvent
    | protocol.ExecutionRemovedEvent
    | protocol.NotebookRemovedEvent
    | protocol.ProjectRemovedEvent
    | protocol.RunRemovedEvent
    | protocol.RuntimeRemovedEvent
    | protocol.VariableRemovedEvent
)


@overload
def record(
    value: protocol.Analysis,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.AnalysisEvent: ...


@overload
def record(
    value: protocol.Attachment,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.AttachmentEvent: ...


@overload
def record(
    value: protocol.Cell,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.CellEvent: ...


@overload
def record(
    value: protocol.Console,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.ConsoleEvent: ...


@overload
def record(
    value: protocol.Custom,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime,
) -> protocol.CustomEvent: ...


@overload
def record(
    value: protocol.Display,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.DisplayEvent: ...


@overload
def record(
    value: protocol.Document,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.DocumentEvent: ...


@overload
def record(
    value: protocol.Execution,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.ExecutionEvent: ...


@overload
def record(
    value: protocol.Host,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.HostEvent: ...


@overload
def record(
    value: protocol.Notebook,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.NotebookEvent: ...


@overload
def record(
    value: protocol.Project,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.ProjectEvent: ...


@overload
def record(
    value: protocol.Run,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.RunEvent: ...


@overload
def record(
    value: protocol.Runtime,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.RuntimeEvent: ...


@overload
def record(
    value: protocol.Variable,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.VariableEvent: ...


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

        case protocol.Display():
            return protocol.DisplayEvent(
                protocol.DisplayMessage(
                    display=value, request_id=request_id, time=time
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

        case protocol.Notebook():
            return protocol.NotebookEvent(
                protocol.NotebookMessage(
                    notebook=value, request_id=request_id, time=time
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


@overload
def body(event: protocol.AnalysisEvent) -> protocol.Analysis: ...


@overload
def body(event: protocol.AttachmentEvent) -> protocol.Attachment: ...


@overload
def body(event: protocol.CellEvent) -> protocol.Cell: ...


@overload
def body(event: protocol.ConsoleEvent) -> protocol.Console: ...


@overload
def body(event: protocol.CustomEvent) -> protocol.Custom: ...


@overload
def body(event: protocol.DisplayEvent) -> protocol.Display: ...


@overload
def body(event: protocol.DocumentEvent) -> protocol.Document: ...


@overload
def body(event: protocol.ExecutionEvent) -> protocol.Execution: ...


@overload
def body(event: protocol.HostEvent) -> protocol.Host: ...


@overload
def body(event: protocol.NotebookEvent) -> protocol.Notebook: ...


@overload
def body(event: protocol.ProjectEvent) -> protocol.Project: ...


@overload
def body(event: protocol.RunEvent) -> protocol.Run: ...


@overload
def body(event: protocol.RuntimeEvent) -> protocol.Runtime: ...


@overload
def body(event: protocol.VariableEvent) -> protocol.Variable: ...


def body(event: RecordEvent) -> Body:
    """Read a record payload without copying it."""
    match event:
        case protocol.AnalysisEvent(data=data):
            return data.analysis

        case protocol.AttachmentEvent(data=data):
            return data.attachment

        case protocol.CellEvent(data=data):
            return data.cell

        case protocol.ConsoleEvent(data=data):
            return data.console

        case protocol.CustomEvent(data=data):
            return data.custom

        case protocol.DisplayEvent(data=data):
            return data.display

        case protocol.DocumentEvent(data=data):
            return data.document

        case protocol.ExecutionEvent(data=data):
            return data.execution

        case protocol.HostEvent(data=data):
            return data.host

        case protocol.NotebookEvent(data=data):
            return data.notebook

        case protocol.ProjectEvent(data=data):
            return data.project

        case protocol.RunEvent(data=data):
            return data.run

        case protocol.RuntimeEvent(data=data):
            return data.runtime

        case protocol.VariableEvent(data=data):
            return data.variable

    raise TypeError(f"Not a record event: {type(event)}")


@overload
def removed(
    record_type: type[protocol.Attachment],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.AttachmentRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Cell],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.CellRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Console],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.ConsoleRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Display],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.DisplayRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Execution],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.ExecutionRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Notebook],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.NotebookRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Project],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.ProjectRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Run],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.RunRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Runtime],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.RuntimeRemovedEvent: ...


@overload
def removed(
    record_type: type[protocol.Variable],
    object_id: str,
    *,
    request_id: str | UnsetType = UNSET,
    time: datetime | UnsetType = UNSET,
) -> protocol.VariableRemovedEvent: ...


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
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Cell:
        return protocol.CellRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Console:
        return protocol.ConsoleRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Display:
        return protocol.DisplayRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Execution:
        return protocol.ExecutionRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Notebook:
        return protocol.NotebookRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Project:
        return protocol.ProjectRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Run:
        return protocol.RunRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Runtime:
        return protocol.RuntimeRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    if record_type is protocol.Variable:
        return protocol.VariableRemovedEvent(
            protocol.RemovedMessage(
                id=object_id, request_id=request_id, time=time
            )
        )

    raise TypeError(f"No removal event for {record_type}")
