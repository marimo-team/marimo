/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { afterEach, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { editorMountScheduler } from "@/core/codemirror/editor-mount-scheduler";
import { store } from "@/core/state/jotai";
import {
  ensureCellEditorView,
  getCellEditorView,
  initialNotebookState,
  notebookAtom,
} from "../cells";

const id = cellId("cell");
const view = new EditorView();

afterEach(() => {
  store.set(notebookAtom, initialNotebookState());
});

it("returns an editor only once it is built, and building is explicit", () => {
  const handle = { current: { editorView: null } } as {
    current: {
      editorView: EditorView | null;
    };
  };
  store.set(notebookAtom, {
    ...initialNotebookState(),
    cellIds: [id],
    cellHandles: { [id]: handle },
  });
  const build = vi.fn(() => {
    handle.current = { editorView: view };
  });
  const release = editorMountScheduler.register(id, build);

  expect(getCellEditorView(id)).toBeUndefined();
  expect(build).not.toHaveBeenCalled();

  expect(ensureCellEditorView(id)).toBe(view);
  expect(getCellEditorView(id)).toBe(view);
  expect(build).toHaveBeenCalledTimes(1);
  release();
});
