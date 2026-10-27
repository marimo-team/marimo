/* Copyright 2026 Marimo. All rights reserved. */

/** The editable document, its drafts, and its synchronization with the host. */

export {
  DocumentProvider,
  useCellCode,
  useCellCodeExtension,
  useCellConfig,
  useCellName,
  useCellOrder,
  useDocumentEdit,
  useDocumentSync,
} from "./hooks";
export { createDocumentModel, type DocumentModel } from "./model";
