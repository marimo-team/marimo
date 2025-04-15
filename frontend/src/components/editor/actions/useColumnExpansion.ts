/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "@/core/cells/cells";
import { getNotebook } from "@/core/cells/cells";
import { useCallback } from "react";
import { canCollapseOutline } from "@/core/dom/outline";

/**
 * Hooks to collapse and expand all columns in the notebook.
 */

export const useCollapseAllColumns = () => {
  const { collapseCell } = useCellActions();

  return useCallback(async () => {
    const notebook = getNotebook();
    const cellIds = notebook.cellIds.inOrderIds;

    // Find all markdown cells that aren't already hidden
    for (const cellId of cellIds) {
        const outline = notebook.cellRuntime[cellId].outline
        // Check if the cell is a markdown cell with a TOC outline
        if (!outline) {
          continue;
        }
        // Check if the cell is a collapsible header
        if (!canCollapseOutline(outline)) {
          continue;
        }
        // Collapse the cell
        collapseCell({cellId});
    }
  }, []);
};

export const useExpandAllColumns = () => {
  const { expandCell } = useCellActions();

  return useCallback(async () => {
    const notebook = getNotebook();
    const cellIds = notebook.cellIds.inOrderIds;

    // Find all markdown cells that aren't already hidden
    for (const cellId of cellIds) {
        const outline = notebook.cellRuntime[cellId].outline
        // Check if the cell is a markdown cell with a TOC outline
        if (!outline) {
          continue;
        }
        // Check if the cell is a collapsible header
        if (!canCollapseOutline(outline)) {
          continue;
        }
        // Collapse the cell
        expandCell({cellId});

    }
  }, []);
}
