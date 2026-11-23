/* Copyright 2026 Marimo. All rights reserved. */

import { Api, CatalogStreamEvent } from "./contract.ts";

export * from "../Host.ts";
export { Api };
export const Group = Api.groups.Host;
export const Events = Group.endpoints.events;
export const StreamEvent = CatalogStreamEvent;
export type StreamEvent = typeof StreamEvent.Type;
