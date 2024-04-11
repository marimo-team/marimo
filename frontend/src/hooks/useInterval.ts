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
  },
) {
  const { delayMs, whenVisible } = opts;
  const savedCallback = useRef<() => void>();

  // Store the callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Run the interval
  useEffect(() => {
    if (delayMs === null) {
      return;
    }

    const id = setInterval(() => {
      if (whenVisible && document.visibilityState !== "visible") {
        return;
      }

      savedCallback.current?.();
    }, delayMs);

    return () => clearInterval(id);
  }, [delayMs, whenVisible]);

  // When the document becomes visible, run the callback
  useEventListener(document, "visibilitychange", () => {
    if (document.visibilityState === "visible" && whenVisible) {
      savedCallback.current?.();
    }
  });

  return null;
}
