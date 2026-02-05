/* Copyright 2026 Marimo. All rights reserved. */
import { useEffect, useRef } from "react";

/**
 * A hook that skips running a callback on the first render,
 * then executes it on subsequent renders when dependencies change.
 *
 * @param callback - Function to execute after first render
 * @param deps - Dependencies that trigger the callback when changed
 */
export function useEffectSkipFirstRender(
  callback: () => void,
  deps: React.DependencyList,
) {
  const hasRendered = useRef(false);

  useEffect(() => {
    if (!hasRendered.current) {
      hasRendered.current = true;
      return;
    }
    callback();
  }, deps);
}
