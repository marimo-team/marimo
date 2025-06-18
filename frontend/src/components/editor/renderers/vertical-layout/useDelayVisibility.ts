/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import type { AppMode } from "@/core/mode";
import { useOnMount } from "@/hooks/useLifecycle";

export function useDelayVisibility(numCells: number, mode: AppMode) {
  // Start the app as invisible and delay proportional to the number of cells,
  // to avoid most of the flickering when the app is loaded (b/c it is
  // streamed).
  const [invisible, setInvisible] = useState(true);
  useOnMount(() => {
    // Only do this on read mode
    if (mode !== "read") {
      return;
    }

    const delay = Math.max(Math.min((numCells - 1) * 15, 100), 0);
    const timeout = setTimeout(() => {
      setInvisible(false);
    }, delay);
    return () => clearTimeout(timeout);
    // Delay only when app is first loaded
  });

  return { invisible };
}
