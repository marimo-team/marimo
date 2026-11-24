/* Copyright 2026 Marimo. All rights reserved. */

import type { HttpApiEndpoint } from "effect/http-api";
import type { ObjectDefinition } from "../Objects.ts";

export function defineFeature<
  const Object extends ObjectDefinition = never,
  const CatalogRoute extends HttpApiEndpoint.Constraint = never,
  const NotebookRoute extends HttpApiEndpoint.Constraint = never,
>({
  objects = [],
  catalog,
  notebook,
}: {
  objects?: readonly Object[];
  catalog?: { endpoints: readonly CatalogRoute[] };
  notebook?: { endpoints: readonly NotebookRoute[] };
}) {
  return {
    objects,
    catalogEndpoints: catalog?.endpoints ?? [],
    notebookEndpoints: notebook?.endpoints ?? [],
  };
}

export type Feature = ReturnType<typeof defineFeature>;
