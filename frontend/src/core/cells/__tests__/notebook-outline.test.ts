/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { CONFIG } from "@/core/notebook/document/__tests__/fixtures";
import {
  createNotebookActions,
  notebookAtom,
  notebookOutline,
  notebookReducer,
} from "../cells";

const first = cellId("first");
const second = cellId("second");

/** A completed execution that showed `html`. */
function showed(id: string, html: string) {
  return MockExecutions.shown(id, { mimetype: "text/html", data: html });
}

const firstItem = { name: "First", level: 1, by: { id: "first" } };
const secondItem = { name: "Second", level: 2, by: { id: "second" } };

function setup() {
  const store = createStore();
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [first]: { code: "x = 1" }, [second]: {} },
    }),
  );
  const replica = MockExecutions.seed(store, [
    showed(first, '<h1 id="first">First</h1>'),
    showed(second, '<h2 id="second">Second</h2>'),
  ]);
  const actions = createNotebookActions((action) =>
    store.set(notebookAtom, (state) => notebookReducer(state, action)),
  );
  /** Replace what the host reports for the cells. */
  const report = (records: ReturnType<typeof showed>[]) => {
    const next = MockExecutions.inputs(records);
    store.set(replica.executionsAtom, next.executions);
    store.set(replica.resultsAtom, next.results);
  };
  return { store, actions, report };
}

describe("notebookOutline", () => {
  it("reads headings from the host's outputs in cell order", () => {
    const { store } = setup();
    expect(store.get(notebookOutline)).toEqual({
      items: [firstItem, secondItem],
    });
  });

  it("does not notify outline subscribers when cell code changes", () => {
    const { store } = setup();
    const initial = store.get(notebookOutline);
    const listener = vi.fn();
    const unsubscribe = store.sub(notebookOutline, listener);

    store.set(notebookAtom, (state) => ({
      ...state,
      cellData: {
        ...state.cellData,
        [first]: { ...state.cellData[first], code: "x = 2" },
      },
    }));

    expect(store.get(notebookOutline)).toBe(initial);
    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });

  it("updates headings when outputs change or are removed", () => {
    const { store, report } = setup();

    report([
      showed(first, '<h1 id="updated">Updated</h1>'),
      showed(second, '<h2 id="second">Second</h2>'),
    ]);
    expect(store.get(notebookOutline)).toEqual({
      items: [{ name: "Updated", level: 1, by: { id: "updated" } }, secondItem],
    });

    report([showed(second, '<h2 id="second">Second</h2>')]);
    expect(store.get(notebookOutline)).toEqual({ items: [secondItem] });
  });

  it("keeps headings in cell order after moving and deleting cells", () => {
    const { store, actions } = setup();
    actions.reconcileDocument({
      order: [second, first],
      cells: new Map([
        [first, { id: first, code: "x = 1", name: "_", config: CONFIG }],
        [second, { id: second, code: "y = 2", name: "_", config: CONFIG }],
      ]),
    });
    expect(store.get(notebookOutline)).toEqual({
      items: [secondItem, firstItem],
    });

    actions.reconcileDocument({
      order: [first],
      cells: new Map([
        [first, { id: first, code: "x = 1", name: "_", config: CONFIG }],
      ]),
    });
    expect(store.get(notebookOutline)).toEqual({ items: [firstItem] });
  });

  it("leaves subscribers alone when a run shows the same output again", () => {
    const { store, report } = setup();
    const listener = vi.fn();
    const unsubscribe = store.sub(notebookOutline, listener);

    report([
      showed(first, '<h1 id="first">First</h1>'),
      showed(second, '<h2 id="second">Second</h2>'),
    ]);

    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });
});
