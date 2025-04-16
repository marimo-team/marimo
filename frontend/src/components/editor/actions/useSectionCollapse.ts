/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "@/core/cells/cells";
import { getNotebook } from "@/core/cells/cells";
import { canCollapseOutline } from "@/core/dom/outline";
import useEvent from "react-use-event-hook";

/**
 * Hooks to collapse and expand all sections in the notebook.
 */

const useCollapseAllSections = () => {
  const { collapseCell } = useCellActions();

  return useEvent(async () => {
    const notebook = getNotebook();
    const cellIds = notebook.cellIds.inOrderIds;

    // Find all markdown cells that aren't already hidden
    for (const cellId of cellIds) {
      const outline = notebook.cellRuntime[cellId].outline;
      // Check if the cell is a markdown cell with a TOC outline
      if (!outline) {
        continue;
      }
      // Check if the cell is a collapsible header
      if (!canCollapseOutline(outline)) {
        continue;
      }
      // Collapse the cell
      collapseCell({ cellId });
    }
  });
};

const useExpandAllSections = () => {
  const { expandCell } = useCellActions();

  return useEvent(async () => {
    const notebook = getNotebook();
    const cellIds = notebook.cellIds.inOrderIds;

    // Find all markdown cells that aren't already hidden
    for (const cellId of cellIds) {
      const outline = notebook.cellRuntime[cellId].outline;
      // Check if the cell is a markdown cell with a TOC outline
      if (!outline) {
        continue;
      }
      // Check if the cell is a collapsible header
      if (!canCollapseOutline(outline)) {
        continue;
      }
      // Collapse the cell
      expandCell({ cellId });
    }
  });
};

// Consolidate the two hooks into one object
export const useSectionCollapse = () => {

  return {
    collapseAllSections: useCollapseAllSections(),
    expandAllSections: useExpandAllSections(),
  };
}
