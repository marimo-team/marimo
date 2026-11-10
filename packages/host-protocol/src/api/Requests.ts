/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { Integer, closedStruct } from "../internal/schema.ts";
import { ProjectId, CellId, Etag, CodeFingerprint } from "../model/Ids.ts";
import { Document } from "../model/Document.ts";

export const CreateNotebookRequest = Schema.Struct({
  project_id: ProjectId,
  path: Schema.optionalKey(
    Schema.String.annotateKey({
      description:
        "Where to put the file, relative to the project root and written the way the host's operating system writes paths.",
      examples: ["analysis.py"],
    }),
  ),
  name: Schema.optionalKey(
    Schema.String.annotateKey({
      description:
        "A label to show people. In a project with a root it defaults to the filename.",
    }),
  ),
}).annotate({
  description:
    "The notebook's own fields, minus what the host assigns. A project with a root requires `path`; one without requires `name`.",
  identifier: "CreateNotebookRequest",
});

export const UpdateNotebookRequest = Schema.Struct({
  path: Schema.optionalKey(
    Schema.String.annotateKey({
      description:
        "The new location, relative to the project root and written the way the host's operating system writes paths.",
    }),
  ),
  name: Schema.optionalKey(
    Schema.String.annotateKey({ description: "The new label to show people." }),
  ),
})
  .check(Schema.isMinProperties(1))
  .annotate({
    description: "The fields to change. At least one is present.",
    identifier: "UpdateNotebookRequest",
  });

export const OpenNotebookResponse = Schema.Struct({
  url: Schema.String.annotateKey({
    description:
      "The URL the host used to show the notebook, with the host's token omitted.",
  }),
}).annotate({ identifier: "OpenNotebookResponse" });

export const InputReplyRequest = Schema.Struct({
  value: Schema.String.annotateKey({
    description:
      "The text to deliver to the input exactly as submitted, including an empty string when the answer is empty.",
  }),
}).annotate({
  description: "The answer to one pending input.",
  identifier: "InputReplyRequest",
});

export const StartRuntimeRequest = Schema.Struct({
  decisions: Schema.optionalKey(
    Schema.Record(Schema.String, Schema.String).annotateKey({
      description:
        "Answers to the questions in a `decision-required` problem.\nEach key is a decision's `id` and each value is the `id` of\nthe chosen option. A client that already knows its choices can\nsend them the first time.\n",
      examples: [{ environment: "sandbox" }],
    }),
  ),
}).annotate({ identifier: "StartRuntimeRequest" });

export const CellConfigInput = Schema.Struct({
  column: Schema.optionalKey(
    Schema.NullOr(Integer).annotateKey({ default: null }),
  ),
  disabled: Schema.optionalKey(Schema.Boolean.annotateKey({ default: false })),
  hide_code: Schema.optionalKey(Schema.Boolean.annotateKey({ default: false })),
  expand_output: Schema.optionalKey(
    Schema.Boolean.annotateKey({ default: false }),
  ),
}).annotate({
  description:
    "A cell's settings as a client writes them. A field left out takes its default.",
  identifier: "CellConfigInput",
});

export const CellInput = Schema.Struct({
  id: CellId.annotateKey({
    description: "The cell's id. A client chooses the id of a cell it creates.",
  }),
  code: Schema.String.annotateKey({ description: "The cell's source code." }),
  name: Schema.optionalKey(
    Schema.String.annotateKey({
      description: "The cell's name. `_` for an anonymous cell.",
      default: "_",
    }),
  ),
  config: Schema.optionalKey(CellConfigInput),
}).annotate({
  description:
    "A cell as a client writes it. Code must be a string, even when the host withholds source in cell records. Null is not an edit or a request to preserve existing source. The host derives the etags.",
  identifier: "CellInput",
});

export const PutCell = Schema.Struct({
  kind: Schema.Literal("put_cell"),
  base_etag: Schema.NullOr(Schema.String).annotateKey({
    description:
      "The cell's etag as last read, `*` to skip the check, or null to create the cell. Null when the cell exists, or an etag when it does not, is `precondition-failed`.",
  }),
  cell: CellInput,
  after: Schema.optionalKey(
    CellId.annotateKey({
      description:
        "The cell a created cell goes after. Ignored for an existing cell.",
    }),
  ),
  before: Schema.optionalKey(
    CellId.annotateKey({
      description:
        "The cell a created cell goes before. Ignored for an existing cell. With neither `after` nor `before`, a created cell goes at the end.",
    }),
  ),
}).annotate({
  description: "Replaces a whole cell, or creates one.",
  identifier: "PutCell",
});

export const DeleteCell = Schema.Struct({
  kind: Schema.Literal("delete_cell"),
  id: CellId.annotateKey({ description: "The cell to remove." }),
  base_etag: Schema.String.annotateKey({
    description: "The cell's etag as last read, or `*`.",
  }),
}).annotate({
  description: "Removes a cell.",
  identifier: "DeleteCell",
});

export const SetOrder = Schema.Struct({
  kind: Schema.Literal("set_order"),
  base_etag: Schema.String.annotateKey({
    description: "The document's `order_etag` as last read, or `*`.",
  }),
  order: Schema.Array(CellId).annotateKey({
    description:
      "Every cell id exactly once, in the new order, counting cells this edit creates and leaving out cells it deletes.",
  }),
}).annotate({
  description: "Replaces the cell order.",
  identifier: "SetOrder",
});

export const Change = Schema.Union([PutCell, DeleteCell, SetOrder]).annotate({
  description: "One change to the document, tagged on `kind`.",
  identifier: "Change",
});

export const EditRequest = Schema.Struct({
  changes: Schema.Array(Change).annotateKey({
    description: "The changes, applied in order as one unit.",
  }),
}).annotate({ identifier: "EditRequest" });

export const CellVersion = Schema.Struct({
  etag: Etag,
  code_fingerprint: CodeFingerprint,
  version: Integer.check(Schema.isGreaterThanOrEqualTo(1)).annotateKey({
    description: "The cell's version after the edit.",
  }),
}).annotate({
  description: "A cell's etag, code fingerprint, and version after an edit.",
  identifier: "CellVersion",
});

export const EditResponse = Schema.Struct({
  document: Document,
  cells: Schema.Record(Schema.String, Schema.NullOr(CellVersion)).annotateKey({
    description:
      "The version of each cell the request created or changed, by id, and null for each cell it deleted.",
  }),
}).annotate({
  description:
    "The document as an edit or save left it, or at a later revision, and the cells it touched.",
  identifier: "EditResponse",
});

export const SaveRequest = Schema.Struct({
  decisions: Schema.optionalKey(
    Schema.Record(Schema.String, Schema.String).annotateKey({
      description:
        "Answers to the questions in a `decision-required` problem, as for `runtime.start`.",
    }),
  ),
}).annotate({
  description:
    "What a save needs from the client, which is nothing until the host asks a question. `{}` is the usual body.",
  identifier: "SaveRequest",
});

export const RequestedCell = Schema.Struct({
  id: CellId,
  etag: Schema.optionalKey(
    Etag.annotateKey({
      description:
        "The cell's `etag` as last read. A cell whose source, name, or config differs is `precondition-failed`. Absent, the cell runs as it is.",
    }),
  ),
}).annotate({ identifier: "RequestedCell" });

export const RunRequest = closedStruct({
  cells: Schema.Array(RequestedCell).check(Schema.isMinLength(1)).annotateKey({
    description:
      "Cells to run by id. The notebook's execution settings determine their order and whether dependent cells run too.",
  }),
}).annotate({
  description: "Notebook cells to run.",
  identifier: "RunRequest",
});

export const ExecuteRequest = closedStruct({
  code: Schema.String.annotateKey({
    description:
      "Python code that can read the notebook's current values.\nAssignments stay local to the call. Changes to shared objects persist.\n",
  }),
}).annotate({
  description: "Python code to execute with access to notebook values.",
  identifier: "ExecuteRequest",
});
