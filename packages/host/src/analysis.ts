/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { Etag, NotebookId } from "./common.ts";
import { ObjectType } from "./catalog.ts";
import { Diagnostic } from "./execution.ts";

export const CellAnalysis = Schema.Struct({
  defs: Schema.Array(Schema.String),
  refs: Schema.Array(Schema.String),
  errors: Schema.Array(Diagnostic),
}).annotate({
  identifier: "CellAnalysis",
  description:
    "Experimental (analysis). Definitions, references, and diagnostics computed for a cell.",
});
export type CellAnalysis = typeof CellAnalysis.Type;
export const Analysis = Schema.Struct({
  notebook_id: NotebookId,
  document_etag: Etag,
  cells: Schema.Record(Schema.String, CellAnalysis),
}).annotate({
  identifier: "Analysis",
  description:
    "Experimental (analysis). Analysis of every cell at one document revision.",
});
export type Analysis = typeof Analysis.Type;

export const AnalysisObjectType = Schema.Literals([
  ...ObjectType.literals,
  "analysis",
]).annotate({ identifier: "ObjectType" });
export type AnalysisObjectType = typeof AnalysisObjectType.Type;
