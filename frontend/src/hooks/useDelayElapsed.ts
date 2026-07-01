/* Copyright 2026 Marimo. All rights reserved. */

import { useLayoutEffect, useState } from "react";

/**
 * Returns `false` until `delayMs` has elapsed since mount (or since `delayMs`
 * last changed), then `true`. Resolves to `true` immediately when
 * `delayMs <= 0`. Useful for suppressing spinner/fallback flashes.
 */
export function useDelayElapsed(delayMs: number): boolean {
  const [elapsed, setElapsed] = useState(delayMs <= 0);

  // Layout effect (not a plain effect) so that when `delayMs` flips from `<= 0`
  // to `> 0` — e.g. a gate re-closing — we reset `elapsed` to `false` before
  // the browser paints, rather than briefly flashing the fallback for a frame.
  useLayoutEffect(() => {
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
