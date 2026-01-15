/* Copyright 2026 Marimo. All rights reserved. */
import { useCallback, useEffect, useRef } from "react";
import { useEventListener } from "./useEventListener";

/**
 * Creates an interval that runs a callback every `delayMs` milliseconds.
 *
 * @param callback - The callback to run.
 * @param opts - The options for the interval.
 * @param opts.delayMs - The delay in milliseconds between runs.
 * @param opts.whenVisible - Whether to run the callback when the document is visible.
 * @param opts.disabled - Whether to disable the interval.
 * @param opts.skipIfRunning - Whether to skip the callback if it is already running.
 */
export function useInterval(
  callback: () => void,
  opts: {
    delayMs: number | null;
    whenVisible: boolean;
    disabled?: boolean;
    skipIfRunning?: boolean;
  },
) {
  const {
    delayMs,
    whenVisible,
    disabled = false,
    skipIfRunning = false,
  } = opts;
  const savedCallback = useRef<() => void | Promise<void>>(undefined);
  const isRunning = useRef(false);

  // Store the callback
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  const runCallback = useCallback(async () => {
    if (isRunning.current && skipIfRunning) {
      return;
    }
    isRunning.current = true;
    try {
      await savedCallback.current?.();
    } finally {
      isRunning.current = false;
    }
  }, [skipIfRunning]);

  // Run the interval
  useEffect(() => {
    if (delayMs === null || disabled) {
      return;
    }

    const id = setInterval(() => {
      if (whenVisible && document.visibilityState !== "visible") {
        return;
      }

      runCallback();
    }, delayMs);

    return () => clearInterval(id);
  }, [delayMs, whenVisible, disabled, runCallback]);

  // When the document becomes visible, run the callback
  useEventListener(document, "visibilitychange", () => {
    if (document.visibilityState === "visible" && whenVisible && !disabled) {
      runCallback();
    }
  });

  return null;
}
