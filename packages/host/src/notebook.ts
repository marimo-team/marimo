/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import {
  CellId,
  CodeFingerprint,
  Etag,
  NotebookId,
  PositiveInt,
  ProjectId,
  Timestamp,
} from "./common.ts";

export const Notebook = Schema.Struct({
  id: NotebookId,
  project_id: ProjectId,
  path: Schema.NullOr(Schema.String),
  name: Schema.String,
  operations: Schema.Array(Schema.String),
  updated_at: Schema.NullOr(Timestamp),
}).annotate({ identifier: "Notebook" });
export type Notebook = typeof Notebook.Type;
export const CreateNotebookRequest = Schema.Struct({
  project_id: ProjectId,
  path: Schema.optionalKey(Schema.String),
  name: Schema.optionalKey(Schema.String),
}).annotate({
  identifier: "CreateNotebookRequest",
  description:
    "A project with a root requires path; one without a root requires name.",
});
export type CreateNotebookRequest = typeof CreateNotebookRequest.Type;
export const UpdateNotebookRequest = Schema.Struct({
  path: Schema.optionalKey(Schema.String),
  name: Schema.optionalKey(Schema.String),
})
  .check(
    Schema.makeFilter(
      (value) => value.path !== undefined || value.name !== undefined,
      {
        expected: "at least one of path or name",
        toJsonSchema: () => ({
          anyOf: [{ required: ["path"] }, { required: ["name"] }],
        }),
      },
    ),
  )
  .annotate({ identifier: "UpdateNotebookRequest" });
export type UpdateNotebookRequest = typeof UpdateNotebookRequest.Type;
export const OpenNotebookResponse = Schema.Struct({
  url: Schema.String,
}).annotate({ identifier: "OpenNotebookResponse" });
export type OpenNotebookResponse = typeof OpenNotebookResponse.Type;
export const CellConfig = Schema.Struct({
  column: Schema.NullOr(Schema.Int),
  disabled: Schema.Boolean,
  hide_code: Schema.Boolean,
  expand_output: Schema.Boolean,
}).annotate({ identifier: "CellConfig" });
export type CellConfig = typeof CellConfig.Type;
export const Cell = Schema.Struct({
  id: CellId,
  notebook_id: NotebookId,
  code: Schema.NullOr(Schema.String),
  name: Schema.String,
  config: CellConfig,
  etag: Etag,
  code_fingerprint: CodeFingerprint,
  version: PositiveInt,
}).annotate({ identifier: "Cell" });
export type Cell = typeof Cell.Type;
export const Document = Schema.Struct({
  notebook_id: NotebookId,
  order: Schema.Array(CellId),
  app_config: Schema.Record(Schema.String, Schema.Unknown),
  etag: Etag,
  saved_etag: Schema.NullOr(Etag),
  order_etag: Etag,
  app_config_etag: Etag,
  version: PositiveInt,
}).annotate({ identifier: "Document" });
export type Document = typeof Document.Type;
