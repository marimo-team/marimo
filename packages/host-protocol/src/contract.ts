/* Copyright 2026 Marimo. All rights reserved. */

import { makeApi } from "./api/Host.ts";
import * as Notebook from "./api/Notebook.ts";
import { derive } from "./model/Events.ts";
import { objects as stableObjects } from "./Objects.ts";
import type { Feature } from "./experimental/defineFeature.ts";

export function makeHostContract<const F extends Feature>(
  features: readonly F[],
) {
  const objects = [
    ...stableObjects,
    ...features.flatMap<F["objects"][number]>((feature) => feature.objects),
  ];
  const contributions = <Scope extends "catalog" | "notebook">(
    scope: Scope,
  ) => ({
    endpoints: features.flatMap<F[Scope]["endpoints"][number]>(
      (feature) => feature[scope].endpoints,
    ),
    events: features.flatMap<F[Scope]["events"][number]>(
      (feature) => feature[scope].events,
    ),
  });
  const catalog = contributions("catalog");
  const notebook = contributions("notebook");
  const events = derive(objects, catalog.events, notebook.events);
  const notebookGroup = Notebook.group(
    events.NotebookStreamEvent,
    ...notebook.endpoints,
  );
  const Api = makeApi(events, catalog.endpoints, notebookGroup);
  return { Api, events, notebookGroup };
}
