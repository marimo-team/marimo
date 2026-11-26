/* Copyright 2026 Marimo. All rights reserved. */
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { createCell } from "@/core/cells/types";
import { store } from "@/core/state/jotai";
import { cellIdState } from "../../config/extension";
import { editorMountScheduler } from "../../editor-mount-scheduler";
import { findNext, getMatches, replaceAll } from "../navigate";
import { findReplaceAtom } from "../state";

const { writes } = vi.hoisted(() => ({ writes: vi.fn() }));
vi.mock("@/core/cells/actions", async () => {
  const { atom } = await import("jotai");
  return {
    setCellCodeAtom: atom(null, (_get, _set, update) => writes(update)),
  };
});

/** Follow the document, as the real action does. */
function writeToNotebook({ cellId, code }: { cellId: CellId; code: string }) {
  const notebook = store.get(notebookAtom);
  store.set(notebookAtom, {
    ...notebook,
    cellData: {
      ...notebook.cellData,
      [cellId]: createCell({ id: cellId, code }),
    },
  });
}

const withoutEditor: CellHandle = { editorView: null };

function setNotebook(cells: [CellId, string, CellHandle | null][]) {
  store.set(notebookAtom, {
    ...initialNotebookState(),
    cellIds: cells.map(([id]) => id),
    cellData: Object.fromEntries(
      cells.map(([id, code]) => [id, createCell({ id, code })]),
    ),
    cellHandles: Object.fromEntries(
      cells.map(([id, , handle]) => [id, { current: handle }]),
    ),
  });
}

beforeEach(() => {
  writes.mockImplementation(writeToNotebook);
});

afterEach(() => {
  writes.mockReset();
  store.set(notebookAtom, initialNotebookState());
  store.set(findReplaceAtom, { type: "clearCurrentView" });
});

it("counts matches in cells without editors and builds only the navigation target", () => {
  const [a, b] = [cellId("a"), cellId("b")];
  setNotebook([
    [a, "x = 1", withoutEditor],
    [b, 'mo.md(r"""needle""")', withoutEditor],
  ]);
  const view = new EditorView({ state: EditorState.create({ doc: "needle" }) });
  const build = vi.fn(() => {
    store.get(notebookAtom).cellHandles[b].current = {
      editorView: view,
    };
  });
  editorMountScheduler.register(b, build);
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });

  expect(getMatches()).toMatchObject({ count: 1 });
  expect(build).not.toHaveBeenCalled();
  expect(findNext()).toMatchObject({ from: 0, to: 6 });
  expect(build).toHaveBeenCalledTimes(1);
  view.destroy();
});

it("moves past a match whose editor cannot be built", () => {
  const [stuck, buildable] = [cellId("stuck"), cellId("buildable")];
  setNotebook([
    [stuck, "needle = 1", withoutEditor],
    [buildable, "needle = 2", withoutEditor],
  ]);
  const view = new EditorView({
    state: EditorState.create({
      doc: "needle = 2",
      extensions: cellIdState.of(buildable),
    }),
  });
  editorMountScheduler.register(buildable, () => {
    store.get(notebookAtom).cellHandles[buildable].current = {
      editorView: view,
    };
  });
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });

  expect(findNext()).toMatchObject({ from: 0, to: 6 });
  expect(store.get(findReplaceAtom).currentView?.cellId).toBe(buildable);
  view.destroy();
});

it("ignores cells that are not on the page", () => {
  const [visible, folded] = [cellId("visible"), cellId("folded")];
  setNotebook([
    [visible, "needle = 1", withoutEditor],
    [folded, "needle = 2", null],
  ]);
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });
  store.set(findReplaceAtom, { type: "setReplace", replace: "found" });

  expect(getMatches()).toMatchObject({ count: 1 });
  replaceAll();
  expect(writes).toHaveBeenCalledExactlyOnceWith({
    cellId: visible,
    code: "found = 1",
  });
});

it("replaces and undoes matches in markdown without building its editor", () => {
  const id = cellId("markdown");
  const code = 'mo.md(r"""needle""")';
  setNotebook([[id, code, withoutEditor]]);
  const build = vi.fn();
  const release = editorMountScheduler.register(id, build);
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });
  store.set(findReplaceAtom, { type: "setReplace", replace: "updated" });

  const undo = replaceAll();
  expect(writes).toHaveBeenLastCalledWith({
    cellId: id,
    code: expect.stringContaining("updated"),
  });
  expect(typeof undo).toBe("function");
  if (undo) {
    undo();
  }
  expect(writes).toHaveBeenLastCalledWith({ cellId: id, code });
  expect(build).not.toHaveBeenCalled();
  release();
});
