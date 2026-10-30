/* Copyright 2026 Marimo. All rights reserved. */

import { useCallback } from "react";
import { getNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { useNotebookDocumentEdit } from "@/core/notebook/document";
import type { CellConfig } from "@/core/network/types";
import { Objects } from "@/utils/objects";

const markdownAdapter = new MarkdownLanguageAdapter();

/** The kind of cell a visibility change applies to. */
export type CellCodeKind = "code" | "markdown";

const cellCodeKind = (code: string): CellCodeKind =>
  markdownAdapter.isSupported(code) ? "markdown" : "code";

/**
 * Hook returning a callback that hides or shows the code editor for every
 * cell of the given kind.
 */
export const useSetCodeVisibility = () => {
  const edit = useNotebookDocumentEdit();

  return useCallback(
    (hidden: boolean, kind: CellCodeKind) => {
      const notebook = getNotebook();

      const newConfigs: Record<CellId, Partial<CellConfig>> = {};

      for (const cellId of notebook.cellIds.inOrderIds) {
        const cell = notebook.cellData[cellId];
        if (cell === undefined || cell.config.hide_code === hidden) {
          continue;
        }
        if (cellCodeKind(cell.code) !== kind) {
          continue;
        }
        newConfigs[cellId] = { hide_code: hidden };
      }

      const entries = Objects.entries(newConfigs);
      if (entries.length === 0) {
        return;
      }

      edit((tx) => {
        for (const [cellId, config] of entries) {
          tx.updateConfig(cellId, config);
        }
      });
    },
    [edit],
  );
};
