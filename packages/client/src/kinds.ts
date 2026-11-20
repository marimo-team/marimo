/* Copyright 2026 Marimo. All rights reserved. */

import { ObjectKind } from "./protocol.ts";

export const catalogKinds = [
  "host",
  "project",
  "notebook",
  "runtime",
  "attachment",
] as const satisfies readonly ObjectKind[];

export type CatalogKind = (typeof catalogKinds)[number];

export const notebookKinds = ObjectKind.options.filter(
  (kind) => kind !== "host" && kind !== "project",
);

export type NotebookKind = (typeof notebookKinds)[number];
