/* Copyright 2026 Marimo. All rights reserved. */

/** Save the host's document from React. */

import { useAtomValue } from "jotai";
import { useCallback } from "react";
import { useNotebookDocumentSync } from "@/core/notebook/document";
import { activeNotebookBackendAtom } from "../session/active-notebook";

/**
 * Save the notebook's document through its host. This client's edits are
 * flushed first, so the host writes nothing older than what the editor
 * shows, and a failure at either step rejects.
 *
 * ```ts
 * const saveDocument = useNotebookDocumentSave();
 * await saveDocument();
 * ```
 */
export function useNotebookDocumentSave() {
  const { flush } = useNotebookDocumentSync();
  const backend = useAtomValue(activeNotebookBackendAtom);
  return useCallback(async () => {
    if (backend === null) {
      throw new Error("The notebook is not connected");
    }
    const { notebook_id } = await flush();
    const result = await backend.notebook(notebook_id).save();
    if (!result.ok) {
      throw new Error(result.problem.detail ?? result.problem.title);
    }
  }, [flush, backend]);
}
