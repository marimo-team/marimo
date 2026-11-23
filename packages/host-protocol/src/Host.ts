/* Copyright 2026 Marimo. All rights reserved. */

import type { SchemaRepresentation } from "effect";
import type { HttpApiEndpoint } from "effect/http-api";
import * as Notebook from "./api/Notebook.ts";
import { makeApi } from "./api/Host.ts";
import { derive } from "./model/Events.ts";
import { Api, events } from "./stable.ts";
import type { ObjectDefinition } from "./Objects.ts";

export { Create, group, HostToken } from "./api/Host.ts";
export { Api };
export const Group = Api.groups.Host;
export const Events = Group.endpoints.events;
export const StreamEvent = events.CatalogStreamEvent;
export type StreamEvent = typeof StreamEvent.Type;

export const make = <
  const Objects extends ReadonlyArray<ObjectDefinition>,
  const Endpoints extends readonly HttpApiEndpoint.Constraint[] = readonly [],
>(
  objects: Objects,
  ...notebookEndpoints: Endpoints
) => {
  const events = derive(objects);
  return makeApi(
    events,
    [],
    Notebook.group(events.NotebookStreamEvent, ...notebookEndpoints),
  );
};

/**
 * How `OpenApi.fromApi` names the schemas of this protocol.
 *
 * Effect calls the wire schema of a class `<Class>Encoded`, so a problem would
 * be published as `NotFoundProblemEncoded`. With this policy it is published
 * as `NotFoundProblem`, the name of its class.
 *
 * ```ts
 * OpenApi.fromApi(Host.Api, { referencePolicy: Host.referencePolicy });
 * ```
 */
export const referencePolicy: SchemaRepresentation.ReferencePolicy = ({
  identifier,
}) => identifier?.replace(/Encoded$/, "");
