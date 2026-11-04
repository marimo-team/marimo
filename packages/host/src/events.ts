/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import { Analysis } from "./analysis.ts";
import { Attachment, Host, Project } from "./catalog.ts";
import { Empty, Timestamp } from "./common.ts";
import {
  Console,
  Custom,
  Display,
  Execution,
  Input,
  Run,
  Runtime,
  Variable,
} from "./execution.ts";
import { Cell, Document, Notebook } from "./notebook.ts";

const cursor = Schema.NonEmptyString.check(Schema.isPattern(/^[^\r\n\0]+$/));
const metadata = {
  request_id: Schema.optionalKey(Schema.String),
  time: Schema.optionalKey(Timestamp),
};
const message = <Fields extends Schema.Struct.Fields>(
  identifier: string,
  fields: Fields,
) => Schema.Struct({ ...metadata, ...fields }).annotate({ identifier });
const event = <const Name extends string, Data extends Schema.Top>(
  identifier: string,
  name: Name,
  data: Data,
) =>
  Schema.Struct({
    event: Schema.tag(name),
    id: Schema.optionalKey(cursor),
    data,
  }).annotate({ identifier });

export const HostMessage = message("HostMessage", { host: Host });
export type HostMessage = typeof HostMessage.Type;
export const HostEvent = event("HostEvent", "host", HostMessage);
export type HostEvent = typeof HostEvent.Type;

export const ProjectMessage = message("ProjectMessage", { project: Project });
export type ProjectMessage = typeof ProjectMessage.Type;
export const ProjectEvent = event("ProjectEvent", "project", ProjectMessage);
export type ProjectEvent = typeof ProjectEvent.Type;

export const NotebookMessage = message("NotebookMessage", {
  notebook: Notebook,
});
export type NotebookMessage = typeof NotebookMessage.Type;
export const NotebookEvent = event(
  "NotebookEvent",
  "notebook",
  NotebookMessage,
);
export type NotebookEvent = typeof NotebookEvent.Type;

export const DocumentMessage = message("DocumentMessage", {
  document: Document,
});
export type DocumentMessage = typeof DocumentMessage.Type;
export const DocumentEvent = event(
  "DocumentEvent",
  "document",
  DocumentMessage,
);
export type DocumentEvent = typeof DocumentEvent.Type;

export const CellMessage = message("CellMessage", { cell: Cell });
export type CellMessage = typeof CellMessage.Type;
export const CellEvent = event("CellEvent", "cell", CellMessage);
export type CellEvent = typeof CellEvent.Type;

export const RuntimeMessage = message("RuntimeMessage", { runtime: Runtime });
export type RuntimeMessage = typeof RuntimeMessage.Type;
export const RuntimeEvent = event("RuntimeEvent", "runtime", RuntimeMessage);
export type RuntimeEvent = typeof RuntimeEvent.Type;

export const AttachmentMessage = message("AttachmentMessage", {
  attachment: Attachment,
});
export type AttachmentMessage = typeof AttachmentMessage.Type;
export const AttachmentEvent = event(
  "AttachmentEvent",
  "attachment",
  AttachmentMessage,
);
export type AttachmentEvent = typeof AttachmentEvent.Type;

export const RunMessage = message("RunMessage", { run: Run });
export type RunMessage = typeof RunMessage.Type;
export const RunEvent = event("RunEvent", "run", RunMessage);
export type RunEvent = typeof RunEvent.Type;

export const ExecutionMessage = message("ExecutionMessage", {
  execution: Execution,
});
export type ExecutionMessage = typeof ExecutionMessage.Type;
export const ExecutionEvent = event(
  "ExecutionEvent",
  "execution",
  ExecutionMessage,
);
export type ExecutionEvent = typeof ExecutionEvent.Type;

export const ConsoleMessage = message("ConsoleMessage", { console: Console });
export type ConsoleMessage = typeof ConsoleMessage.Type;
export const ConsoleEvent = event("ConsoleEvent", "console", ConsoleMessage);
export type ConsoleEvent = typeof ConsoleEvent.Type;

export const DisplayMessage = message("DisplayMessage", { display: Display });
export type DisplayMessage = typeof DisplayMessage.Type;
export const DisplayEvent = event("DisplayEvent", "display", DisplayMessage);
export type DisplayEvent = typeof DisplayEvent.Type;

export const InputMessage = message("InputMessage", { input: Input });
export type InputMessage = typeof InputMessage.Type;
export const InputEvent = event("InputEvent", "input", InputMessage);
export type InputEvent = typeof InputEvent.Type;

export const VariableMessage = message("VariableMessage", {
  variable: Variable,
});
export type VariableMessage = typeof VariableMessage.Type;
export const VariableEvent = event(
  "VariableEvent",
  "variable",
  VariableMessage,
);
export type VariableEvent = typeof VariableEvent.Type;

export const CustomMessage = message("CustomMessage", {
  custom: Custom,
  time: Timestamp,
});
export type CustomMessage = typeof CustomMessage.Type;
export const CustomEvent = event("CustomEvent", "custom", CustomMessage);
export type CustomEvent = typeof CustomEvent.Type;
export const RemovedMessage = message("RemovedMessage", { id: Schema.String });
export type RemovedMessage = typeof RemovedMessage.Type;
export const ProjectRemovedEvent = event(
  "ProjectRemovedEvent",
  "project.removed",
  RemovedMessage,
);
export type ProjectRemovedEvent = typeof ProjectRemovedEvent.Type;
export const NotebookRemovedEvent = event(
  "NotebookRemovedEvent",
  "notebook.removed",
  RemovedMessage,
);
export type NotebookRemovedEvent = typeof NotebookRemovedEvent.Type;
export const CellRemovedEvent = event(
  "CellRemovedEvent",
  "cell.removed",
  RemovedMessage,
);
export type CellRemovedEvent = typeof CellRemovedEvent.Type;
export const RuntimeRemovedEvent = event(
  "RuntimeRemovedEvent",
  "runtime.removed",
  RemovedMessage,
);
export type RuntimeRemovedEvent = typeof RuntimeRemovedEvent.Type;
export const AttachmentRemovedEvent = event(
  "AttachmentRemovedEvent",
  "attachment.removed",
  RemovedMessage,
);
export type AttachmentRemovedEvent = typeof AttachmentRemovedEvent.Type;
export const RunRemovedEvent = event(
  "RunRemovedEvent",
  "run.removed",
  RemovedMessage,
);
export type RunRemovedEvent = typeof RunRemovedEvent.Type;
export const ExecutionRemovedEvent = event(
  "ExecutionRemovedEvent",
  "execution.removed",
  RemovedMessage,
);
export type ExecutionRemovedEvent = typeof ExecutionRemovedEvent.Type;
export const ConsoleRemovedEvent = event(
  "ConsoleRemovedEvent",
  "console.removed",
  RemovedMessage,
);
export type ConsoleRemovedEvent = typeof ConsoleRemovedEvent.Type;
export const DisplayRemovedEvent = event(
  "DisplayRemovedEvent",
  "display.removed",
  RemovedMessage,
);
export type DisplayRemovedEvent = typeof DisplayRemovedEvent.Type;
export const VariableRemovedEvent = event(
  "VariableRemovedEvent",
  "variable.removed",
  RemovedMessage,
);
export type VariableRemovedEvent = typeof VariableRemovedEvent.Type;

export const ReadyEvent = Schema.Struct({
  event: Schema.tag("ready"),
  id: cursor,
  data: Empty,
}).annotate({ identifier: "ReadyEvent" });
export type ReadyEvent = typeof ReadyEvent.Type;
export const ResetEvent = event("ResetEvent", "reset", Empty);
export type ResetEvent = typeof ResetEvent.Type;
export const AnalysisMessage = message("AnalysisMessage", {
  analysis: Analysis,
});
export type AnalysisMessage = typeof AnalysisMessage.Type;
export const AnalysisEvent = event(
  "AnalysisEvent",
  "analysis",
  AnalysisMessage,
);
export type AnalysisEvent = typeof AnalysisEvent.Type;

export const CatalogEvent = Schema.Union([
  HostEvent,
  ProjectEvent,
  NotebookEvent,
  RuntimeEvent,
  AttachmentEvent,
  ProjectRemovedEvent,
  NotebookRemovedEvent,
  RuntimeRemovedEvent,
  AttachmentRemovedEvent,
  ReadyEvent,
  ResetEvent,
]).annotate({ identifier: "CatalogEvent" });
export type CatalogEvent = typeof CatalogEvent.Type;
export const NotebookStreamEvent = Schema.Union([
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
  CustomEvent,
  NotebookRemovedEvent,
  CellRemovedEvent,
  RuntimeRemovedEvent,
  AttachmentRemovedEvent,
  RunRemovedEvent,
  ExecutionRemovedEvent,
  ConsoleRemovedEvent,
  DisplayRemovedEvent,
  VariableRemovedEvent,
  ReadyEvent,
  ResetEvent,
]).annotate({ identifier: "NotebookStreamEvent" });
export type NotebookStreamEvent = typeof NotebookStreamEvent.Type;
export const Event = Schema.Union([
  HostEvent,
  ProjectEvent,
  ProjectRemovedEvent,
  ...NotebookStreamEvent.members,
]).annotate({ identifier: "Event" });
export type Event = typeof Event.Type;
export const AnalysisNotebookEvent = Schema.Union([
  ...NotebookStreamEvent.members,
  AnalysisEvent,
]).annotate({ identifier: "NotebookStreamEvent" });
export type AnalysisNotebookEvent = typeof AnalysisNotebookEvent.Type;
export const AnalysisProtocolEvent = Schema.Union([
  ...Event.members,
  AnalysisEvent,
]).annotate({ identifier: "Event" });
export type AnalysisProtocolEvent = typeof AnalysisProtocolEvent.Type;

export const eventCodec = <S extends Schema.Top>(schema: S) =>
  Schema.Struct({
    event: Schema.String,
    id: Schema.optionalKey(cursor),
    data: Schema.fromJsonString(Schema.Unknown),
  }).pipe(Schema.decodeTo(schema));
