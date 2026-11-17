/* Copyright 2026 Marimo. All rights reserved. */

/** The objects a host publishes and the event streams that carry each. */

import type { Schema } from "effect";
import { Host, Notebook, Project } from "./model/Catalog.ts";
import { Cell, Document } from "./model/Document.ts";
import { Execution, Run } from "./model/Execution.ts";
import { Console, Display, Input, Variable } from "./model/Items.ts";
import { Attachment, Runtime } from "./model/Runtime.ts";

/** The catalog stream is `/events`. A notebook stream is `/notebooks/{notebook_id}/events`. */
export type StreamName = "catalog" | "notebook";

export interface ObjectKind {
  /** Names the object's event and its field in that event's data. */
  readonly kind: string;
  readonly schema: Schema.Constraint;
  readonly streams: ReadonlyArray<StreamName>;
  /** Whether the object has a `<kind>.removed` event. */
  readonly removable: boolean;
}

const catalog = ["catalog"] as const;
const notebook = ["notebook"] as const;
const both = ["catalog", "notebook"] as const;

export const objects = [
  { kind: "host", schema: Host, streams: catalog, removable: false },
  { kind: "project", schema: Project, streams: catalog, removable: true },
  { kind: "notebook", schema: Notebook, streams: both, removable: true },
  { kind: "document", schema: Document, streams: notebook, removable: false },
  { kind: "cell", schema: Cell, streams: notebook, removable: true },
  { kind: "runtime", schema: Runtime, streams: both, removable: true },
  { kind: "attachment", schema: Attachment, streams: both, removable: true },
  { kind: "run", schema: Run, streams: notebook, removable: true },
  { kind: "execution", schema: Execution, streams: notebook, removable: true },
  { kind: "console", schema: Console, streams: notebook, removable: true },
  { kind: "display", schema: Display, streams: notebook, removable: true },
  { kind: "input", schema: Input, streams: notebook, removable: false },
  { kind: "variable", schema: Variable, streams: notebook, removable: true },
] as const satisfies ReadonlyArray<ObjectKind>;
