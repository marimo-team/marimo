/* Copyright 2026 Marimo. All rights reserved. */
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { createCell } from "@/core/cells/types";
import { store } from "@/core/state/jotai";
import { editorMountScheduler } from "../../editor-mount-scheduler";
import { getSearchDocuments } from "../documents";
import { getMatches, findNext, replaceAll } from "../navigate";
import { findReplaceAtom } from "../state";

const { writes } = vi.hoisted(() => ({ writes: vi.fn() }));
vi.mock("@/core/cells/actions", async () => {
  const { atom } = await import("jotai");
  return {
    setCellCodeAtom: atom(null, (_get, _set, update) => writes(update)),
  };
});

afterEach(() => {
  writes.mockClear();
  store.set(notebookAtom, initialNotebookState());
  store.set(findReplaceAtom, { type: "clearCurrentView" });
});

it("counts unmounted Python and markdown and builds only the navigation target", () => {
  const a = cellId("a");
  const b = cellId("b");
  store.set(notebookAtom, {
    ...initialNotebookState(),
    cellIds: [a, b],
    cellData: {
      [a]: createCell({ id: a, code: "x = 1" }),
      [b]: createCell({ id: b, code: 'mo.md(r"""needle""")' }),
    },
    cellHandles: { [a]: { current: null }, [b]: { current: null } },
  });
  const view = new EditorView({ state: EditorState.create({ doc: "needle" }) });
  const build = vi.fn(() => {
    store.get(notebookAtom).cellHandles[b].current = {
      editorView: view,
      editorViewOrNull: view,
    };
  });
  editorMountScheduler.request(b, build, true);
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });
  expect(getSearchDocuments().map((doc) => doc.state.doc.toString())).toEqual([
    "x = 1",
    "needle",
  ]);
  expect(getMatches()).toMatchObject({ count: 1 });
  expect(build).not.toHaveBeenCalled();
  expect(findNext()).toMatchObject({ from: 0, to: 6 });
  expect(build).toHaveBeenCalledTimes(1);
  view.destroy();
});

it("replaces and undoes matches in an unmounted markdown document without building it", () => {
  const id = cellId("markdown");
  const code = 'mo.md(r"""needle""")';
  store.set(notebookAtom, {
    ...initialNotebookState(),
    cellIds: [id],
    cellData: { [id]: createCell({ id, code }) },
    cellHandles: { [id]: { current: null } },
  });
  const build = vi.fn();
  const release = editorMountScheduler.request(id, build, true);
  store.set(findReplaceAtom, { type: "setFind", find: "needle" });
  store.set(findReplaceAtom, { type: "setReplace", replace: "updated" });
  const undo = replaceAll();
  expect(writes).toHaveBeenLastCalledWith({
    cellId: id,
    code: expect.stringContaining("updated"),
  });
  expect(writes.mock.lastCall?.[0].code).toMatch(/^mo.md/);
  expect(typeof undo).toBe("function");
  if (undo) {
    undo();
  }
  expect(writes).toHaveBeenLastCalledWith({
    cellId: id,
    code: expect.stringContaining("needle"),
  });
  expect(build).not.toHaveBeenCalled();
  release();
});
