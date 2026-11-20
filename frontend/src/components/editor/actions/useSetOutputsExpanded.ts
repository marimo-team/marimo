/* Copyright 2026 Marimo. All rights reserved. */

import { useStore } from "jotai";
import { useCallback } from "react";
import { getNotebook, type NotebookState } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { isOutputEmpty } from "@/core/cells/outputs";
import { type CellOutput, cellOutputAtom } from "@/core/executions";
import { useNotebookDocumentEdit } from "@/core/notebook/document";
import type { CellConfig } from "@/core/network/types";
import { Objects } from "@/utils/objects";

/**
 * The `expand_output` config changes needed to expand or clamp every output.
 */
export function outputExpansionConfigs(
  notebook: Pick<NotebookState, "cellIds" | "cellData">,
  outputOf: (cellId: CellId) => CellOutput | null,
  expanded: boolean,
): Record<CellId, Partial<CellConfig>> {
  const configs: Record<CellId, Partial<CellConfig>> = {};
  for (const cellId of notebook.cellIds) {
    const cell = notebook.cellData[cellId];
    if (
      cell === undefined ||
      (cell.config.expand_output ?? false) === expanded
    ) {
      continue;
    }
    if (expanded && isOutputEmpty(outputOf(cellId))) {
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
  const edit = useNotebookDocumentEdit();
  const store = useStore();

  return useCallback(
    (expanded: boolean) => {
      const entries = Objects.entries(
        outputExpansionConfigs(
          getNotebook(),
          (cellId) => store.get(cellOutputAtom(cellId)),
          expanded,
        ),
      );
      if (entries.length === 0) {
        return;
      }

      edit((tx) => {
        for (const [cellId, config] of entries) {
          tx.updateConfig(cellId, config);
        }
      });
    },
    [edit, store],
  );
};
