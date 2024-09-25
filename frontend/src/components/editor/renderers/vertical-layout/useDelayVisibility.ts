/* Copyright 2024 Marimo. All rights reserved. */
import type { AppMode } from "@/core/mode";
import { getNotebook } from "@/core/cells/cells";
import { useState, useEffect } from "react";

export function useDelayVisibility(numCells: number, mode: AppMode) {
  // Start the app as invisible and delay proportional to the number of cells,
  // to avoid most of the flickering when the app is loaded (b/c it is
  // streamed). Delaying also helps prevent cell editors from stealing focus.
  const [invisible, setInvisible] = useState(true);
  useEffect(() => {
    const delay = Math.max(Math.min((numCells - 1) * 15, 100), 0);
    const timeout = setTimeout(() => {
      setInvisible(false);
      // After 1 frame, focus on the first cell if it's been mounted
      if (mode !== "read") {
        requestAnimationFrame(() => {
          focusFirstEditor();
        });
      }
    }, delay);
    return () => clearTimeout(timeout);
    // Delay only when app is first loaded
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { invisible };
}

function focusFirstEditor() {
  const { cellIds, cellData, cellHandles } = getNotebook();
  // Focus on the first cell if it's been mounted and is not hidden
  for (const cellId of cellIds.columns[0].topLevelIds) {
    const handle = cellHandles[cellId];
    const hidden = cellData[cellId].config.hide_code;
    if (!hidden && handle?.current?.editorView) {
      handle.current.editorView.focus();
      return;
    }
  }
}
