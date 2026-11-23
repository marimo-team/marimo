/* Copyright 2026 Marimo. All rights reserved. */

import { notebookGroup, events } from "./stable.ts";

export * from "./api/Notebook.ts";
export const Group = notebookGroup;
export const Events = Group.endpoints.events;
export const StreamEvent = events.NotebookStreamEvent;
export type StreamEvent = typeof StreamEvent.Type;
