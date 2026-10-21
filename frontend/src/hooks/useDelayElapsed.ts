/* Copyright 2026 Marimo. All rights reserved. */

import { useLayoutEffect, useState } from "react";

/**
 * Returns `false` until `delayMs` has elapsed since mount (or since `delayMs`
 * last changed), then `true`. Resolves to `true` immediately when
 * `delayMs <= 0`. Useful for suppressing spinner/fallback flashes.
 */
export function useDelayElapsed(delayMs: number): boolean {
  const [timer, setTimer] = useState({ delayMs, elapsed: delayMs <= 0 });

  if (!Object.is(timer.delayMs, delayMs)) {
    setTimer({ delayMs, elapsed: delayMs <= 0 });
  }

  useLayoutEffect(() => {
    if (delayMs <= 0) {
      return;
    }
    const timeout = setTimeout(
      () => setTimer({ delayMs, elapsed: true }),
      delayMs,
    );
    return () => clearTimeout(timeout);
  }, [delayMs]);

  return Object.is(timer.delayMs, delayMs) ? timer.elapsed : delayMs <= 0;
}
