/* Copyright 2026 Marimo. All rights reserved. */

import { useCallback } from "react";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/languages/markdown";
import { useRequestClient } from "@/core/network/requests";
import type { CellConfig } from "@/core/network/types";
import { Objects } from "@/utils/objects";

interface SetCodeVisibilityOptions {
  /** When `true`, hide the code; when `false`, show it. */
  hidden: boolean;
  /** Restrict the change to markdown cells. */
  markdownOnly?: boolean;
}

/**
 * Hook returning a callback that hides or shows the code editor for every
 * cell, optionally restricted to markdown cells.
 */
export const useSetCodeVisibility = () => {
  const { updateCellConfig } = useCellActions();
  const { saveCellConfig } = useRequestClient();

  return useCallback(
    async ({ hidden, markdownOnly = false }: SetCodeVisibilityOptions) => {
      const markdownAdapter = new MarkdownLanguageAdapter();
      const notebook = getNotebook();

      const newConfigs: Record<CellId, Partial<CellConfig>> = {};

      for (const cellId of notebook.cellIds.inOrderIds) {
        const cell = notebook.cellData[cellId];
        if (cell === undefined) {
          continue;
        }
        const { code, config } = cell;
        if (config.hide_code === hidden) {
          continue;
        }
        if (markdownOnly && !markdownAdapter.isSupported(code)) {
          continue;
        }
        newConfigs[cellId] = { hide_code: hidden };
      }

      const entries = Objects.entries(newConfigs);
      if (entries.length === 0) {
        return;
      }

      await saveCellConfig({ configs: newConfigs });

      for (const [cellId, config] of entries) {
        updateCellConfig({ cellId, config });
      }
    },
    [updateCellConfig, saveCellConfig],
  );
};
