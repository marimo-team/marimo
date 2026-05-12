/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useState } from "react";

/**
 * Returns `false` until `delayMs` has elapsed since mount (or since `delayMs`
 * last changed), then `true`. Resolves to `true` immediately when
 * `delayMs <= 0`. Useful for suppressing spinner/fallback flashes.
 */
export function useDelayElapsed(delayMs: number): boolean {
  const [elapsed, setElapsed] = useState(delayMs <= 0);

  useEffect(() => {
    if (delayMs <= 0) {
      setElapsed(true);
      return;
    }
    setElapsed(false);
    const timeout = setTimeout(() => setElapsed(true), delayMs);
    return () => clearTimeout(timeout);
  }, [delayMs]);

  return elapsed;
}
