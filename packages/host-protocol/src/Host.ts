/* Copyright 2026 Marimo. All rights reserved. */

import type { SchemaRepresentation } from "effect";
import { Api, events } from "./stable.ts";

export { Create, group, HostToken, RequestValidation } from "./api/Host.ts";
export { Api };
export const Group = Api.groups.Host;
export const Events = Group.endpoints.events;
export const StreamEvent = events.CatalogStreamEvent;
export type StreamEvent = typeof StreamEvent.Type;

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
