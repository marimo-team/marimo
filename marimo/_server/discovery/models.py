# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from marimo-desktop/schemas/local-discovery/openapi.yaml.
# Regenerate with `cargo xtask generate-local-discovery`.
# ruff: noqa: TC003 - msgspec resolves annotations at runtime

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from msgspec import UNSET, Meta, Struct, UnsetType


class ConsoleEvent(Struct):
    data: str


class CreateNotebookRequest(Struct):
    path: Annotated[
        str,
        Meta(
            description="Relative .py path within the workspace, including symlink resolution.\nThe parent must exist. Absolute paths and escapes return 400.\n",
            min_length=1,
        ),
    ]
    project_id: Annotated[
        str,
        Meta(
            description="Destination workspace ID from Catalog.projects.\n",
            min_length=1,
        ),
    ]


class ErrorResponse(Struct):
    message: Annotated[
        str,
        Meta(
            description="Human-readable explanation; must not contain credentials."
        ),
    ]


class ExecuteRequest(Struct):
    code: str


class InstanceRecord(Struct):
    id: UUID
    kind: Annotated[
        str,
        Meta(
            description="Open application identifier, such as marimo or vscode. Editors may use\ntheir URI scheme. Never infer capabilities or launch URLs from it.\n"
        ),
    ]
    name: Annotated[
        str,
        Meta(
            description="Publisher-chosen plain-text label, defaulting to a concise application\nname and optionally customized. Consumers display it verbatim; it is\nnot unique and must not be used as identity.\n"
        ),
    ]
    pid: Annotated[int, Meta(ge=1)]
    started_at: datetime
    token: str
    url: Annotated[
        str,
        Meta(
            description="HTTP API base URL using literal 127.0.0.1 or [::1]."
        ),
    ]


class OpenNotebookResponse(Struct):
    uri: Annotated[str, Meta(description="Absolute host-defined launch URI.")]


class OutputData(Struct):
    data: str
    mimetype: str


class SessionError(Struct):
    code: Annotated[
        str,
        Meta(
            description="Host-defined error code. Clients accept unknown codes."
        ),
    ]
    message: str


SessionMode: TypeAlias = Literal["edit", "app"]


SessionStatus: TypeAlias = Literal[
    "starting", "running", "terminating", "terminated", "failed", "expired"
]


class SessionSummary(Struct):
    marimo_version: str | None
    mode: SessionMode
    session_id: Annotated[
        str,
        Meta(
            description="Opaque ID, unique within the instance and stable while listed."
        ),
    ]
    started_at: datetime
    status: SessionStatus


class StartSessionRequest(Struct):
    notebook_id: Annotated[str, Meta(min_length=1)]


class DoneEvent(Struct):
    output: OutputData
    success: bool


class Notebook(Struct):
    id: str
    openable: bool
    path: (
        Annotated[
            str,
            Meta(
                description="Native path relative to the project root; null if root is null."
            ),
        ]
        | None
    )
    project_id: str
    sessions: list[SessionSummary]
    title: str
    updated_at: (
        Annotated[
            datetime,
            Meta(
                description="Best-effort activity time for display, never synchronization."
            ),
        ]
        | None
    )


class NotebookSummary(Struct):
    id: str
    openable: bool
    path: (
        Annotated[
            str,
            Meta(
                description="Native path relative to the project root; null if root is null."
            ),
        ]
        | None
    )
    sessions: list[SessionSummary]
    title: str
    updated_at: (
        Annotated[
            datetime,
            Meta(
                description="Best-effort activity time for display, never synchronization."
            ),
        ]
        | None
    )


class ProjectSummary(Struct):
    id: str
    name: str
    notebooks: list[NotebookSummary]
    root: (
        Annotated[
            str,
            Meta(
                description="Absolute native workspace path, or null without a filesystem root."
            ),
        ]
        | None
    )
    truncated: bool


class Session(Struct):
    marimo_version: str | None
    mode: SessionMode
    notebook_id: str
    project_id: str
    session_id: str
    started_at: datetime
    status: SessionStatus
    error: SessionError | UnsetType = UNSET
    kernel_generation: (
        Annotated[
            str,
            Meta(
                description="Opaque startup attempt ID. Changes on accepted restart, remains\nstable until the next attempt. A different generation during observation\nmeans the requested restart was superseded.\n",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET
    startup_phase: (
        Annotated[
            str,
            Meta(
                description="Optional host-defined progress phase while starting. Omitted when\nno phase is available or the session is no longer starting.\nClients accept unknown phases and may display generic startup UI.\nProgress changes do not invalidate the catalog's session summaries.\n",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class SessionCreateResult(Struct):
    marimo_version: str | None
    mode: SessionMode
    notebook_id: str
    project_id: str
    reused: bool
    session_id: str
    started_at: datetime
    status: SessionStatus
    error: SessionError | UnsetType = UNSET
    kernel_generation: (
        Annotated[
            str,
            Meta(
                description="Opaque startup attempt ID. Changes on accepted restart, remains\nstable until the next attempt. A different generation during observation\nmeans the requested restart was superseded.\n",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET
    startup_phase: (
        Annotated[
            str,
            Meta(
                description="Optional host-defined progress phase while starting. Omitted when\nno phase is available or the session is no longer starting.\nClients accept unknown phases and may display generic startup UI.\nProgress changes do not invalidate the catalog's session summaries.\n",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class Catalog(Struct):
    instance_id: UUID
    operations: Annotated[
        list[str],
        Meta(
            description="Optional operation identifiers; unknown identifiers must be accepted.\nsession.start requires session.read and session.watch. session.watch,\nsession.stop, and session.restart require session.read.\n"
        ),
    ]
    projects: list[ProjectSummary]
