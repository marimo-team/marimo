/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import {
  CellId,
  CodeFingerprint,
  ExecutionId,
  ItemId,
  NonNegativeInt,
  NotebookId,
  RunId,
  RuntimeId,
  Timestamp,
} from "./common.ts";

export const RuntimeStatus = Schema.Literals([
  "starting",
  "running",
  "terminating",
  "failed",
]).annotate({ identifier: "RuntimeStatus" });
export type RuntimeStatus = typeof RuntimeStatus.Type;
export const Runtime = Schema.Struct({
  id: RuntimeId,
  notebook_id: NotebookId,
  status: RuntimeStatus,
  message: Schema.NullOr(Schema.String),
  marimo_version: Schema.NullOr(Schema.String),
  started_at: Timestamp,
}).annotate({ identifier: "Runtime" });
export type Runtime = typeof Runtime.Type;
export const Lifecycle = Schema.Literals([
  "queued",
  "running",
  "completed",
]).annotate({ identifier: "Lifecycle" });
export type Lifecycle = typeof Lifecycle.Type;
export const RunOutcome = Schema.Literals([
  "succeeded",
  "failed",
  "interrupted",
]).annotate({ identifier: "RunOutcome" });
export type RunOutcome = typeof RunOutcome.Type;
export const Run = Schema.Struct({
  id: RunId,
  notebook_id: NotebookId,
  caused_by: Schema.NullOr(ExecutionId),
  status: Lifecycle,
  outcome: Schema.NullOr(RunOutcome),
  started_at: Schema.NullOr(Timestamp),
  completed_at: Schema.NullOr(Timestamp),
}).annotate({ identifier: "Run" });
export type Run = typeof Run.Type;
export const DisplayData = Schema.Struct({
  mimetype: Schema.String,
  data: Schema.String,
}).annotate({ identifier: "DisplayData" });
export type DisplayData = typeof DisplayData.Type;
export const Revision = Schema.Struct({
  execution: ExecutionId,
  update: NonNegativeInt,
}).annotate({ identifier: "Revision" });
export type Revision = typeof Revision.Type;
export const Variable = Schema.Struct({
  id: ItemId,
  execution_id: ExecutionId,
  name: Schema.String,
  revision: Revision,
  type: Schema.NullOr(Schema.String),
  preview: Schema.NullOr(Schema.String),
}).annotate({ identifier: "Variable" });
export type Variable = typeof Variable.Type;
export const Position = Schema.Struct({
  line: NonNegativeInt,
  character: NonNegativeInt,
}).annotate({ identifier: "Position" });
export type Position = typeof Position.Type;
export const Range = Schema.Struct({ start: Position, end: Position }).annotate(
  { identifier: "Range" },
);
export type Range = typeof Range.Type;
export const Related = Schema.Struct({
  cell_id: CellId,
  range: Schema.NullOr(Range),
  message: Schema.String,
}).annotate({ identifier: "Related" });
export type Related = typeof Related.Type;
export const Diagnostic = Schema.Struct({
  kind: Schema.String,
  message: Schema.String,
  source: Schema.NullOr(Schema.String),
  severity: Schema.Literals(["error", "warning", "information", "hint"]),
  range: Schema.NullOr(Range),
  name: Schema.NullOr(Schema.String),
  traceback: Schema.NullOr(DisplayData),
  related: Schema.Array(Related),
}).annotate({ identifier: "Error" });
export type Diagnostic = typeof Diagnostic.Type;
export const ValueOutcome = Schema.Struct({
  kind: Schema.tag("value"),
  display: Schema.NullOr(DisplayData),
}).annotate({ identifier: "ValueOutcome" });
export type ValueOutcome = typeof ValueOutcome.Type;
export const ErrorOutcome = Schema.Struct({
  kind: Schema.tag("error"),
  error: Diagnostic,
}).annotate({ identifier: "ErrorOutcome" });
export type ErrorOutcome = typeof ErrorOutcome.Type;
export const InterruptedOutcome = Schema.Struct({
  kind: Schema.tag("interrupted"),
}).annotate({ identifier: "InterruptedOutcome" });
export type InterruptedOutcome = typeof InterruptedOutcome.Type;
export const Outcome = Schema.Union([
  ValueOutcome,
  ErrorOutcome,
  InterruptedOutcome,
]).annotate({ identifier: "Outcome" });
export type Outcome = typeof Outcome.Type;
export const Execution = Schema.Struct({
  id: ExecutionId,
  run_id: Schema.NullOr(RunId),
  runtime_id: Schema.NullOr(RuntimeId),
  caused_by: Schema.NullOr(ExecutionId),
  cell_id: Schema.NullOr(CellId),
  code: Schema.NullOr(Schema.String),
  code_fingerprint: CodeFingerprint,
  depends_on: Schema.Record(Schema.String, Schema.NullOr(Revision)),
  status: Lifecycle,
  outcome: Schema.NullOr(Outcome),
  started_at: Schema.NullOr(Timestamp),
  completed_at: Schema.NullOr(Timestamp),
}).annotate({ identifier: "Execution" });
export type Execution = typeof Execution.Type;
const item = { id: ItemId, execution_id: ExecutionId, seq: NonNegativeInt };
export const Console = Schema.Struct({
  ...item,
  name: Schema.Literals(["stdout", "stderr"]),
  text: Schema.String,
}).annotate({ identifier: "Console" });
export type Console = typeof Console.Type;
export const Display = Schema.Struct({
  ...item,
  mimetype: Schema.String,
  data: Schema.String,
}).annotate({ identifier: "Display" });
export type Display = typeof Display.Type;
export const InputStatus = Schema.Literals([
  "pending",
  "answered",
  "cancelled",
]).annotate({ identifier: "InputStatus" });
export type InputStatus = typeof InputStatus.Type;
export const Input = Schema.Struct({
  ...item,
  prompt: Schema.String,
  password: Schema.Boolean,
  status: InputStatus,
}).annotate({ identifier: "Input" });
export type Input = typeof Input.Type;
export const InputReplyRequest = Schema.Struct({
  value: Schema.String,
}).annotate({ identifier: "InputReplyRequest" });
export type InputReplyRequest = typeof InputReplyRequest.Type;
export const StartRuntimeRequest = Schema.Struct({
  decisions: Schema.optionalKey(Schema.Record(Schema.String, Schema.String)),
}).annotate({ identifier: "StartRuntimeRequest" });
export type StartRuntimeRequest = typeof StartRuntimeRequest.Type;
export const Custom = Schema.Struct({
  type: Schema.NonEmptyString,
  data: Schema.Unknown,
}).annotate({ identifier: "Custom" });
export type Custom = typeof Custom.Type;
