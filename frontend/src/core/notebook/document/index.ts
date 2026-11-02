/* Copyright 2026 Marimo. All rights reserved. */

/** The editable document, its drafts, and its synchronization with the host. */

export {
  DocumentProvider,
  useNotebookCellCode,
  useNotebookCellCodeExtension,
  useNotebookCellConfig,
  useNotebookCellName,
  useNotebookCellOrder,
  useNotebookDocumentEdit,
  useNotebookDocumentSync,
} from "./hooks";
export {
  createDocumentModel,
  type DocumentEdit,
  type DocumentEditor,
  type DocumentModel,
  type DocumentSyncStatus,
  type EditableCell,
  type EditableDocument,
} from "./model";
