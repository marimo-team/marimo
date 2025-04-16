/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "@/core/cells/cells";
import { getNotebook } from "@/core/cells/cells";
import { canCollapseOutline } from "@/core/dom/outline";
import useEvent from "react-use-event-hook";

/**
 * Hooks to collapse and expand all sections in the notebook.
 */

export const useSectionCollapse = () => {
  const { collapseCell, expandCell } = useCellActions();

  const processAllSections = async (action: 'collapse' | 'expand') => {
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
      // Collapse or expand the cell based on the action
      action === 'collapse' ? collapseCell({ cellId }) : expandCell({ cellId });
    };
  }

  return {
    collapseAllSections: useEvent(() => processAllSections('collapse')),
    expandAllSections: useEvent(() => processAllSections('expand')),
  }
}
