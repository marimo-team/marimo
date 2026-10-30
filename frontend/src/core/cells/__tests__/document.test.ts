/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import type {
  DocumentModel,
  EditableCell,
  EditableDocument,
} from "@/core/notebook/document";
import { store } from "@/core/state/jotai";
import { activeDocumentModelAtom } from "@/core/session/active-notebook";
import { exportedForTesting, type NotebookState } from "../cells";
import { applyDocument, flushDocument, followDocument } from "../document";
import { type CellId, SCRATCH_CELL_ID } from "../ids";

const { initialNotebookState } = exportedForTesting;

const a = cellId("a");
const b = cellId("b");
const c = cellId("c");

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

/** A notebook that follows `cells`, as the session builds one. */
function notebookOf(cells: EditableCell[]): NotebookState {
  return applyDocument(initialNotebookState(), documentOf(cells));
}

describe("applyDocument", () => {
  it("adds the document's cells to an empty notebook", () => {
    const state = notebookOf([cell(a), cell(b, { code: "" })]);

    expect(state.cellIds).toEqual([a, b]);
    expect(state.cellData[a]).toMatchObject({
      code: "a = 1",
      name: "_",
      edited: true,
      lastCodeRun: null,
    });
    expect(state.cellData[b].edited).toBe(false);
    expect(state.cellRuntime[a]).toBeDefined();
    expect(state.cellHandles[a]).toBeDefined();
    expect(state.cellData[SCRATCH_CELL_ID]).toBeDefined();
  });

  it("returns the same state when the document matches", () => {
    const cells = [cell(a), cell(b)];
    const state = notebookOf(cells);

    expect(applyDocument(state, documentOf(cells))).toBe(state);
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
      edited: true,
    });
  });

  it("removes cells the document no longer has", () => {
    const state = notebookOf([cell(a), cell(b), cell(c)]);

    const next = applyDocument(state, documentOf([cell(a), cell(c)]));

    expect(next.cellIds).toEqual([a, c]);
    expect(next.cellData[b]).toBeUndefined();
    expect(next.cellRuntime[b]).toBeUndefined();
    expect(next.cellHandles[b]).toBeUndefined();
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
});
