/* Copyright 2026 Marimo. All rights reserved. */
// Generated from protocols/host/openapi.yaml. Do not edit.
// Regenerate with: pnpm --dir packages/client codegen

import * as zod from "zod";

export const ProjectId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a project. Unique within the host and unchanged while the project exists.",
  );

export type ProjectId = zod.input<typeof ProjectId>;
export type ProjectIdOutput = zod.output<typeof ProjectId>;

export const NotebookId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a notebook. Unique within the host and unchanged while the notebook exists.",
  );

export type NotebookId = zod.input<typeof NotebookId>;
export type NotebookIdOutput = zod.output<typeof NotebookId>;

export const RuntimeId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a runtime. Unique within the host; every start and restart creates a new id.",
  );

export type RuntimeId = zod.input<typeof RuntimeId>;
export type RuntimeIdOutput = zod.output<typeof RuntimeId>;

export const AttachmentId = zod
  .string()
  .min(1)
  .describe("Identifies an attachment. Unique within the host.");

export type AttachmentId = zod.input<typeof AttachmentId>;
export type AttachmentIdOutput = zod.output<typeof AttachmentId>;

export const RunId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a run independently of the request's `Idempotency-Key`. Events carry the key in `request_id`.",
  );

export type RunId = zod.input<typeof RunId>;
export type RunIdOutput = zod.output<typeof RunId>;

export const ExecutionId = zod
  .string()
  .min(1)
  .describe("Identifies an execution. Unique within the host.");

export type ExecutionId = zod.input<typeof ExecutionId>;
export type ExecutionIdOutput = zod.output<typeof ExecutionId>;

export const ItemId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a console, display, or variable item. Unique within the host; sending an item again with the same id replaces it.",
  );

export type ItemId = zod.input<typeof ItemId>;
export type ItemIdOutput = zod.output<typeof ItemId>;

export const CellId = zod
  .string()
  .min(1)
  .describe(
    "Identifies a cell within its notebook. Stable while the host serves the notebook; whether it survives a reload of the store depends on the format. `setup` is the setup cell.",
  );

export type CellId = zod.input<typeof CellId>;
export type CellIdOutput = zod.output<typeof CellId>;

export const Process = zod
  .object({
    pid: zod.int().min(1).describe("The process id."),
    started_at: zod.iso
      .datetime({ offset: true })
      .describe("When the process started."),
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

export const ObjectType = zod
  .enum([
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
    "variable",
    "custom",
  ])
  .describe(
    "The kinds a stream carries, and the values `types` accepts. The\ncatalog stream carries host, project, notebook, runtime, and\nattachment. A notebook's stream carries notebook, document,\nanalysis, cell, runtime, attachment, run, execution, console,\ndisplay, variable, and custom. Custom events describe occurrences\nrather than object state.\n",
  );

export type ObjectType = zod.input<typeof ObjectType>;
export type ObjectTypeOutput = zod.output<typeof ObjectType>;

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
    "A notebook occurrence with a producer-defined payload. It is replayed\nwhile event history is retained, but is never included in snapshots\nand does not belong to a run. The notebook is identified by the stream.\n",
  );

export type Custom = zod.input<typeof Custom>;
export type CustomOutput = zod.output<typeof Custom>;

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
      .string()
      .nullable()
      .describe(
        "The absolute path of the project's directory, written the way the host's operating system writes paths. Null when the project has no directory.",
      ),
    status: ProjectStatus,
    message: zod
      .string()
      .nullable()
      .describe(
        "Why the host stopped scanning. Null unless `status` is `partial`.",
      ),
    operations: zod
      .array(zod.string())
      .describe(
        "Operations this client may call on the project, today `notebook.create`. A subset of `host.operations`, narrowed by permission and never by state. The host sends the project again when it changes.",
      ),
  })
  .describe(
    "A project is a group of notebooks that the host presents together, usually a directory.",
  );

export type Project = zod.input<typeof Project>;
export type ProjectOutput = zod.output<typeof Project>;

export const Notebook = zod
  .object({
    id: NotebookId,
    project_id: ProjectId,
    path: zod
      .string()
      .nullable()
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
        "Operations this client may call on the notebook, such as `notebook.edit` or `runtime.start`. A subset of `host.operations`, narrowed by permission and never by state; whether a runtime is attached shows in the `runtime` object, and preconditions still apply when an operation is called. The host sends the notebook again when it changes.",
      ),
    updated_at: zod.iso
      .datetime({ offset: true })
      .nullable()
      .describe(
        "When the file was last modified, as of the host's last look at it. Null when the host does not know.",
      ),
  })
  .describe(
    "A notebook is a document and its results as the host knows them,\nusually backed by a file. Its kernel, when it has one, is a\nseparate object, the runtime. A host sends at most one `notebook`\nevent per second for the same notebook, since `updated_at`\nchanges on every save.\n",
  );

export type Notebook = zod.input<typeof Notebook>;
export type NotebookOutput = zod.output<typeof Notebook>;

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
      .string()
      .nullable()
      .describe(
        "A note about the current status, such as progress while `starting` or the reason when `failed`. Null otherwise.",
      ),
    marimo_version: zod
      .string()
      .nullable()
      .describe(
        "The version of marimo running the kernel. Null until the host knows it.",
      ),
    started_at: zod.iso
      .datetime({ offset: true })
      .describe("When this runtime started."),
  })
  .describe(
    "A runtime is a kernel attached to one notebook, and a notebook has\nat most one. It ends when a client or the host stops it or its\nprocess exits, and the host then sends `runtime.removed`. Every start and restart creates\na new runtime with a new id. Results carry their producer's runtime\nid so clients can tell which are live.\n",
  );

export type Runtime = zod.input<typeof Runtime>;
export type RuntimeOutput = zod.output<typeof Runtime>;

export const attachmentIdentityMax = 128;

export const attachmentIdentityRegExp = new RegExp("^[!-~]+$");
export const attachmentKindRegExp = new RegExp("^[a-z0-9-]+$");
export const attachmentNameMax = 256;

export const Attachment = zod
  .object({
    id: AttachmentId,
    notebook_id: NotebookId,
    identity: zod
      .string()
      .min(1)
      .max(attachmentIdentityMax)
      .regex(attachmentIdentityRegExp)
      .optional()
      .describe(
        "The opaque client identity supplied by `Marimo-Attachment-Identity`.\nOmitted when none was supplied. Consumers can group attachments\nwith the same identity within a host. It does not identify an\nindividual connection or change its lifetime.\n",
      ),
    kind: zod
      .string()
      .regex(attachmentKindRegExp)
      .describe(
        "What kind of thing is attached, supplied by `Marimo-Attachment-Kind`, such as `browser`, `editor`, or `agent`. Defaults to `client` when the header is omitted. Clients accept kinds they do not recognize.",
      ),
    name: zod
      .string()
      .max(attachmentNameMax)
      .nullable()
      .describe(
        "A label to show people, supplied by `Marimo-Attachment-Name`, such as the browser or editor's name. Null when the header is omitted or empty.",
      ),
    since: zod.iso.datetime({ offset: true }).describe("When it attached."),
  })
  .describe(
    "An attachment is a consumer connected to a notebook, such as a\nbrowser tab, an editor, or an agent. Opening the notebook's stream\ncreates one. It is removed when that connection closes, and not\nwhen the notebook's runtime stops or restarts. Each stream has its\nown attachment, even when several share a client identity.\n",
  );

export type Attachment = zod.input<typeof Attachment>;
export type AttachmentOutput = zod.output<typeof Attachment>;

export const Lifecycle = zod
  .enum(["queued", "running", "completed"])
  .describe(
    "Where a run or execution is in its lifecycle. An execution is\n`queued` until it starts, `running` while code executes, and\n`completed` once it has ended. How it ended is its `outcome`.\n",
  );

export type Lifecycle = zod.input<typeof Lifecycle>;
export type LifecycleOutput = zod.output<typeof Lifecycle>;

export const RunOutcome = zod
  .enum(["succeeded", "failed", "interrupted"])
  .describe(
    "How a run ended. `succeeded` means its work settled without an\nexecution error or interruption. `failed` means an execution\nfailed or the host could not finish the cycle. `interrupted`\nmeans the cycle was cut short by interruption, even if an earlier\nexecution failed. Execution outcomes retain their individual results.\n",
  );

export type RunOutcome = zod.input<typeof RunOutcome>;
export type RunOutcomeOutput = zod.output<typeof RunOutcome>;

export const Run = zod
  .object({
    id: RunId,
    notebook_id: NotebookId,
    caused_by: zod
      .union([ExecutionId, zod.null()])
      .describe(
        "The execution that caused this runtime-scheduled run. This records provenance, not membership in that execution's run, and does not extend the earlier run's lifetime. Null for a client request or when the runtime does not know the source.",
      ),
    status: Lifecycle.describe(
      "Queued until the first execution starts, running until the cycle has settled or been terminated, and completed once all member executions are terminal and no more can be scheduled in this run. A run can complete with no executions.",
    ),
    outcome: zod
      .union([RunOutcome, zod.null()])
      .describe(
        "Null until completed, then final. Published with the terminal status and completed_at. An execution failure does not complete a run while other work remains. Interruption must have taken effect, not merely been requested.",
      ),
    started_at: zod.iso
      .datetime({ offset: true })
      .nullable()
      .describe("When the first execution started. Null if none has started."),
    completed_at: zod.iso
      .datetime({ offset: true })
      .nullable()
      .describe("When the run ended. Null until the run is `completed`."),
  })
  .describe(
    "One bounded cycle of notebook work initiated by an action. It\nincludes synchronous callbacks and reactive work owned and awaited\nby the runtime's scheduler. Context inherited by an independent task\nrecords provenance, not ownership of the cycle. The host completes it\nonly after all member executions have ended and scheduling for the\ncycle has finished. It never reopens or acquires new executions.\nIndependently triggered later work starts another run, even when\nits cause belongs to an earlier run. Every consumer attached to\nthe notebook sees it.\n\nRetention is up to the host and independent of replay history.\nHosts SHOULD retain ephemeral results briefly after completion to\nallow reconnection. Runs, executions, and items each have removal\nevents; a cell result may outlive its run.\n",
  );

export type Run = zod.input<typeof Run>;
export type RunOutput = zod.output<typeof Run>;

export const DisplayData = zod
  .object({
    mimetype: zod
      .string()
      .describe("The format of `data`, such as `text/html` or `image/png`."),
    data: zod
      .string()
      .describe(
        "The rendered value. JSON mimetypes are encoded as text; binary mimetypes are base64. Never a URL only the runtime can serve.",
      ),
  })
  .describe("A rendered value.");

export type DisplayData = zod.input<typeof DisplayData>;
export type DisplayDataOutput = zod.output<typeof DisplayData>;

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

export const Variable = zod
  .object({
    id: ItemId,
    execution_id: ExecutionId.describe("The execution that bound the name."),
    name: zod.string().describe("The name in the namespace."),
    revision: Revision,
    type: zod
      .string()
      .nullable()
      .describe(
        "The runtime's label for the value's type. A host may leave it null.",
      ),
    preview: zod
      .string()
      .nullable()
      .describe("A short rendering of the value. A host may leave it null."),
  })
  .describe(
    "A name a cell's execution bound in the notebook's namespace, with\nthe revision of its value. The execution binds it as it ends, and\nthe item is removed with the execution. An update, as when a\nstate setter runs or a client sets a value, advances the revision\nwithout binding again, and the producer sends the item again with\nthe same id. Hosts publish a cell execution's variables before its\n`completed` status, and remove a cell's previous execution and\nits items before publishing the next one. A scratch execution's\nnames live only while it runs, so it publishes no variables.\n",
  );

export type Variable = zod.input<typeof Variable>;
export type VariableOutput = zod.output<typeof Variable>;

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
        "The producer's identifier, scoped by source. Open; this protocol defines `exception`, `interrupted`, and `internal` for executions, and reserves `multiple-definitions` and `cycle-dependencies` for analysis, because every host schedules them the same way. Clients show unrecognized kinds as plain errors.",
      ),
    message: zod
      .string()
      .describe("A description of the error to show people."),
    source: zod
      .string()
      .nullable()
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
      .string()
      .nullable()
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

export const Outcome = zod
  .union([ValueOutcome, ErrorOutcome, InterruptedOutcome])
  .describe(
    "How an execution ended, tagged on `kind`. A `value` carries the\nexecution's value as last rendered; while the execution is\nrunning it is the value so far, and it is final once the\nexecution is `completed`. An `error` carries the error that ended it.\nAn `interrupted` execution was cancelled before or during execution. Other\nkinds are defined by later versions of this protocol.\n",
  );

export type Outcome = zod.input<typeof Outcome>;
export type OutcomeOutput = zod.output<typeof Outcome>;

export const Etag = zod
  .string()
  .describe(
    "An identifier derived from content, so that every host, kernel,\nand store computes the same value for the same state. It is the\nfirst 16 hexadecimal characters, in lower case, of SHA-256 over\nthe UTF-8 encoding of a canonical text. Each etag says what its\ntext is; a text made of several values is those values joined by\nnewlines. Clients do not compute etags. They read them from the\nstream and from responses, and send them back as preconditions.\n",
  );

export type Etag = zod.input<typeof Etag>;
export type EtagOutput = zod.output<typeof Etag>;

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
        "The execution in the same run that caused this one. Null for executions requested directly.",
      ),
    cell_id: zod
      .union([CellId, zod.null()])
      .describe(
        "The cell this execution belongs to. Null for scratch code, a cell outside the document.",
      ),
    code: zod
      .string()
      .nullable()
      .describe(
        "The submitted code for an execution with no cell. Null for a cell's execution; its source is available through the cell when the host exposes it.",
      ),
    code_hash: Etag.describe(
      "The `code_hash` of the code that was evaluated, computed as a cell's is.",
    ),
    depends_on: zod
      .record(zod.string(), zod.union([Revision, zod.null()]))
      .describe(
        "The variables the execution used, by name, each at the revision the runtime holds its result valid against. Null for a name no retained cell execution had bound. Empty while queued, stamped as the execution ends, and final from then on.",
      ),
    status: Lifecycle,
    outcome: zod
      .union([Outcome, zod.null()])
      .describe(
        "How the execution ended. Null while queued; while running, a value carries the display so far; final once completed.",
      ),
    started_at: zod.iso
      .datetime({ offset: true })
      .nullable()
      .describe(
        "When the code started executing. Null while queued and for an execution that never ran.",
      ),
    completed_at: zod.iso
      .datetime({ offset: true })
      .nullable()
      .describe("When the execution ended. Null until it is completed."),
  })
  .describe(
    "One cell evaluated within a run, or scratch code evaluated once.\nIt moves through `queued`, `running`, and `completed`, and ends with\none outcome. Side effects belong to the execution whose context\nproduced them; items can arrive after the execution is completed\nwhile it remains retained.\n",
  );

export type Execution = zod.input<typeof Execution>;
export type ExecutionOutput = zod.output<typeof Execution>;

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
    mimetype: zod
      .string()
      .describe("The format of `data`, such as `image/png`."),
    data: zod
      .string()
      .describe(
        "The rendered value. JSON mimetypes are encoded as text; binary mimetypes are base64. Never a URL only the runtime can serve.",
      ),
  })
  .describe(
    "A value an execution showed as a side effect, such as a figure\nfrom `plt.show()`. A producer replaces one by sending it again\nwith the same id, which is how a progress bar updates in place.\n",
  );

export type Display = zod.input<typeof Display>;
export type DisplayOutput = zod.output<typeof Display>;

export const CellConfig = zod
  .object({
    column: zod
      .int()
      .nullable()
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

export const Cell = zod
  .object({
    id: CellId,
    notebook_id: NotebookId,
    code: zod
      .string()
      .nullable()
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
      "Identifies code, name, and config together, and is the precondition for editing the cell. Its text is `code_hash`, `name`, and the config values `column`, `disabled`, `hide_code`, and `expand_output` in that order, each written as a JSON scalar such as `null`, `0`, or `true`.",
    ),
    code_hash: Etag.describe(
      "Identifies the code alone. Its text is the actual source, even when `code` is null. Withholding source does not change this hash, the cell or document etags, or their versions. Unchanged by renaming the cell or editing its config. Compare with an execution's `code_hash` to tell whether a result came from the current code without needing the source.",
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

export const Document = zod
  .object({
    notebook_id: NotebookId.describe("The notebook this document belongs to."),
    order: zod
      .array(CellId)
      .describe(
        "Cell ids in display order. A permutation of the notebook's cells, each appearing exactly once.",
      ),
    app_config: zod
      .record(zod.string(), zod.unknown())
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

export const HostMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    host: Host,
  })
  .describe(
    "The data of a `host` event. The host object, plus which request caused the event and when.",
  );

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
  .describe("A `host` event from a host stream.");

export type HostEvent = zod.input<typeof HostEvent>;
export type HostEventOutput = zod.output<typeof HostEvent>;

export const ProjectMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    project: Project,
  })
  .describe("The data of a `project` event. The project as it now is.");

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
  .describe("A `project` event from a host stream.");

export type ProjectEvent = zod.input<typeof ProjectEvent>;
export type ProjectEventOutput = zod.output<typeof ProjectEvent>;

export const NotebookMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    notebook: Notebook,
  })
  .describe("The data of a `notebook` event. The notebook as it now is.");

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
  .describe("A `notebook` event from a host stream.");

export type NotebookEvent = zod.input<typeof NotebookEvent>;
export type NotebookEventOutput = zod.output<typeof NotebookEvent>;

export const DocumentMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    document: Document,
  })
  .describe("The data of a `document` event. The document as it now is.");

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
  .describe("A `document` event from a host stream.");

export type DocumentEvent = zod.input<typeof DocumentEvent>;
export type DocumentEventOutput = zod.output<typeof DocumentEvent>;

export const AnalysisMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    analysis: Analysis,
  })
  .describe("The data of an `analysis` event. The analysis as it now is.");

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
  .describe("A `analysis` event from a host stream.");

export type AnalysisEvent = zod.input<typeof AnalysisEvent>;
export type AnalysisEventOutput = zod.output<typeof AnalysisEvent>;

export const CellMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    cell: Cell,
  })
  .describe("The data of a `cell` event. The cell as it now is.");

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
  .describe("A `cell` event from a host stream.");

export type CellEvent = zod.input<typeof CellEvent>;
export type CellEventOutput = zod.output<typeof CellEvent>;

export const RuntimeMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    runtime: Runtime,
  })
  .describe("The data of a `runtime` event. The runtime as it now is.");

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
  .describe("A `runtime` event from a host stream.");

export type RuntimeEvent = zod.input<typeof RuntimeEvent>;
export type RuntimeEventOutput = zod.output<typeof RuntimeEvent>;

export const AttachmentMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    attachment: Attachment,
  })
  .describe("The data of an `attachment` event. The attachment as it now is.");

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
  .describe("A `attachment` event from a host stream.");

export type AttachmentEvent = zod.input<typeof AttachmentEvent>;
export type AttachmentEventOutput = zod.output<typeof AttachmentEvent>;

export const RunMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    run: Run,
  })
  .describe("The data of a `run` event. The run as it now is.");

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
  .describe("A `run` event from a host stream.");

export type RunEvent = zod.input<typeof RunEvent>;
export type RunEventOutput = zod.output<typeof RunEvent>;

export const ExecutionMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    execution: Execution,
  })
  .describe("The data of an `execution` event. The execution as it now is.");

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
  .describe("A `execution` event from a host stream.");

export type ExecutionEvent = zod.input<typeof ExecutionEvent>;
export type ExecutionEventOutput = zod.output<typeof ExecutionEvent>;

export const ConsoleMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    console: Console,
  })
  .describe("The data of a `console` event. The item as it now is.");

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
  .describe("A `console` event from a host stream.");

export type ConsoleEvent = zod.input<typeof ConsoleEvent>;
export type ConsoleEventOutput = zod.output<typeof ConsoleEvent>;

export const DisplayMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    display: Display,
  })
  .describe("The data of a `display` event. The item as it now is.");

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
  .describe("A `display` event from a host stream.");

export type DisplayEvent = zod.input<typeof DisplayEvent>;
export type DisplayEventOutput = zod.output<typeof DisplayEvent>;

export const VariableMessage = zod
  .object({
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    variable: Variable,
  })
  .describe("The data of a `variable` event. The item as it now is.");

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
  .describe("A `variable` event from a host stream.");

export type VariableEvent = zod.input<typeof VariableEvent>;
export type VariableEventOutput = zod.output<typeof VariableEvent>;

export const CustomMessage = zod
  .object({
    custom: Custom,
    request_id: zod
      .string()
      .optional()
      .describe(
        "The `Idempotency-Key` of the request that caused this event. Omitted when no request did, and on snapshots unless that request's work is still in progress.",
      ),
    time: zod.iso
      .datetime({ offset: true })
      .describe("When the host emitted this event. Preserved on replay."),
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
  .describe("A `custom` event from a host stream.");

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
    time: zod.iso
      .datetime({ offset: true })
      .optional()
      .describe(
        "When the host made this change. Present on live and replayed events; omitted on snapshots.",
      ),
    id: zod.string().describe("The id of the object that was removed."),
  })
  .describe(
    "The data of a `project.removed`, `notebook.removed`,\n`cell.removed`, `runtime.removed`, `attachment.removed`,\n`run.removed`, `execution.removed`, `console.removed`,\n`display.removed`, or `variable.removed` event. The client deletes the object with this\nid; the event name says which kind it is. Removing a notebook\nremoves its document and cells with it, without events of their\nown; the document never has one.\n",
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
  .describe("A `project.removed` event from a host stream.");

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
  .describe("A `notebook.removed` event from a host stream.");

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
  .describe("A `cell.removed` event from a host stream.");

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
  .describe("A `runtime.removed` event from a host stream.");

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
  .describe("A `attachment.removed` event from a host stream.");

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
  .describe("A `run.removed` event from a host stream.");

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
  .describe("A `execution.removed` event from a host stream.");

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
  .describe("A `console.removed` event from a host stream.");

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
  .describe("A `display.removed` event from a host stream.");

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
  .describe("A `variable.removed` event from a host stream.");

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
    data: zod.object({}),
  })
  .describe("A `reset` event from a host stream.");

export type ResetEvent = zod.input<typeof ResetEvent>;
export type ResetEventOutput = zod.output<typeof ResetEvent>;

export const ReadyEvent = zod
  .object({
    event: zod.enum(["ready"]),
    id: zod
      .string()
      .min(1)
      .describe("The resume cursor. Omitted on snapshot and reset events."),
    data: zod.object({}),
  })
  .describe("A `ready` event from a host stream.");

export type ReadyEvent = zod.input<typeof ReadyEvent>;
export type ReadyEventOutput = zod.output<typeof ReadyEvent>;

export const Event = zod
  .union([
    HostEvent,
    ProjectEvent,
    NotebookEvent,
    DocumentEvent,
    AnalysisEvent,
    CellEvent,
    RuntimeEvent,
    AttachmentEvent,
    RunEvent,
    ExecutionEvent,
    ConsoleEvent,
    DisplayEvent,
    VariableEvent,
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
    "A record, removal, or control message from a host stream.\nThe data is decoded JSON. Snapshot records and reset events omit\nthe cursor; ready and live events carry it. Unknown event names\nbelong to later versions or host extensions.\n",
  );

export type Event = zod.input<typeof Event>;
export type EventOutput = zod.output<typeof Event>;

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

export const editConflictChangeMin = 0;

export const EditConflict = zod
  .object({
    change: zod
      .int()
      .min(editConflictChangeMin)
      .describe(
        "The index of the stale change in the request's `changes`, or of the stale cell in a run's `cells`. `0` for a save with a stale `If-Match`.",
      ),
    cell: zod
      .union([Cell, zod.null()])
      .describe(
        "The cell the change named, as it now is. Null when the document does not have it, or when the change named the order.",
      ),
    document: Document,
  })
  .describe(
    "The first stale change of an edit or run, and the state the host holds.",
  );

export type EditConflict = zod.input<typeof EditConflict>;
export type EditConflictOutput = zod.output<typeof EditConflict>;

export const problemStatusMin = 400;
export const problemStatusMax = 599;

export const Problem = zod
  .object({
    type: zod
      .string()
      .describe(
        "What kind of problem this is, as a URI. The kinds this\nprotocol defines all start with `tag:marimo.io,2026:host/` and\nend with one of `invalid-request` (400), `unauthorized` (401),\n`forbidden` (403), `not-found` (404), `method-not-allowed`\n(405), `not-acceptable` (406), `conflict` (409), `no-runtime`\n(409), `decision-required` (409), `internal` (500), or\n`unsupported-operation` (501). A client that sees a kind it\ndoes not recognize falls back to `status`.\n",
      ),
    title: zod
      .string()
      .describe("A short, human-readable name for the kind of problem."),
    status: zod
      .int()
      .min(problemStatusMin)
      .max(problemStatusMax)
      .describe("The HTTP status code of the response."),
    detail: zod
      .string()
      .optional()
      .describe("A human-readable explanation of what went wrong this time."),
    decisions: zod
      .array(Decision)
      .optional()
      .describe(
        "The choices the client has to make before the host can carry out the request. Only present for `decision-required`.",
      ),
    edit: EditConflict.optional().describe(
      "Which change was stale and what the host holds instead. Only present for a `conflict` answering an edit, a save, or a run of cells.",
    ),
  })
  .describe(
    "An error. Every error response has this one shape, following RFC\n9457, and is served as `application/problem+json`. `status`\nrepeats the HTTP status, and `type` says more precisely what went\nwrong. `decisions` appears only when `type` is\n`tag:marimo.io,2026:host/decision-required`. A client ignores\nmembers it does not recognize. An error never contains a token.\n",
  );

export type Problem = zod.input<typeof Problem>;
export type ProblemOutput = zod.output<typeof Problem>;

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

export const OpenNotebookResponse = zod.object({
  url: zod
    .string()
    .describe(
      "The URL the host used to show the notebook. It never contains the host's token.",
    ),
});

export type OpenNotebookResponse = zod.input<typeof OpenNotebookResponse>;
export type OpenNotebookResponseOutput = zod.output<
  typeof OpenNotebookResponse
>;

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

export const cellConfigInputColumnDefault = null;
export const cellConfigInputDisabledDefault = false;
export const cellConfigInputHideCodeDefault = false;
export const cellConfigInputExpandOutputDefault = false;

export const CellConfigInput = zod
  .object({
    column: zod.int().nullish().default(cellConfigInputColumnDefault),
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
    "A cell as a client writes it. Code must be a string, even when the host withholds source in cell records. Null is not an edit or a request to preserve existing source. The host derives the etags and the analysis.",
  );

export type CellInput = zod.input<typeof CellInput>;
export type CellInputOutput = zod.output<typeof CellInput>;

export const PutCell = zod
  .object({
    kind: zod.enum(["put_cell"]),
    base_etag: zod
      .string()
      .nullable()
      .describe(
        "The cell's etag as last read, `*` to skip the check, or null to create the cell. Null when the cell exists, or an etag when it does not, is a `conflict`.",
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

export const CellVersion = zod
  .object({
    etag: Etag,
    code_hash: Etag,
    version: zod.int().min(1).describe("The cell's version after the edit."),
  })
  .describe("A cell's etags and version after an edit.");

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

export const RequestedCell = zod.object({
  id: CellId,
  code_hash: Etag.optional().describe(
    "The cell's `code_hash` as last read. A cell whose code differs is a `conflict`. Absent, the cell runs as it is.",
  ),
});

export type RequestedCell = zod.input<typeof RequestedCell>;
export type RequestedCellOutput = zod.output<typeof RequestedCell>;

export const RunRequest = zod
  .object({
    code: zod
      .string()
      .optional()
      .describe("Python code to run as scratch code."),
    cells: zod
      .array(RequestedCell)
      .min(1)
      .optional()
      .describe(
        "Cells of the document to run, in no particular order. The runtime's execution configuration determines whether dependent cells run too.",
      ),
  })
  .describe("What to run, exactly one of `code` and `cells`.");

export type RunRequest = zod.input<typeof RunRequest>;
export type RunRequestOutput = zod.output<typeof RunRequest>;
