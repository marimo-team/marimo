/* Copyright 2023 Marimo. All rights reserved. */
import { CellState } from "@/core/model/cells";
import { useState, useEffect } from "react";

export function useDelayVisibility(cells: CellState[]) {
  // Start the app as invisible and delay proportional to the number of cells,
  // to avoid most of the flickering when the app is loaded (b/c it is
  // streamed). Delaying also helps prevent cell editors from stealing focus.
  const [invisible, setInvisible] = useState(true);
  useEffect(() => {
    const delay = Math.max(Math.min((cells.length - 1) * 15, 100), 0);
    const timeout = setTimeout(() => {
      setInvisible(false);
      // After 1 frame, focus on the first cell if it's been mounted
      requestAnimationFrame(() => {
        cells[0]?.ref.current?.editorView.focus();
      });
    }, delay);
    return () => clearTimeout(timeout);
    // Delay only when app is first loaded
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { invisible };
}
