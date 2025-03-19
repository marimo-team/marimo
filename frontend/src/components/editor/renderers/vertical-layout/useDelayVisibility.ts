/* Copyright 2024 Marimo. All rights reserved. */
import type { AppMode } from "@/core/mode";
import { getNotebook } from "@/core/cells/cells";
import { useState } from "react";
import { Logger } from "@/utils/Logger";
import type { CellId } from "@/core/cells/ids";
import { useOnMount } from "@/hooks/useLifecycle";

export function useDelayVisibility(numCells: number, mode: AppMode) {
  // Start the app as invisible and delay proportional to the number of cells,
  // to avoid most of the flickering when the app is loaded (b/c it is
  // streamed). Delaying also helps prevent cell editors from stealing focus.
  const [invisible, setInvisible] = useState(true);
  useOnMount(() => {
    const delay = Math.max(Math.min((numCells - 1) * 15, 100), 0);
    const timeout = setTimeout(() => {
      setInvisible(false);
      // After 1 frame, either focus on the cell from URL or the first cell
      if (mode !== "read") {
        requestAnimationFrame(() => {
          // Check if the URL contains a scrollTo parameter
          const hash = window.location.hash;
          const cellName = extractCellNameFromHash(hash);

          if (cellName) {
            // If we have a scrollTo parameter, focus on that cell
            focusCellByName(cellName);
          } else {
            // Otherwise focus on the first cell
            focusFirstEditor();
          }
        });
      }
    }, delay);
    return () => clearTimeout(timeout);
    // Delay only when app is first loaded
  });

  return { invisible };
}

function focusFirstEditor() {
  const { cellIds, cellData, cellHandles } = getNotebook();
  // Focus on the first cell if it's been mounted and is not hidden
  for (const cellId of cellIds.iterateTopLevelIds) {
    const handle = cellHandles[cellId];
    const hidden = cellData[cellId].config.hide_code;
    if (!hidden && handle?.current?.editorView) {
      handle.current.editorView.focus();
      return;
    }
  }
}

/**
 * Focus the cell with the given name
 */
function focusCellByName(cellName: string) {
  // Find the cell div with data-cell-name attribute matching the cellName
  const cellElement = document.querySelector(`[data-cell-name="${cellName}"]`);

  if (cellElement) {
    // Scroll the element into view
    cellElement.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });

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

function extractCellNameFromHash(hash: string) {
  const scrollToMatch = hash.match(/scrollTo=([^&]+)/);
  const cellName = scrollToMatch?.[1];
  if (cellName) {
    return cellName.split("&")[0];
  }
  return null;
}

export const exportedForTesting = {
  extractCellNameFromHash,
};
