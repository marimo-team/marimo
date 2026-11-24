/* Copyright 2026 Marimo. All rights reserved. */

import { Api, events } from "./index.ts";

export * from "../api/Notebook.ts";
export const Group = Api.groups.Notebook;
export const Events = Group.endpoints.events;
export const StreamEvent = events.NotebookStreamEvent;
export type StreamEvent = typeof StreamEvent.Type;
