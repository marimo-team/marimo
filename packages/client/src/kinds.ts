/* Copyright 2026 Marimo. All rights reserved. */

import {
  CatalogStreamEvent,
  NotebookStreamEvent,
  ObjectKind,
} from "./protocol.ts";

function objectKinds<Tag extends string>(tags: readonly Tag[]) {
  const names = new Set<string>(tags);
  return ObjectKind.options.filter((kind): kind is Extract<ObjectKind, Tag> =>
    names.has(kind),
  );
}

export const catalogKinds = objectKinds(
  CatalogStreamEvent.options.map((schema) => schema.shape.event.options[0]),
);
export type CatalogKind = (typeof catalogKinds)[number];

export const notebookKinds = objectKinds(
  NotebookStreamEvent.options.map((schema) => schema.shape.event.options[0]),
);
export type NotebookKind = (typeof notebookKinds)[number];
