/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useState } from "react";

/**
 * Returns `false` until `delayMs` has elapsed since mount (or since `delayMs`
 * last changed), then `true`. Resolves to `true` immediately when
 * `delayMs <= 0`. Useful for suppressing spinner/fallback flashes.
 */
export function useDelayElapsed(delayMs: number): boolean {
  const [timer, setTimer] = useState({ delayMs, elapsed: delayMs <= 0 });

  // Reset during render so a changed delay never commits a stale `elapsed`
  // (e.g. a gate re-closing shows no fallback flash before paint)
  if (!Object.is(timer.delayMs, delayMs)) {
    setTimer({ delayMs, elapsed: delayMs <= 0 });
  }

  useEffect(() => {
    if (delayMs <= 0) {
      return;
    }
    const timeout = setTimeout(
      () => setTimer({ delayMs, elapsed: true }),
      delayMs,
    );
    return () => clearTimeout(timeout);
  }, [delayMs]);

  return timer.elapsed;
}
