/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import {
  CellId,
  CodeFingerprint,
  Etag,
  NonNegativeInt,
  PositiveInt,
} from "./common.ts";
import { Cell, Document } from "./notebook.ts";

export const CellConfigInput = Schema.Struct({
  column: Schema.optionalKey(
    Schema.NullOr(Schema.Int).annotate({ default: null }),
  ),
  disabled: Schema.optionalKey(Schema.Boolean.annotate({ default: false })),
  hide_code: Schema.optionalKey(Schema.Boolean.annotate({ default: false })),
  expand_output: Schema.optionalKey(
    Schema.Boolean.annotate({ default: false }),
  ),
}).annotate({ identifier: "CellConfigInput" });
export type CellConfigInput = typeof CellConfigInput.Type;
export const CellInput = Schema.Struct({
  id: CellId,
  code: Schema.String,
  name: Schema.optionalKey(Schema.String.annotate({ default: "_" })),
  config: Schema.optionalKey(CellConfigInput),
}).annotate({ identifier: "CellInput" });
export type CellInput = typeof CellInput.Type;
export const PutCell = Schema.Struct({
  kind: Schema.tag("put_cell"),
  base_etag: Schema.NullOr(Schema.String),
  cell: CellInput,
  after: Schema.optionalKey(CellId),
  before: Schema.optionalKey(CellId),
})
  .check(
    Schema.makeFilter(
      (value) => value.after === undefined || value.before === undefined,
      {
        expected: "at most one of after or before",
        toJsonSchema: () => ({ not: { required: ["after", "before"] } }),
      },
    ),
  )
  .annotate({ identifier: "PutCell" });
export type PutCell = typeof PutCell.Type;
export const DeleteCell = Schema.Struct({
  kind: Schema.tag("delete_cell"),
  id: CellId,
  base_etag: Schema.String,
}).annotate({ identifier: "DeleteCell" });
export type DeleteCell = typeof DeleteCell.Type;
export const SetOrder = Schema.Struct({
  kind: Schema.tag("set_order"),
  base_etag: Schema.String,
  order: Schema.Array(CellId),
}).annotate({ identifier: "SetOrder" });
export type SetOrder = typeof SetOrder.Type;
export const Change = Schema.Union([PutCell, DeleteCell, SetOrder]).annotate({
  identifier: "Change",
});
export type Change = typeof Change.Type;
export const EditRequest = Schema.Struct({
  changes: Schema.Array(Change),
}).annotate({ identifier: "EditRequest" });
export type EditRequest = typeof EditRequest.Type;
export const CellVersion = Schema.Struct({
  etag: Etag,
  code_fingerprint: CodeFingerprint,
  version: PositiveInt,
}).annotate({ identifier: "CellVersion" });
export type CellVersion = typeof CellVersion.Type;
export const EditResponse = Schema.Struct({
  document: Document,
  cells: Schema.Record(Schema.String, Schema.NullOr(CellVersion)),
}).annotate({ identifier: "EditResponse" });
export type EditResponse = typeof EditResponse.Type;
export const EditConflict = Schema.Struct({
  change: NonNegativeInt,
  cell: Schema.NullOr(Cell),
  document: Document,
}).annotate({ identifier: "EditConflict" });
export type EditConflict = typeof EditConflict.Type;
export const SaveRequest = Schema.Struct({
  decisions: Schema.optionalKey(Schema.Record(Schema.String, Schema.String)),
}).annotate({ identifier: "SaveRequest" });
export type SaveRequest = typeof SaveRequest.Type;
export const RequestedCell = Schema.Struct({
  id: CellId,
  etag: Schema.optionalKey(Etag),
}).annotate({ identifier: "RequestedCell" });
export type RequestedCell = typeof RequestedCell.Type;
export const RunRequest = Schema.Struct({
  code: Schema.optionalKey(Schema.String),
  cells: Schema.optionalKey(
    Schema.Array(RequestedCell).check(Schema.isMinLength(1)),
  ),
})
  .check(
    Schema.makeFilter(
      (value) => (value.code !== undefined) !== (value.cells !== undefined),
      {
        expected: "exactly one of code or cells",
        toJsonSchema: () => ({
          oneOf: [{ required: ["code"] }, { required: ["cells"] }],
        }),
      },
    ),
  )
  .annotate({ identifier: "RunRequest" });
export type RunRequest = typeof RunRequest.Type;
