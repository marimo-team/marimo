# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from host-protocol/openapi.yaml in marimo-team/pair.
# Regenerate with `cargo xtask generate-host-protocol`.
# ruff: noqa: TC003 - msgspec resolves annotations at runtime

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, NewType, TypeAlias

from msgspec import UNSET, Meta, Struct, UnsetType

if TYPE_CHECKING:
    AttachmentId = NewType("AttachmentId", str)
else:
    AttachmentId = NewType(
        "AttachmentId",
        Annotated[
            str,
            Meta(
                description="Identifies an attachment. Unique within the host.",
                min_length=1,
            ),
        ],
    )


class Binding(Struct):
    name: str
    preview: (
        Annotated[
            str,
            Meta(
                description="A short rendering of the value. A host may leave it null."
            ),
        ]
        | None
    )
    type: (
        Annotated[
            str,
            Meta(
                description="The runtime's label for the value's type. A host may leave it null."
            ),
        ]
        | None
    )


class DecisionOption(Struct):
    id: Annotated[str, Meta(description="Identifies this answer.")]
    label: Annotated[str, Meta(description="Text to show a person.")]


class DisplayData(Struct):
    data: Annotated[
        str,
        Meta(
            description="The rendered value. JSON mimetypes are encoded as text; binary mimetypes are base64. Never a URL only the runtime can serve."
        ),
    ]
    mimetype: Annotated[
        str,
        Meta(
            description="The format of `data`, such as `text/html` or `image/png`."
        ),
    ]


if TYPE_CHECKING:
    ExecutionId = NewType("ExecutionId", str)
else:
    ExecutionId = NewType(
        "ExecutionId",
        Annotated[
            str,
            Meta(
                description="Identifies an execution. Unique within the host.",
                min_length=1,
            ),
        ],
    )


class Host(Struct):
    operations: Annotated[
        list[str],
        Meta(
            description="The operations this host implements, such as `runtime.start`. Whether a client may call one on a given project or notebook is that object's `operations`. Clients accept names they do not recognize."
        ),
    ]


class HostMessage(Struct):
    host: Host
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class InterruptedOutcome(Struct, tag_field="kind", tag="interrupted"):
    pass


if TYPE_CHECKING:
    ItemId = NewType("ItemId", str)
else:
    ItemId = NewType(
        "ItemId",
        Annotated[
            str,
            Meta(
                description="Identifies a console or display item. Unique within the host; sending an item again with the same id replaces it.",
                min_length=1,
            ),
        ],
    )


Lifecycle: TypeAlias = Annotated[
    Literal["queued", "running", "idle"],
    Meta(
        description="Where a run or execution is in its lifecycle. An execution is\n`queued` until it starts, `running` while code executes, and\n`idle` once it has ended. How it ended is its `outcome`.\n"
    ),
]


if TYPE_CHECKING:
    NotebookId = NewType("NotebookId", str)
else:
    NotebookId = NewType(
        "NotebookId",
        Annotated[
            str,
            Meta(
                description="Identifies a notebook. Unique within the host and unchanged while the notebook exists.",
                min_length=1,
            ),
        ],
    )


ObjectType: TypeAlias = Annotated[
    Literal[
        "host",
        "project",
        "notebook",
        "runtime",
        "attachment",
        "run",
        "execution",
        "console",
        "display",
    ],
    Meta(
        description="The kinds a stream carries, and the values `types` accepts. The\ncatalog stream carries host, project, notebook, runtime, and\nattachment. A notebook's stream carries notebook, runtime,\nattachment, run, execution, console, and display.\n"
    ),
]


class OpenNotebookResponse(Struct):
    url: Annotated[
        str,
        Meta(
            description="The URL the host used to show the notebook. It never contains the host's token."
        ),
    ]


class Position(Struct):
    character: Annotated[
        int,
        Meta(
            description="Zero-based offset in the line, in UTF-16 code units.",
            ge=0,
        ),
    ]
    line: Annotated[
        int, Meta(description="Zero-based line within the code.", ge=0)
    ]


class Process(Struct):
    pid: Annotated[int, Meta(description="The process id.", ge=1)]
    started_at: Annotated[
        datetime, Meta(description="When the process started.")
    ]


if TYPE_CHECKING:
    ProjectId = NewType("ProjectId", str)
else:
    ProjectId = NewType(
        "ProjectId",
        Annotated[
            str,
            Meta(
                description="Identifies a project. Unique within the host and unchanged while the project exists.",
                min_length=1,
            ),
        ],
    )


ProjectStatus: TypeAlias = Annotated[
    Literal["indexing", "indexed", "partial"],
    Meta(
        description="How far a host has gotten finding the notebooks in a project.\nWhile it is `indexing`, more notebooks are coming. Once it is\n`indexed`, the host believes it has found every notebook under the\nroot. A `partial` project is one the host stopped scanning on\npurpose, or one with something it could not read.\n"
    ),
]


class Range(Struct):
    end: Annotated[
        Position,
        Meta(
            description="Exclusive end. Equal to start when only a point is known."
        ),
    ]
    start: Position


class Related(Struct):
    cell_id: str
    message: Annotated[
        str,
        Meta(
            description="What that cell contributes, such as `reads x from C`."
        ),
    ]
    range: (
        Annotated[Range, Meta(description="Where in that cell, when known.")]
        | None
    )


class RemovedMessage(Struct):
    id: Annotated[
        str, Meta(description="The id of the object that was removed.")
    ]
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


if TYPE_CHECKING:
    RunId = NewType("RunId", str)
else:
    RunId = NewType(
        "RunId",
        Annotated[
            str,
            Meta(
                description="Identifies a run. The request's `Idempotency-Key` for a client request; minted by the host when the runtime schedules a run.",
                min_length=1,
            ),
        ],
    )


class RunRequest(Struct):
    code: Annotated[
        str, Meta(description="The Python code to run as scratch code.")
    ]


if TYPE_CHECKING:
    RuntimeId = NewType("RuntimeId", str)
else:
    RuntimeId = NewType(
        "RuntimeId",
        Annotated[
            str,
            Meta(
                description="Identifies a runtime. Unique within the host; every start and restart creates a new id.",
                min_length=1,
            ),
        ],
    )


RuntimeStatus: TypeAlias = Annotated[
    Literal["starting", "running", "terminating", "failed"],
    Meta(
        description="Where a runtime is in its life. A `starting` runtime is bringing\nits kernel up. A `running` runtime accepts work. A `terminating`\nruntime is shutting its kernel down. A `failed` runtime could not\nstart, or its kernel exited unexpectedly. A runtime that has\nended is removed rather than given a status.\n"
    ),
]


class StartRuntimeRequest(Struct):
    decisions: (
        Annotated[
            dict[str, str],
            Meta(
                description="Answers to the questions in a `decision-required` problem.\nEach key is a decision's `id` and each value is the `id` of\nthe chosen option. A client that already knows its choices can\nsend them the first time.\n"
            ),
        ]
        | UnsetType
    ) = UNSET


class UpdateNotebookRequest(Struct):
    name: (
        Annotated[str, Meta(description="The new label to show people.")]
        | UnsetType
    ) = UNSET
    path: (
        Annotated[
            str,
            Meta(
                description="The new location, relative to the project root and written the way the host's operating system writes paths."
            ),
        ]
        | UnsetType
    ) = UNSET


class ValueOutcome(Struct, tag_field="kind", tag="value"):
    display: (
        Annotated[
            DisplayData,
            Meta(
                description="The value as last rendered. Replaced as it grows. Null when the code produced no value."
            ),
        ]
        | None
    )


class Attachment(Struct):
    id: AttachmentId
    kind: Annotated[
        str,
        Meta(
            description="What kind of thing is attached, such as `browser`, `editor`, or `agent`. Clients accept kinds they do not recognize."
        ),
    ]
    name: (
        Annotated[
            str,
            Meta(
                description="A label to show people, such as the browser or editor's name. Null when there is none."
            ),
        ]
        | None
    )
    notebook_id: NotebookId
    since: Annotated[datetime, Meta(description="When it attached.")]


class AttachmentMessage(Struct):
    attachment: Attachment
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Console(Struct):
    execution_id: ExecutionId
    id: ItemId
    name: Annotated[
        Literal["stdout", "stderr"],
        Meta(description="Which stream the text went to."),
    ]
    seq: Annotated[
        int,
        Meta(
            description="Position among the execution's items, increasing in the order they were produced.",
            ge=0,
        ),
    ]
    text: Annotated[str, Meta(description="The text, exactly as written.")]


class ConsoleMessage(Struct):
    console: Console
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class CreateNotebookRequest(Struct):
    project_id: ProjectId
    name: (
        Annotated[
            str,
            Meta(
                description="A label to show people. In a project with a root it defaults to the filename."
            ),
        ]
        | UnsetType
    ) = UNSET
    path: (
        Annotated[
            str,
            Meta(
                description="Where to put the file, relative to the project root and written the way the host's operating system writes paths."
            ),
        ]
        | UnsetType
    ) = UNSET


class Decision(Struct):
    id: Annotated[
        str,
        Meta(
            description="Identifies the question when the client answers it."
        ),
    ]
    options: Annotated[
        list[DecisionOption], Meta(description="The possible answers.")
    ]
    prompt: Annotated[
        str, Meta(description="The question, worded for a person.")
    ]


class Display(Struct):
    data: Annotated[
        str,
        Meta(
            description="The rendered value. JSON mimetypes are encoded as text; binary mimetypes are base64. Never a URL only the runtime can serve."
        ),
    ]
    execution_id: ExecutionId
    id: ItemId
    mimetype: Annotated[
        str, Meta(description="The format of `data`, such as `image/png`.")
    ]
    seq: Annotated[
        int,
        Meta(
            description="Position among the execution's items, increasing in the order they were produced.",
            ge=0,
        ),
    ]


class DisplayMessage(Struct):
    display: Display
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Error(Struct):
    kind: Annotated[
        str,
        Meta(
            description="The producer's identifier, scoped by source. Open; this RFC defines `exception`, `interrupted`, and `internal`. Clients show unrecognized kinds as plain errors."
        ),
    ]
    message: Annotated[
        str, Meta(description="A description of the error to show people.")
    ]
    name: (
        Annotated[
            str,
            Meta(
                description="The exception class, such as `ZeroDivisionError`. Set when kind is exception, null otherwise."
            ),
        ]
        | None
    )
    range: (
        Annotated[Range, Meta(description="Where in the code, when known.")]
        | None
    )
    related: Annotated[
        list[Related],
        Meta(
            description="Every involved cell, including this one, in canonical order. Each copy of a cross-cell error carries the same list; clients deduplicate on kind and related cell ids. Empty when the error involves this code alone."
        ),
    ]
    severity: Annotated[
        Literal["error", "warning", "information", "hint"],
        Meta(
            description="Error unless the producer says otherwise. Only error affects scheduling."
        ),
    ]
    source: (
        Annotated[
            str,
            Meta(
                description="Who produced it, such as `marimo` or a SQL analyzer. Scopes kind."
            ),
        ]
        | None
    )
    traceback: (
        Annotated[
            DisplayData,
            Meta(
                description="The traceback as rendered by the runtime, plain text or HTML by its mimetype. Null when unavailable or not shown."
            ),
        ]
        | None
    )


class ErrorOutcome(Struct, tag_field="kind", tag="error"):
    error: Error


class HostRecord(Struct):
    name: Annotated[
        str,
        Meta(
            description="A label for the host to show people, such as `VS Code` or `marimo`. Two hosts can share a name; the filename is the identity."
        ),
    ]
    process: Process
    token: Annotated[
        str,
        Meta(
            description="The secret a client sends to prove it read the record.",
            min_length=1,
        ),
    ]
    url: Annotated[
        str,
        Meta(
            description="Where the host's API is. The scheme is `http`, and the host part is `127.0.0.1` or `[::1]`, written exactly that way."
        ),
    ]
    version: Annotated[
        Literal[1],
        Meta(
            description="The version of this record's format. This document describes version 1."
        ),
    ]


class Notebook(Struct):
    id: NotebookId
    name: Annotated[
        str,
        Meta(
            description="A label to show people. Derived from the filename when the host has nothing better."
        ),
    ]
    operations: Annotated[
        list[str],
        Meta(
            description="Operations this client may call on the notebook. A subset of `host.operations`, narrowed by permission and never by state; whether a runtime is attached shows in the `runtime` object, and preconditions still apply when an operation is called. The host sends the notebook again when it changes."
        ),
    ]
    path: (
        Annotated[
            str,
            Meta(
                description="The file's path relative to the project root, written the way the host's operating system writes paths. Null when the notebook has no file, such as one not yet saved, or one deleted while a runtime still refers to it."
            ),
        ]
        | None
    )
    project_id: ProjectId
    updated_at: (
        Annotated[
            datetime,
            Meta(
                description="When the file was last modified, as of the host's last look at it. Null when the host does not know."
            ),
        ]
        | None
    )


class NotebookMessage(Struct):
    notebook: Notebook
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


Outcome: TypeAlias = Annotated[
    ValueOutcome | ErrorOutcome | InterruptedOutcome,
    Meta(
        description="How an execution ended, tagged on `kind`. A `value` carries the\nexecution's value as last rendered; while the execution is\nrunning it is the value so far, and it is final once the\nexecution is `idle`. An `error` carries the error that ended it.\nAn `interrupted` execution was cancelled before or during execution. Other\nkinds are defined by later versions of this protocol.\n"
    ),
]


class Problem(Struct):
    status: Annotated[
        int,
        Meta(
            description="The HTTP status code of the response.", ge=400, le=599
        ),
    ]
    title: Annotated[
        str,
        Meta(
            description="A short, human-readable name for the kind of problem."
        ),
    ]
    type: Annotated[
        str,
        Meta(
            description="What kind of problem this is, as a URI. The kinds this\nprotocol defines all start with `tag:marimo.io,2026:host/` and\nend with one of `invalid-request` (400), `unauthorized` (401),\n`forbidden` (403), `not-found` (404), `not-acceptable` (406),\n`conflict` (409), `no-runtime` (409), `decision-required`\n(409), `internal` (500), or `unsupported-operation` (501). A\nclient that sees a kind it does not recognize falls back to\n`status`.\n"
        ),
    ]
    decisions: (
        Annotated[
            list[Decision],
            Meta(
                description="The choices the client has to make before the host can carry out the request. Only present for `decision-required`."
            ),
        ]
        | UnsetType
    ) = UNSET
    detail: (
        Annotated[
            str,
            Meta(
                description="A human-readable explanation of what went wrong this time."
            ),
        ]
        | UnsetType
    ) = UNSET


class Project(Struct):
    id: ProjectId
    message: (
        Annotated[
            str,
            Meta(
                description="Why the host stopped scanning. Null unless `status` is `partial`."
            ),
        ]
        | None
    )
    name: Annotated[
        str,
        Meta(
            description="A label to show people, usually the name of the root directory."
        ),
    ]
    operations: Annotated[
        list[str],
        Meta(
            description="Operations this client may call on the project, today `notebook.create`. A subset of `host.operations`, narrowed by permission and never by state. The host sends the project again when it changes."
        ),
    ]
    root: (
        Annotated[
            str,
            Meta(
                description="The absolute path of the project's directory, written the way the host's operating system writes paths. Null when the project has no directory."
            ),
        ]
        | None
    )
    status: ProjectStatus


class ProjectMessage(Struct):
    project: Project
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Run(Struct):
    caused_by: (
        Annotated[
            ExecutionId,
            Meta(
                description="The execution that caused this runtime-scheduled run. Null for a client request or when the runtime does not know the source."
            ),
        ]
        | None
    )
    completed_at: (
        Annotated[
            datetime,
            Meta(
                description="When the run ended. Null until the run is `idle`."
            ),
        ]
        | None
    )
    id: RunId
    notebook_id: NotebookId
    started_at: (
        Annotated[
            datetime,
            Meta(
                description="When the first execution started. Null if none has started."
            ),
        ]
        | None
    )
    status: Annotated[
        Lifecycle,
        Meta(
            description="Queued until the first execution starts, running while any execution is queued or running, and idle when the queue drains. A run can go idle with no executions."
        ),
    ]


class RunMessage(Struct):
    run: Run
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Runtime(Struct):
    id: RuntimeId
    marimo_version: (
        Annotated[
            str,
            Meta(
                description="The version of marimo running the kernel. Null until the host knows it."
            ),
        ]
        | None
    )
    message: (
        Annotated[
            str,
            Meta(
                description="A note about the current status, such as progress while `starting` or the reason when `failed`. Null otherwise."
            ),
        ]
        | None
    )
    notebook_id: NotebookId
    started_at: Annotated[
        datetime, Meta(description="When this runtime started.")
    ]
    status: RuntimeStatus


class RuntimeMessage(Struct):
    runtime: Runtime
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Execution(Struct):
    bindings: Annotated[
        list[Binding],
        Meta(
            description="Names bound in the namespace, with a type and preview, stamped when the execution ends. Empty while running and for scratch code, whose bindings die with the execution."
        ),
    ]
    caused_by: (
        Annotated[
            ExecutionId,
            Meta(
                description="The execution in the same run that caused this one. Null for executions requested directly."
            ),
        ]
        | None
    )
    cell_id: (
        Annotated[
            str,
            Meta(
                description="The cell this execution belongs to. Null for scratch code, a cell outside the document."
            ),
        ]
        | None
    )
    code: (
        Annotated[
            str,
            Meta(
                description="The submitted code for an execution with no cell. Null for a cell's execution, since the cell holds its code."
            ),
        ]
        | None
    )
    code_hash: Annotated[
        str, Meta(description="A hash of the code that was evaluated.")
    ]
    completed_at: (
        Annotated[
            datetime,
            Meta(
                description="When the execution ended. Null until it is idle."
            ),
        ]
        | None
    )
    id: ExecutionId
    outcome: (
        Annotated[
            Outcome,
            Meta(
                description="How the execution ended. Null while queued; while running, a value carries the display so far; final once idle."
            ),
        ]
        | None
    )
    run_id: (
        Annotated[
            RunId,
            Meta(
                description="The run that queued this execution. May name a run the host has dropped. Null for a restored result whose run is unknown."
            ),
        ]
        | None
    )
    runtime_id: (
        Annotated[
            RuntimeId,
            Meta(
                description="The runtime that produced this execution. Live when it equals the current runtime's id. Null when the producer is unknown."
            ),
        ]
        | None
    )
    stale: (
        Annotated[
            bool,
            Meta(
                description="Whether an input changed since this result was produced. Null for scratch code, which has no inputs in the graph."
            ),
        ]
        | None
    )
    started_at: (
        Annotated[
            datetime,
            Meta(
                description="When the code started executing. Null while queued and for an execution that never ran."
            ),
        ]
        | None
    )
    status: Lifecycle


class ExecutionMessage(Struct):
    execution: Execution
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET
