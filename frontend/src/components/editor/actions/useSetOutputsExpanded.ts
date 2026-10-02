/* Copyright 2026 Marimo. All rights reserved. */

import { useCallback } from "react";
import {
  getNotebook,
  type NotebookState,
  useCellActions,
} from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import { useRequestClient } from "@/core/network/requests";
import type { CellConfig } from "@/core/network/types";
import { Objects } from "@/utils/objects";

/**
 * The `expand_output` config changes needed to expand or clamp every output.
 *
 * Both actions skip cells without output, so their source isn't annotated
 * with a config that has no effect.
 */
export function outputExpansionConfigs(
  notebook: NotebookState,
  expanded: boolean,
): Record<CellId, Partial<CellConfig>> {
  const configs: Record<CellId, Partial<CellConfig>> = {};
  for (const cellId of notebook.cellIds.inOrderIds) {
    const cell = notebook.cellData[cellId];
    if (
      cell === undefined ||
      (cell.config.expand_output ?? false) === expanded
    ) {
      continue;
    }
    if (isOutputEmpty(notebook.cellRuntime[cellId]?.output)) {
      continue;
    }
    configs[cellId] = { expand_output: expanded };
  }
  return configs;
}

/**
 * Hook returning a callback that shows every cell's output in full, or clamps
 * every output to a fixed height, by setting each cell's `expand_output` config.
 */
export const useSetOutputsExpanded = () => {
  const { updateCellConfig } = useCellActions();
  const { saveCellConfig } = useRequestClient();

  return useCallback(
    async (expanded: boolean) => {
      const newConfigs = outputExpansionConfigs(getNotebook(), expanded);

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
