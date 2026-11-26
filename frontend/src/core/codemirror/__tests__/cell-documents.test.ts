/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { afterEach, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { createCell } from "@/core/cells/types";
import { store } from "@/core/state/jotai";
import { getCellDocuments, writeCellCode } from "../cell-documents";

const { writes } = vi.hoisted(() => ({ writes: vi.fn() }));
vi.mock("@/core/cells/actions", async () => {
  const { atom } = await import("jotai");
  return { setCellCodeAtom: atom(null, (_get, _set, w) => writes(w)) };
});

const id = cellId("cell");

function setNotebook(code: string, view: EditorView | null) {
  store.set(notebookAtom, {
    ...initialNotebookState(),
    cellIds: [id],
    cellData: { [id]: createCell({ id, code }) },
    cellHandles: {
      [id]: {
        current: { editorView: view },
      },
    },
  });
}

afterEach(() => {
  writes.mockClear();
  store.set(notebookAtom, initialNotebookState());
});

it("derives a document from the stored code when the cell has no editor", () => {
  setNotebook('mo.md(r"""# Title""")', null);

  const [document] = getCellDocuments();

  expect(document.view).toBeNull();
  expect(document.state.doc.toString()).toBe("# Title");
  expect(document.code).toBe('mo.md(r"""# Title""")');
});

it("reads a mounted editor's document and Python code", () => {
  const view = new EditorView({ doc: "x = 1" });
  setNotebook("x = 1", view);

  const [document] = getCellDocuments();

  expect(document.view).toBe(view);
  expect(document.state).toBe(view.state);
  expect(document.code).toBe("x = 1");
  view.destroy();
});

it("writes document changes back as the cell's Python code", () => {
  setNotebook('mo.md(r"""# Title""")', null);
  const [document] = getCellDocuments();

  document.applyChanges({ from: 2, to: 7, insert: "Heading" }, "input");

  expect(writes).toHaveBeenCalledExactlyOnceWith({
    cellId: id,
    code: expect.stringContaining("# Heading"),
  });
  expect(writes.mock.lastCall?.[0].code).toMatch(/^mo\.md\(/);
});

it("does not write code the cell already has", () => {
  setNotebook("x = 1", null);

  writeCellCode(id, "x = 1");
  expect(writes).not.toHaveBeenCalled();

  writeCellCode(id, "x = 2");
  expect(writes).toHaveBeenCalledExactlyOnceWith({ cellId: id, code: "x = 2" });
});
