/* Copyright 2026 Marimo. All rights reserved. */

import { ObjectType } from "./protocol.ts";

export const catalogKinds = [
  "host",
  "project",
  "notebook",
  "runtime",
  "attachment",
] as const satisfies readonly ObjectType[];

export type CatalogKind = (typeof catalogKinds)[number];

export const notebookKinds = ObjectType.options.filter(
  (kind) => kind !== "host" && kind !== "project",
);

export type NotebookKind = (typeof notebookKinds)[number];
