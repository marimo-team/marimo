/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { atom } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import type {
  DocumentEdit,
  DocumentEditor,
  DocumentModel,
  DocumentSyncStatus,
  EditableCell,
  EditableDocument,
} from "@/core/notebook/document";
import {
  adaptiveLanguageConfiguration,
  languageAdapterState,
} from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { store } from "@/core/state/jotai";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { MultiColumn } from "@/utils/id-tree";
import { isRtcEnabled } from "../../rtc/state";
import {
  createNotebookActions,
  exportedForTesting,
  type NotebookState,
  notebookReducer,
} from "../cells";
import {
  applyDocument,
  flushDocument,
  followDocument,
  withDocumentSave,
} from "../document";
import { type CellId, SCRATCH_CELL_ID } from "../ids";

vi.mock("../../rtc/state", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../rtc/state")>()),
  isRtcEnabled: vi.fn(() => false),
}));

const { initialNotebookState } = exportedForTesting;

const a = cellId("a");
const b = cellId("b");
const c = cellId("c");
const d = cellId("d");

function cell(id: CellId, patch: Partial<EditableCell> = {}): EditableCell {
  return {
    id,
    code: `${id} = 1`,
    name: "_",
    config: {
      column: null,
      disabled: false,
      hide_code: false,
      expand_output: false,
    },
    ...patch,
  };
}

function documentOf(cells: EditableCell[]): EditableDocument {
  return {
    order: cells.map((cell) => cell.id),
    cells: new Map(cells.map((cell) => [cell.id, cell])),
  };
}

/** A mounted cell editor, as the notebook's cells have. */
function createEditor(content: string) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      python(),
      adaptiveLanguageConfiguration({
        cellId: a,
        completionConfig: {
          activate_on_typing: true,
          signature_hint_on_typing: false,
          copilot: false,
          codeium_api_key: null,
        },
        hotkeys: new OverridingHotkeyProvider({}),
        placeholderType: "marimo-import",
        lspConfig: {},
      }),
    ],
  });
  return new EditorView({ state, parent: globalThis.document.body });
}

/** A notebook that follows `cells`, as the session builds one. */
function notebookOf(cells: EditableCell[]): NotebookState {
  return applyDocument(initialNotebookState(), documentOf(cells));
}

describe("applyDocument", () => {
  it("adds the document's cells to an empty notebook", () => {
    const state = notebookOf([cell(a), cell(b, { code: "" })]);

    expect(state.cellIds.inOrderIds).toEqual([a, b]);
    expect(state.cellData[a]).toMatchObject({
      code: "a = 1",
      name: "_",
      edited: false,
      lastCodeRun: null,
    });
    expect(state.cellRuntime[a]).toBeDefined();
    expect(state.cellHandles[a]).toBeDefined();
    expect(state.cellData[SCRATCH_CELL_ID]).toBeDefined();
  });

  it("returns the same state when the document matches", () => {
    const cells = [cell(a), cell(b)];
    const state = notebookOf(cells);

    expect(applyDocument(state, documentOf(cells))).toBe(state);
  });

  it("brings a code change into the cell's editor", () => {
    const state = notebookOf([cell(a), cell(b)]);
    const view = createEditor("b = 1");
    state.cellHandles[b].current = { editorView: view, editorViewOrNull: view };
    state.cellData[b] = { ...state.cellData[b], lastCodeRun: "b = 1" };

    const next = applyDocument(
      state,
      documentOf([cell(a), cell(b, { code: "b = 2" })]),
    );

    expect(next.cellData[b]).toMatchObject({ code: "b = 2", edited: true });
    expect(next.cellData[a]).toBe(state.cellData[a]);
    expect(view.state.doc.toString()).toBe("b = 2");
  });

  it("leaves an editor that already shows the document's code alone", () => {
    const state = notebookOf([cell(a)]);
    // The editor runs ahead of the notebook while this client types.
    const view = createEditor('mo.md("hi")');
    state.cellHandles[a].current = { editorView: view, editorViewOrNull: view };

    const next = applyDocument(
      state,
      documentOf([cell(a, { code: 'mo.md("hi")' })]),
    );

    expect(next.cellData[a].code).toBe('mo.md("hi")');
    expect(view.state.doc.toString()).toBe('mo.md("hi")');
    expect(view.state.field(languageAdapterState).type).toBe("python");
  });

  it("leaves an RTC editor to Loro", () => {
    vi.mocked(isRtcEnabled).mockReturnValueOnce(true);
    const state = notebookOf([cell(a)]);
    const view = createEditor("a = 1");
    state.cellHandles[a].current = { editorView: view, editorViewOrNull: view };

    const next = applyDocument(state, documentOf([cell(a, { code: "a = 2" })]));

    expect(next.cellData[a].code).toBe("a = 2");
    expect(view.state.doc.toString()).toBe("a = 1");
  });

  it("keeps the code this client has when the host withholds source", () => {
    const state = notebookOf([cell(a)]);

    expect(applyDocument(state, documentOf([cell(a, { code: null })]))).toBe(
      state,
    );
  });

  it("follows a cell's name and config", () => {
    const state = notebookOf([cell(a)]);

    const next = applyDocument(
      state,
      documentOf([
        cell(a, {
          name: "renamed",
          config: { ...cell(a).config, hide_code: true },
        }),
      ]),
    );

    expect(next.cellData[a]).toMatchObject({
      name: "renamed",
      config: { hide_code: true },
      edited: false,
    });
  });

  it("removes cells the document no longer has", () => {
    const state = notebookOf([cell(a), cell(b), cell(c)]);

    const next = applyDocument(state, documentOf([cell(a), cell(c)]));

    expect(next.cellIds.inOrderIds).toEqual([a, c]);
    expect(next.cellData[b]).toBeUndefined();
    expect(next.cellRuntime[b]).toBeUndefined();
    expect(next.cellHandles[b]).toBeUndefined();
  });

  it("regroups columns from the cells' configs, keeping column ids and collapsed sections", () => {
    const column1 = { ...cell(d).config, column: 1 };
    const state = notebookOf([
      cell(a),
      cell(b),
      cell(c),
      cell(d, { config: column1 }),
    ]);
    const [first, second] = state.cellIds.getColumns();
    const collapsed = {
      ...state,
      cellIds: new MultiColumn([first.collapse(a, b), second]),
    };

    const next = applyDocument(
      collapsed,
      documentOf([cell(c), cell(a), cell(b), cell(d, { config: column1 })]),
    );

    expect(next.cellIds.inOrderIds).toEqual([c, a, b, d]);
    expect(next.cellIds.getColumnIds()).toEqual(
      collapsed.cellIds.getColumnIds(),
    );
    expect(next.cellIds.atOrThrow(0).isCollapsed(a)).toBe(true);
    expect(next.cellIds.atOrThrow(1).inOrderIds).toEqual([d]);
  });

  it("keeps a trailing empty column", () => {
    const state = notebookOf([cell(a)]);
    const withEmpty = {
      ...state,
      cellIds: state.cellIds.addColumn(state.cellIds.atOrThrow(0).id),
    };

    const next = applyDocument(withEmpty, documentOf([cell(a, { code: "" })]));

    expect(next.cellIds.colLength).toBe(2);
    expect(next.cellData[a].code).toBe("");
  });
});

describe("documentEditMiddleware", () => {
  type Call = [string, ...unknown[]];
  let calls: Call[];
  let state: NotebookState;
  const editor: DocumentEditor = {
    setCode: (id, code) => calls.push(["setCode", id, code]),
    setName: (id, name) => calls.push(["setName", id, name]),
    updateConfig: (id, patch) => calls.push(["updateConfig", id, patch]),
    createCell: (cell, placement) =>
      calls.push(["createCell", cell, placement]),
    deleteCell: (id) => calls.push(["deleteCell", id]),
    setOrder: (order) => calls.push(["setOrder", order]),
  };
  const model: DocumentModel = {
    documentAtom: atom(null),
    editAtom: atom(null, (_get, _set, edit: DocumentEdit) => edit(editor)),
    syncStatusAtom: atom<DocumentSyncStatus>({ status: "idle" }),
    flush: vi.fn(),
    retry: vi.fn(),
    start: vi.fn(),
  };
  const actions = createNotebookActions((action) => {
    state = notebookReducer(state, action);
  });

  beforeEach(() => {
    calls = [];
    state = notebookOf([cell(a), cell(b), cell(c)]);
    store.set(activeDocumentModelAtom, model);
  });

  afterEach(() => {
    store.set(activeDocumentModelAtom, null);
  });

  it("creates a cell at the end without setting the order", () => {
    actions.createNewCell({
      cellId: c,
      before: false,
      code: "d = 1",
      newCellId: d,
    });

    expect(calls.map((call) => call[0])).toEqual(["createCell"]);
    expect(calls[0][1]).toMatchObject({ id: d, code: "d = 1" });
  });

  it("creates a cell elsewhere and sets the order", () => {
    actions.createNewCell({ cellId: a, before: true, newCellId: d });

    expect(calls.map((call) => call[0])).toEqual(["createCell", "setOrder"]);
    expect(calls[1][1]).toEqual([d, a, b, c]);
  });

  it("deletes a cell", () => {
    actions.deleteCell({ cellId: b });

    expect(calls).toEqual([["deleteCell", b]]);
  });

  it("writes code, name, and config", () => {
    actions.updateCellCode({
      cellId: a,
      code: "a = 2",
      formattingChange: false,
    });
    actions.updateCellName({ cellId: a, name: "first" });
    actions.updateCellConfig({ cellId: a, config: { hide_code: true } });

    expect(calls).toEqual([
      ["setCode", a, "a = 2"],
      ["setName", a, "first"],
      ["updateConfig", a, { hide_code: true }],
    ]);
  });

  it("sets the order when a cell moves", () => {
    actions.moveCell({ cellId: c, before: true });

    expect(calls).toEqual([["setOrder", [a, c, b]]]);
  });

  it("sets the column of a cell that changes column", () => {
    state = notebookOf([
      cell(a),
      cell(b),
      cell(c, { config: { ...cell(c).config, column: 1 } }),
    ]);

    actions.moveCell({ cellId: b, direction: "right" });

    expect(state.cellIds.atOrThrow(1).inOrderIds).toEqual([b, c]);
    expect(calls).toEqual([["updateConfig", b, { column: 1 }]]);
  });

  it("clears columns merged into one", () => {
    state = notebookOf([
      cell(a),
      cell(b),
      cell(c, { config: { ...cell(c).config, column: 1 } }),
    ]);

    actions.mergeAllColumns();

    expect(calls).toEqual([["updateConfig", c, { column: null }]]);
  });

  it("ignores the document and the kernel's run state", () => {
    actions.prepareForRun({ cellId: a });
    actions.setLastRun({
      lastCodeRun: { [a]: "a = 0" },
      lastExecutionTime: {},
    });
    actions.resetCellRuntimes();
    actions.reconcileDocument(documentOf([cell(a)]));

    expect(calls).toEqual([]);
  });

  it("leaves the scratchpad alone", () => {
    actions.updateCellCode({
      cellId: SCRATCH_CELL_ID,
      code: "scratch",
      formattingChange: false,
    });

    expect(calls).toEqual([]);
  });
});

describe("followDocument", () => {
  it("reconciles the document now and on each change, until aborted", () => {
    const documentAtom = atom<EditableDocument | null>(null);
    const reconcile = vi.fn();
    const controller = new AbortController();

    followDocument({
      store,
      model: { documentAtom },
      reconcile,
      signal: controller.signal,
    });
    expect(reconcile).not.toHaveBeenCalled();

    const first = documentOf([cell(a)]);
    store.set(documentAtom, first);
    expect(reconcile).toHaveBeenCalledWith(first);

    controller.abort();
    store.set(documentAtom, documentOf([cell(b)]));
    expect(reconcile).toHaveBeenCalledOnce();
  });
});

describe("flushing before host commands", () => {
  const model = {
    flush: vi.fn<() => Promise<never>>(),
    retry: vi.fn<() => Promise<never>>(),
  } as unknown as DocumentModel;

  beforeEach(() => {
    vi.mocked(model.flush).mockReset();
    vi.mocked(model.retry).mockReset();
    store.set(activeDocumentModelAtom, model);
  });

  afterEach(() => {
    store.set(activeDocumentModelAtom, null);
  });

  it("flushes the session's model, or nothing without one", async () => {
    vi.mocked(model.flush).mockResolvedValue(undefined as never);
    await flushDocument();
    expect(model.flush).toHaveBeenCalledOnce();

    store.set(activeDocumentModelAtom, null);
    await expect(flushDocument()).resolves.toBeUndefined();
  });

  it("saves after a flush and resumes the model when the flush failed", async () => {
    vi.mocked(model.flush).mockRejectedValue(new Error("conflict"));
    vi.mocked(model.retry).mockResolvedValue(undefined as never);
    const save = vi.fn().mockResolvedValue("saved");

    await expect(withDocumentSave(save)).resolves.toBe("saved");
    expect(save).toHaveBeenCalledOnce();
    expect(model.retry).toHaveBeenCalledOnce();

    vi.mocked(model.flush).mockResolvedValue(undefined as never);
    await withDocumentSave(save);
    expect(model.retry).toHaveBeenCalledOnce();
  });
});
