/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "@/core/cells/cells";
import { getNotebook } from "@/core/cells/cells";
import { saveCellConfig } from "@/core/network/requests";
import { useCallback } from "react";
import { MarkdownLanguageAdapter } from "@/core/codemirror/language/markdown";
import type { CellId } from "@/core/cells/ids";
import type { CellConfig } from "@/core/network/types";
import { Objects } from "@/utils/objects";

/**
 * Hook to hide all markdown code cells
 */
export const useHideAllMarkdownCode = () => {
  const { updateCellConfig } = useCellActions();

  return useCallback(async () => {
    const markdownAdapter = new MarkdownLanguageAdapter();
    const notebook = getNotebook();
    const cellIds = notebook.cellIds.inOrderIds;

    const newConfigs: Record<CellId, Partial<CellConfig>> = {};

    // Find all markdown cells that aren't already hidden
    for (const cellId of cellIds) {
      if (notebook.cellData[cellId] === undefined) {
        continue;
      }
      const { code, config } = notebook.cellData[cellId];
      if (config.hide_code) {
        continue;
      }
      if (markdownAdapter.isSupported(code)) {
        newConfigs[cellId] = { hide_code: true };
      }
    }

    const entries = Objects.entries(newConfigs);

    if (entries.length === 0) {
      return;
    }

    // Save to backend
    await saveCellConfig({ configs: newConfigs });

    // Update on frontend
    for (const [cellId, config] of entries) {
      updateCellConfig({ cellId, config });
    }
  }, [updateCellConfig]);
};
