/* Copyright 2026 Marimo. All rights reserved. */

import { Schema } from "effect";
import {
  AttachmentId,
  NotebookId,
  PositiveInt,
  ProjectId,
  Timestamp,
} from "./common.ts";

export const Process = Schema.Struct({
  pid: PositiveInt,
  started_at: Timestamp,
}).annotate({ identifier: "Process" });
export type Process = typeof Process.Type;
export const HostRecord = Schema.Struct({
  version: Schema.Literal(1),
  process: Process,
  name: Schema.String,
  url: Schema.String,
  token: Schema.NonEmptyString,
}).annotate({ identifier: "HostRecord" });
export type HostRecord = typeof HostRecord.Type;
export const Host = Schema.Struct({
  operations: Schema.Array(Schema.String),
}).annotate({ identifier: "Host" });
export type Host = typeof Host.Type;
export const ObjectType = Schema.Literals([
  "host",
  "project",
  "notebook",
  "document",
  "cell",
  "runtime",
  "attachment",
  "run",
  "execution",
  "console",
  "display",
  "input",
  "variable",
  "custom",
]).annotate({ identifier: "ObjectType" });
export type ObjectType = typeof ObjectType.Type;
export const ProjectStatus = Schema.Literals([
  "indexing",
  "indexed",
  "partial",
]).annotate({ identifier: "ProjectStatus" });
export type ProjectStatus = typeof ProjectStatus.Type;
export const Project = Schema.Struct({
  id: ProjectId,
  name: Schema.String,
  root: Schema.NullOr(Schema.String),
  status: ProjectStatus,
  message: Schema.NullOr(Schema.String),
  operations: Schema.Array(Schema.String),
}).annotate({ identifier: "Project" });
export type Project = typeof Project.Type;
export const AttachmentIdentity = Schema.String.check(
  Schema.isMinLength(1),
  Schema.isMaxLength(128),
  Schema.isPattern(/^[!-~]+$/),
);
export const AttachmentKind = Schema.String.check(
  Schema.isPattern(/^[a-z0-9-]+$/),
);
export const AttachmentName = Schema.String.check(Schema.isMaxLength(256));
export const Attachment = Schema.Struct({
  id: AttachmentId,
  notebook_id: NotebookId,
  identity: Schema.optionalKey(AttachmentIdentity),
  kind: AttachmentKind,
  name: Schema.NullOr(AttachmentName),
  since: Timestamp,
}).annotate({ identifier: "Attachment" });
export type Attachment = typeof Attachment.Type;
