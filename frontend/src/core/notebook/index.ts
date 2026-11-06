/* Copyright 2026 Marimo. All rights reserved. */

/** What the editor reads about the current notebook. */

export {
  useNotebookAttachments,
  attachmentLabel,
  type Attachment,
} from "./attachments";
export {
  useNotebookCellCode,
  useNotebookCellCodeExtension,
  useNotebookCellConfig,
  useNotebookCellName,
  useNotebookCellOrder,
  useNotebookDocumentEdit,
  useNotebookDocumentSync,
} from "./document";
export { canEditAtom, notebookOperationsAtom } from "./operations";
