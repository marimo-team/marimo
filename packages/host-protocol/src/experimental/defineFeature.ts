/* Copyright 2026 Marimo. All rights reserved. */

import type { HttpApiEndpoint } from "effect/http-api";
import type { ObjectDefinition } from "../Objects.ts";

export interface Feature {
  readonly objects: readonly ObjectDefinition[];
  readonly notebookEndpoints: readonly HttpApiEndpoint.Constraint[];
}

export function defineFeature<
  const Objects extends Feature["objects"] = readonly [],
  const Endpoints extends Feature["notebookEndpoints"] = readonly [],
>(feature: {
  readonly objects?: Objects;
  readonly notebookEndpoints?: Endpoints;
}) {
  return {
    objects: feature.objects ?? ([] as const),
    notebookEndpoints: feature.notebookEndpoints ?? ([] as const),
  };
}
