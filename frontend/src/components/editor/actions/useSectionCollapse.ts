/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "@/core/cells/cells";
import useEvent from "react-use-event-hook";

/**
 * Hooks to collapse and expand all sections in the notebook.
 */

export const useSectionCollapse = () => {
  const { collapseAllCells, expandAllCells } = useCellActions();

  return {
    collapseAllSections: useEvent(() => collapseAllCells()),
    expandAllSections: useEvent(() => expandAllCells()),
  };
};
