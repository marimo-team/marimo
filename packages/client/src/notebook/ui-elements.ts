/* Copyright 2026 Marimo. All rights reserved. */

import type { UIElementOutput } from "../protocol.ts";
import type { NotebookResource } from "../reducers/notebook.ts";

/** The latest kernel record and the request that last updated it. */
export interface ConfirmedUIElement {
  readonly element: UIElementOutput;
  readonly requestId?: string;
}

export type UIElements = ReadonlyMap<string, ConfirmedUIElement>;

/** Confirmed state, independent of whether any UI element is mounted. */
export const uiElements: NotebookResource<UIElements, "ui_element"> = {
  initial: new Map(),
  on: {
    ui_element: (state, { data }) =>
      new Map(state).set(data.ui_element.id, { element: data.ui_element }),
    "ui_element.update": (state, { data }) => {
      const current = state.get(data.id);
      if (!current) {
        return state;
      }
      return new Map(state).set(data.id, {
        element: {
          ...current.element,
          state: { ...current.element.state, ...data.state },
        },
        requestId: data.request_id,
      });
    },
    "ui_element.removed": (state, { data }) => {
      if (!state.has(data.id)) {
        return state;
      }
      const next = new Map(state);
      next.delete(data.id);
      return next;
    },
  },
};
