/* Copyright 2024 Marimo. All rights reserved. */

import { getNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { useOnMount } from "@/hooks/useLifecycle";
import { extractCellNameFromHash } from "@/utils/cell-urls";
import { Logger } from "@/utils/Logger";

/**
 * Focus the first editor.
 *
 * If the URL contains a /#scrollTo= hash, focus on that cell.
 * Otherwise, focus on the first non-hidden cell.
 */
export function useFocusFirstEditor() {
  useOnMount(() => {
    const delay = 100; // ms just so its not immediate

    const timeout = setTimeout(() => {
      // Let the DOM render
      requestAnimationFrame(() => {
        // Check if the URL contains a scrollTo parameter
        const hash = globalThis.location.hash;
        const cellName = extractCellNameFromHash(hash);

        if (cellName) {
          // If we have a scrollTo parameter, focus on that cell
          focusCellByName(cellName);
        } else {
          // Otherwise focus on the first cell
          try {
            focusFirstEditor();
          } catch (error) {
            Logger.warn("Error focusing first editor", error);
          }
        }
      });
    }, delay);

    return () => clearTimeout(timeout);
    // Delay only when app is first loaded
  });
}

function focusFirstEditor() {
  const { cellIds, cellData, cellHandles } = getNotebook();

  // Focus on the first cell if it's been mounted and is not hidden
  for (const cellId of cellIds.iterateTopLevelIds) {
    const handle = cellHandles[cellId];
    const hidden = cellData[cellId]?.config.hide_code;
    if (!hidden && handle?.current?.editorView) {
      handle.current.editorView.focus();
      return;
    }
  }
}

let hasScrolledToCell = false;

/**
 * Focus the cell with the given name
 */
function focusCellByName(cellName: string) {
  // Only do this once per page load
  if (hasScrolledToCell) {
    return;
  }

  // Find the cell div with data-cell-name attribute matching the cellName
  const cellElement = document.querySelector(`[data-cell-name="${cellName}"]`);

  if (cellElement) {
    // Scroll the element into view
    cellElement.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });

    hasScrolledToCell = true;

    // Try to focus the cell
    if (cellElement instanceof HTMLElement) {
      cellElement.focus();

      // Look for an editor to focus
      const { cellHandles } = getNotebook();
      const cellId = cellElement.dataset.cellId as CellId | undefined;

      if (!cellId) {
        Logger.error(`Missing cellId for cell with name ${cellName}`);
        return;
      }

      const editor = cellHandles[cellId]?.current?.editorView;
      if (editor) {
        editor.focus();
      }
    }
  } else {
    Logger.warn(
      `Cannot focus cell with name ${cellName} because it was not found`,
    );
    // Fall back to focusing the first editor if cell not found
    focusFirstEditor();
  }
}
