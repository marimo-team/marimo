/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import {
  createNotebookActions,
  notebookAtom,
  notebookOutline,
  notebookReducer,
} from "../cells";
import { exportedForTesting } from "../document-changes";
import type { Outline } from "../outline";

const first = cellId("first");
const second = cellId("second");
const firstOutline: Outline = {
  items: [{ name: "First", level: 1, by: { id: "first" } }],
};
const secondOutline: Outline = {
  items: [{ name: "Second", level: 2, by: { id: "second" } }],
};

function setup() {
  const store = createStore();
  store.set(
    notebookAtom,
    MockNotebook.notebookState({
      cellData: { [first]: { code: "x = 1" }, [second]: {} },
      cellRuntime: {
        [first]: { outline: firstOutline },
        [second]: { outline: secondOutline },
      },
    }),
  );
  const actions = createNotebookActions((action) =>
    store.set(notebookAtom, (state) => notebookReducer(state, action)),
  );
  return { store, actions };
}

afterEach(() => {
  exportedForTesting.cancelPendingChanges();
});

describe("notebookOutline", () => {
  it("does not notify outline subscribers when cell code changes", () => {
    const { store, actions } = setup();
    const initial = store.get(notebookOutline);
    const listener = vi.fn();
    const unsubscribe = store.sub(notebookOutline, listener);

    actions.updateCellCode({
      cellId: first,
      code: "x = 2",
      formattingChange: false,
    });

    expect(store.get(notebookOutline)).toBe(initial);
    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });

  it("updates headings when runtime outlines change or are removed", () => {
    const { store } = setup();
    const updated: Outline = {
      items: [{ name: "Updated", level: 1, by: { id: "updated" } }],
    };

    for (const outline of [updated, null]) {
      store.set(notebookAtom, (state) => ({
        ...state,
        cellRuntime: {
          ...state.cellRuntime,
          [first]: { ...state.cellRuntime[first], outline },
        },
      }));
      expect(store.get(notebookOutline)).toEqual({
        items: [...(outline?.items ?? []), ...secondOutline.items],
      });
    }
  });

  it("keeps headings in cell order after moving and deleting cells", () => {
    const { store, actions } = setup();
    actions.moveCell({ cellId: second, before: true });
    expect(store.get(notebookOutline)).toEqual({
      items: [...secondOutline.items, ...firstOutline.items],
    });

    actions.deleteCell({ cellId: second });
    expect(store.get(notebookOutline)).toEqual(firstOutline);
  });

  it("notifies subscribers when output is replaced with the same headings", () => {
    const { store } = setup();
    const listener = vi.fn();
    const unsubscribe = store.sub(notebookOutline, listener);

    store.set(notebookAtom, (state) => ({
      ...state,
      cellRuntime: {
        ...state.cellRuntime,
        [first]: { ...state.cellRuntime[first], outline: { ...firstOutline } },
      },
    }));

    // Consumers must reconnect to replacement heading elements in the DOM.
    expect(listener).toHaveBeenCalledOnce();
    unsubscribe();
  });
});
