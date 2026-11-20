/* Copyright 2026 Marimo. All rights reserved. */
import { useDelayElapsed } from "@/hooks/useDelayElapsed";

const DELAY_MS = 200;

/**
 * Returns true if the interrupt button should be shown.
 * This is based on the cell's running state and how long it has been running.
 */
export function useShouldShowInterrupt(running: boolean) {
  // Start a timer when the run starts.
  // After 200ms, show the interrupt button to avoid flickering.
  const hasRunLongEnough = useDelayElapsed(running ? DELAY_MS : 0);

  return running && hasRunLongEnough;
}
