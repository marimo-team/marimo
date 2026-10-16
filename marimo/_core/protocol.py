# Copyright 2026 Marimo. All rights reserved.
# AUTO-GENERATED FILE — DO NOT EDIT.
# Generated from protocols/host/openapi.yaml.
# Regenerate with `make host-protocol-codegen`.
# ruff: noqa: TC003 - msgspec resolves annotations at runtime
# ruff: noqa: RUF036 - the generator orders unions; the wire shape is the same

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal, NewType, TypeAlias

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


class Binding(Struct, frozen=True):
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
        bool, Meta(description="Whether clients hide the code by default.")
    ]


class CellConfigInput(Struct, frozen=True):
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


class CellInput(Struct, frozen=True):
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


class Custom(Struct, frozen=True):
    data: Annotated[
        Any,
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
        datetime,
        Meta(
            description="When the host emitted this event. Preserved on replay."
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


class DecisionOption(Struct, frozen=True):
    id: Annotated[str, Meta(description="Identifies this answer.")]
    label: Annotated[str, Meta(description="Text to show a person.")]


class DeleteCell(Struct, frozen=True, tag_field="kind", tag="delete_cell"):
    base_etag: Annotated[
        str, Meta(description="The cell's etag as last read, or `*`.")
    ]
    id: Annotated[CellId, Meta(description="The cell to remove.")]


class DisplayData(Struct, frozen=True):
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


Etag: TypeAlias = Annotated[
    str,
    Meta(
        description="An identifier derived from content, so that every host, kernel,\nand store computes the same value for the same state. It is the\nfirst 16 hexadecimal characters, in lower case, of SHA-256 over\nthe UTF-8 encoding of a canonical text. Each etag says what its\ntext is; a text made of several values is those values joined by\nnewlines. Clients do not compute etags. They read them from the\nstream and from responses, and send them back as preconditions.\n"
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


class Host(Struct, frozen=True):
    operations: Annotated[
        tuple[str, ...],
        Meta(
            description="The operations this host implements, such as `runtime.start`. Whether a client may call one on a given project or notebook is that object's `operations`. Clients accept names they do not recognize."
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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class InterruptedOutcome(
    Struct, frozen=True, tag_field="kind", tag="interrupted"
):
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
    Literal["queued", "running", "completed"],
    Meta(
        description="Where a run or execution is in its lifecycle. An execution is\n`queued` until it starts, `running` while code executes, and\n`completed` once it has ended. How it ended is its `outcome`.\n"
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
        "document",
        "analysis",
        "cell",
        "runtime",
        "attachment",
        "run",
        "execution",
        "console",
        "display",
        "custom",
    ],
    Meta(
        description="The kinds a stream carries, and the values `types` accepts. The\ncatalog stream carries host, project, notebook, runtime, and\nattachment. A notebook's stream carries notebook, document,\nanalysis, cell, runtime, attachment, run, execution, console,\ndisplay, and custom. Custom events describe occurrences rather\nthan object state.\n"
    ),
]


class OpenNotebookResponse(Struct, frozen=True):
    url: Annotated[
        str,
        Meta(
            description="The URL the host used to show the notebook. It never contains the host's token."
        ),
    ]


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


class Process(Struct, frozen=True):
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


class PutCell(Struct, frozen=True, tag_field="kind", tag="put_cell"):
    base_etag: (
        Annotated[
            str,
            Meta(
                description="The cell's etag as last read, `*` to skip the check, or null to create the cell. Null when the cell exists, or an etag when it does not, is a `conflict`."
            ),
        ]
        | None
    )
    cell: CellInput
    after: (
        Annotated[
            CellId,
            Meta(
                description="The cell a created cell goes after. Ignored for an existing cell."
            ),
        ]
        | UnsetType
    ) = UNSET
    before: (
        Annotated[
            CellId,
            Meta(
                description="The cell a created cell goes before. Ignored for an existing cell. With neither `after` nor `before`, a created cell goes at the end."
            ),
        ]
        | UnsetType
    ) = UNSET


class Range(Struct, frozen=True):
    end: Annotated[
        Position,
        Meta(
            description="Exclusive end. Equal to start when only a point is known."
        ),
    ]
    start: Position


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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class RequestedCell(Struct, frozen=True):
    id: CellId
    code_hash: (
        Annotated[
            Etag,
            Meta(
                description="The cell's `code_hash` as last read. A cell whose code differs is a `conflict`. Absent, the cell runs as it is."
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
                description="Identifies a run independently of the request's `Idempotency-Key`. Events carry the key in `request_id`.",
                min_length=1,
            ),
        ],
    )


RunOutcome: TypeAlias = Annotated[
    Literal["succeeded", "failed", "interrupted"],
    Meta(
        description="How a run ended. `succeeded` means its work settled without an\nexecution error or interruption. `failed` means an execution\nfailed or the host could not finish the cycle. `interrupted`\nmeans the cycle was cut short by interruption, even if an earlier\nexecution failed. Execution outcomes retain their individual results.\n"
    ),
]


class RunRequest(Struct, frozen=True):
    cells: (
        Annotated[
            tuple[RequestedCell, ...],
            Meta(
                description="Cells of the document to run, in no particular order. The runtime's execution configuration determines whether dependent cells run too.",
                min_length=1,
            ),
        ]
        | UnsetType
    ) = UNSET
    code: (
        Annotated[str, Meta(description="Python code to run as scratch code.")]
        | UnsetType
    ) = UNSET


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


class SaveRequest(Struct, frozen=True):
    decisions: (
        Annotated[
            dict[str, str],
            Meta(
                description="Answers to the questions in a `decision-required` problem, as for `runtime.start`."
            ),
        ]
        | UnsetType
    ) = UNSET


class SetAppConfig(
    Struct, frozen=True, tag_field="kind", tag="set_app_config"
):
    app_config: Annotated[
        dict[str, Any], Meta(description="The new app config, whole.")
    ]
    base_etag: Annotated[
        str,
        Meta(
            description="The document's `app_config_etag` as last read, or `*`."
        ),
    ]


class SetOrder(Struct, frozen=True, tag_field="kind", tag="set_order"):
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


class StartRuntimeRequest(Struct, frozen=True):
    decisions: (
        Annotated[
            dict[str, str],
            Meta(
                description="Answers to the questions in a `decision-required` problem.\nEach key is a decision's `id` and each value is the `id` of\nthe chosen option. A client that already knows its choices can\nsend them the first time.\n"
            ),
        ]
        | UnsetType
    ) = UNSET


class UpdateNotebookRequest(Struct, frozen=True):
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


class ValueOutcome(Struct, frozen=True, tag_field="kind", tag="value"):
    display: (
        Annotated[
            DisplayData,
            Meta(
                description="The value as last rendered. Replaced as it grows. Null when the code produced no value."
            ),
        ]
        | None
    )


class Attachment(Struct, frozen=True):
    id: AttachmentId
    kind: Annotated[
        str,
        Meta(
            description="What kind of thing is attached, supplied by `Marimo-Attachment-Kind`, such as `browser`, `editor`, or `agent`. Defaults to `client` when the header is omitted. Clients accept kinds they do not recognize.",
            pattern="^[a-z0-9-]+$",
        ),
    ]
    name: (
        Annotated[
            str,
            Meta(
                description="A label to show people, supplied by `Marimo-Attachment-Name`, such as the browser or editor's name. Null when the header is omitted or empty.",
                max_length=256,
            ),
        ]
        | None
    )
    notebook_id: NotebookId
    since: Annotated[datetime, Meta(description="When it attached.")]
    identity: (
        Annotated[
            str,
            Meta(
                description="The opaque client identity supplied by `Marimo-Attachment-Identity`.\nOmitted when none was supplied. Consumers can group attachments\nwith the same identity within a host. It does not identify an\nindividual connection or change its lifetime.\n",
                max_length=128,
                min_length=1,
                pattern="^[!-~]+$",
            ),
        ]
        | UnsetType
    ) = UNSET


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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Cell(Struct, frozen=True):
    code: Annotated[
        str,
        Meta(
            description="The cell's source code, with newline line endings. A host normalizes other line endings when it loads a file."
        ),
    ]
    code_hash: Annotated[
        Etag,
        Meta(
            description="Identifies the code alone. Its text is `code`. Unchanged by renaming the cell or editing its config. Compare with an execution's `code_hash` to tell whether a result came from the current code."
        ),
    ]
    config: CellConfig
    etag: Annotated[
        Etag,
        Meta(
            description="Identifies code, name, and config together, and is the precondition for editing the cell. Its text is `code_hash`, `name`, and the config values `column`, `disabled`, `hide_code`, and `expand_output` in that order, each written as a JSON scalar such as `null`, `0`, or `true`."
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


class CellEtags(Struct, frozen=True):
    code_hash: Etag
    etag: Etag


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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


Change: TypeAlias = Annotated[
    PutCell | DeleteCell | SetOrder | SetAppConfig,
    Meta(description="One change to the document, tagged on `kind`."),
]


class Console(Struct, frozen=True):
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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class CreateNotebookRequest(Struct, frozen=True):
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
        str, Meta(description="The question, worded for a person.")
    ]


class Display(Struct, frozen=True):
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


class DisplayMessage(Struct, frozen=True):
    display: Display
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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Document(Struct, frozen=True):
    app_config: Annotated[
        dict[str, Any],
        Meta(
            description="Notebook-level settings, the keyword arguments to `marimo.App` such as `width` and `title`."
        ),
    ]
    app_config_etag: Annotated[
        Etag,
        Meta(
            description="Identifies the app config alone. Its text is the app config as canonical JSON, with keys sorted by code point, no whitespace, and strings carrying only the escapes JSON requires."
        ),
    ]
    etag: Annotated[
        Etag,
        Meta(
            description="Identifies the document as currently applied. Its text is `order_etag`, `app_config_etag`, and every cell's `etag` in order, so it changes when any of them does."
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
            description="Identifies the order alone. Its text is the cell IDs in order as a JSON array, with no whitespace and strings carrying only the escapes JSON requires. Editing a cell does not change it."
        ),
    ]
    policy: Annotated[
        Literal["autorun", "lazy"],
        Meta(
            description="When dependents of an evaluated cell run. `autorun` runs them on every change; `lazy` marks them stale and runs them when asked. Set by the host."
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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class EditConflict(Struct, frozen=True):
    cell: (
        Annotated[
            Cell,
            Meta(
                description="The cell the change named, as it now is. Null when the document does not have it, or when the change named the order or the app config."
            ),
        ]
        | None
    )
    change: Annotated[
        int,
        Meta(
            description="The index of the stale change in the request's `changes`, or of the stale cell in a run's `cells`. `0` for a save with a stale `If-Match`.",
            ge=0,
        ),
    ]
    document: Document


class EditRequest(Struct, frozen=True):
    changes: Annotated[
        tuple[Change, ...],
        Meta(description="The changes, applied in order as one unit."),
    ]


class EditResponse(Struct, frozen=True):
    cells: Annotated[
        dict[str, CellEtags | None],
        Meta(
            description="The etags of each cell the request created or changed, by id, and null for each cell it deleted."
        ),
    ]
    document: Document


class Error(Struct, frozen=True):
    kind: Annotated[
        str,
        Meta(
            description="The producer's identifier, scoped by source. Open; this protocol defines `exception`, `interrupted`, and `internal` for executions, and reserves `multiple-definitions` and `cycle-dependencies` for analysis, because every host schedules them the same way. Clients show unrecognized kinds as plain errors."
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
            DisplayData,
            Meta(
                description="The traceback as rendered by the runtime, plain text or HTML by its mimetype. Null when unavailable or not shown."
            ),
        ]
        | None
    )


class ErrorOutcome(Struct, frozen=True, tag_field="kind", tag="error"):
    error: Error


class HostRecord(Struct, frozen=True):
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


class Notebook(Struct, frozen=True):
    id: NotebookId
    name: Annotated[
        str,
        Meta(
            description="A label to show people. Derived from the filename when the host has nothing better."
        ),
    ]
    operations: Annotated[
        tuple[str, ...],
        Meta(
            description="Operations this client may call on the notebook, such as `notebook.edit` or `runtime.start`. A subset of `host.operations`, narrowed by permission and never by state; whether a runtime is attached shows in the `runtime` object, and preconditions still apply when an operation is called. The host sends the notebook again when it changes."
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
        description="How an execution ended, tagged on `kind`. A `value` carries the\nexecution's value as last rendered; while the execution is\nrunning it is the value so far, and it is final once the\nexecution is `completed`. An `error` carries the error that ended it.\nAn `interrupted` execution was cancelled before or during execution. Other\nkinds are defined by later versions of this protocol.\n"
    ),
]


class Problem(Struct, frozen=True):
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
            description="What kind of problem this is, as a URI. The kinds this\nprotocol defines all start with `tag:marimo.io,2026:host/` and\nend with one of `invalid-request` (400), `unauthorized` (401),\n`forbidden` (403), `not-found` (404), `method-not-allowed`\n(405), `not-acceptable` (406), `conflict` (409), `no-runtime`\n(409), `decision-required` (409), `internal` (500), or\n`unsupported-operation` (501). A client that sees a kind it\ndoes not recognize falls back to `status`.\n"
        ),
    ]
    decisions: (
        Annotated[
            tuple[Decision, ...],
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
    edit: (
        Annotated[
            EditConflict,
            Meta(
                description="Which change was stale and what the host holds instead. Only present for a `conflict` answering an edit, a save, or a run of cells."
            ),
        ]
        | UnsetType
    ) = UNSET


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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Run(Struct, frozen=True):
    caused_by: (
        Annotated[
            ExecutionId,
            Meta(
                description="The execution that caused this runtime-scheduled run. This records provenance, not membership in that execution's run, and does not extend the earlier run's lifetime. Null for a client request or when the runtime does not know the source."
            ),
        ]
        | None
    )
    completed_at: (
        Annotated[
            datetime,
            Meta(
                description="When the run ended. Null until the run is `completed`."
            ),
        ]
        | None
    )
    id: RunId
    notebook_id: NotebookId
    outcome: (
        Annotated[
            RunOutcome,
            Meta(
                description="Null until completed, then final. Published with the terminal status and completed_at. An execution failure does not complete a run while other work remains. Interruption must have taken effect, not merely been requested."
            ),
        ]
        | None
    )
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
            description="Queued until the first execution starts, running until the cycle has settled or been terminated, and completed once all member executions are terminal and no more can be scheduled in this run. A run can complete with no executions."
        ),
    ]


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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class Runtime(Struct, frozen=True):
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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


class CellAnalysis(Struct, frozen=True):
    defs: Annotated[
        tuple[str, ...], Meta(description="Names this cell defines.")
    ]
    errors: Annotated[
        tuple[Error, ...],
        Meta(
            description="Diagnostics about the code. Only an `error` affects scheduling. `multiple-definitions` lists the definers in `related`, each `range` at its definition; `cycle-dependencies` lists the cycle. Both are reported on every cell involved, differing only in `range`. Every other kind belongs to the analyzer named in `source`."
        ),
    ]
    refs: Annotated[
        tuple[str, ...],
        Meta(description="Names this cell reads from other cells."),
    ]


class Execution(Struct, frozen=True):
    bindings: Annotated[
        tuple[Binding, ...],
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
            CellId,
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
        Etag,
        Meta(
            description="The `code_hash` of the code that was evaluated, computed as a cell's is."
        ),
    ]
    completed_at: (
        Annotated[
            datetime,
            Meta(
                description="When the execution ended. Null until it is completed."
            ),
        ]
        | None
    )
    id: ExecutionId
    outcome: (
        Annotated[
            Outcome,
            Meta(
                description="How the execution ended. Null while queued; while running, a value carries the display so far; final once completed."
            ),
        ]
        | None
    )
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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET


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
            datetime,
            Meta(
                description="When the host made this change. Present on live and replayed events; omitted on snapshots."
            ),
        ]
        | UnsetType
    ) = UNSET
