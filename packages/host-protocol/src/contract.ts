/* Copyright 2026 Marimo. All rights reserved. */

import { makeApi } from "./api/Host.ts";
import * as Notebook from "./api/Notebook.ts";
import { Custom, derive } from "./model/Events.ts";
import { type ObjectDefinition, objects as stableObjects } from "./Objects.ts";
import type { Feature } from "./experimental/defineFeature.ts";

function validateObjects(objects: readonly ObjectDefinition[]) {
  const eventNames = new Set(["custom", "ready", "reset"]);
  // The Python record adapter dispatches on the payload class alone.
  const payloads = new Map<ObjectDefinition["schema"]["ast"], string>([
    [Custom.ast, "custom"],
  ]);
  for (const { kind, schema, removable } of objects) {
    for (const name of removable ? [kind, `${kind}.removed`] : [kind]) {
      if (eventNames.has(name)) {
        throw new Error(`Duplicate event name: ${name}`);
      }
      eventNames.add(name);
    }
    const owner = payloads.get(schema.ast);
    if (owner !== undefined) {
      throw new Error(
        `Object kinds ${owner} and ${kind} share a payload schema`,
      );
    }
    payloads.set(schema.ast, kind);
  }
}

export function makeHostContract<const F extends Feature>(
  features: readonly F[],
) {
  const objects = [
    ...stableObjects,
    ...features.flatMap<F["objects"][number]>((feature) => feature.objects),
  ];
  validateObjects(objects);
  const events = derive(objects);
  const notebookGroup = Notebook.group(
    events.NotebookStreamEvent,
    ...features.flatMap<F["notebookEndpoints"][number]>(
      (feature) => feature.notebookEndpoints,
    ),
  );
  const catalogEndpoints = features.flatMap<F["catalogEndpoints"][number]>(
    (feature) => feature.catalogEndpoints,
  );
  const Api = makeApi(events, catalogEndpoints, notebookGroup);
  return { Api, events, notebookGroup };
}
