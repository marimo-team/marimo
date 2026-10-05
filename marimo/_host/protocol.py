# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from marimo-desktop/host-protocol/openapi.yaml.
# Regenerate with `cargo xtask generate-host-protocol`.
# ruff: noqa: TC003 - msgspec resolves annotations at runtime

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from msgspec import UNSET, Meta, Struct, UnsetType

AttachmentId: TypeAlias = Annotated[
    str,
    Meta(
        description="Identifies an attachment. Unique within the host.",
        min_length=1,
    ),
]


class DecisionOption(Struct):
    id: Annotated[str, Meta(description="Identifies this answer.")]
    label: Annotated[str, Meta(description="Text to show a person.")]


class ExecuteRequest(Struct):
    code: Annotated[str, Meta(description="The Python code to run.")]


class Output(Struct):
    data: Annotated[
        str,
        Meta(
            description="The output, in the format `mimetype` names. JSON formats are encoded as text."
        ),
    ]
    mimetype: Annotated[
        str, Meta(description="The format of `data`, such as `text/html`.")
    ]


class ExecutionError(Struct):
    kind: Annotated[
        Literal["exception", "syntax", "interruption", "internal"],
        Meta(description="marimo's class of error."),
    ]
    message: Annotated[str, Meta(description="The error's message.")]
    name: (
        Annotated[
            str,
            Meta(
                description="The Python exception class, such as `ZeroDivisionError`. Set for `exception`, null otherwise."
            ),
        ]
        | None
    )
    traceback: (
        Annotated[
            str,
            Meta(
                description="The formatted traceback, or null when there is none."
            ),
        ]
        | None
    )


ExecutionId: TypeAlias = Annotated[
    str,
    Meta(
        description="Identifies an execution. It is the `Idempotency-Key` of the request that started it.",
        min_length=1,
    ),
]


ExecutionStatus: TypeAlias = Annotated[
    Literal["queued", "running", "succeeded", "failed", "interrupted"],
    Meta(
        description="Where an execution is. It is `queued` until the kernel picks it\nup and `running` until the code finishes. Then it is `succeeded`,\n`failed` with `errors` set, or `interrupted` because someone asked\nfor it to stop or the runtime went away.\n"
    ),
]


ExportFormat: TypeAlias = Annotated[
    Literal["py", "html"],
    Meta(
        description="A format a notebook can be exported in. `py` is the notebook's source and every host supports it. `html` is the notebook rendered with its outputs."
    ),
]


ExportOutputs: TypeAlias = Annotated[
    Literal["runtime", "cache", "none"],
    Meta(
        description="Where an export's outputs came from. `runtime` when the notebook had one, `cache` when the host had outputs saved from an earlier run, `none` when the export has no outputs."
    ),
]


class Host(Struct):
    operations: Annotated[
        list[str],
        Meta(
            description="The operations this host supports, such as `runtime.start`. Clients accept names they do not recognize."
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


NotebookId: TypeAlias = Annotated[
    str,
    Meta(
        description="Identifies a notebook. Unique within the host and unchanged while the notebook exists.",
        min_length=1,
    ),
]


ObjectType: TypeAlias = Annotated[
    Literal[
        "host",
        "project",
        "notebook",
        "runtime",
        "attachment",
        "execution",
        "console",
    ],
    Meta(
        description="The kinds a stream carries, and the values `types` accepts. The\ncatalog stream carries host, project, notebook, runtime, and\nattachment. A notebook's stream carries notebook, runtime,\nattachment, execution, and console.\n"
    ),
]


class OpenNotebookResponse(Struct):
    url: Annotated[
        str,
        Meta(
            description="The URL the host used to show the notebook. It never contains the host's token."
        ),
    ]


class Process(Struct):
    pid: Annotated[int, Meta(description="The process id.", ge=1)]
    started_at: Annotated[
        datetime, Meta(description="When the process started.")
    ]


ProjectId: TypeAlias = Annotated[
    str,
    Meta(
        description="Identifies a project. Unique within the host and unchanged while the project exists.",
        min_length=1,
    ),
]


ProjectStatus: TypeAlias = Annotated[
    Literal["indexing", "indexed", "partial"],
    Meta(
        description="How far a host has gotten finding the notebooks in a project.\nWhile it is `indexing`, more notebooks are coming. Once it is\n`indexed`, the host believes it has found every notebook under the\nroot. A `partial` project is one the host stopped scanning on\npurpose, or one with something it could not read.\n"
    ),
]


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


RuntimeId: TypeAlias = Annotated[
    str,
    Meta(
        description="Identifies a runtime. Unique within the host and unchanged by kernel restarts.",
        min_length=1,
    ),
]


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
    path: Annotated[
        str,
        Meta(
            description="The new location, relative to the project root and written the way the host's operating system writes paths."
        ),
    ]


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
    name: Annotated[
        Literal["stdout", "stderr"],
        Meta(description="Which stream the text went to."),
    ]
    text: Annotated[str, Meta(description="The text, exactly as printed.")]


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
    path: Annotated[
        str,
        Meta(
            description="Where to put the file, relative to the project root and written the way the host's operating system writes paths."
        ),
    ]
    project_id: ProjectId


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


class Execution(Struct):
    code: Annotated[str, Meta(description="The code that ran.")]
    completed_at: (
        Annotated[
            datetime,
            Meta(
                description="When the execution reached a final status. Null until then."
            ),
        ]
        | None
    )
    errors: Annotated[
        list[ExecutionError],
        Meta(description="Why it failed. Empty otherwise."),
    ]
    id: ExecutionId
    notebook_id: NotebookId
    output: (
        Annotated[
            Output,
            Meta(
                description="The output so far, as marimo would show it. marimo replaces it as the code appends to it, so it is one value rather than a list. Final once `status` is. Null when there is none yet.",
                title="Display",
            ),
        ]
        | None
    )
    started_at: (
        Annotated[
            datetime,
            Meta(
                description="When the kernel started running the code. Null while `queued`."
            ),
        ]
        | None
    )
    status: ExecutionStatus


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
    path: (
        Annotated[
            str,
            Meta(
                description="The file's path relative to the project root, written the way the host's operating system writes paths. Null when the notebook has no file, such as one deleted while a runtime still refers to it."
            ),
        ]
        | None
    )
    project_id: ProjectId
    title: Annotated[str, Meta(description="A title to show people.")]
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


class Runtime(Struct):
    generation: Annotated[
        int,
        Meta(
            description="How many times the kernel has been restarted. A new runtime starts at 0.",
            ge=0,
        ),
    ]
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
    sandbox: Annotated[
        bool,
        Meta(
            description="Whether the kernel runs in a sandbox, an isolated environment built from the dependencies the notebook declares in its own file."
        ),
    ]
    started_at: Annotated[
        datetime,
        Meta(
            description="When the runtime started. A kernel restart does not change it."
        ),
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
