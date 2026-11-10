/* Copyright 2026 Marimo. All rights reserved. */

/** Runs, their executions, and how each one ended. */

import { Schema } from "effect";
import { Integer } from "../internal/schema.ts";
import {
  NotebookId,
  RuntimeId,
  RunId,
  ExecutionId,
  CellId,
  CodeFingerprint,
  Timestamp,
} from "./Ids.ts";

export const Lifecycle = Schema.Literals([
  "queued",
  "running",
  "completed",
]).annotate({
  description:
    "Where a run or execution is in its lifecycle. An execution is\n`queued` until it starts, `running` while code executes, and\n`completed` once it has ended. A run is `queued` until its first\nexecution starts, `running` until its cycle has settled or been cut\nshort, and `completed` once no more work can join it. How either\nended is its `outcome`.\n",
  identifier: "Lifecycle",
});

export const RunOutcome = Schema.Literals([
  "succeeded",
  "failed",
  "interrupted",
]).annotate({
  description:
    "How a run ended. `succeeded` means its work settled without an\nexecution error or interruption. `failed` means an execution's\ncode raised or the host could not finish the cycle. An execution\nskipped because of another cell does not fail its run. `interrupted`\nmeans the cycle was cut short by interruption, even if an earlier\nexecution failed. Execution outcomes retain their individual results.\n",
  identifier: "RunOutcome",
});

export const Run = Schema.Struct({
  id: RunId,
  notebook_id: NotebookId,
  runtime_id: RuntimeId.annotateKey({
    description: "The runtime that produced this run.",
  }),
  cells: Schema.Array(CellId).annotateKey({
    description:
      "The cells the run was requested for. Fixed when the run is accepted, so a client can tell which cells a queued run will reach before the runtime has planned their executions. Each one's execution in this run reports the fingerprint of the source accepted for it. Empty for scratch code and for a run the runtime scheduled itself.",
  }),
  status: Lifecycle.annotateKey({
    description:
      "Queued until the first execution starts, running until the cycle has settled or been terminated, and completed once all member executions are terminal and no more can be scheduled in this run. A run can complete with no executions.",
  }),
  outcome: Schema.NullOr(RunOutcome).annotateKey({
    description:
      "Null until completed, then final. Published with the terminal status and completed_at. An execution failure does not complete a run while other work remains. Interruption must have taken effect, not merely been requested.",
  }),
  started_at: Schema.NullOr(Timestamp).annotateKey({
    description: "When the first execution started. Null if none has started.",
  }),
  completed_at: Schema.NullOr(Timestamp).annotateKey({
    description: "When the run ended. Null until the run is `completed`.",
  }),
}).annotate({
  description:
    "One bounded cycle of notebook work initiated by an action. It\nincludes synchronous callbacks and reactive work owned and awaited\nby the runtime's scheduler. Context inherited by an independent task\nrecords provenance, not ownership of the cycle. The host completes it\nonly after all member executions have ended and scheduling for the\ncycle has finished. Completion fixes its status and execution membership.\nIndependently triggered later work starts another run, even when\nits cause belongs to an earlier run. Every consumer attached to\nthe notebook sees it.\n\nRetention is up to the host and independent of replay history.\nHosts SHOULD retain ephemeral results briefly after completion to\nallow reconnection. Runs, executions, and items each have removal\nevents; a cell result may outlive its run.\n",
  identifier: "Run",
});

export const DisplayData = Schema.Struct({
  mimetype: Schema.String.annotateKey({
    description: "The format of `data`, such as `text/html` or `image/png`.",
    examples: ["text/html"],
  }),
  data: Schema.String.annotateKey({
    description:
      "The rendered value, embedded so clients can display it independently of the runtime. JSON mimetypes are encoded as text and binary mimetypes as base64.",
  }),
}).annotate({
  description: "A rendered value.",
  identifier: "DisplayData",
});

export const Revision = Schema.Struct({
  execution: ExecutionId.annotateKey({
    description:
      "The execution whose evaluation produced the value. Usually the variable's `execution_id`, and earlier when the runtime carried the value forward.",
  }),
  update: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
    description:
      "How many times the value has been updated since it was produced. Zero at binding.",
  }),
}).annotate({
  description:
    "A variable's value at a point in time. Two revisions are equal\nwhen `execution` and `update` are equal. Clients compare\nrevisions for equality.\n",
  identifier: "Revision",
});

export const Position = Schema.Struct({
  line: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
    description: "Zero-based line within the code.",
  }),
  character: Integer.check(Schema.isGreaterThanOrEqualTo(0)).annotateKey({
    description: "Zero-based offset in the line, in UTF-16 code units.",
  }),
}).annotate({
  description: "A position within code, using LSP coordinates.",
  identifier: "Position",
});

export const Range = Schema.Struct({
  start: Position,
  end: Position.annotateKey({
    description: "Exclusive end. Equal to start when only a point is known.",
  }),
}).annotate({
  description: "A span within code.",
  identifier: "Range",
});

export const Related = Schema.Struct({
  cell_id: CellId,
  range: Schema.NullOr(Range).annotateKey({
    description: "Where in that cell, when known.",
  }),
  message: Schema.String.annotateKey({
    description: "What that cell contributes, such as `reads x from C`.",
  }),
}).annotate({
  description: "A cell involved in an error, possibly the one carrying it.",
  identifier: "Related",
});

export const Error = Schema.Struct({
  kind: Schema.String.annotateKey({
    description:
      "The producer's identifier, scoped by source. Open; this protocol defines `exception`, `interrupted`, and `internal` for executions. Clients show unrecognized kinds as plain errors.",
  }),
  message: Schema.String.annotateKey({
    description: "A description of the error to show people.",
  }),
  source: Schema.NullOr(Schema.String).annotateKey({
    description:
      "Who produced it, such as `marimo` or a SQL analyzer. Scopes kind.",
  }),
  severity: Schema.Literals([
    "error",
    "warning",
    "information",
    "hint",
  ]).annotateKey({
    description:
      "Error unless the producer says otherwise. Only error affects scheduling.",
  }),
  range: Schema.NullOr(Range).annotateKey({
    description: "Where in the code, when known.",
  }),
  name: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The exception class, such as `ZeroDivisionError`. Set when kind is exception, null otherwise.",
  }),
  traceback: Schema.NullOr(DisplayData).annotateKey({
    description:
      "The traceback as rendered by the runtime, plain text or HTML by its mimetype. Null when unavailable or not shown.",
  }),
  related: Schema.Array(Related).annotateKey({
    description:
      "Every involved cell, including this one, in canonical order. Each copy of a cross-cell error carries the same list; clients deduplicate on kind and related cell ids. Empty when the error involves this code alone.",
  }),
}).annotate({
  description:
    "A problem shaped like an LSP diagnostic. Further members are\nkind-specific, as in Problem Details, and a client ignores\nmembers it does not know.\n",
  identifier: "Error",
});

export const ValueOutcome = Schema.Struct({
  kind: Schema.Literal("value"),
  display: Schema.NullOr(DisplayData).annotateKey({
    description:
      "The value as last rendered. Replaced as it grows. Null when the code produced no value.",
  }),
}).annotate({ identifier: "ValueOutcome" });

export const ErrorOutcome = Schema.Struct({
  kind: Schema.Literal("error"),
  error: Error,
}).annotate({ identifier: "ErrorOutcome" });

export const InterruptedOutcome = Schema.Struct({
  kind: Schema.Literal("interrupted"),
}).annotate({ identifier: "InterruptedOutcome" });

export const SkippedOutcome = Schema.Struct({
  kind: Schema.Literal("skipped"),
  reason: Schema.String.annotateKey({
    description:
      "Why the cell did not evaluate. The string is open. This protocol\ndefines `upstream-failed`, a cell it depends on did not produce\nits value because it raised or could not resolve a reference,\n`upstream-stopped`, a cell it depends on stopped the cycle on\npurpose, and `superseded`, a later execution of the same cell\nreplaced this one before it started because the cell's source\nchanged while it waited. Clients show unrecognized reasons as\nskipped, with the message.\n",
  }),
  message: Schema.String.annotateKey({
    description: "Why the cell did not run, to show in place of its output.",
  }),
  related: Schema.Array(Related).annotateKey({
    description: "The cells involved, the cause first and this cell last.",
  }),
}).annotate({ identifier: "SkippedOutcome" });

export const Outcome = Schema.Union([
  ValueOutcome,
  ErrorOutcome,
  InterruptedOutcome,
  SkippedOutcome,
]).annotate({
  description:
    "How an execution ended, tagged on `kind`. A `value` carries the\nexecution's value as last rendered; while the execution is\nrunning it is the value so far, and it is final once the\nexecution is `completed`. An `error` carries the error that ended it.\nAn `interrupted` execution was cancelled before or during execution.\nA `skipped` execution did not evaluate because of another cell; it\nhas no value and binds no variables. Other kinds are defined by\nlater versions of this protocol.\n",
  identifier: "Outcome",
});

export const Execution = Schema.Struct({
  id: ExecutionId,
  run_id: Schema.NullOr(RunId).annotateKey({
    description:
      "The run that owns this execution. Every live execution belongs to exactly one run. May name a run the host has dropped. Null only for a restored result whose run is unknown.",
  }),
  runtime_id: Schema.NullOr(RuntimeId).annotateKey({
    description:
      "The runtime that produced this execution. Live when it equals the current runtime's id. Null when the producer is unknown.",
  }),
  caused_by: Schema.NullOr(ExecutionId).annotateKey({
    description:
      "The execution in the same run whose code was running when this one was scheduled, such as scratch code that ran a cell, set a UI element's value, or wrote state, and the cells that reacted to it. Null for an execution a client requested and for the cells that reacted to one.",
  }),
  cell_id: Schema.NullOr(CellId).annotateKey({
    description:
      "The cell this execution belongs to. Null for scratch code, a cell outside the document.",
  }),
  code: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The submitted code for an execution with no cell. Null for a cell's execution; its source is available through the cell when the host exposes it.",
  }),
  code_fingerprint: CodeFingerprint.annotateKey({
    description:
      "Fingerprint of the code the execution evaluates. Fixed when the execution is published, while it is still queued.",
  }),
  depends_on: Schema.Record(Schema.String, Schema.NullOr(Revision)).annotateKey(
    {
      description:
        "The variable revisions this result is valid against, keyed by name. Null for a name no retained cell execution had bound. Empty while queued, stamped as the execution ends, and final from then on.",
    },
  ),
  status: Lifecycle,
  outcome: Schema.NullOr(Outcome).annotateKey({
    description:
      "How the execution ended. Null while queued; while running, a value carries the display so far; final once completed.",
  }),
  started_at: Schema.NullOr(Timestamp).annotateKey({
    description:
      "When the code started executing. Null while queued or if the execution completed before starting.",
  }),
  completed_at: Schema.NullOr(Timestamp).annotateKey({
    description: "When the execution ended. Null until it is completed.",
  }),
}).annotate({
  description:
    "One cell evaluated within a run, or scratch code evaluated once.\nIt moves through `queued`, `running`, and `completed`, and ends with\none outcome. Side effects belong to the execution whose context\nproduced them, and items can arrive after completion while the\nexecution remains retained. Each new input belongs to a running\nexecution. Input calls from completed or removed executions raise\n`EOFError` in the calling code. Exactly one of `cell_id` and `code`\nis null: a cell's execution carries the cell and no code, and a\nscratch execution carries its code and no cell.\n",
  identifier: "Execution",
});
