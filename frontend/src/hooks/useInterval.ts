/* Copyright 2024 Marimo. All rights reserved. */
import { useRef, useEffect } from "react";
import { useEventListener } from "./useEventListener";

/**
 * Creates an interval that runs a callback every `delayMs` milliseconds.
 */
export function useInterval(
  callback: () => void,
  opts: {
    delayMs: number | null;
    whenVisible: boolean;
    disabled?: boolean;
  },
) {
  const { delayMs, whenVisible, disabled = false } = opts;
  const savedCallback = useRef<() => void>(undefined);

  // Store the callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Run the interval
  useEffect(() => {
    if (delayMs === null || disabled) {
      return;
    }

    const id = setInterval(() => {
      if (whenVisible && document.visibilityState !== "visible") {
        return;
      }

      savedCallback.current?.();
    }, delayMs);

    return () => clearInterval(id);
  }, [delayMs, whenVisible, disabled]);

  // When the document becomes visible, run the callback
  useEventListener(document, "visibilitychange", () => {
    if (document.visibilityState === "visible" && whenVisible && !disabled) {
      savedCallback.current?.();
    }
  });

  return null;
}
