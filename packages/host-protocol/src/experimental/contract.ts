/* Copyright 2026 Marimo. All rights reserved. */

import { derive } from "../Events.ts";
import { make } from "../Host.ts";
import { objects as stableObjects } from "../Objects.ts";
import type { Feature } from "./defineFeature.ts";
import * as registry from "./features.ts";

export function compose<const F extends Feature>(features: readonly F[]) {
  const objects = [
    ...stableObjects,
    ...features.flatMap<F["objects"][number]>((feature) => feature.objects),
  ];
  const endpoints = features.flatMap<F["notebookEndpoints"][number]>(
    (feature) => feature.notebookEndpoints,
  );
  return { Api: make(objects, ...endpoints), ...derive(objects) };
}

export const { Api, CatalogStreamEvent, NotebookStreamEvent } = compose(
  Object.values(registry),
);
