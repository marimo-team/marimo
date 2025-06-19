/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import type { AppMode } from "@/core/mode";
import { useOnMount } from "@/hooks/useLifecycle";
import { clamp } from "@/utils/math";

const DELAY_PER_CELL = 30; // ms

export function useDelayVisibility(numCells: number, mode: AppMode) {
  // Start the app as invisible and delay proportional to the number of cells,
  // to avoid most of the flickering when the app is loaded (b/c it is
  // streamed).
  const [invisible, setInvisible] = useState(true);
  useOnMount(() => {
    // Only do this on read mode
    if (mode !== "read") {
      setInvisible(false);
      return;
    }

    // linear with cells, at min 100ms and at most 2s
    const delay = clamp((numCells - 1) * DELAY_PER_CELL, 100, 2000);
    const timeout = setTimeout(() => {
      setInvisible(false);
    }, delay);
    return () => clearTimeout(timeout);
    // Delay only when app is first loaded
  });

  return { invisible };
}
