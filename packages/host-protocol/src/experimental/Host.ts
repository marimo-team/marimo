/* Copyright 2026 Marimo. All rights reserved. */

import { Api, events } from "./index.ts";

export {
  Create,
  group,
  HostToken,
  RequestValidation,
  referencePolicy,
} from "../Host.ts";
export { Api };
export const Group = Api.groups.Host;
export const Events = Group.endpoints.events;
export const StreamEvent = events.CatalogStreamEvent;
export type StreamEvent = typeof StreamEvent.Type;
