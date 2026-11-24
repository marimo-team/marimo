# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from packages/host-protocol.
# Regenerate with `make host-protocol-codegen`.
# ruff: noqa: TC003 - msgspec resolves annotations at runtime
# ruff: noqa: RUF036 - the generator orders unions; the wire shape is the same

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, NewType, TypeAlias

from msgspec import UNSET, Meta, Struct, UnsetType

Identity: TypeAlias = Annotated[
    str,
    Meta(
        description="The opaque client identity supplied by `Marimo-Attachment-Identity`.\nNull when none was supplied. Consumers can group attachments\nwith the same identity within a host. It does not identify an\nindividual connection or change its lifetime.\n",
        max_length=128,
        min_length=1,
        pattern="^[!-~]+$",
    ),
]


Name: TypeAlias = Annotated[
    str,
    Meta(
        description="A label to show people, supplied by `Marimo-Attachment-Name`, such as the browser or editor's name. Null when the header is omitted or empty.",
        max_length=256,
    ),
]


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


class CancelledOutcome(Struct, frozen=True, tag_field="kind", tag="cancelled"):
    pass


class CellConfig(Struct, frozen=True):
    column: (
        Annotated[
            int,
            Meta(
                description="The column the cell sits in, for multi-column layouts. Null in a single column."
            ),
        ]
        | None
    )
    disabled: Annotated[
        bool, Meta(description="Whether the cell is kept from running.")
    ]
    expand_output: Annotated[
        bool,
        Meta(
            description="Whether clients show the full output rather than a scrolled box."
        ),
    ]
    hide_code: Annotated[
        bool,
        Meta(
            description="Whether clients hide the code by default. This is a presentation preference; source availability is represented by `Cell.code`."
        ),
    ]


class CellConfigInput(Struct, frozen=True, forbid_unknown_fields=True):
    column: int | None | UnsetType = UNSET
    disabled: bool | UnsetType = False
    expand_output: bool | UnsetType = False
    hide_code: bool | UnsetType = False


if TYPE_CHECKING:
    CellId = NewType("CellId", str)
else:
    CellId = NewType(
        "CellId",
        Annotated[
            str,
            Meta(
                description="Identifies a cell within its notebook. Stable while the host serves the notebook; whether it survives a reload of the store depends on the format. `setup` is the setup cell.",
                min_length=1,
            ),
        ],
    )


class CellInput(Struct, frozen=True, forbid_unknown_fields=True):
    code: Annotated[str, Meta(description="The cell's source code.")]
    id: Annotated[
        CellId,
        Meta(
            description="The cell's id. A client chooses the id of a cell it creates."
        ),
    ]
    config: CellConfigInput | UnsetType = UNSET
    name: (
        Annotated[
            str,
            Meta(description="The cell's name. `_` for an anonymous cell."),
        ]
        | UnsetType
    ) = "_"


if TYPE_CHECKING:
    CodeFingerprint = NewType("CodeFingerprint", str)
else:
    CodeFingerprint = NewType(
        "CodeFingerprint",
        Annotated[
            str,
            Meta(
                description="Opaque code identity assigned by the host. Clients compare cell and execution fingerprints for freshness. Incompatible schemes MUST produce distinct fingerprints.",
                min_length=1,
            ),
        ],
    )


class ConflictProblem(
    Struct, frozen=True, tag_field="type", tag="urn:marimo:problem:conflict"
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[409] = 409
    title: str = "Conflict"


class ConsoleText(Struct, frozen=True, tag_field="kind", tag="text"):
    stream: Annotated[
        Literal["stdout", "stderr"],
        Meta(description="Which stream the text went to."),
    ]
    text: Annotated[str, Meta(description="The text, exactly as written.")]


class CreateCell(
    Struct,
    frozen=True,
    forbid_unknown_fields=True,
    tag_field="kind",
    tag="create_cell",
):
    cell: CellInput


class DecisionOption(Struct, frozen=True):
    id: Annotated[str, Meta(description="Identifies this answer.")]
    label: Annotated[
        str,
        Meta(
            description="Text to show a person.",
            examples=["Sandbox from the notebook's dependencies"],
        ),
    ]


class DeleteCell(
    Struct,
    frozen=True,
    forbid_unknown_fields=True,
    tag_field="kind",
    tag="delete_cell",
):
    base_etag: Annotated[
        str, Meta(description="The cell's etag as last read, or `*`.")
    ]
    id: Annotated[CellId, Meta(description="The cell to remove.")]


if TYPE_CHECKING:
    Etag = NewType("Etag", str)
else:
    Etag = NewType(
        "Etag",
        Annotated[
            str,
            Meta(
                description="An identifier a host derives from content, so the same content has the same etag. It is opaque to clients. They read etags from the stream and from responses, and send them back as preconditions.",
                min_length=1,
            ),
        ],
    )


class ExecuteRequest(Struct, frozen=True, forbid_unknown_fields=True):
    code: Annotated[
        str,
        Meta(
            description="Python code that can read the notebook's current values.\nAssignments stay local to the call. Changes to shared objects persist.\n"
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


class ExecutionQueued(Struct, frozen=True, tag_field="status", tag="queued"):
    pass


class ForbiddenProblem(
    Struct, frozen=True, tag_field="type", tag="urn:marimo:problem:forbidden"
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[403] = 403
    title: str = "Forbidden"


class Host(Struct, frozen=True):
    operations: Annotated[
        tuple[str, ...],
        Meta(
            description="The operations this host implements, such as `runtime.start`. Whether a client may call one on a given project or notebook is that object's `operations`. Clients accept names they do not recognize."
        ),
    ]


class InputReplyRequest(Struct, frozen=True, forbid_unknown_fields=True):
    value: Annotated[
        str,
        Meta(
            description="The text to deliver to the input exactly as submitted, including an empty string when the answer is empty."
        ),
    ]


InputStatus: TypeAlias = Annotated[
    Literal["pending", "answered", "cancelled"],
    Meta(
        description="An input starts `pending` while it waits for an answer. It becomes\n`answered` when the host accepts a reply for delivery, or `cancelled`\nwhen the host ends the wait while input is still pending. Both\n`answered` and `cancelled` are final. An answered input stays\nanswered if execution later fails before consuming the value.\n"
    ),
]


class InternalProblem(
    Struct, frozen=True, tag_field="type", tag="urn:marimo:problem:internal"
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[500] = 500
    title: str = "Internal error"


class InvalidRequestProblem(
    Struct,
    frozen=True,
    tag_field="type",
    tag="urn:marimo:problem:invalid-request",
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[400] = 400
    title: str = "Invalid request"


if TYPE_CHECKING:
    ItemId = NewType("ItemId", str)
else:
    ItemId = NewType(
        "ItemId",
        Annotated[
            str,
            Meta(
                description="Identifies an output, console, input, or variable item uniquely within the host. Sending an item again with the same id replaces it.",
                min_length=1,
            ),
        ],
    )


if TYPE_CHECKING:
    JsonValue: TypeAlias = (
        str
        | int
        | float
        | bool
        | None
        | list["JsonValue"]
        | dict[str, "JsonValue"]
    )
else:
    # msgspec cannot decode recursive aliases. Its JSON decoder returns JSON values.
    JsonValue = object


class Media(Struct, frozen=True):
    data: Annotated[
        str,
        Meta(
            description="The rendered value, embedded so clients can display it independently of the runtime. JSON mimetypes are encoded as text and binary mimetypes as base64."
        ),
    ]
    mimetype: Annotated[
        str,
        Meta(
            description="The format of `data`, such as `text/html` or `image/png`.",
            examples=["text/html"],
        ),
    ]


class MethodNotAllowedProblem(
    Struct,
    frozen=True,
    tag_field="type",
    tag="urn:marimo:problem:method-not-allowed",
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[405] = 405
    title: str = "Method not allowed"


class NoRuntimeProblem(
    Struct, frozen=True, tag_field="type", tag="urn:marimo:problem:no-runtime"
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[409] = 409
    title: str = "No runtime"


class NotFoundProblem(
    Struct, frozen=True, tag_field="type", tag="urn:marimo:problem:not-found"
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[404] = 404
    title: str = "Not found"


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


ObjectKind: TypeAlias = Annotated[
    Literal[
        "host",
        "project",
        "notebook",
        "document",
        "cell",
        "runtime",
        "attachment",
        "run",
        "execution",
        "output",
        "console",
        "input",
        "variable",
        "analysis",
        "custom",
    ],
    Meta(
        description="The kinds a stream carries, and the values `kinds` accepts. The catalog stream carries host, project, notebook, runtime, and attachment. A notebook's stream carries notebook, document, cell, runtime, attachment, run, execution, output, console, input, variable, analysis, and custom. Custom events describe occurrences rather than object state."
    ),
]


class OpenNotebookResponse(Struct, frozen=True):
    url: Annotated[
        str,
        Meta(
            description="The URL the host used to show the notebook, with the host's token omitted."
        ),
    ]


class Output(Struct, frozen=True):
    execution_id: ExecutionId
    id: ItemId
    media: (
        Annotated[
            Media,
            Meta(
                description="The output as last rendered. Null when the code set it to nothing or cleared it."
            ),
        ]
        | None
    )


class Position(Struct, frozen=True):
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


class Range(Struct, frozen=True):
    end: Annotated[
        Position,
        Meta(
            description="Exclusive end. Equal to start when only a point is known."
        ),
    ]
    start: Position


class ReadyEvent(Struct, frozen=True, tag_field="event", tag="ready"):
    data: Annotated[dict[str, Any], Meta(max_length=0)]
    id: Annotated[
        str,
        Meta(
            description="The resume cursor. Omitted on snapshot and reset events.",
            min_length=1,
        ),
    ]


class Related(Struct, frozen=True):
    cell_id: CellId
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


class ReplaceCell(
    Struct,
    frozen=True,
    forbid_unknown_fields=True,
    tag_field="kind",
    tag="replace_cell",
):
    base_etag: Annotated[
        str, Meta(description="The cell's etag as last read, or `*`.")
    ]
    cell: CellInput


class RequestedCell(Struct, frozen=True, forbid_unknown_fields=True):
    id: CellId
    etag: (
        Annotated[
            Etag,
            Meta(
                description="The cell's `etag` as last read. A cell whose source, name, or config differs is `precondition-failed`. Absent, the cell runs as it is."
            ),
        ]
        | UnsetType
    ) = UNSET


class ResetEvent(Struct, frozen=True, tag_field="event", tag="reset"):
    data: Annotated[dict[str, Any], Meta(max_length=0)]
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class Revision(Struct, frozen=True):
    execution_id: Annotated[
        ExecutionId,
        Meta(
            description="The execution whose evaluation produced the value. Usually the variable's `execution_id`, and earlier when the runtime carried the value forward."
        ),
    ]
    update: Annotated[
        int,
        Meta(
            description="How many times the value has been updated since it was produced. Zero at binding.",
            ge=0,
        ),
    ]


class RunCellsOrigin(Struct, frozen=True, tag_field="kind", tag="cells"):
    cell_ids: Annotated[
        tuple[CellId, ...],
        Meta(
            description="The cells the run was requested for. Fixed when the run is accepted, so a client can tell which cells a queued run will reach before the runtime has planned their executions. Each one's execution in this run reports the fingerprint of the source accepted for it.",
            min_length=1,
        ),
    ]


class RunCodeOrigin(Struct, frozen=True, tag_field="kind", tag="code"):
    code: Annotated[
        str,
        Meta(
            description="The submitted code, which the run's scratch execution evaluates."
        ),
    ]


class RunFailedOutcome(Struct, frozen=True, tag_field="kind", tag="failed"):
    message: (
        Annotated[
            str,
            Meta(
                description="Why the host could not finish the cycle, to show people. Null when the run failed because an execution's code raised."
            ),
        ]
        | None
    )


if TYPE_CHECKING:
    RunId = NewType("RunId", str)
else:
    RunId = NewType(
        "RunId",
        Annotated[
            str,
            Meta(
                description="Identifies a run independently of the request's `Idempotency-Key`. Events carry the key in `request_id`.",
                min_length=1,
            ),
        ],
    )


class RunQueued(Struct, frozen=True, tag_field="status", tag="queued"):
    pass


class RunRequest(Struct, frozen=True, forbid_unknown_fields=True):
    cells: Annotated[
        tuple[RequestedCell, ...],
        Meta(
            description="Cells to run by id. The notebook's execution settings determine their order and whether dependent cells run too.",
            min_length=1,
        ),
    ]


class RunRuntimeOrigin(Struct, frozen=True, tag_field="kind", tag="runtime"):
    pass


class RuntimeFailedOutcome(
    Struct, frozen=True, tag_field="kind", tag="failed"
):
    message: (
        Annotated[
            str,
            Meta(
                description="Why the kernel could not start or why it exited, to show people. Null when the host does not know."
            ),
        ]
        | None
    )


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


class RuntimeReady(Struct, frozen=True, tag_field="status", tag="ready"):
    pass


class RuntimeStarting(Struct, frozen=True, tag_field="status", tag="starting"):
    message: (
        Annotated[
            str,
            Meta(
                description="A note about progress, such as the packages being installed. Null when the host has nothing to report."
            ),
        ]
        | None
    )


class RuntimeStoppedOutcome(
    Struct, frozen=True, tag_field="kind", tag="stopped"
):
    pass


class RuntimeStopping(Struct, frozen=True, tag_field="status", tag="stopping"):
    pass


class SaveRequest(Struct, frozen=True, forbid_unknown_fields=True):
    decisions: (
        Annotated[
            dict[str, str],
            Meta(
                description="Answers to the questions in a `decision-required` problem, as for `runtime.start`."
            ),
        ]
        | UnsetType
    ) = UNSET


class SetOrder(
    Struct,
    frozen=True,
    forbid_unknown_fields=True,
    tag_field="kind",
    tag="set_order",
):
    base_etag: Annotated[
        str,
        Meta(description="The document's `order_etag` as last read, or `*`."),
    ]
    order: Annotated[
        tuple[CellId, ...],
        Meta(
            description="Every cell id exactly once, in the new order, counting cells this edit creates and leaving out cells it deletes."
        ),
    ]


class StartRuntimeRequest(Struct, frozen=True, forbid_unknown_fields=True):
    decisions: (
        Annotated[
            dict[str, str],
            Meta(
                description="Answers to the questions in a `decision-required` problem.\nEach key is a decision's `id` and each value is the `id` of\nthe chosen option. A client that already knows its choices can\nsend them the first time.\n",
                examples=[{"environment": "sandbox"}],
            ),
        ]
        | UnsetType
    ) = UNSET


class SucceededOutcome(Struct, frozen=True, tag_field="kind", tag="succeeded"):
    pass


Timestamp: TypeAlias = Annotated[
    datetime,
    Meta(
        description="A date and time with its offset from UTC, as RFC 3339 writes it."
    ),
]


class UnauthorizedProblem(
    Struct,
    frozen=True,
    tag_field="type",
    tag="urn:marimo:problem:unauthorized",
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[401] = 401
    title: str = "Unauthorized"


class UnknownProblem(Struct, frozen=True):
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
        str, Meta(description="What kind of problem this is, as a URI.")
    ]
    detail: (
        Annotated[
            str,
            Meta(
                description="A human-readable explanation of what went wrong this time."
            ),
        ]
        | UnsetType
    ) = UNSET


class UnsupportedOperationProblem(
    Struct,
    frozen=True,
    tag_field="type",
    tag="urn:marimo:problem:unsupported-operation",
):
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[501] = 501
    title: str = "Unsupported operation"


class UpdateNotebookRequest(Struct, frozen=True, forbid_unknown_fields=True):
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


class Variable(Struct, frozen=True):
    execution_id: Annotated[
        ExecutionId, Meta(description="The execution that bound the name.")
    ]
    id: ItemId
    name: Annotated[str, Meta(description="The name in the namespace.")]
    preview: (
        Annotated[
            str,
            Meta(
                description="A short rendering of the value. A host may leave it null."
            ),
        ]
        | None
    )
    revision: Revision
    type: (
        Annotated[
            str,
            Meta(
                description="The runtime's label for the value's type. A host may leave it null."
            ),
        ]
        | None
    )


class VariableMessage(Struct, frozen=True):
    variable: Variable
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Attachment(Struct, frozen=True):
    created_at: Annotated[Timestamp, Meta(description="When it attached.")]
    id: AttachmentId
    identity: (
        Annotated[
            Identity,
            Meta(
                description="The opaque client identity supplied by `Marimo-Attachment-Identity`.\nNull when none was supplied. Consumers can group attachments\nwith the same identity within a host. It does not identify an\nindividual connection or change its lifetime.\n"
            ),
        ]
        | None
    )
    kind: Annotated[
        str,
        Meta(
            description="What kind of thing is attached, supplied by `Marimo-Attachment-Kind`, such as `browser`, `editor`, or `agent`. Defaults to `client` when the header is omitted. Clients accept kinds they do not recognize.",
            pattern="^[a-z0-9-]+$",
        ),
    ]
    name: (
        Annotated[
            Name,
            Meta(
                description="A label to show people, supplied by `Marimo-Attachment-Name`, such as the browser or editor's name. Null when the header is omitted or empty."
            ),
        ]
        | None
    )
    notebook_id: NotebookId


class AttachmentMessage(Struct, frozen=True):
    attachment: Attachment
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Cell(Struct, frozen=True):
    code: (
        Annotated[
            str,
            Meta(
                description="The cell's source code, with newline line endings, or null when the host does not expose source to this client. An empty string is an empty cell. A host normalizes other line endings when it loads a file. Source availability does not grant editing permission; see the notebook's operations."
            ),
        ]
        | None
    )
    code_fingerprint: Annotated[
        CodeFingerprint,
        Meta(
            description="Fingerprint of the actual source, including when `code` is null. Formatting-only edits may preserve it. Independent of cell name, config, and source visibility."
        ),
    ]
    config: CellConfig
    etag: Annotated[
        Etag,
        Meta(
            description="Precondition for edits and cell runs. Covers exact source, name, and config."
        ),
    ]
    id: CellId
    name: Annotated[
        str,
        Meta(
            description="The cell's name. `_` for an anonymous cell; otherwise a Python identifier, unique within the notebook."
        ),
    ]
    notebook_id: NotebookId
    version: Annotated[
        int,
        Meta(
            description="The document version at which the cell was created or last changed.",
            ge=1,
        ),
    ]


class CellDiagnostic(Struct, frozen=True):
    kind: Annotated[str, Meta(description="Identifier scoped to the source.")]
    message: str
    range: (
        Annotated[
            Range,
            Meta(
                description="Span in this cell, or null for a whole-cell finding or unknown location."
            ),
        ]
        | None
    )
    related: tuple[Related, ...]
    severity: Literal["error", "warning", "information", "hint"]
    source: Annotated[str, Meta(description="Analyzer that defines the kind.")]


class CellMessage(Struct, frozen=True):
    cell: Cell
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class CellVersion(Struct, frozen=True):
    code_fingerprint: CodeFingerprint
    etag: Etag
    version: Annotated[
        int, Meta(description="The cell's version after the edit.", ge=1)
    ]


Change: TypeAlias = Annotated[
    CreateCell | ReplaceCell | DeleteCell | SetOrder,
    Meta(description="One change to the document, tagged on `kind`."),
]


class ConsoleMedia(Struct, frozen=True, tag_field="kind", tag="media"):
    media: Annotated[
        Media,
        Meta(
            description="Something rendered into the console, such as a figure from `plt.show()` or a formatted traceback."
        ),
    ]


class CreateNotebookRequest(Struct, frozen=True, forbid_unknown_fields=True):
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
                description="Where to put the file, relative to the project root and written the way the host's operating system writes paths.",
                examples=["analysis.py"],
            ),
        ]
        | UnsetType
    ) = UNSET


class Custom(Struct, frozen=True):
    data: Annotated[
        JsonValue,
        Meta(
            description="Any JSON value, including null. The producer defines its schema and consumers of the type validate it."
        ),
    ]
    type: Annotated[
        str,
        Meta(
            description="A namespaced event type under a namespace the producer controls, such as `marimo.pair.agent-message`. Clients ignore types they do not recognize while retaining the stream cursor.",
            min_length=1,
        ),
    ]


class CustomMessage(Struct, frozen=True):
    custom: Custom
    time: Annotated[
        Timestamp,
        Meta(
            description="When the host published this event. Preserved on replay."
        ),
    ]
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET


class Decision(Struct, frozen=True):
    id: Annotated[
        str,
        Meta(
            description="Identifies the question when the client answers it."
        ),
    ]
    options: Annotated[
        tuple[DecisionOption, ...], Meta(description="The possible answers.")
    ]
    prompt: Annotated[
        str,
        Meta(
            description="The question, worded for a person.",
            examples=["Where should forecasts.py run?"],
        ),
    ]


class DecisionRequiredProblem(
    Struct,
    frozen=True,
    tag_field="type",
    tag="urn:marimo:problem:decision-required",
):
    decisions: Annotated[
        tuple[Decision, ...],
        Meta(
            description="The choices the client has to make before the host can carry out the request."
        ),
    ]
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[409] = 409
    title: str = "Decision required"


class Document(Struct, frozen=True):
    app_config: Annotated[
        dict[str, Any],
        Meta(
            description="Notebook-level settings, the keyword arguments to `marimo.App` such as `width` and `app_title`. Informational for now; no change sets it over this protocol."
        ),
    ]
    app_config_etag: Annotated[
        Etag, Meta(description="Identifies the app config alone.")
    ]
    etag: Annotated[
        Etag,
        Meta(
            description="Identifies the document as currently applied. It changes when the order, the app config, or any cell's `etag` does."
        ),
    ]
    notebook_id: Annotated[
        NotebookId, Meta(description="The notebook this document belongs to.")
    ]
    order: Annotated[
        tuple[CellId, ...],
        Meta(
            description="Cell ids in display order. A permutation of the notebook's cells, each appearing exactly once."
        ),
    ]
    order_etag: Annotated[
        Etag,
        Meta(
            description="Identifies the order alone. Editing a cell does not change it."
        ),
    ]
    saved_etag: (
        Annotated[
            Etag,
            Meta(
                description="Identifies the document as last written to the host's store, computed the same way over that state. Equal to `etag` when every accepted change has been persisted. Null when nothing has been persisted, which is the case for a scratch copy."
            ),
        ]
        | None
    )
    version: Annotated[
        int,
        Meta(
            description="Counts changes to the cells, the order, or the app config. A save does not advance it. Comparable only within one notebook while it is in the catalog.",
            ge=1,
        ),
    ]


class DocumentMessage(Struct, frozen=True):
    document: Document
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class EditRequest(Struct, frozen=True, forbid_unknown_fields=True):
    changes: Annotated[
        tuple[Change, ...],
        Meta(description="The changes, applied in order as one unit."),
    ]


class EditResponse(Struct, frozen=True):
    cells: Annotated[
        dict[str, CellVersion | None],
        Meta(
            description="The version of each cell the request created or changed, by id, and null for each cell it deleted."
        ),
    ]
    document: Document


class EmitRequest(Struct, frozen=True, forbid_unknown_fields=True):
    data: Annotated[
        JsonValue,
        Meta(
            description="Any JSON value, including null. The producer defines its schema and consumers of the type validate it."
        ),
    ]
    type: Annotated[
        str,
        Meta(
            description="A namespaced event type under a namespace the producer controls, such as `marimo.pair.agent-message`. Clients ignore types they do not recognize while retaining the stream cursor.",
            min_length=1,
        ),
    ]


class Error(Struct, frozen=True):
    kind: Annotated[
        str,
        Meta(
            description="The producer's identifier, scoped by source. Open; this protocol defines `exception` and `internal` for executions. Clients show unrecognized kinds as plain errors."
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
        tuple[Related, ...],
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
            Media,
            Meta(
                description="The traceback as rendered by the runtime, plain text or HTML by its mimetype. Null when unavailable or not shown."
            ),
        ]
        | None
    )


class ExecutionFailedOutcome(
    Struct, frozen=True, tag_field="kind", tag="failed"
):
    error: Error


class ExecutionRunning(Struct, frozen=True, tag_field="status", tag="running"):
    started_at: Annotated[
        Timestamp, Meta(description="When the code started executing.")
    ]


class ExecutionSkippedOutcome(
    Struct, frozen=True, tag_field="kind", tag="skipped"
):
    message: Annotated[
        str,
        Meta(
            description="Why the cell did not run, to show in place of its output."
        ),
    ]
    reason: Annotated[
        str,
        Meta(
            description="Why the cell did not evaluate. The string is open. This protocol\ndefines `upstream-failed`, a cell it depends on did not produce\nits value because it raised or could not resolve a reference,\n`upstream-stopped`, a cell it depends on stopped the cycle on\npurpose, and `superseded`, a later execution of the same cell\nreplaced this one before it started because the cell's source\nchanged while it waited. Clients show unrecognized reasons as\nskipped, with the message.\n"
        ),
    ]
    related: Annotated[
        tuple[Related, ...],
        Meta(
            description="The cells involved, the cause first and this cell last."
        ),
    ]


class HostMessage(Struct, frozen=True):
    host: Host
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Input(Struct, frozen=True):
    execution_id: ExecutionId
    id: Annotated[
        ItemId,
        Meta(
            description="Identifies this prompt uniquely across executions and runtime restarts."
        ),
    ]
    password: Annotated[
        bool,
        Meta(
            description="Whether clients must obscure the value as it is entered."
        ),
    ]
    prompt: Annotated[
        str, Meta(description="The prompt to display, which may be empty.")
    ]
    seq: Annotated[
        int,
        Meta(
            description="Position among the execution's console and input items, increasing in production order.",
            ge=0,
        ),
    ]
    status: InputStatus


class InputMessage(Struct, frozen=True):
    input: Input
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Notebook(Struct, frozen=True):
    id: NotebookId
    modified_at: (
        Annotated[
            Timestamp,
            Meta(
                description="A hint of when the file was last modified, for display and ordering. It can lag, since a host need not send the notebook again when only this value changes. Null when the host does not know."
            ),
        ]
        | None
    )
    name: Annotated[
        str,
        Meta(
            description="A label to show people. Derived from the filename when the host has nothing better."
        ),
    ]
    operations: Annotated[
        tuple[str, ...],
        Meta(
            description="Operations this client may call on the notebook, such as `notebook.edit` or `runtime.start`. A subset of `host.operations` selected by the client's permissions, independently of the notebook's current state. The `runtime` object shows whether a runtime is attached, and preconditions still apply when an operation is called. The host sends the notebook again when it changes."
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


class NotebookMessage(Struct, frozen=True):
    notebook: Notebook
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class OutputMessage(Struct, frozen=True):
    output: Output
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class PreconditionFailedProblem(
    Struct,
    frozen=True,
    tag_field="type",
    tag="urn:marimo:problem:precondition-failed",
):
    cell: (
        Annotated[
            Cell,
            Meta(
                description="The cell that entry named, as it now is. Null when the document does not have it, or when the entry named the order or the whole document."
            ),
        ]
        | None
    )
    document: Annotated[
        Document, Meta(description="The document as it now is.")
    ]
    index: Annotated[
        int,
        Meta(
            description="The position of the first stale entry in the request, counted in an edit's `changes` or a run's `cells`. `0` for a save with a stale `If-Match`.",
            ge=0,
        ),
    ]
    detail: str | UnsetType = UNSET
    instance: str | UnsetType = UNSET
    status: Literal[412] = 412
    title: str = "Precondition failed"


Problem: TypeAlias = Annotated[
    InvalidRequestProblem
    | UnauthorizedProblem
    | ForbiddenProblem
    | NotFoundProblem
    | MethodNotAllowedProblem
    | ConflictProblem
    | NoRuntimeProblem
    | DecisionRequiredProblem
    | PreconditionFailedProblem
    | InternalProblem
    | UnsupportedOperationProblem,
    Meta(
        description="An error. Every error response is a problem, following RFC 9457, and is served as `application/problem+json`. `type` says which. A client ignores members it does not recognize. Hosts redact tokens from errors."
    ),
]


class Process(Struct, frozen=True):
    pid: Annotated[int, Meta(description="The process id.", ge=1)]
    started_at: Annotated[
        Timestamp, Meta(description="When the process started.")
    ]


class Project(Struct, frozen=True):
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
        tuple[str, ...],
        Meta(
            description="Operations this client may call on the project, today `notebook.create`. A subset of `host.operations` selected by the client's permissions, independently of the project's current state. The host sends the project again when it changes."
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


class ProjectMessage(Struct, frozen=True):
    project: Project
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class RemovedMessage(Struct, frozen=True):
    id: Annotated[
        str, Meta(description="The id of the object that was removed.")
    ]
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


RunOrigin: TypeAlias = Annotated[
    RunCellsOrigin | RunCodeOrigin | RunRuntimeOrigin,
    Meta(
        description="What a run was given when it was created, tagged on `kind`. A\n`cells` run was given the cells in `cell_ids`. A `code` run was\ngiven the code in `code`, which its scratch execution evaluates. A\n`runtime` run was given neither. The runtime scheduled it in\nresponse to a change, such as the cells that read a UI element\nafter its value changes. Other kinds are defined by later versions\nof this protocol.\n"
    ),
]


RunOutcome: TypeAlias = Annotated[
    SucceededOutcome | RunFailedOutcome | CancelledOutcome,
    Meta(
        description="How a run ended, tagged on `kind`. `succeeded` means its work\nsettled without an execution failing or being cancelled. `failed`\nmeans an execution's code raised or the host could not finish the\ncycle. An execution skipped because of another cell does not fail\nits run. `cancelled` means the cycle was cut short by a cancel,\nan interrupt, or its runtime stopping, even if an earlier execution\nfailed. Execution outcomes retain their individual results.\n"
    ),
]


class RunRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="run.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class RunRunning(Struct, frozen=True, tag_field="status", tag="running"):
    started_at: Annotated[
        Timestamp, Meta(description="When the first execution started.")
    ]


RuntimeOutcome: TypeAlias = Annotated[
    RuntimeStoppedOutcome | RuntimeFailedOutcome,
    Meta(
        description="How a runtime ended, tagged on `kind`. A `stopped` runtime was\nended by a client or the host. A `failed` runtime could not start,\nor its kernel exited unexpectedly.\n"
    ),
]


class RuntimeRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="runtime.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class VariableEvent(Struct, frozen=True, tag_field="event", tag="variable"):
    data: VariableMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class VariableRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="variable.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class AttachmentEvent(
    Struct, frozen=True, tag_field="event", tag="attachment"
):
    data: AttachmentMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class AttachmentRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="attachment.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class CellAnalysis(Struct, frozen=True):
    defs: Annotated[
        tuple[str, ...], Meta(description="Names this cell defines.")
    ]
    diagnostics: Annotated[
        tuple[CellDiagnostic, ...],
        Meta(
            description="Diagnostics about the code. Only an `error` affects scheduling. `multiple-definitions` lists the definers in `related`, each `range` at its definition; `cycle-dependencies` lists the cycle. Both are reported on every cell involved, differing only in `range`. Every other kind belongs to the analyzer named in `source`."
        ),
    ]
    refs: Annotated[
        tuple[str, ...],
        Meta(description="Names this cell reads from other cells."),
    ]
    parents: (
        Annotated[
            tuple[CellId, ...],
            Meta(
                description="Cell IDs of the direct dependencies in this revision. An empty list means no parents. Omitted when the host does not provide the graph."
            ),
        ]
        | UnsetType
    ) = UNSET


class CellEvent(Struct, frozen=True, tag_field="event", tag="cell"):
    data: CellMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class CellRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="cell.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


ConsoleContent: TypeAlias = ConsoleText | ConsoleMedia


class ConsoleRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="console.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class CustomEvent(Struct, frozen=True, tag_field="event", tag="custom"):
    data: CustomMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class DocumentEvent(Struct, frozen=True, tag_field="event", tag="document"):
    data: DocumentMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


ExecutionOutcome: TypeAlias = Annotated[
    SucceededOutcome
    | ExecutionFailedOutcome
    | CancelledOutcome
    | ExecutionSkippedOutcome,
    Meta(
        description="How an execution ended, tagged on `kind`. A `succeeded` execution\nevaluated its code without raising, and what it showed is its\n`output` item. A `failed` execution carries the error that ended it.\nA `cancelled` execution was stopped before or while it ran.\nA `skipped` execution did not evaluate because of another cell; it\nhas no value and binds no variables. Other kinds are defined by\nlater versions of this protocol.\n"
    ),
]


class ExecutionRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="execution.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class HostEvent(Struct, frozen=True, tag_field="event", tag="host"):
    data: HostMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class HostRecord(Struct, frozen=True):
    name: Annotated[
        str,
        Meta(
            description="A label for the host to show people, such as `VS Code` or `marimo`. Two hosts can share a name; the filename is the identity.",
            examples=["marimo"],
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
            description="Where the host's API is. The scheme is `http`, and the host part is `127.0.0.1` or `[::1]`, written exactly that way.",
            examples=["http://127.0.0.1:2718/api/marimo/v1"],
        ),
    ]
    version: Annotated[
        Literal[1],
        Meta(
            description="The version of this record's format. This document describes version 1."
        ),
    ]


class InputEvent(Struct, frozen=True, tag_field="event", tag="input"):
    data: InputMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class NotebookEvent(Struct, frozen=True, tag_field="event", tag="notebook"):
    data: NotebookMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class NotebookRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="notebook.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class OutputEvent(Struct, frozen=True, tag_field="event", tag="output"):
    data: OutputMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class OutputRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="output.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class ProjectEvent(Struct, frozen=True, tag_field="event", tag="project"):
    data: ProjectMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class ProjectRemovedEvent(
    Struct, frozen=True, tag_field="event", tag="project.removed"
):
    data: RemovedMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class RunCompleted(Struct, frozen=True, tag_field="status", tag="completed"):
    completed_at: Annotated[Timestamp, Meta(description="When the run ended.")]
    outcome: Annotated[
        RunOutcome,
        Meta(
            description="An execution failure does not complete a run while other work remains. Interruption must have taken effect, not merely been requested."
        ),
    ]
    started_at: (
        Annotated[
            Timestamp,
            Meta(
                description="When the first execution started. Null if none started."
            ),
        ]
        | None
    )


RunState: TypeAlias = Annotated[
    RunQueued | RunRunning | RunCompleted,
    Meta(
        description="Where a run is in its lifecycle, tagged on `status`. A run is\n`queued` until its first execution starts and `running` until the\ncycle has settled or been terminated. It is `completed` once all\nmember executions are terminal and no more can be scheduled in this\nrun, and that state is final. A run can complete with no executions.\n"
    ),
]


class RuntimeEnded(Struct, frozen=True, tag_field="status", tag="ended"):
    ended_at: Annotated[Timestamp, Meta(description="When the runtime ended.")]
    outcome: RuntimeOutcome


RuntimeState: TypeAlias = Annotated[
    RuntimeStarting | RuntimeReady | RuntimeStopping | RuntimeEnded,
    Meta(
        description="Where a runtime is in its life, tagged on `status`. A `starting`\nruntime is bringing its kernel up. A `ready` runtime accepts work.\nA `stopping` runtime is shutting its kernel down. An `ended`\nruntime has no kernel and does not change again.\n"
    ),
]


class Analysis(Struct, frozen=True):
    cells: Annotated[
        dict[str, CellAnalysis],
        Meta(description="Every cell of that revision, by id."),
    ]
    document_etag: Annotated[
        Etag,
        Meta(
            description="The document revision this analysis describes. Equal to the document's `etag` while the analysis is current."
        ),
    ]
    notebook_id: Annotated[
        NotebookId, Meta(description="The notebook this analysis belongs to.")
    ]


class AnalysisMessage(Struct, frozen=True):
    analysis: Analysis
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Console(Struct, frozen=True):
    content: Annotated[
        ConsoleContent, Meta(description="What was written, tagged on `kind`.")
    ]
    execution_id: ExecutionId
    id: ItemId
    seq: Annotated[
        int,
        Meta(
            description="Position among the execution's console and input items, increasing in the order they were produced.",
            ge=0,
        ),
    ]


class ConsoleMessage(Struct, frozen=True):
    console: Console
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class ExecutionCompleted(
    Struct, frozen=True, tag_field="status", tag="completed"
):
    completed_at: (
        Annotated[
            Timestamp,
            Meta(
                description="When the execution ended. Null for a restored result whose store does not record it."
            ),
        ]
        | None
    )
    depends_on: Annotated[
        dict[str, Revision | None],
        Meta(
            description="The variable revisions this result is valid against, keyed by name. Null for a name no retained cell execution had bound. Stamped as the execution ends."
        ),
    ]
    outcome: ExecutionOutcome
    started_at: (
        Annotated[
            Timestamp,
            Meta(
                description="When the code started executing. Null if the execution never started or the start time of a restored result is unknown."
            ),
        ]
        | None
    )


ExecutionState: TypeAlias = Annotated[
    ExecutionQueued | ExecutionRunning | ExecutionCompleted,
    Meta(
        description="Where an execution is in its lifecycle, tagged on `status`. An\nexecution is `queued` until it starts, `running` while code\nexecutes, and `completed` once it has ended with its `outcome`.\n"
    ),
]


class Run(Struct, frozen=True):
    created_at: Annotated[
        Timestamp,
        Meta(
            description="When the host accepted the run, or when the runtime scheduled it."
        ),
    ]
    id: RunId
    notebook_id: NotebookId
    origin: RunOrigin
    runtime_id: Annotated[
        RuntimeId, Meta(description="The runtime that produced this run.")
    ]
    state: RunState


class RunMessage(Struct, frozen=True):
    run: Run
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Runtime(Struct, frozen=True):
    created_at: Annotated[
        Timestamp,
        Meta(
            description="When the host created this runtime and began starting it."
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
    notebook_id: NotebookId
    state: RuntimeState


class RuntimeMessage(Struct, frozen=True):
    runtime: Runtime
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class AnalysisEvent(Struct, frozen=True, tag_field="event", tag="analysis"):
    data: AnalysisMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class ConsoleEvent(Struct, frozen=True, tag_field="event", tag="console"):
    data: ConsoleMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class Execution(Struct, frozen=True):
    caused_by_id: (
        Annotated[
            ExecutionId,
            Meta(
                description="The execution in the same run whose code was running when this one was scheduled, such as scratch code that ran a cell, set a UI element's value, or wrote state, and the cells that reacted to it. Null for an execution a client requested and for the cells that reacted to one."
            ),
        ]
        | None
    )
    cell_id: (
        Annotated[
            CellId,
            Meta(
                description="The cell this execution belongs to. Null for a scratch execution, which evaluates the code in its run's `origin`."
            ),
        ]
        | None
    )
    code_fingerprint: Annotated[
        CodeFingerprint,
        Meta(
            description="Fingerprint of the code the execution evaluates. Fixed when the execution is published, while it is still queued."
        ),
    ]
    created_at: (
        Annotated[
            Timestamp,
            Meta(
                description="When the runtime scheduled this execution. Null for a restored result, whose timing is unknown."
            ),
        ]
        | None
    )
    id: ExecutionId
    run_id: (
        Annotated[
            RunId,
            Meta(
                description="The run that owns this execution. Every live execution belongs to exactly one run. May name a run the host has dropped. Null only for a restored result whose run is unknown."
            ),
        ]
        | None
    )
    runtime_id: (
        Annotated[
            RuntimeId,
            Meta(
                description="The runtime that produced this execution. Live while that runtime is the notebook's and has not ended. Null when the producer is unknown."
            ),
        ]
        | None
    )
    state: ExecutionState


class ExecutionMessage(Struct, frozen=True):
    execution: Execution
    request_id: (
        Annotated[
            str,
            Meta(
                description="The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress."
            ),
        ]
        | UnsetType
    ) = UNSET
    time: (
        Annotated[
            Timestamp,
            Meta(
                description="When the host published this event. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class RunEvent(Struct, frozen=True, tag_field="event", tag="run"):
    data: RunMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


class RuntimeEvent(Struct, frozen=True, tag_field="event", tag="runtime"):
    data: RuntimeMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


CatalogStreamEvent: TypeAlias = Annotated[
    HostEvent
    | ProjectEvent
    | NotebookEvent
    | RuntimeEvent
    | AttachmentEvent
    | ProjectRemovedEvent
    | NotebookRemovedEvent
    | RuntimeRemovedEvent
    | AttachmentRemovedEvent
    | ResetEvent
    | ReadyEvent,
    Meta(description="Any event the catalog stream carries."),
]


class ExecutionEvent(Struct, frozen=True, tag_field="event", tag="execution"):
    data: ExecutionMessage
    id: (
        Annotated[
            str,
            Meta(
                description="The resume cursor. Omitted on snapshot and reset events.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET


NotebookStreamEvent: TypeAlias = Annotated[
    NotebookEvent
    | DocumentEvent
    | CellEvent
    | RuntimeEvent
    | AttachmentEvent
    | RunEvent
    | ExecutionEvent
    | OutputEvent
    | ConsoleEvent
    | InputEvent
    | VariableEvent
    | AnalysisEvent
    | CustomEvent
    | NotebookRemovedEvent
    | CellRemovedEvent
    | RuntimeRemovedEvent
    | AttachmentRemovedEvent
    | RunRemovedEvent
    | ExecutionRemovedEvent
    | OutputRemovedEvent
    | ConsoleRemovedEvent
    | VariableRemovedEvent
    | ResetEvent
    | ReadyEvent,
    Meta(description="Any event a notebook stream carries."),
]


Event: TypeAlias = Annotated[
    HostEvent
    | ProjectEvent
    | NotebookEvent
    | DocumentEvent
    | CellEvent
    | RuntimeEvent
    | AttachmentEvent
    | RunEvent
    | ExecutionEvent
    | OutputEvent
    | ConsoleEvent
    | InputEvent
    | VariableEvent
    | AnalysisEvent
    | CustomEvent
    | ProjectRemovedEvent
    | NotebookRemovedEvent
    | CellRemovedEvent
    | RuntimeRemovedEvent
    | AttachmentRemovedEvent
    | RunRemovedEvent
    | ExecutionRemovedEvent
    | OutputRemovedEvent
    | ConsoleRemovedEvent
    | VariableRemovedEvent
    | ResetEvent
    | ReadyEvent,
    Meta(
        description="A record, removal, or control message from a host stream. The data is decoded JSON. Snapshot records and reset events omit the cursor, and ready and live events carry it. Unknown event names belong to later versions or host extensions."
    ),
]
