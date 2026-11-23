/* Copyright 2026 Marimo. All rights reserved. */

import type { HttpApiEndpoint } from "effect/http-api";
import type { event } from "../internal/events.ts";
import type { ObjectDefinition } from "../Objects.ts";

type Endpoint = HttpApiEndpoint.Constraint;
type StreamEvent = ReturnType<typeof event>;

interface Contributions<Route extends Endpoint, Event extends StreamEvent> {
  endpoints?: readonly Route[];
  events?: readonly Event[];
}

function scope<Route extends Endpoint, Event extends StreamEvent>({
  endpoints = [],
  events = [],
}: Contributions<Route, Event> = {}) {
  return { endpoints, events };
}

export function defineFeature<
  const Object extends ObjectDefinition = never,
  const CatalogRoute extends Endpoint = never,
  const CatalogEvent extends StreamEvent = never,
  const NotebookRoute extends Endpoint = never,
  const NotebookEvent extends StreamEvent = never,
>({
  objects = [],
  catalog,
  notebook,
}: {
  objects?: readonly Object[];
  catalog?: Contributions<CatalogRoute, CatalogEvent>;
  notebook?: Contributions<NotebookRoute, NotebookEvent>;
}) {
  return { objects, catalog: scope(catalog), notebook: scope(notebook) };
}

export type Feature = ReturnType<typeof defineFeature>;
