/* Copyright 2026 Marimo. All rights reserved. */
// Generated from packages/host-protocol. Do not edit.
// Regenerate with: pnpm --dir packages/client codegen

import * as zod from "zod";

export const Timestamp = zod.iso
  .datetime({ offset: true })
  .describe("A date and time with its offset from UTC, as RFC 3339 writes it.");

export type Timestamp = zod.input<typeof Timestamp>;
export type TimestampOutput = zod.output<typeof Timestamp>;

export const Host = zod
  .object({
    operations: zod
      .array(zod.string())
      .describe(
        "The operations this host implements, such as `runtime.start`. Whether a client may call one on a given project or notebook is that object's `operations`. Clients accept names they do not recognize.",
      ),
  })
  .describe(
    "What the host can do. There is exactly one host object, and it is\nthe first object in a snapshot when the filter includes `host`.\nA resumed stream only sends it if its operations changed since\nthe cursor. The host sends it again if its operations change.\n",
  );

export type Host = zod.input<typeof Host>;
export type HostOutput = zod.output<typeof Host>;

export const HostMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    host: Host,
  })
  .describe("The data of the `host` event. The host as it now is.");

export type HostMessage = zod.input<typeof HostMessage>;
export type HostMessageOutput = zod.output<typeof HostMessage>;

export const HostEvent = zod
  .object({
    event: zod.enum(["host"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: HostMessage,
  })
  .describe("The `host` event, carried by the catalog stream.");

export type HostEvent = zod.input<typeof HostEvent>;
export type HostEventOutput = zod.output<typeof HostEvent>;

export const ProjectId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a project. Unique within the host and unchanged while the project exists.",
  );

export type ProjectId = zod.input<typeof ProjectId>;
export type ProjectIdOutput = zod.output<typeof ProjectId>;

export const ProjectStatus = zod
  .enum(["indexing", "indexed", "partial"])
  .describe(
    "How far a host has gotten finding the notebooks in a project.\nWhile it is `indexing`, more notebooks are coming. Once it is\n`indexed`, the host believes it has found every notebook under the\nroot. A `partial` project is one the host stopped scanning on\npurpose, or one with something it could not read.\n",
  );

export type ProjectStatus = zod.input<typeof ProjectStatus>;
export type ProjectStatusOutput = zod.output<typeof ProjectStatus>;

export const Project = zod
  .object({
    id: ProjectId,
    name: zod
      .string()
      .describe(
        "A label to show people, usually the name of the root directory.",
      ),
    root: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The absolute path of the project's directory, written the way the host's operating system writes paths. Null when the project has no directory.",
      ),
    status: ProjectStatus,
    message: zod
      .union([zod.string(), zod.null()])
      .describe(
        "Why the host stopped scanning. Null unless `status` is `partial`.",
      ),
    operations: zod
      .array(zod.string())
      .describe(
        "Operations this client may call on the project, today `notebook.create`. A subset of `host.operations` selected by the client's permissions, independently of the project's current state. The host sends the project again when it changes.",
      ),
  })
  .describe(
    "A project is a group of notebooks that the host presents together, usually a directory.",
  );

export type Project = zod.input<typeof Project>;
export type ProjectOutput = zod.output<typeof Project>;

export const ProjectMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    project: Project,
  })
  .describe("The data of the `project` event. The project as it now is.");

export type ProjectMessage = zod.input<typeof ProjectMessage>;
export type ProjectMessageOutput = zod.output<typeof ProjectMessage>;

export const ProjectEvent = zod
  .object({
    event: zod.enum(["project"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: ProjectMessage,
  })
  .describe("The `project` event, carried by the catalog stream.");

export type ProjectEvent = zod.input<typeof ProjectEvent>;
export type ProjectEventOutput = zod.output<typeof ProjectEvent>;

export const NotebookId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a notebook. Unique within the host and unchanged while the notebook exists.",
  );

export type NotebookId = zod.input<typeof NotebookId>;
export type NotebookIdOutput = zod.output<typeof NotebookId>;

export const Notebook = zod
  .object({
    id: NotebookId,
    project_id: ProjectId,
    path: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The file's path relative to the project root, written the way the host's operating system writes paths. Null when the notebook has no file, such as one not yet saved, or one deleted while a runtime still refers to it.",
      ),
    name: zod
      .string()
      .describe(
        "A label to show people. Derived from the filename when the host has nothing better.",
      ),
    operations: zod
      .array(zod.string())
      .describe(
        "Operations this client may call on the notebook, such as `notebook.edit` or `runtime.start`. A subset of `host.operations` selected by the client's permissions, independently of the notebook's current state. The `runtime` object shows whether a runtime is attached, and preconditions still apply when an operation is called. The host sends the notebook again when it changes.",
      ),
    updated_at: zod
      .union([Timestamp, zod.null()])
      .describe(
        "When the file was last modified, as of the host's last look at it. Null when the host does not know.",
      ),
  })
  .describe(
    "A notebook is a document and its results as the host knows them,\nusually backed by a file. Its kernel, when it has one, is a\nseparate object, the runtime. A host sends at most one `notebook`\nevent per second for the same notebook, since `updated_at`\nchanges on every save.\n",
  );

export type Notebook = zod.input<typeof Notebook>;
export type NotebookOutput = zod.output<typeof Notebook>;

export const NotebookMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    notebook: Notebook,
  })
  .describe("The data of the `notebook` event. The notebook as it now is.");

export type NotebookMessage = zod.input<typeof NotebookMessage>;
export type NotebookMessageOutput = zod.output<typeof NotebookMessage>;

export const NotebookEvent = zod
  .object({
    event: zod.enum(["notebook"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: NotebookMessage,
  })
  .describe(
    "The `notebook` event, carried by the catalog and notebook streams.",
  );

export type NotebookEvent = zod.input<typeof NotebookEvent>;
export type NotebookEventOutput = zod.output<typeof NotebookEvent>;

export const CellId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a cell within its notebook. Stable while the host serves the notebook; whether it survives a reload of the store depends on the format. `setup` is the setup cell.",
  );

export type CellId = zod.input<typeof CellId>;
export type CellIdOutput = zod.output<typeof CellId>;

export const Etag = zod
  .string()
  .describe(
    "An identifier derived from content, so that every host, kernel,\nand store computes the same value for the same state. It is the\nfirst 16 hexadecimal characters, in lower case, of SHA-256 over\nthe UTF-8 encoding of a canonical text. Each etag says what its\ntext is; a text made of several values is those values joined by\nnewlines. Clients do not compute etags. They read them from the\nstream and from responses, and send them back as preconditions.\n",
  );

export type Etag = zod.input<typeof Etag>;
export type EtagOutput = zod.output<typeof Etag>;

export const Document = zod
  .object({
    notebook_id: NotebookId.describe("The notebook this document belongs to."),
    order: zod
      .array(CellId)
      .describe(
        "Cell ids in display order. A permutation of the notebook's cells, each appearing exactly once.",
      ),
    app_config: zod
      .looseObject({})
      .describe(
        "Notebook-level settings, the keyword arguments to `marimo.App` such as `width` and `app_title`. Informational for now; no change sets it over this protocol.",
      ),
    etag: Etag.describe(
      "Identifies the document as currently applied. Its text is `order_etag`, `app_config_etag`, and every cell's `etag` in order, so it changes when any of them does.",
    ),
    saved_etag: zod
      .union([Etag, zod.null()])
      .describe(
        "Identifies the document as last written to the host's store, computed the same way over that state. Equal to `etag` when every accepted change has been persisted. Null when nothing has been persisted, which is the case for a scratch copy.",
      ),
    order_etag: Etag.describe(
      "Identifies the order alone. Its text is the cell IDs in order as a JSON array, with no whitespace and strings carrying only the escapes JSON requires. Editing a cell does not change it.",
    ),
    app_config_etag: Etag.describe(
      "Identifies the app config alone. Its text is the app config as canonical JSON, with keys sorted by code point, no whitespace, and strings carrying only the escapes JSON requires.",
    ),
    version: zod
      .int()
      .min(1)
      .describe(
        "Counts changes to the cells, the order, or the app config. A save does not advance it. Comparable only within one notebook while it is in the catalog.",
      ),
  })
  .describe(
    "The document as a whole, without its cells, which are their own\nobjects: the cell order and app config. One per notebook,\nand removed with it. The order and the app\nconfig carry their own etags, so an edit to one does not conflict\nwith an edit to the other, or with edits to cells.\n",
  );

export type Document = zod.input<typeof Document>;
export type DocumentOutput = zod.output<typeof Document>;

export const DocumentMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    document: Document,
  })
  .describe("The data of the `document` event. The document as it now is.");

export type DocumentMessage = zod.input<typeof DocumentMessage>;
export type DocumentMessageOutput = zod.output<typeof DocumentMessage>;

export const DocumentEvent = zod
  .object({
    event: zod.enum(["document"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: DocumentMessage,
  })
  .describe("The `document` event, carried by the notebook stream.");

export type DocumentEvent = zod.input<typeof DocumentEvent>;
export type DocumentEventOutput = zod.output<typeof DocumentEvent>;

export const CellConfig = zod
  .object({
    column: zod
      .union([zod.int(), zod.null()])
      .describe(
        "The column the cell sits in, for multi-column layouts. Null in a single column.",
      ),
    disabled: zod.boolean().describe("Whether the cell is kept from running."),
    hide_code: zod
      .boolean()
      .describe(
        "Whether clients hide the code by default. This is a presentation preference; source availability is represented by `Cell.code`.",
      ),
    expand_output: zod
      .boolean()
      .describe(
        "Whether clients show the full output rather than a scrolled box.",
      ),
  })
  .describe(
    "How a cell is laid out and whether it runs. Every field is always present, so a cell's etag is well defined.",
  );

export type CellConfig = zod.input<typeof CellConfig>;
export type CellConfigOutput = zod.output<typeof CellConfig>;

export const CodeFingerprint = zod
  .string()
  .min(1)
  .describe(
    "Opaque code identity assigned by the host. Clients compare cell and execution fingerprints for freshness. Incompatible schemes MUST produce distinct fingerprints.",
  );

export type CodeFingerprint = zod.input<typeof CodeFingerprint>;
export type CodeFingerprintOutput = zod.output<typeof CodeFingerprint>;

export const Cell = zod
  .object({
    id: CellId,
    notebook_id: NotebookId,
    code: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The cell's source code, with newline line endings, or null when the host does not expose source to this client. An empty string is an empty cell. A host normalizes other line endings when it loads a file. Source availability does not grant editing permission; see the notebook's operations.",
      ),
    name: zod
      .string()
      .describe(
        "The cell's name. `_` for an anonymous cell; otherwise a Python identifier, unique within the notebook.",
      ),
    config: CellConfig,
    etag: Etag.describe(
      "Precondition for edits and cell runs. Covers exact source, name, and config. Its text is the newline-joined sequence of the first 16 hex characters of SHA-256 of the UTF-8 source, `name`, and the config values `column`, `disabled`, `hide_code`, and `expand_output`, in that order. Config values are JSON scalars.",
    ),
    code_fingerprint: CodeFingerprint.describe(
      "Fingerprint of the actual source, including when `code` is null. Formatting-only edits may preserve it. Independent of cell name, config, and source visibility.",
    ),
    version: zod
      .int()
      .min(1)
      .describe(
        "The document version at which the cell was created or last changed.",
      ),
  })
  .describe(
    "A unit of code and configuration in the document. A cell event\nfires when its code, name, or config changes. Markdown and SQL\ncells are code that calls `mo.md` or `mo.sql`; a client chooses\nthe editor to show.\n",
  );

export type Cell = zod.input<typeof Cell>;
export type CellOutput = zod.output<typeof Cell>;

export const CellMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    cell: Cell,
  })
  .describe("The data of the `cell` event. The cell as it now is.");

export type CellMessage = zod.input<typeof CellMessage>;
export type CellMessageOutput = zod.output<typeof CellMessage>;

export const CellEvent = zod
  .object({
    event: zod.enum(["cell"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: CellMessage,
  })
  .describe("The `cell` event, carried by the notebook stream.");

export type CellEvent = zod.input<typeof CellEvent>;
export type CellEventOutput = zod.output<typeof CellEvent>;

export const RuntimeId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a runtime. Unique within the host; every start and restart creates a new id.",
  );

export type RuntimeId = zod.input<typeof RuntimeId>;
export type RuntimeIdOutput = zod.output<typeof RuntimeId>;

export const RuntimeStatus = zod
  .enum(["starting", "running", "terminating", "failed"])
  .describe(
    "Where a runtime is in its life. A `starting` runtime is bringing\nits kernel up. A `running` runtime accepts work. A `terminating`\nruntime is shutting its kernel down. A `failed` runtime could not\nstart, or its kernel exited unexpectedly. A runtime that has\nended is removed rather than given a status.\n",
  );

export type RuntimeStatus = zod.input<typeof RuntimeStatus>;
export type RuntimeStatusOutput = zod.output<typeof RuntimeStatus>;

export const Runtime = zod
  .object({
    id: RuntimeId,
    notebook_id: NotebookId,
    status: RuntimeStatus,
    message: zod
      .union([zod.string(), zod.null()])
      .describe(
        "A note about the current status, such as progress while `starting` or the reason when `failed`. Null otherwise.",
      ),
    marimo_version: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The version of marimo running the kernel. Null until the host knows it.",
      ),
    started_at: Timestamp.describe("When this runtime started."),
  })
  .describe(
    "A runtime is a kernel attached to one notebook, and a notebook has\nat most one. It ends when a client or the host stops it or its\nprocess exits, and the host then sends `runtime.removed`. Every start and restart creates\na new runtime with a new id. Results carry their producer's runtime\nid so clients can tell which are live.\n",
  );

export type Runtime = zod.input<typeof Runtime>;
export type RuntimeOutput = zod.output<typeof Runtime>;

export const RuntimeMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    runtime: Runtime,
  })
  .describe("The data of the `runtime` event. The runtime as it now is.");

export type RuntimeMessage = zod.input<typeof RuntimeMessage>;
export type RuntimeMessageOutput = zod.output<typeof RuntimeMessage>;

export const RuntimeEvent = zod
  .object({
    event: zod.enum(["runtime"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RuntimeMessage,
  })
  .describe(
    "The `runtime` event, carried by the catalog and notebook streams.",
  );

export type RuntimeEvent = zod.input<typeof RuntimeEvent>;
export type RuntimeEventOutput = zod.output<typeof RuntimeEvent>;

export const AttachmentId = zod
  .string()
  .min(1)
  .describe("Identifies an attachment. Unique within the host.");

export type AttachmentId = zod.input<typeof AttachmentId>;
export type AttachmentIdOutput = zod.output<typeof AttachmentId>;

export const attachmentIdentityOneMax = 128;

export const attachmentIdentityOneRegExp = new RegExp("^[!-~]+$");
export const attachmentKindRegExp = new RegExp("^[a-z0-9-]+$");
export const attachmentNameOneMax = 256;

export const Attachment = zod
  .object({
    id: AttachmentId,
    notebook_id: NotebookId,
    identity: zod
      .union([
        zod
          .string()
          .min(1)
          .max(attachmentIdentityOneMax)
          .regex(attachmentIdentityOneRegExp),
        zod.null(),
      ])
      .describe(
        "The opaque client identity supplied by `Marimo-Attachment-Identity`.\nNull when none was supplied. Consumers can group attachments\nwith the same identity within a host. It does not identify an\nindividual connection or change its lifetime.\n",
      ),
    kind: zod
      .string()
      .regex(attachmentKindRegExp)
      .describe(
        "What kind of thing is attached, supplied by `Marimo-Attachment-Kind`, such as `browser`, `editor`, or `agent`. Defaults to `client` when the header is omitted. Clients accept kinds they do not recognize.",
      ),
    name: zod
      .union([zod.string().max(attachmentNameOneMax), zod.null()])
      .describe(
        "A label to show people, supplied by `Marimo-Attachment-Name`, such as the browser or editor's name. Null when the header is omitted or empty.",
      ),
    since: Timestamp.describe("When it attached."),
  })
  .describe(
    "An attachment is a consumer connected to a notebook, such as a\nbrowser tab, an editor, or an agent. Opening the notebook's stream\ncreates one. It is removed when that connection closes, and not\nwhen the notebook's runtime stops or restarts. Each stream has its\nown attachment, even when several share a client identity.\n",
  );

export type Attachment = zod.input<typeof Attachment>;
export type AttachmentOutput = zod.output<typeof Attachment>;

export const AttachmentMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    attachment: Attachment,
  })
  .describe("The data of the `attachment` event. The attachment as it now is.");

export type AttachmentMessage = zod.input<typeof AttachmentMessage>;
export type AttachmentMessageOutput = zod.output<typeof AttachmentMessage>;

export const AttachmentEvent = zod
  .object({
    event: zod.enum(["attachment"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: AttachmentMessage,
  })
  .describe(
    "The `attachment` event, carried by the catalog and notebook streams.",
  );

export type AttachmentEvent = zod.input<typeof AttachmentEvent>;
export type AttachmentEventOutput = zod.output<typeof AttachmentEvent>;

export const RunId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a run independently of the request's `Idempotency-Key`. Events carry the key in `request_id`.",
  );

export type RunId = zod.input<typeof RunId>;
export type RunIdOutput = zod.output<typeof RunId>;

export const Lifecycle = zod
  .enum(["queued", "running", "completed"])
  .describe(
    "Where a run or execution is in its lifecycle. An execution is\n`queued` until it starts, `running` while code executes, and\n`completed` once it has ended. A run is `queued` until its first\nexecution starts, `running` until its cycle has settled or been cut\nshort, and `completed` once no more work can join it. How either\nended is its `outcome`.\n",
  );

export type Lifecycle = zod.input<typeof Lifecycle>;
export type LifecycleOutput = zod.output<typeof Lifecycle>;

export const RunOutcome = zod
  .enum(["succeeded", "failed", "interrupted"])
  .describe(
    "How a run ended. `succeeded` means its work settled without an\nexecution error or interruption. `failed` means an execution's\ncode raised or the host could not finish the cycle. An execution\nskipped because of another cell does not fail its run. `interrupted`\nmeans the cycle was cut short by interruption, even if an earlier\nexecution failed. Execution outcomes retain their individual results.\n",
  );

export type RunOutcome = zod.input<typeof RunOutcome>;
export type RunOutcomeOutput = zod.output<typeof RunOutcome>;

export const Run = zod
  .object({
    id: RunId,
    notebook_id: NotebookId,
    runtime_id: RuntimeId.describe("The runtime that produced this run."),
    cells: zod
      .array(CellId)
      .describe(
        "The cells the run was requested for. Fixed when the run is accepted, so a client can tell which cells a queued run will reach before the runtime has planned their executions. Each one's execution in this run reports the fingerprint of the source accepted for it. Empty for scratch code and for a run the runtime scheduled itself.",
      ),
    status: Lifecycle.describe(
      "Queued until the first execution starts, running until the cycle has settled or been terminated, and completed once all member executions are terminal and no more can be scheduled in this run. A run can complete with no executions.",
    ),
    outcome: zod
      .union([RunOutcome, zod.null()])
      .describe(
        "Null until completed, then final. Published with the terminal status and completed_at. An execution failure does not complete a run while other work remains. Interruption must have taken effect, not merely been requested.",
      ),
    started_at: zod
      .union([Timestamp, zod.null()])
      .describe("When the first execution started. Null if none has started."),
    completed_at: zod
      .union([Timestamp, zod.null()])
      .describe("When the run ended. Null until the run is `completed`."),
  })
  .describe(
    "One bounded cycle of notebook work initiated by an action. It\nincludes synchronous callbacks and reactive work owned and awaited\nby the runtime's scheduler. Context inherited by an independent task\nrecords provenance, not ownership of the cycle. The host completes it\nonly after all member executions have ended and scheduling for the\ncycle has finished. Completion fixes its status and execution membership.\nIndependently triggered later work starts another run, even when\nits cause belongs to an earlier run. Every consumer attached to\nthe notebook sees it.\n\nRetention is up to the host and independent of replay history.\nHosts SHOULD retain ephemeral results briefly after completion to\nallow reconnection. Runs, executions, and items each have removal\nevents; a cell result may outlive its run.\n",
  );

export type Run = zod.input<typeof Run>;
export type RunOutput = zod.output<typeof Run>;

export const RunMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    run: Run,
  })
  .describe("The data of the `run` event. The run as it now is.");

export type RunMessage = zod.input<typeof RunMessage>;
export type RunMessageOutput = zod.output<typeof RunMessage>;

export const RunEvent = zod
  .object({
    event: zod.enum(["run"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RunMessage,
  })
  .describe("The `run` event, carried by the notebook stream.");

export type RunEvent = zod.input<typeof RunEvent>;
export type RunEventOutput = zod.output<typeof RunEvent>;

export const ExecutionId = zod
  .string()
  .min(1)
  .describe("Identifies an execution. Unique within the host.");

export type ExecutionId = zod.input<typeof ExecutionId>;
export type ExecutionIdOutput = zod.output<typeof ExecutionId>;

export const revisionUpdateMin = 0;

export const Revision = zod
  .object({
    execution: ExecutionId.describe(
      "The execution whose evaluation produced the value. Usually the variable's `execution_id`, and earlier when the runtime carried the value forward.",
    ),
    update: zod
      .int()
      .min(revisionUpdateMin)
      .describe(
        "How many times the value has been updated since it was produced. Zero at binding.",
      ),
  })
  .describe(
    "A variable's value at a point in time. Two revisions are equal\nwhen `execution` and `update` are equal. Clients compare\nrevisions for equality.\n",
  );

export type Revision = zod.input<typeof Revision>;
export type RevisionOutput = zod.output<typeof Revision>;

export const DisplayData = zod
  .object({
    mimetype: zod
      .string()
      .describe("The format of `data`, such as `text/html` or `image/png`."),
    data: zod
      .string()
      .describe(
        "The rendered value, embedded so clients can display it independently of the runtime. JSON mimetypes are encoded as text and binary mimetypes as base64.",
      ),
  })
  .describe("A rendered value.");

export type DisplayData = zod.input<typeof DisplayData>;
export type DisplayDataOutput = zod.output<typeof DisplayData>;

export const ValueOutcome = zod.object({
  kind: zod.enum(["value"]),
  display: zod
    .union([DisplayData, zod.null()])
    .describe(
      "The value as last rendered. Replaced as it grows. Null when the code produced no value.",
    ),
});

export type ValueOutcome = zod.input<typeof ValueOutcome>;
export type ValueOutcomeOutput = zod.output<typeof ValueOutcome>;

export const positionLineMin = 0;

export const positionCharacterMin = 0;

export const Position = zod
  .object({
    line: zod
      .int()
      .min(positionLineMin)
      .describe("Zero-based line within the code."),
    character: zod
      .int()
      .min(positionCharacterMin)
      .describe("Zero-based offset in the line, in UTF-16 code units."),
  })
  .describe("A position within code, using LSP coordinates.");

export type Position = zod.input<typeof Position>;
export type PositionOutput = zod.output<typeof Position>;

export const Range = zod
  .object({
    start: Position,
    end: Position.describe(
      "Exclusive end. Equal to start when only a point is known.",
    ),
  })
  .describe("A span within code.");

export type Range = zod.input<typeof Range>;
export type RangeOutput = zod.output<typeof Range>;

export const Related = zod
  .object({
    cell_id: CellId,
    range: zod
      .union([Range, zod.null()])
      .describe("Where in that cell, when known."),
    message: zod
      .string()
      .describe("What that cell contributes, such as `reads x from C`."),
  })
  .describe("A cell involved in an error, possibly the one carrying it.");

export type Related = zod.input<typeof Related>;
export type RelatedOutput = zod.output<typeof Related>;

export const Error = zod
  .object({
    kind: zod
      .string()
      .describe(
        "The producer's identifier, scoped by source. Open; this protocol defines `exception`, `interrupted`, and `internal` for executions. Clients show unrecognized kinds as plain errors.",
      ),
    message: zod
      .string()
      .describe("A description of the error to show people."),
    source: zod
      .union([zod.string(), zod.null()])
      .describe(
        "Who produced it, such as `marimo` or a SQL analyzer. Scopes kind.",
      ),
    severity: zod
      .enum(["error", "warning", "information", "hint"])
      .describe(
        "Error unless the producer says otherwise. Only error affects scheduling.",
      ),
    range: zod
      .union([Range, zod.null()])
      .describe("Where in the code, when known."),
    name: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The exception class, such as `ZeroDivisionError`. Set when kind is exception, null otherwise.",
      ),
    traceback: zod
      .union([DisplayData, zod.null()])
      .describe(
        "The traceback as rendered by the runtime, plain text or HTML by its mimetype. Null when unavailable or not shown.",
      ),
    related: zod
      .array(Related)
      .describe(
        "Every involved cell, including this one, in canonical order. Each copy of a cross-cell error carries the same list; clients deduplicate on kind and related cell ids. Empty when the error involves this code alone.",
      ),
  })
  .describe(
    "A problem shaped like an LSP diagnostic. Further members are\nkind-specific, as in Problem Details, and a client ignores\nmembers it does not know.\n",
  );

export type Error = zod.input<typeof Error>;
export type ErrorOutput = zod.output<typeof Error>;

export const ErrorOutcome = zod.object({
  kind: zod.enum(["error"]),
  error: Error,
});

export type ErrorOutcome = zod.input<typeof ErrorOutcome>;
export type ErrorOutcomeOutput = zod.output<typeof ErrorOutcome>;

export const InterruptedOutcome = zod.object({
  kind: zod.enum(["interrupted"]),
});

export type InterruptedOutcome = zod.input<typeof InterruptedOutcome>;
export type InterruptedOutcomeOutput = zod.output<typeof InterruptedOutcome>;

export const SkippedOutcome = zod.object({
  kind: zod.enum(["skipped"]),
  reason: zod
    .string()
    .describe(
      "Why the cell did not evaluate. The string is open. This protocol\ndefines `upstream-failed`, a cell it depends on did not produce\nits value because it raised or could not resolve a reference,\n`upstream-stopped`, a cell it depends on stopped the cycle on\npurpose, and `superseded`, a later execution of the same cell\nreplaced this one before it started because the cell's source\nchanged while it waited. Clients show unrecognized reasons as\nskipped, with the message.\n",
    ),
  message: zod
    .string()
    .describe("Why the cell did not run, to show in place of its output."),
  related: zod
    .array(Related)
    .describe("The cells involved, the cause first and this cell last."),
});

export type SkippedOutcome = zod.input<typeof SkippedOutcome>;
export type SkippedOutcomeOutput = zod.output<typeof SkippedOutcome>;

export const Outcome = zod
  .union([ValueOutcome, ErrorOutcome, InterruptedOutcome, SkippedOutcome])
  .describe(
    "How an execution ended, tagged on `kind`. A `value` carries the\nexecution's value as last rendered; while the execution is\nrunning it is the value so far, and it is final once the\nexecution is `completed`. An `error` carries the error that ended it.\nAn `interrupted` execution was cancelled before or during execution.\nA `skipped` execution did not evaluate because of another cell; it\nhas no value and binds no variables. Other kinds are defined by\nlater versions of this protocol.\n",
  );

export type Outcome = zod.input<typeof Outcome>;
export type OutcomeOutput = zod.output<typeof Outcome>;

export const Execution = zod
  .object({
    id: ExecutionId,
    run_id: zod
      .union([RunId, zod.null()])
      .describe(
        "The run that owns this execution. Every live execution belongs to exactly one run. May name a run the host has dropped. Null only for a restored result whose run is unknown.",
      ),
    runtime_id: zod
      .union([RuntimeId, zod.null()])
      .describe(
        "The runtime that produced this execution. Live when it equals the current runtime's id. Null when the producer is unknown.",
      ),
    caused_by: zod
      .union([ExecutionId, zod.null()])
      .describe(
        "The execution in the same run whose code was running when this one was scheduled, such as scratch code that ran a cell, set a UI element's value, or wrote state, and the cells that reacted to it. Null for an execution a client requested and for the cells that reacted to one.",
      ),
    cell_id: zod
      .union([CellId, zod.null()])
      .describe(
        "The cell this execution belongs to. Null for scratch code, a cell outside the document.",
      ),
    code: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The submitted code for an execution with no cell. Null for a cell's execution; its source is available through the cell when the host exposes it.",
      ),
    code_fingerprint: CodeFingerprint.describe(
      "Fingerprint of the code the execution evaluates. Fixed when the execution is published, while it is still queued.",
    ),
    depends_on: zod
      .record(zod.string(), zod.union([Revision, zod.null()]))
      .describe(
        "The variable revisions this result is valid against, keyed by name. Null for a name no retained cell execution had bound. Empty while queued, stamped as the execution ends, and final from then on.",
      ),
    status: Lifecycle,
    outcome: zod
      .union([Outcome, zod.null()])
      .describe(
        "How the execution ended. Null while queued; while running, a value carries the display so far; final once completed.",
      ),
    started_at: zod
      .union([Timestamp, zod.null()])
      .describe(
        "When the code started executing. Null while queued or if the execution completed before starting.",
      ),
    completed_at: zod
      .union([Timestamp, zod.null()])
      .describe("When the execution ended. Null until it is completed."),
  })
  .describe(
    "One cell evaluated within a run, or scratch code evaluated once.\nIt moves through `queued`, `running`, and `completed`, and ends with\none outcome. Side effects belong to the execution whose context\nproduced them, and items can arrive after completion while the\nexecution remains retained. Each new input belongs to a running\nexecution. Input calls from completed or removed executions raise\n`EOFError` in the calling code. Exactly one of `cell_id` and `code`\nis null: a cell's execution carries the cell and no code, and a\nscratch execution carries its code and no cell.\n",
  );

export type Execution = zod.input<typeof Execution>;
export type ExecutionOutput = zod.output<typeof Execution>;

export const ExecutionMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    execution: Execution,
  })
  .describe("The data of the `execution` event. The execution as it now is.");

export type ExecutionMessage = zod.input<typeof ExecutionMessage>;
export type ExecutionMessageOutput = zod.output<typeof ExecutionMessage>;

export const ExecutionEvent = zod
  .object({
    event: zod.enum(["execution"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: ExecutionMessage,
  })
  .describe("The `execution` event, carried by the notebook stream.");

export type ExecutionEvent = zod.input<typeof ExecutionEvent>;
export type ExecutionEventOutput = zod.output<typeof ExecutionEvent>;

export const ItemId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a console, display, input, or variable item uniquely within the host. Sending an item again with the same id replaces it.",
  );

export type ItemId = zod.input<typeof ItemId>;
export type ItemIdOutput = zod.output<typeof ItemId>;

export const consoleSeqMin = 0;

export const Console = zod
  .object({
    id: ItemId,
    execution_id: ExecutionId,
    seq: zod
      .int()
      .min(consoleSeqMin)
      .describe(
        "Position among the execution's items, increasing in the order they were produced.",
      ),
    name: zod
      .enum(["stdout", "stderr"])
      .describe("Which stream the text went to."),
    text: zod.string().describe("The text, exactly as written."),
  })
  .describe(
    "Text an execution wrote to stdout or stderr. Items are ordinary\nobjects: a producer replaces one by sending it again with the\nsame id, and items are removed with their execution.\n",
  );

export type Console = zod.input<typeof Console>;
export type ConsoleOutput = zod.output<typeof Console>;

export const ConsoleMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    console: Console,
  })
  .describe("The data of the `console` event. The console as it now is.");

export type ConsoleMessage = zod.input<typeof ConsoleMessage>;
export type ConsoleMessageOutput = zod.output<typeof ConsoleMessage>;

export const ConsoleEvent = zod
  .object({
    event: zod.enum(["console"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: ConsoleMessage,
  })
  .describe("The `console` event, carried by the notebook stream.");

export type ConsoleEvent = zod.input<typeof ConsoleEvent>;
export type ConsoleEventOutput = zod.output<typeof ConsoleEvent>;

export const displaySeqMin = 0;

export const Display = zod
  .object({
    id: ItemId,
    execution_id: ExecutionId,
    seq: zod
      .int()
      .min(displaySeqMin)
      .describe(
        "Position among the execution's items, increasing in the order they were produced.",
      ),
    content: DisplayData.describe("The rendered value."),
  })
  .describe(
    "A value an execution showed as a side effect, such as a figure\nfrom `plt.show()`. A producer replaces one by sending it again\nwith the same id, which is how a progress bar updates in place.\n",
  );

export type Display = zod.input<typeof Display>;
export type DisplayOutput = zod.output<typeof Display>;

export const DisplayMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    display: Display,
  })
  .describe("The data of the `display` event. The display as it now is.");

export type DisplayMessage = zod.input<typeof DisplayMessage>;
export type DisplayMessageOutput = zod.output<typeof DisplayMessage>;

export const DisplayEvent = zod
  .object({
    event: zod.enum(["display"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: DisplayMessage,
  })
  .describe("The `display` event, carried by the notebook stream.");

export type DisplayEvent = zod.input<typeof DisplayEvent>;
export type DisplayEventOutput = zod.output<typeof DisplayEvent>;

export const InputStatus = zod
  .enum(["pending", "answered", "cancelled"])
  .describe(
    "An input starts `pending` while it waits for an answer. It becomes\n`answered` when the host accepts a reply for delivery, or `cancelled`\nwhen the host ends the wait while input is still pending. Both\n`answered` and `cancelled` are final. An answered input stays\nanswered if execution later fails before consuming the value.\n",
  );

export type InputStatus = zod.input<typeof InputStatus>;
export type InputStatusOutput = zod.output<typeof InputStatus>;

export const inputSeqMin = 0;

export const Input = zod
  .object({
    id: ItemId.describe(
      "Identifies this prompt uniquely across executions and runtime restarts.",
    ),
    execution_id: ExecutionId,
    seq: zod
      .int()
      .min(inputSeqMin)
      .describe(
        "Position among the execution's console, display, and input items, increasing in production order.",
      ),
    prompt: zod.string().describe("The prompt to display, which may be empty."),
    password: zod
      .boolean()
      .describe("Whether clients must obscure the value as it is entered."),
    status: InputStatus,
  })
  .describe(
    "A running execution's request for a line of text. Its identity,\nexecution, prompt, password flag, and position stay fixed while\nits status tracks the request. The record remains with its\nexecution after it is answered or cancelled. Submitted answers\ntravel through the reply endpoint to the runtime.\n",
  );

export type Input = zod.input<typeof Input>;
export type InputOutput = zod.output<typeof Input>;

export const InputMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    input: Input,
  })
  .describe("The data of the `input` event. The input as it now is.");

export type InputMessage = zod.input<typeof InputMessage>;
export type InputMessageOutput = zod.output<typeof InputMessage>;

export const InputEvent = zod
  .object({
    event: zod.enum(["input"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: InputMessage,
  })
  .describe("The `input` event, carried by the notebook stream.");

export type InputEvent = zod.input<typeof InputEvent>;
export type InputEventOutput = zod.output<typeof InputEvent>;

export const Variable = zod
  .object({
    id: ItemId,
    execution_id: ExecutionId.describe("The execution that bound the name."),
    name: zod.string().describe("The name in the namespace."),
    revision: Revision,
    type: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The runtime's label for the value's type. A host may leave it null.",
      ),
    preview: zod
      .union([zod.string(), zod.null()])
      .describe("A short rendering of the value. A host may leave it null."),
  })
  .describe(
    "A name a cell's execution bound in the notebook's namespace, with\nthe revision of its value. The execution binds it as it ends, and\nthe item is removed with the execution. An update, as when a\nstate setter runs or a client sets a value, advances the revision\nwithout binding again, and the producer sends the item again with\nthe same id. Hosts publish a cell execution's variables before its\n`completed` status, and remove a cell's previous execution and\nits items before publishing the next one. A scratch execution's\nnames live only while it runs, so it publishes no variables.\n",
  );

export type Variable = zod.input<typeof Variable>;
export type VariableOutput = zod.output<typeof Variable>;

export const VariableMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    variable: Variable,
  })
  .describe("The data of the `variable` event. The variable as it now is.");

export type VariableMessage = zod.input<typeof VariableMessage>;
export type VariableMessageOutput = zod.output<typeof VariableMessage>;

export const VariableEvent = zod
  .object({
    event: zod.enum(["variable"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: VariableMessage,
  })
  .describe("The `variable` event, carried by the notebook stream.");

export type VariableEvent = zod.input<typeof VariableEvent>;
export type VariableEventOutput = zod.output<typeof VariableEvent>;

export const CellAnalysis = zod
  .object({
    defs: zod.array(zod.string()).describe("Names this cell defines."),
    refs: zod
      .array(zod.string())
      .describe("Names this cell reads from other cells."),
    errors: zod
      .array(Error)
      .describe(
        "Diagnostics about the code. Only an `error` affects scheduling. `multiple-definitions` lists the definers in `related`, each `range` at its definition; `cycle-dependencies` lists the cycle. Both are reported on every cell involved, differing only in `range`. Every other kind belongs to the analyzer named in `source`.",
      ),
  })
  .describe(
    "What a cell's text implies: the names it defines and reads, which\nare the edges of the dependency graph, and the errors found in the\ntext alone or across the set of cells. A pure function of the\ncode, so two producers compute the same values.\n",
  );

export type CellAnalysis = zod.input<typeof CellAnalysis>;
export type CellAnalysisOutput = zod.output<typeof CellAnalysis>;

export const Analysis = zod
  .object({
    notebook_id: NotebookId.describe("The notebook this analysis belongs to."),
    document_etag: Etag.describe(
      "The document revision this analysis describes. Equal to the document's `etag` while the analysis is current.",
    ),
    cells: zod
      .record(zod.string(), CellAnalysis)
      .describe("Every cell of that revision, by id."),
  })
  .describe(
    "What a document's cells imply, computed together over one\nrevision of the document so that cross-cell errors agree. One\nper notebook, and removed with it. It follows the document it\ndescribes, and `document_etag` says which revision that is.\n",
  );

export type Analysis = zod.input<typeof Analysis>;
export type AnalysisOutput = zod.output<typeof Analysis>;

export const AnalysisMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    analysis: Analysis,
  })
  .describe("The data of the `analysis` event. The analysis as it now is.");

export type AnalysisMessage = zod.input<typeof AnalysisMessage>;
export type AnalysisMessageOutput = zod.output<typeof AnalysisMessage>;

export const AnalysisEvent = zod
  .object({
    event: zod.enum(["analysis"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: AnalysisMessage,
  })
  .describe("The `analysis` event, carried by the notebook stream.");

export type AnalysisEvent = zod.input<typeof AnalysisEvent>;
export type AnalysisEventOutput = zod.output<typeof AnalysisEvent>;

export const Custom = zod
  .object({
    type: zod
      .string()
      .min(1)
      .describe(
        "A namespaced event type under a namespace the producer controls, such as `marimo.pair.agent-message`. Clients ignore types they do not recognize while retaining the stream cursor.",
      ),
    data: zod
      .unknown()
      .describe(
        "Any JSON value, including null. The producer defines its schema and consumers of the type validate it.",
      ),
  })
  .describe(
    "A notebook occurrence with a producer-defined payload. It is replayed\nwhile event history is retained. Delivery is limited to live events\nand replay on the notebook stream, with `run_id` omitted from the\nstream's filters. The notebook is identified by the stream.\n",
  );

export type Custom = zod.input<typeof Custom>;
export type CustomOutput = zod.output<typeof Custom>;

export const CustomMessage = zod
  .object({
    custom: Custom,
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.describe(
      "When the host emitted this event. Preserved on replay.",
    ),
  })
  .describe(
    "The data of a `custom` event. This envelope is standardized; the custom type and payload are defined by their producer.",
  );

export type CustomMessage = zod.input<typeof CustomMessage>;
export type CustomMessageOutput = zod.output<typeof CustomMessage>;

export const CustomEvent = zod
  .object({
    event: zod.enum(["custom"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: CustomMessage,
  })
  .describe("The `custom` event, carried by the notebook stream.");

export type CustomEvent = zod.input<typeof CustomEvent>;
export type CustomEventOutput = zod.output<typeof CustomEvent>;

export const RemovedMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: Timestamp.optional().describe(
      "When the host made this change. Present on live and replayed events; omitted on snapshots.",
    ),
    id: zod.string().describe("The id of the object that was removed."),
  })
  .describe(
    "The data of an event ending in `.removed`. The event name identifies the kind of object to delete from the client's view. Removing a notebook also removes its document and cells, and removing an execution removes its inputs. Clients discard these child records when they receive the parent's removal event.",
  );

export type RemovedMessage = zod.input<typeof RemovedMessage>;
export type RemovedMessageOutput = zod.output<typeof RemovedMessage>;

export const ProjectRemovedEvent = zod
  .object({
    event: zod.enum(["project.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe("The `project.removed` event, carried by the catalog stream.");

export type ProjectRemovedEvent = zod.input<typeof ProjectRemovedEvent>;
export type ProjectRemovedEventOutput = zod.output<typeof ProjectRemovedEvent>;

export const NotebookRemovedEvent = zod
  .object({
    event: zod.enum(["notebook.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe(
    "The `notebook.removed` event, carried by the catalog and notebook streams.",
  );

export type NotebookRemovedEvent = zod.input<typeof NotebookRemovedEvent>;
export type NotebookRemovedEventOutput = zod.output<
  typeof NotebookRemovedEvent
>;

export const CellRemovedEvent = zod
  .object({
    event: zod.enum(["cell.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe("The `cell.removed` event, carried by the notebook stream.");

export type CellRemovedEvent = zod.input<typeof CellRemovedEvent>;
export type CellRemovedEventOutput = zod.output<typeof CellRemovedEvent>;

export const RuntimeRemovedEvent = zod
  .object({
    event: zod.enum(["runtime.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe(
    "The `runtime.removed` event, carried by the catalog and notebook streams.",
  );

export type RuntimeRemovedEvent = zod.input<typeof RuntimeRemovedEvent>;
export type RuntimeRemovedEventOutput = zod.output<typeof RuntimeRemovedEvent>;

export const AttachmentRemovedEvent = zod
  .object({
    event: zod.enum(["attachment.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe(
    "The `attachment.removed` event, carried by the catalog and notebook streams.",
  );

export type AttachmentRemovedEvent = zod.input<typeof AttachmentRemovedEvent>;
export type AttachmentRemovedEventOutput = zod.output<
  typeof AttachmentRemovedEvent
>;

export const RunRemovedEvent = zod
  .object({
    event: zod.enum(["run.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe("The `run.removed` event, carried by the notebook stream.");

export type RunRemovedEvent = zod.input<typeof RunRemovedEvent>;
export type RunRemovedEventOutput = zod.output<typeof RunRemovedEvent>;

export const ExecutionRemovedEvent = zod
  .object({
    event: zod.enum(["execution.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe("The `execution.removed` event, carried by the notebook stream.");

export type ExecutionRemovedEvent = zod.input<typeof ExecutionRemovedEvent>;
export type ExecutionRemovedEventOutput = zod.output<
  typeof ExecutionRemovedEvent
>;

export const ConsoleRemovedEvent = zod
  .object({
    event: zod.enum(["console.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe("The `console.removed` event, carried by the notebook stream.");

export type ConsoleRemovedEvent = zod.input<typeof ConsoleRemovedEvent>;
export type ConsoleRemovedEventOutput = zod.output<typeof ConsoleRemovedEvent>;

export const DisplayRemovedEvent = zod
  .object({
    event: zod.enum(["display.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe("The `display.removed` event, carried by the notebook stream.");

export type DisplayRemovedEvent = zod.input<typeof DisplayRemovedEvent>;
export type DisplayRemovedEventOutput = zod.output<typeof DisplayRemovedEvent>;

export const VariableRemovedEvent = zod
  .object({
    event: zod.enum(["variable.removed"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: RemovedMessage,
  })
  .describe("The `variable.removed` event, carried by the notebook stream.");

export type VariableRemovedEvent = zod.input<typeof VariableRemovedEvent>;
export type VariableRemovedEventOutput = zod.output<
  typeof VariableRemovedEvent
>;

export const ResetEvent = zod
  .object({
    event: zod.enum(["reset"]),
    id: zod
      .string()
      .min(1)
      .optional()
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: zod.looseObject({}),
  })
  .describe("The `reset` event, carried by every stream.");

export type ResetEvent = zod.input<typeof ResetEvent>;
export type ResetEventOutput = zod.output<typeof ResetEvent>;

export const ReadyEvent = zod
  .object({
    event: zod.enum(["ready"]),
    id: zod
      .string()
      .min(1)
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: zod.looseObject({}),
  })
  .describe("The `ready` event, carried by every stream.");

export type ReadyEvent = zod.input<typeof ReadyEvent>;
export type ReadyEventOutput = zod.output<typeof ReadyEvent>;

export const Event = zod
  .union([
    HostEvent,
    ProjectEvent,
    NotebookEvent,
    DocumentEvent,
    CellEvent,
    RuntimeEvent,
    AttachmentEvent,
    RunEvent,
    ExecutionEvent,
    ConsoleEvent,
    DisplayEvent,
    InputEvent,
    VariableEvent,
    AnalysisEvent,
    CustomEvent,
    ProjectRemovedEvent,
    NotebookRemovedEvent,
    CellRemovedEvent,
    RuntimeRemovedEvent,
    AttachmentRemovedEvent,
    RunRemovedEvent,
    ExecutionRemovedEvent,
    ConsoleRemovedEvent,
    DisplayRemovedEvent,
    VariableRemovedEvent,
    ResetEvent,
    ReadyEvent,
  ])
  .describe(
    "A record, removal, or control message from a host stream. The data is decoded JSON. Snapshot records and reset events omit the cursor, and ready and live events carry it. Unknown event names belong to later versions or host extensions.",
  );

export type Event = zod.input<typeof Event>;
export type EventOutput = zod.output<typeof Event>;

export const ObjectType = zod
  .enum([
    "host",
    "project",
    "notebook",
    "document",
    "cell",
    "runtime",
    "attachment",
    "run",
    "execution",
    "console",
    "display",
    "input",
    "variable",
    "analysis",
    "custom",
  ])
  .describe(
    "The kinds a stream carries, and the values `types` accepts. The catalog stream carries host, project, notebook, runtime, and attachment. A notebook's stream carries notebook, document, cell, runtime, attachment, run, execution, console, display, input, variable, analysis, and custom. Custom events describe occurrences rather than object state.",
  );

export type ObjectType = zod.input<typeof ObjectType>;
export type ObjectTypeOutput = zod.output<typeof ObjectType>;

export const Process = zod
  .object({
    pid: zod.int().min(1).describe("The process id."),
    started_at: Timestamp.describe("When the process started."),
  })
  .describe(
    "The process that wrote a record. A client checks that a process\nwith this `pid` that started at `started_at` still exists. If it\ndoes not, the record is stale and may be removed.\n",
  );

export type Process = zod.input<typeof Process>;
export type ProcessOutput = zod.output<typeof Process>;

export const HostRecord = zod
  .object({
    version: zod
      .literal(1)
      .describe(
        "The version of this record's format. This document describes version 1.",
      ),
    process: Process,
    name: zod
      .string()
      .describe(
        "A label for the host to show people, such as `VS Code` or `marimo`. Two hosts can share a name; the filename is the identity.",
      ),
    url: zod
      .string()
      .describe(
        "Where the host's API is. The scheme is `http`, and the host part is `127.0.0.1` or `[::1]`, written exactly that way.",
      ),
    token: zod
      .string()
      .min(1)
      .describe("The secret a client sends to prove it read the record."),
  })
  .describe(
    "A host record is the file a host writes so that clients can find\nit. A host writes `<marimo-state-dir>/hosts-v1/<id>.json` once its API\nis serving at `url`, where `<id>` is an identifier the host makes\nup each time it starts. The record does not change while the host\nruns, and the host removes it when it stops.\n\nA client reads `version` before anything else and skips any record\nit cannot parse or whose version it does not support. It also\nchecks that the file and its directory belong to the current user\nand cannot be read by others, and that `url` points at this\nmachine.\n",
  );

export type HostRecord = zod.input<typeof HostRecord>;
export type HostRecordOutput = zod.output<typeof HostRecord>;

export const invalidRequestProblemStatusDefault = 400;
export const invalidRequestProblemTitleDefault = `Invalid request`;

export const InvalidRequestProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:invalid-request"]),
  status: zod.literal(400).default(invalidRequestProblemStatusDefault),
  title: zod.string().default(invalidRequestProblemTitleDefault),
});

export type InvalidRequestProblem = zod.input<typeof InvalidRequestProblem>;
export type InvalidRequestProblemOutput = zod.output<
  typeof InvalidRequestProblem
>;

export const unauthorizedProblemStatusDefault = 401;
export const unauthorizedProblemTitleDefault = `Unauthorized`;

export const UnauthorizedProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:unauthorized"]),
  status: zod.literal(401).default(unauthorizedProblemStatusDefault),
  title: zod.string().default(unauthorizedProblemTitleDefault),
});

export type UnauthorizedProblem = zod.input<typeof UnauthorizedProblem>;
export type UnauthorizedProblemOutput = zod.output<typeof UnauthorizedProblem>;

export const forbiddenProblemStatusDefault = 403;
export const forbiddenProblemTitleDefault = `Forbidden`;

export const ForbiddenProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:forbidden"]),
  status: zod.literal(403).default(forbiddenProblemStatusDefault),
  title: zod.string().default(forbiddenProblemTitleDefault),
});

export type ForbiddenProblem = zod.input<typeof ForbiddenProblem>;
export type ForbiddenProblemOutput = zod.output<typeof ForbiddenProblem>;

export const notFoundProblemStatusDefault = 404;
export const notFoundProblemTitleDefault = `Not found`;

export const NotFoundProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:not-found"]),
  status: zod.literal(404).default(notFoundProblemStatusDefault),
  title: zod.string().default(notFoundProblemTitleDefault),
});

export type NotFoundProblem = zod.input<typeof NotFoundProblem>;
export type NotFoundProblemOutput = zod.output<typeof NotFoundProblem>;

export const methodNotAllowedProblemStatusDefault = 405;
export const methodNotAllowedProblemTitleDefault = `Method not allowed`;

export const MethodNotAllowedProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:method-not-allowed"]),
  status: zod.literal(405).default(methodNotAllowedProblemStatusDefault),
  title: zod.string().default(methodNotAllowedProblemTitleDefault),
});

export type MethodNotAllowedProblem = zod.input<typeof MethodNotAllowedProblem>;
export type MethodNotAllowedProblemOutput = zod.output<
  typeof MethodNotAllowedProblem
>;

export const conflictProblemStatusDefault = 409;
export const conflictProblemTitleDefault = `Conflict`;

export const ConflictProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:conflict"]),
  status: zod.literal(409).default(conflictProblemStatusDefault),
  title: zod.string().default(conflictProblemTitleDefault),
});

export type ConflictProblem = zod.input<typeof ConflictProblem>;
export type ConflictProblemOutput = zod.output<typeof ConflictProblem>;

export const noRuntimeProblemStatusDefault = 409;
export const noRuntimeProblemTitleDefault = `No runtime`;

export const NoRuntimeProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:no-runtime"]),
  status: zod.literal(409).default(noRuntimeProblemStatusDefault),
  title: zod.string().default(noRuntimeProblemTitleDefault),
});

export type NoRuntimeProblem = zod.input<typeof NoRuntimeProblem>;
export type NoRuntimeProblemOutput = zod.output<typeof NoRuntimeProblem>;

export const DecisionOption = zod
  .object({
    id: zod.string().describe("Identifies this answer."),
    label: zod.string().describe("Text to show a person."),
  })
  .describe("One possible answer to a decision.");

export type DecisionOption = zod.input<typeof DecisionOption>;
export type DecisionOptionOutput = zod.output<typeof DecisionOption>;

export const Decision = zod
  .object({
    id: zod
      .string()
      .describe("Identifies the question when the client answers it."),
    prompt: zod.string().describe("The question, worded for a person."),
    options: zod.array(DecisionOption).describe("The possible answers."),
  })
  .describe(
    "A question the host needs answered before it can carry out a\nrequest. The client answers by repeating the request with\n`decisions` in the body, mapping this `id` to the `id` of an\noption.\n",
  );

export type Decision = zod.input<typeof Decision>;
export type DecisionOutput = zod.output<typeof Decision>;

export const decisionRequiredProblemStatusDefault = 409;
export const decisionRequiredProblemTitleDefault = `Decision required`;

export const DecisionRequiredProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  decisions: zod
    .array(Decision)
    .describe(
      "The choices the client has to make before the host can carry out the request.",
    ),
  type: zod.enum(["urn:marimo:problem:decision-required"]),
  status: zod.literal(409).default(decisionRequiredProblemStatusDefault),
  title: zod.string().default(decisionRequiredProblemTitleDefault),
});

export type DecisionRequiredProblem = zod.input<typeof DecisionRequiredProblem>;
export type DecisionRequiredProblemOutput = zod.output<
  typeof DecisionRequiredProblem
>;

export const preconditionFailedProblemIndexMin = 0;

export const preconditionFailedProblemStatusDefault = 412;
export const preconditionFailedProblemTitleDefault = `Precondition failed`;

export const PreconditionFailedProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  index: zod
    .int()
    .min(preconditionFailedProblemIndexMin)
    .describe(
      "The position of the first stale entry in the request, counted in an edit's `changes` or a run's `cells`. `0` for a save with a stale `If-Match`.",
    ),
  cell: zod
    .union([Cell, zod.null()])
    .describe(
      "The cell that entry named, as it now is. Null when the document does not have it, or when the entry named the order or the whole document.",
    ),
  document: Document.describe("The document as it now is."),
  type: zod.enum(["urn:marimo:problem:precondition-failed"]),
  status: zod.literal(412).default(preconditionFailedProblemStatusDefault),
  title: zod.string().default(preconditionFailedProblemTitleDefault),
});

export type PreconditionFailedProblem = zod.input<
  typeof PreconditionFailedProblem
>;
export type PreconditionFailedProblemOutput = zod.output<
  typeof PreconditionFailedProblem
>;

export const internalProblemStatusDefault = 500;
export const internalProblemTitleDefault = `Internal error`;

export const InternalProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:internal"]),
  status: zod.literal(500).default(internalProblemStatusDefault),
  title: zod.string().default(internalProblemTitleDefault),
});

export type InternalProblem = zod.input<typeof InternalProblem>;
export type InternalProblemOutput = zod.output<typeof InternalProblem>;

export const unsupportedOperationProblemStatusDefault = 501;
export const unsupportedOperationProblemTitleDefault = `Unsupported operation`;

export const UnsupportedOperationProblem = zod.object({
  detail: zod.string().optional(),
  instance: zod.string().optional(),
  type: zod.enum(["urn:marimo:problem:unsupported-operation"]),
  status: zod.literal(501).default(unsupportedOperationProblemStatusDefault),
  title: zod.string().default(unsupportedOperationProblemTitleDefault),
});

export type UnsupportedOperationProblem = zod.input<
  typeof UnsupportedOperationProblem
>;
export type UnsupportedOperationProblemOutput = zod.output<
  typeof UnsupportedOperationProblem
>;

export const Problem = zod
  .union([
    InvalidRequestProblem,
    UnauthorizedProblem,
    ForbiddenProblem,
    NotFoundProblem,
    MethodNotAllowedProblem,
    ConflictProblem,
    NoRuntimeProblem,
    DecisionRequiredProblem,
    PreconditionFailedProblem,
    InternalProblem,
    UnsupportedOperationProblem,
  ])
  .describe(
    "An error. Every error response is a problem, following RFC 9457, and is served as `application/problem+json`. `type` says which. A client ignores members it does not recognize. Hosts redact tokens from errors.",
  );

export type Problem = zod.input<typeof Problem>;
export type ProblemOutput = zod.output<typeof Problem>;

export const unknownProblemStatusMin = 400;
export const unknownProblemStatusMax = 599;

export const UnknownProblem = zod
  .looseObject({
    type: zod.string().describe("What kind of problem this is, as a URI."),
    title: zod
      .string()
      .describe("A short, human-readable name for the kind of problem."),
    status: zod
      .int()
      .min(unknownProblemStatusMin)
      .max(unknownProblemStatusMax)
      .describe("The HTTP status code of the response."),
    detail: zod
      .string()
      .optional()
      .describe("A human-readable explanation of what went wrong this time."),
  })
  .describe(
    "A problem of a type this version does not define. A host on a later version can send one, and a client falls back to its `status`.",
  );

export type UnknownProblem = zod.input<typeof UnknownProblem>;
export type UnknownProblemOutput = zod.output<typeof UnknownProblem>;

export const UpdateNotebookRequest = zod
  .object({
    path: zod
      .string()
      .optional()
      .describe(
        "The new location, relative to the project root and written the way the host's operating system writes paths.",
      ),
    name: zod.string().optional().describe("The new label to show people."),
  })
  .describe("The fields to change. At least one is present.");

export type UpdateNotebookRequest = zod.input<typeof UpdateNotebookRequest>;
export type UpdateNotebookRequestOutput = zod.output<
  typeof UpdateNotebookRequest
>;

export const CellVersion = zod
  .object({
    etag: Etag,
    code_fingerprint: CodeFingerprint,
    version: zod.int().min(1).describe("The cell's version after the edit."),
  })
  .describe("A cell's etag, code fingerprint, and version after an edit.");

export type CellVersion = zod.input<typeof CellVersion>;
export type CellVersionOutput = zod.output<typeof CellVersion>;

export const EditResponse = zod
  .object({
    document: Document,
    cells: zod
      .record(zod.string(), zod.union([CellVersion, zod.null()]))
      .describe(
        "The version of each cell the request created or changed, by id, and null for each cell it deleted.",
      ),
  })
  .describe(
    "The document as an edit or save left it, or at a later revision, and the cells it touched.",
  );

export type EditResponse = zod.input<typeof EditResponse>;
export type EditResponseOutput = zod.output<typeof EditResponse>;

export const SaveRequest = zod
  .object({
    decisions: zod
      .record(zod.string(), zod.string())
      .optional()
      .describe(
        "Answers to the questions in a `decision-required` problem, as for `runtime.start`.",
      ),
  })
  .describe(
    "What a save needs from the client, which is nothing until the host asks a question. `{}` is the usual body.",
  );

export type SaveRequest = zod.input<typeof SaveRequest>;
export type SaveRequestOutput = zod.output<typeof SaveRequest>;

export const StartRuntimeRequest = zod.object({
  decisions: zod
    .record(zod.string(), zod.string())
    .optional()
    .describe(
      "Answers to the questions in a `decision-required` problem.\nEach key is a decision's `id` and each value is the `id` of\nthe chosen option. A client that already knows its choices can\nsend them the first time.\n",
    ),
});

export type StartRuntimeRequest = zod.input<typeof StartRuntimeRequest>;
export type StartRuntimeRequestOutput = zod.output<typeof StartRuntimeRequest>;

export const ExecuteRequest = zod
  .strictObject({
    code: zod
      .string()
      .describe(
        "Python code that can read the notebook's current values.\nAssignments stay local to the call. Changes to shared objects persist.\n",
      ),
  })
  .describe("Python code to execute with access to notebook values.");

export type ExecuteRequest = zod.input<typeof ExecuteRequest>;
export type ExecuteRequestOutput = zod.output<typeof ExecuteRequest>;

export const RequestedCell = zod.object({
  id: CellId,
  etag: Etag.optional().describe(
    "The cell's `etag` as last read. A cell whose source, name, or config differs is `precondition-failed`. Absent, the cell runs as it is.",
  ),
});

export type RequestedCell = zod.input<typeof RequestedCell>;
export type RequestedCellOutput = zod.output<typeof RequestedCell>;

export const RunRequest = zod
  .strictObject({
    cells: zod
      .array(RequestedCell)
      .min(1)
      .describe(
        "Cells to run by id. The notebook's execution settings determine their order and whether dependent cells run too.",
      ),
  })
  .describe("Notebook cells to run.");

export type RunRequest = zod.input<typeof RunRequest>;
export type RunRequestOutput = zod.output<typeof RunRequest>;

export const InputReplyRequest = zod
  .object({
    value: zod
      .string()
      .describe(
        "The text to deliver to the input exactly as submitted, including an empty string when the answer is empty.",
      ),
  })
  .describe("The answer to one pending input.");

export type InputReplyRequest = zod.input<typeof InputReplyRequest>;
export type InputReplyRequestOutput = zod.output<typeof InputReplyRequest>;

export const OpenNotebookResponse = zod.object({
  url: zod
    .string()
    .describe(
      "The URL the host used to show the notebook, with the host's token omitted.",
    ),
});

export type OpenNotebookResponse = zod.input<typeof OpenNotebookResponse>;
export type OpenNotebookResponseOutput = zod.output<
  typeof OpenNotebookResponse
>;

export const cellConfigInputColumnDefault = null;
export const cellConfigInputDisabledDefault = false;
export const cellConfigInputHideCodeDefault = false;
export const cellConfigInputExpandOutputDefault = false;

export const CellConfigInput = zod
  .object({
    column: zod
      .union([zod.int(), zod.null()])
      .default(cellConfigInputColumnDefault),
    disabled: zod.boolean().default(cellConfigInputDisabledDefault),
    hide_code: zod.boolean().default(cellConfigInputHideCodeDefault),
    expand_output: zod.boolean().default(cellConfigInputExpandOutputDefault),
  })
  .describe(
    "A cell's settings as a client writes them. A field left out takes its default.",
  );

export type CellConfigInput = zod.input<typeof CellConfigInput>;
export type CellConfigInputOutput = zod.output<typeof CellConfigInput>;

export const cellInputNameDefault = `_`;

export const CellInput = zod
  .object({
    id: CellId.describe(
      "The cell's id. A client chooses the id of a cell it creates.",
    ),
    code: zod.string().describe("The cell's source code."),
    name: zod
      .string()
      .default(cellInputNameDefault)
      .describe("The cell's name. `_` for an anonymous cell."),
    config: CellConfigInput.optional(),
  })
  .describe(
    "A cell as a client writes it. Code must be a string, even when the host withholds source in cell records. Null is not an edit or a request to preserve existing source. The host derives the etags.",
  );

export type CellInput = zod.input<typeof CellInput>;
export type CellInputOutput = zod.output<typeof CellInput>;

export const PutCell = zod
  .object({
    kind: zod.enum(["put_cell"]),
    base_etag: zod
      .union([zod.string(), zod.null()])
      .describe(
        "The cell's etag as last read, `*` to skip the check, or null to create the cell. Null when the cell exists, or an etag when it does not, is `precondition-failed`.",
      ),
    cell: CellInput,
    after: CellId.optional().describe(
      "The cell a created cell goes after. Ignored for an existing cell.",
    ),
    before: CellId.optional().describe(
      "The cell a created cell goes before. Ignored for an existing cell. With neither `after` nor `before`, a created cell goes at the end.",
    ),
  })
  .describe("Replaces a whole cell, or creates one.");

export type PutCell = zod.input<typeof PutCell>;
export type PutCellOutput = zod.output<typeof PutCell>;

export const DeleteCell = zod
  .object({
    kind: zod.enum(["delete_cell"]),
    id: CellId.describe("The cell to remove."),
    base_etag: zod.string().describe("The cell's etag as last read, or `*`."),
  })
  .describe("Removes a cell.");

export type DeleteCell = zod.input<typeof DeleteCell>;
export type DeleteCellOutput = zod.output<typeof DeleteCell>;

export const SetOrder = zod
  .object({
    kind: zod.enum(["set_order"]),
    base_etag: zod
      .string()
      .describe("The document's `order_etag` as last read, or `*`."),
    order: zod
      .array(CellId)
      .describe(
        "Every cell id exactly once, in the new order, counting cells this edit creates and leaving out cells it deletes.",
      ),
  })
  .describe("Replaces the cell order.");

export type SetOrder = zod.input<typeof SetOrder>;
export type SetOrderOutput = zod.output<typeof SetOrder>;

export const Change = zod
  .union([PutCell, DeleteCell, SetOrder])
  .describe("One change to the document, tagged on `kind`.");

export type Change = zod.input<typeof Change>;
export type ChangeOutput = zod.output<typeof Change>;

export const EditRequest = zod.object({
  changes: zod
    .array(Change)
    .describe("The changes, applied in order as one unit."),
});

export type EditRequest = zod.input<typeof EditRequest>;
export type EditRequestOutput = zod.output<typeof EditRequest>;

export const CreateNotebookRequest = zod
  .object({
    project_id: ProjectId,
    path: zod
      .string()
      .optional()
      .describe(
        "Where to put the file, relative to the project root and written the way the host's operating system writes paths.",
      ),
    name: zod
      .string()
      .optional()
      .describe(
        "A label to show people. In a project with a root it defaults to the filename.",
      ),
  })
  .describe(
    "The notebook's own fields, minus what the host assigns. A project with a root requires `path`; one without requires `name`.",
  );

export type CreateNotebookRequest = zod.input<typeof CreateNotebookRequest>;
export type CreateNotebookRequestOutput = zod.output<
  typeof CreateNotebookRequest
>;
