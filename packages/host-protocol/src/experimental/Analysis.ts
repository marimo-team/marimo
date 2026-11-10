/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { derive } from "../Events.ts";
import * as Host from "../Host.ts";
import * as Objects from "../Objects.ts";
import * as S from "../Schemas.ts";

export const CellAnalysis = Schema.Struct({
  defs: Schema.Array(Schema.String).annotateKey({
    description: "Names this cell defines.",
  }),
  refs: Schema.Array(Schema.String).annotateKey({
    description: "Names this cell reads from other cells.",
  }),
  errors: Schema.Array(S.Error).annotateKey({
    description:
      "Diagnostics about the code. Only an `error` affects scheduling. `multiple-definitions` lists the definers in `related`, each `range` at its definition; `cycle-dependencies` lists the cycle. Both are reported on every cell involved, differing only in `range`. Every other kind belongs to the analyzer named in `source`.",
  }),
}).annotate({
  description:
    "What a cell's text implies: the names it defines and reads, which\nare the edges of the dependency graph, and the errors found in the\ntext alone or across the set of cells. A pure function of the\ncode, so two producers compute the same values.\n",
  identifier: "CellAnalysis",
});

export const Analysis = Schema.Struct({
  notebook_id: S.NotebookId.annotateKey({
    description: "The notebook this analysis belongs to.",
  }),
  document_etag: S.Etag.annotateKey({
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

/** The object table with the analysis object on the notebook stream. */
export const objects = [
  ...Objects.objects,
  {
    kind: "analysis",
    schema: Analysis,
    streams: ["notebook"],
    removable: false,
  },
] as const satisfies ReadonlyArray<Objects.ObjectKind>;

export const Api = Host.make(objects);

export const { NotebookEvent } = derive(objects);
export type NotebookEvent = typeof NotebookEvent.Type;
