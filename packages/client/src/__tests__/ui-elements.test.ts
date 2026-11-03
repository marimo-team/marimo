/* Copyright 2026 Marimo. All rights reserved. */
import { expect, it } from "vitest";
import { createNotebookReducer } from "../reducers/notebook.ts";
import { uiElements } from "../notebook/ui-elements.ts";

it("rebuilds records, applies partial echoes, and clears them on removal or reset", () => {
  const reducer = createNotebookReducer({ uiElements });
  const element = {
    id: "c1-0",
    kind: "element" as const,
    cell_id: "c1",
    config: { component: "marimo-slider", label: null, args: {} },
    state: { value: 3 },
  };
  const created = reducer.reduce(reducer.initial, {
    event: "ui_element",
    data: { ui_element: element },
  });
  const updated = reducer.reduce(created, {
    event: "ui_element.update",
    data: {
      id: element.id,
      state: { value: 4 },
      request_id: "r1",
      time: "2026-11-03T00:00:00Z",
    },
  });
  expect(
    created.resources.uiElements.get(element.id)?.element.state.value,
  ).toBe(3);
  expect(updated.resources.uiElements.get(element.id)).toEqual({
    element: { ...element, state: { value: 4 } },
    requestId: "r1",
  });
  const unchanged = reducer.reduce(updated, {
    event: "ui_element.update",
    data: {
      id: element.id,
      state: {},
      request_id: "r2",
      time: "2026-11-03T00:00:00Z",
    },
  });
  expect(
    unchanged.resources.uiElements.get(element.id)?.element.state.value,
  ).toBe(4);
  expect(unchanged.resources.uiElements.get(element.id)?.requestId).toBe("r2");
  expect(
    reducer.reduce(updated, { event: "reset", data: {} }).resources.uiElements
      .size,
  ).toBe(0);
  const removed = reducer.reduce(updated, {
    event: "ui_element.removed",
    data: { id: element.id, time: "2026-11-03T00:00:00Z" },
  });
  expect(removed.resources.uiElements.size).toBe(0);
  expect(
    reducer
      .reduce(removed, { event: "ui_element", data: { ui_element: element } })
      .resources.uiElements.get(element.id)?.element.state.value,
  ).toBe(3);
});
