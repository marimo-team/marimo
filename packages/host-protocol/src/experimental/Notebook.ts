/* Copyright 2026 Marimo. All rights reserved. */

import { Api, NotebookStreamEvent } from "./contract.ts";

export * from "../Notebook.ts";
export const Group = Api.groups.Notebook;
export const Events = Group.endpoints.events;
export const StreamEvent = NotebookStreamEvent;
export type StreamEvent = typeof StreamEvent.Type;
