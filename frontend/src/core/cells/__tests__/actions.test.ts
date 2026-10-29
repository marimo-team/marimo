/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { createStore } from "jotai";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockDocumentModel } from "@/__mocks__/document";
import { cellId } from "@/__tests__/branded";
import {
  cell,
  CONFIG,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
import {
  addSetupCellAtom,
  createCellAtom,
  moveToNextCellAtom,
} from "../actions";
import { exportedForTesting, notebookAtom, notebookReducer } from "../cells";
import { followDocument } from "../document";
import { SCRATCH_CELL_ID, SETUP_CELL_ID } from "../ids";
import { focusAndScrollCellIntoView } from "../scrollCellIntoView";

vi.mock("../scrollCellIntoView", () => ({
  focusAndScrollCellIntoView: vi.fn(),
}));

const c1 = cellId("c1");
const c2 = cellId("c2");
const stops: Array<() => void> = [];

afterEach(() => {
  for (const stop of stops.splice(0)) {
    stop();
  }
  vi.clearAllMocks();
});

/** A store whose notebook follows a document model, as the session wires it. */
function setup(cells?: Record<string, Protocol.Cell | null>) {
  const store = createStore();
  store.set(notebookAtom, exportedForTesting.initialNotebookState());
  const { model, stop } = mockDocumentModel(
    store,
    cells ? withCells(documentOf(), cells) : documentOf(),
  );
  const controller = new AbortController();
  stops.push(stop, () => controller.abort());
  followDocument({
    store,
    model,
    reconcile: (document) =>
      store.set(notebookAtom, (state) =>
        notebookReducer(state, {
          type: "reconcileDocument",
          payload: document,
        }),
      ),
    signal: controller.signal,
  });
  return {
    store,
    model,
    order: () => store.get(notebookAtom).cellIds.inOrderIds,
    notebook: () => store.get(notebookAtom),
    cellIn: (id: string) => store.get(model.documentAtom)?.cells.get(id),
  };
}

describe("createCellAtom", () => {
  it("creates a cell after another and focuses it once it mounts", () => {
    const { store, order, notebook, cellIn } = setup();

    const id = store.set(createCellAtom, { after: c1, code: "z = 3" });

    expect(id).not.toBeNull();
    expect(order()).toEqual([c1, id, c2]);
    expect(cellIn(id as string)?.code).toBe("z = 3");
    expect(notebook().scrollKey).toBe(id);
    expect(notebook().cellRuntime[id as never]).toBeDefined();
  });

  it("appends to the first column by default", () => {
    const { store, order } = setup();

    const id = store.set(createCellAtom, {});

    expect(order()).toEqual([c1, c2, id]);
  });

  it("keeps a focused hidden cell untouched until it is blurred", () => {
    const { store, notebook } = setup();

    const hidden = store.set(createCellAtom, {
      after: c1,
      config: { hide_code: true },
    });
    const unfocused = store.set(createCellAtom, {
      after: c1,
      config: { hide_code: true },
      focus: false,
    });

    expect(notebook().untouchedNewCells.has(hidden as never)).toBe(true);
    expect(notebook().untouchedNewCells.has(unfocused as never)).toBe(false);
    expect(notebook().scrollKey).toBe(hidden);
  });

  it("names the column of a cell placed first in a later column", () => {
    const { store, notebook, cellIn } = setup({
      c2: cell("c2", "y = 2", { config: { ...CONFIG, column: 1 } }),
    });

    const id = store.set(createCellAtom, { before: c2 });

    expect(cellIn(id as string)?.config.column).toBe(1);
    expect(cellIn(c2)?.config.column).toBeNull();
    expect(notebook().cellIds.atOrThrow(1).inOrderIds).toEqual([id, c2]);
    expect(notebook().cellIds.atOrThrow(0).inOrderIds).toEqual([c1]);
  });

  it("places a cell in the column of its anchor, whatever config it carries", () => {
    const { store, order, notebook, cellIn } = setup({
      c2: cell("c2", "y = 2", { config: { ...CONFIG, column: 1 } }),
    });

    // A pasted cell carries the config of the cell it was copied from.
    const id = store.set(createCellAtom, {
      after: c2,
      code: "z = 3",
      config: { hide_code: true },
    });

    expect(order()).toEqual([c1, c2, id]);
    expect(cellIn(id as string)?.config).toMatchObject({
      hide_code: true,
      column: null,
    });
    expect(notebook().cellIds.atOrThrow(1).inOrderIds).toEqual([c2, id]);
  });

  it("names the column when appending to an empty column", () => {
    const { store, notebook, cellIn } = setup();
    store.set(notebookAtom, (state) => ({
      ...state,
      cellIds: state.cellIds.addColumn(state.cellIds.atOrThrow(0).id),
    }));
    const empty = notebook().cellIds.atOrThrow(1).id;

    const id = store.set(createCellAtom, { endOf: empty });

    expect(cellIn(id as string)?.config.column).toBe(1);
    expect(notebook().cellIds.atOrThrow(1).inOrderIds).toEqual([id]);
  });

  it("creates nothing when a cell already has the code", () => {
    const { store, order } = setup();

    const id = store.set(createCellAtom, {
      code: "x = 1",
      skipIfCodeExists: true,
    });

    expect(id).toBeNull();
    expect(order()).toEqual([c1, c2]);
  });

  it("refuses without a document", () => {
    const store = createStore();
    store.set(notebookAtom, exportedForTesting.initialNotebookState());

    expect(() => store.set(createCellAtom, {})).toThrow("no document");
  });
});

describe("moveToNextCellAtom", () => {
  it("focuses the neighbouring cell within the column", () => {
    const { store, order } = setup();

    store.set(moveToNextCellAtom, { cellId: c1, before: false });

    expect(focusAndScrollCellIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ cellId: c2, codeFocus: "top" }),
    );
    expect(order()).toEqual([c1, c2]);
  });

  it("creates a cell past the edge of the column, unless told not to", () => {
    const { store, order } = setup();

    store.set(moveToNextCellAtom, { cellId: c2, before: false, create: false });
    expect(order()).toEqual([c1, c2]);

    store.set(moveToNextCellAtom, { cellId: c2, before: false });
    expect(order()).toHaveLength(3);
    expect(order().slice(0, 2)).toEqual([c1, c2]);
  });

  it("creates a cell before the first one", () => {
    const { store, order } = setup();

    store.set(moveToNextCellAtom, { cellId: c1, before: true });

    expect(order()).toHaveLength(3);
    expect(order().slice(1)).toEqual([c1, c2]);
  });

  it("leaves the scratchpad's focus alone", () => {
    const { store, order } = setup();

    store.set(moveToNextCellAtom, { cellId: SCRATCH_CELL_ID, before: false });

    expect(focusAndScrollCellIntoView).not.toHaveBeenCalled();
    expect(order()).toEqual([c1, c2]);
  });
});

describe("addSetupCellAtom", () => {
  it("creates the setup cell at the top and focuses it", () => {
    const { store, order, notebook, cellIn } = setup();

    store.set(addSetupCellAtom, { code: "import marimo as mo" });

    expect(order()[0]).toBe(SETUP_CELL_ID);
    expect(cellIn(SETUP_CELL_ID)).toMatchObject({
      name: "setup",
      code: "import marimo as mo",
    });
    expect(notebook().scrollKey).toBe(SETUP_CELL_ID);
  });

  it("only focuses a setup cell that exists", () => {
    const { store, order, cellIn } = setup();
    store.set(addSetupCellAtom, { code: "first" });

    store.set(addSetupCellAtom, { code: "second" });

    expect(order().filter((id) => id === SETUP_CELL_ID)).toHaveLength(1);
    expect(cellIn(SETUP_CELL_ID)?.code).toBe("first");
  });
});
