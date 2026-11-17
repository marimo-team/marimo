/* Copyright 2026 Marimo. All rights reserved. */

import type { CellId } from "@marimo-team/client/protocol";
import { useAtomValue, useSetAtom, useStore } from "jotai";
import { createContext, type ReactNode, useContext, useMemo } from "react";
import { cellCodeBinding } from "./codemirror";
import type { EditableCell } from "./draft";
import type { DocumentModel } from "./model";
import { selectCellField, selectOrder } from "./select";

const DocumentContext = createContext<DocumentModel | null>(null);

/**
 * Expose a session-owned model to React. Construct the model with the same store
 * as the enclosing Jotai Provider. The session owner starts it; mounting or
 * unmounting this provider does not change the model's lifetime.
 *
 * ```tsx
 * <Provider store={store}>
 *   <DocumentProvider model={model}>
 *     <Editor />
 *   </DocumentProvider>
 * </Provider>
 * ```
 */
export function DocumentProvider({
  model,
  children,
}: {
  model: DocumentModel;
  children: ReactNode;
}) {
  return (
    <DocumentContext.Provider value={model}>
      {children}
    </DocumentContext.Provider>
  );
}

function useDocumentModel() {
  const model = useContext(DocumentContext);
  if (model === null) {
    throw new Error("Document hooks require a DocumentProvider");
  }
  return model;
}

/** Null while the document is unavailable; an empty array for an empty document. */
export function useNotebookCellOrder() {
  const { documentAtom } = useDocumentModel();
  return useAtomValue(useMemo(() => selectOrder(documentAtom), [documentAtom]));
}

function useCellField<K extends keyof EditableCell>(id: CellId, field: K) {
  const { documentAtom } = useDocumentModel();
  return useAtomValue(
    useMemo(
      () => selectCellField(documentAtom, id, field),
      [documentAtom, id, field],
    ),
  );
}

/** Undefined for an absent cell; null when the host withholds its source. */
export function useNotebookCellCode(id: CellId) {
  return useCellField(id, "code");
}

/** Undefined when the cell or document is unavailable. */
export function useNotebookCellName(id: CellId) {
  return useCellField(id, "name");
}

/** Undefined when the cell or document is unavailable. */
export function useNotebookCellConfig(id: CellId) {
  return useCellField(id, "config");
}

/**
 * A CodeMirror extension that binds the editor's text to a cell's code.
 * Stable until the cell id or document model changes.
 *
 * ```tsx
 * const extension = useNotebookCellCodeExtension(cellId);
 * ```
 */
export function useNotebookCellCodeExtension(id: CellId) {
  const model = useDocumentModel();
  const store = useStore();
  return useMemo(
    () => cellCodeBinding({ store, model, cellId: id }),
    [model, store, id],
  );
}

/**
 * A stable edit function. Synchronous callbacks publish atomically or roll back.
 *
 * ```ts
 * const edit = useNotebookDocumentEdit();
 * edit((tx) => tx.setCode(cellId, code));
 * ```
 */
export function useNotebookDocumentEdit() {
  return useSetAtom(useDocumentModel().editAtom);
}

/**
 * Sync status and explicit recovery. flush waits for edits, including newer
 * typing, to reach the confirmed source and returns the revision for Run/Save.
 * Rejections retain local edits; retry explicitly resubmits them. Requests
 * with an unknown outcome reuse their original key within the retry window.
 */
export function useNotebookDocumentSync() {
  const model = useDocumentModel();
  const status = useAtomValue(model.syncStatusAtom);
  return { status, flush: model.flush, retry: model.retry };
}
