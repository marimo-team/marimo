/* Copyright 2026 Marimo. All rights reserved. */

export { Client } from "./client.ts";
export type { ClientOptions } from "./request.ts";
export {
  CatalogEvents,
  type CatalogEventsOptions,
  type CatalogEvent,
} from "./catalog/events.ts";
export type { CatalogKind, NotebookKind } from "./kinds.ts";
export {
  NotebookClient,
  type NotebookClientOptions,
} from "./notebook/client.ts";
export {
  NotebookEvents,
  type NotebookEventsOptions,
  type NotebookEvent,
} from "./notebook/events.ts";
export { idempotencyKey, type Result } from "./request.ts";
export {
  type Frame,
  type Transport,
  type NotebookTransport,
  StreamStopped,
} from "./transport/frame.ts";
export { sse, type SseOptions, type StreamUrl } from "./transport/sse.ts";

export {
  createCatalogReducer,
  type CatalogReducer,
  type CatalogReducerState,
  type CatalogResource,
  type CatalogResourceEvent,
} from "./reducers/catalog.ts";
export {
  createNotebookReducer,
  type NotebookReducer,
  type NotebookReducerState,
  type NotebookResource,
  type NotebookResourceEvent,
} from "./reducers/notebook.ts";
export type { HandlerContext } from "./reducers/resources.ts";
