/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { DiagnosticSeverity } from "../../internal/schema.ts";
import { Range, Related } from "../../model/Execution.ts";
import { CellId, Etag, NotebookId } from "../../model/Ids.ts";
import { defineFeature } from "../defineFeature.ts";

export const CellDiagnostic = Schema.Struct({
  source: Schema.String.annotateKey({
    description: "Analyzer that defines the kind.",
  }),
  kind: Schema.String.annotateKey({
    description: "Identifier scoped to the source.",
  }),
  severity: DiagnosticSeverity,
  message: Schema.String,
  range: Schema.NullOr(Range).annotateKey({
    description:
      "Span in this cell, or null for a whole-cell finding or unknown location.",
  }),
  related: Schema.Array(Related),
}).annotate({ identifier: "CellDiagnostic" });

export const CellAnalysis = Schema.Struct({
  defs: Schema.Array(Schema.String).annotateKey({
    description: "Names this cell defines.",
  }),
  refs: Schema.Array(Schema.String).annotateKey({
    description: "Names this cell reads from other cells.",
  }),
  parents: Schema.optionalKey(
    Schema.Array(CellId).annotateKey({
      description:
        "Cell IDs of the direct dependencies in this revision. An empty list means no parents. Omitted when the host does not provide the graph.",
    }),
  ),
  diagnostics: Schema.Array(CellDiagnostic).annotateKey({
    description:
      "Diagnostics about the code. Only an `error` affects scheduling. `multiple-definitions` lists the definers in `related`, each `range` at its definition; `cycle-dependencies` lists the cycle. Both are reported on every cell involved, differing only in `range`. Every other kind belongs to the analyzer named in `source`.",
  }),
}).annotate({
  description:
    "The definitions, references, direct dependencies, and diagnostics for one cell at this document revision.",
  identifier: "CellAnalysis",
});

export const Analysis = Schema.Struct({
  notebook_id: NotebookId.annotateKey({
    description: "The notebook this analysis belongs to.",
  }),
  document_etag: Etag.annotateKey({
    description:
      "The document revision this analysis describes. Equal to the document's `etag` while the analysis is current.",
  }),
  cells: Schema.Record(Schema.String, CellAnalysis).annotateKey({
    description: "Every cell of that revision, by id.",
  }),
}).annotate({
  description:
    "What a document's cells imply, computed together over one\nrevision of the document so that cross-cell errors agree. One\nper notebook, and removed with it. It follows the document it\ndescribes, and `document_etag` says which revision that is.\n",
  identifier: "Analysis",
});

export default defineFeature({
  objects: [
    {
      kind: "analysis",
      schema: Analysis,
      streams: ["notebook"],
      removable: false,
    },
  ],
});
