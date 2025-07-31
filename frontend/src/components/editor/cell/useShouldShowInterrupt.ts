/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useState } from "react";

const DELAY_MS = 200;

/**
 * Returns true if the interrupt button should be shown.
 * This is based on the cell's running state and how long it has been running.
 */
export function useShouldShowInterrupt(running: boolean) {
  // Start a timer when the run starts.
  // After 200ms, show the interrupt button to avoid flickering.
  const [hasRunLongEnough, setHasRunLongEnough] = useState(false);
  useEffect(() => {
    if (!running) {
      return;
    }
    setHasRunLongEnough(false);
    const timeout = setTimeout(() => {
      setHasRunLongEnough(true);
    }, DELAY_MS);
    return () => clearTimeout(timeout);
  }, [running]);

  return running && hasRunLongEnough;
}
