/* Copyright 2026 Marimo. All rights reserved. */

import { history } from "@codemirror/commands";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
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
import type { CellIndex } from "@/utils/id-tree";
import {
  addSetupCellAtom,
  collapseAllCellsAtom,
  collapseCellAtom,
  createCellAtom,
  deleteCellsAtom,
  expandAllCellsAtom,
  expandCellAtom,
  focusCellAtom,
  moveToNextCellAtom,
  showCellIfHiddenAtom,
  undoDeleteCellAtom,
} from "../actions";
import {
  cellDataAtom,
  cellHandleAtom,
  exportedForTesting,
  notebookAtom,
  notebookReducer,
} from "../cells";
import { followDocument } from "../document";
import {
  hideShownCodeAtom,
  restoredEditorStatesAtom,
  shownHiddenCodeAtom,
} from "../editor";
import { collapsedAtom, layoutAtom } from "../layout";
import { type CellId, SCRATCH_CELL_ID, SETUP_CELL_ID } from "../ids";
import { focusAndScrollCellIntoView } from "../scrollCellIntoView";

vi.mock("../scrollCellIntoView", () => ({
  focusAndScrollCellIntoView: vi.fn(),
}));

const c1 = cellId("c1");
const c2 = cellId("c2");
const c3 = cellId("c3");
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
    /** Give a cell an editor, as mounting it would. */
    mountEditor: (id: string) => {
      const view = new EditorView({
        state: EditorState.create({
          doc: store.get(model.documentAtom)?.cells.get(id)?.code ?? "",
          extensions: [history()],
        }),
      });
      store.get(notebookAtom).cellHandles[id as never].current = {
        editorView: view,
        editorViewOrNull: view,
      };
      return view;
    },
    /** Give a cell's output a heading, as the kernel's outline would. */
    heading: (id: string, level: number) =>
      store.set(notebookAtom, (state) => ({
        ...state,
        cellRuntime: {
          ...state.cellRuntime,
          [id]: {
            ...state.cellRuntime[id as never],
            outline: { items: [{ name: `H${level}`, level, by: { id } }] },
          },
        },
      })),
    visible: () => store.get(layoutAtom).columns[0].visible,
    /** Apply a reducer action, as `useReducerActions()` does. */
    dispatch: (action: Parameters<typeof notebookReducer>[1]) =>
      store.set(notebookAtom, (state) => notebookReducer(state, action)),
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

    expect(store.get(shownHiddenCodeAtom).has(hidden as CellId)).toBe(true);
    expect(store.get(shownHiddenCodeAtom).has(unfocused as CellId)).toBe(false);
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

describe("deleteCellsAtom", () => {
  it("deletes a cell, focuses the one above, and remembers it", () => {
    const { store, order, notebook } = setup();

    expect(store.set(deleteCellsAtom, { cellIds: [c2] })).toBe(true);

    expect(order()).toEqual([c1]);
    expect(notebook().cellData[c2]).toBeUndefined();
    expect(notebook().scrollKey).toBe(c1);
    expect(notebook().history).toEqual([
      {
        type: "delete",
        cells: [
          {
            cell: { id: c2, code: "y = 2", name: "_", config: CONFIG },
            placement: { after: c1 },
            serializedEditorState: null,
          },
        ],
      },
    ]);
  });

  it("focuses the cell below when the first cell goes", () => {
    const { store, notebook } = setup();

    store.set(deleteCellsAtom, { cellIds: [c1] });

    expect(notebook().scrollKey).toBe(c2);
    expect(notebook().history[0]).toMatchObject({
      cells: [{ placement: { before: c2 } }],
    });
  });

  it("keeps the last cell", () => {
    const { store, order, notebook } = setup();

    expect(store.set(deleteCellsAtom, { cellIds: [c1, c2] })).toBe(true);
    expect(order()).toEqual([c2]);

    expect(store.set(deleteCellsAtom, { cellIds: [c2] })).toBe(false);
    expect(order()).toEqual([c2]);
    expect(notebook().history).toHaveLength(1);
  });

  it("skips cells the document does not have", () => {
    const { store, order } = setup();

    expect(store.set(deleteCellsAtom, { cellIds: [cellId("gone")] })).toBe(
      false,
    );

    expect(order()).toEqual([c1, c2]);
  });

  it("names the column of a cell that followed a deleted column start", () => {
    const { store, notebook, cellIn } = setup({
      c2: cell("c2", "y = 2", { config: { ...CONFIG, column: 1 } }),
      c3: cell("c3", "z = 3"),
    });
    expect(notebook().cellIds.atOrThrow(1).inOrderIds).toEqual([c2, c3]);

    store.set(deleteCellsAtom, { cellIds: [c2] });

    expect(cellIn(c3)?.config.column).toBe(1);
    expect(notebook().cellIds.atOrThrow(1).inOrderIds).toEqual([c3]);
  });

  it("forgets the untouched state and the cell atoms of a deleted cell", () => {
    const { store } = setup();
    const id = store.set(createCellAtom, {
      after: c1,
      config: { hide_code: true },
    }) as CellId;
    const dataAtom = cellDataAtom(id);
    const handleAtom = cellHandleAtom(id);

    store.set(deleteCellsAtom, { cellIds: [id] });

    expect(store.get(shownHiddenCodeAtom).has(id)).toBe(false);
    expect(cellDataAtom(id)).not.toBe(dataAtom);
    expect(cellHandleAtom(id)).not.toBe(handleAtom);
  });
});

describe("undoDeleteCellAtom", () => {
  it("brings a deleted cell back where it was, with its editor history", () => {
    const { store, order, notebook, cellIn, mountEditor } = setup({
      c3: cell("c3", "z = 3"),
    });
    const view = mountEditor(c2);
    view.dispatch({ changes: { from: 0, insert: "# " } });
    store.set(deleteCellsAtom, { cellIds: [c2] });
    expect(order()).toEqual([c1, c3]);

    store.set(undoDeleteCellAtom);

    expect(order()).toEqual([c1, c2, c3]);
    expect(cellIn(c2)?.code).toBe("y = 2");
    expect(store.get(restoredEditorStatesAtom).get(c2)).toMatchObject({
      doc: "y = 2",
    });
    expect(notebook().cellData[c2].edited).toBe(true);
    expect(notebook().scrollKey).toBe(c2);
    expect(notebook().history).toEqual([]);
  });

  it("restores the config and the id of the setup cell", () => {
    const { store, order, cellIn } = setup({
      [SETUP_CELL_ID]: cell(SETUP_CELL_ID, "import marimo as mo", {
        name: "setup",
        config: { ...CONFIG, hide_code: true, disabled: true },
      }),
    });
    store.set(deleteCellsAtom, { cellIds: [SETUP_CELL_ID] });
    expect(order()).toEqual([c1, c2]);

    store.set(undoDeleteCellAtom);

    expect(order()).toEqual([c1, c2, SETUP_CELL_ID]);
    expect(cellIn(SETUP_CELL_ID)).toMatchObject({
      name: "setup",
      code: "import marimo as mo",
      config: { hide_code: true, disabled: true },
    });
  });

  it("restores every cell of one deletion at once, in order", () => {
    const { store, order, notebook } = setup({ c3: cell("c3", "z = 3") });
    store.set(deleteCellsAtom, { cellIds: [c1, c2] });
    expect(order()).toEqual([c3]);
    expect(notebook().history).toHaveLength(1);

    store.set(undoDeleteCellAtom);

    expect(order()).toEqual([c1, c2, c3]);
    expect(notebook().history).toEqual([]);
  });

  it("undoes a move recorded in the history", () => {
    const { store, model, order, notebook, dispatch } = setup({
      c3: cell("c3", "z = 3"),
    });
    const column = notebook().cellIds.atOrThrow(0);
    dispatch({
      type: "moveCellsRelativeTo",
      payload: {
        cellIds: [c1, c2],
        targetCellId: c3,
        position: "after",
        previousPlacements: [
          { columnId: column.id, index: 0 as CellIndex },
          { columnId: column.id, index: 1 as CellIndex },
        ],
      },
    });
    expect(order()).toEqual([c3, c1, c2]);
    // The middleware would write the order to the document.
    store.set(model.editAtom, (tx) => tx.setOrder([c3, c1, c2]));

    store.set(deleteCellsAtom, { cellIds: [c3] });
    expect(order()).toEqual([c1, c2]);

    store.set(undoDeleteCellAtom);
    expect(order()).toEqual([c3, c1, c2]);

    store.set(undoDeleteCellAtom);
    expect(order()).toEqual([c1, c2, c3]);
    expect(notebook().history).toEqual([]);
  });

  it("appends a restored cell whose anchor another client removed", () => {
    const { store, order, notebook } = setup();
    store.set(notebookAtom, (state) => ({
      ...state,
      history: [
        {
          type: "delete",
          cells: [
            {
              cell: { id: "c9", code: "q = 9" },
              placement: { after: cellId("gone") },
              serializedEditorState: null,
            },
          ],
        },
      ],
    }));

    store.set(undoDeleteCellAtom);

    expect(order()).toEqual([c1, c2, "c9"]);
    expect(notebook().history).toEqual([]);
  });

  it("does nothing without history", () => {
    const { store, order } = setup();

    store.set(undoDeleteCellAtom);

    expect(order()).toEqual([c1, c2]);
  });
});

describe("folding", () => {
  it("folds a header's section and unfolds it, focusing the header", () => {
    const { store, notebook, visible, heading } = setup({
      c3: cell("c3", "z = 3"),
    });
    heading(c1, 1);

    store.set(collapseCellAtom, { cellId: c1 });
    expect(visible()).toEqual([c1]);
    expect(store.get(layoutAtom).columns[0].folds.get(c1)).toEqual([c2, c3]);
    expect(notebook().scrollKey).toBe(c1);

    store.set(expandCellAtom, { cellId: c1 });
    expect(visible()).toEqual([c1, c2, c3]);
    expect(store.get(collapsedAtom).size).toBe(0);
  });

  it("creates after a folded header below its fold and opens the section", () => {
    const { store, order, visible, heading } = setup({
      c3: cell("c3", "z = 3"),
    });
    heading(c1, 1);
    store.set(collapseCellAtom, { cellId: c1 });

    const id = store.set(createCellAtom, { after: c1, code: "w = 4" });

    // The section runs to the next heading, so the new cell is in it.
    expect(order()).toEqual([c1, c2, c3, id]);
    expect(visible()).toEqual([c1, c2, c3, id]);
    expect(store.get(collapsedAtom).size).toBe(0);
  });

  it("leaves a fold closed over a cell created without focus", () => {
    const { store, order, visible, heading } = setup({
      c3: cell("c3", "z = 3"),
    });
    heading(c1, 1);
    store.set(collapseCellAtom, { cellId: c1 });

    const id = store.set(createCellAtom, {
      after: c1,
      code: "w = 4",
      focus: false,
    });

    expect(order()).toEqual([c1, c2, c3, id]);
    expect(visible()).toEqual([c1]);
  });

  it("does not fold a cell without a heading", () => {
    const { store, visible } = setup();

    store.set(collapseCellAtom, { cellId: c1 });

    expect(visible()).toEqual([c1, c2]);
    expect(store.get(collapsedAtom).size).toBe(0);
  });

  it("folds and unfolds every section", () => {
    const { store, visible, heading } = setup({ c3: cell("c3", "z = 3") });
    heading(c1, 1);
    heading(c2, 2);

    store.set(collapseAllCellsAtom);
    expect(visible()).toEqual([c1]);
    expect([...store.get(collapsedAtom)]).toEqual([c1, c2]);

    store.set(expandAllCellsAtom);
    expect(visible()).toEqual([c1, c2, c3]);
  });

  it("unfolds whatever hides a cell", () => {
    const { store, visible, heading } = setup({ c3: cell("c3", "z = 3") });
    heading(c1, 1);
    heading(c2, 2);
    store.set(collapseAllCellsAtom);

    store.set(showCellIfHiddenAtom, { cellId: c3 });

    expect(visible()).toEqual([c1, c2, c3]);
    expect(store.get(collapsedAtom).size).toBe(0);
  });

  it("moves focus over folded cells", () => {
    const { store, heading } = setup({ c3: cell("c3", "z = 3") });
    heading(c2, 1);
    store.set(collapseCellAtom, { cellId: c2 });

    store.set(focusCellAtom, { cellId: c1, where: "after" });
    expect(focusAndScrollCellIntoView).toHaveBeenLastCalledWith(
      expect.objectContaining({ cellId: c2, codeFocus: "top" }),
    );

    store.set(moveToNextCellAtom, { cellId: c2, before: false, create: false });
    expect(focusAndScrollCellIntoView).toHaveBeenCalledTimes(1);
  });
});

describe("hidden code showing for now", () => {
  it("shows a new hidden cell's code until it is hidden again", () => {
    const { store } = setup();
    const id = store.set(createCellAtom, {
      after: c1,
      config: { hide_code: true },
    }) as CellId;
    expect(store.get(shownHiddenCodeAtom).has(id)).toBe(true);

    const before = store.get(shownHiddenCodeAtom);
    store.set(hideShownCodeAtom, { cellId: id });
    store.set(hideShownCodeAtom, { cellId: id });

    expect(store.get(shownHiddenCodeAtom).has(id)).toBe(false);
    expect(store.get(shownHiddenCodeAtom)).not.toBe(before);
  });
});
