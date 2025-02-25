/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Schedule a callback to run when the browser is idle.
 *
 * @param callback - The callback to run when the browser is idle.
 */
export function onIdle(callback: () => void) {
  if ("scheduler" in window) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).scheduler.postTask(callback, {
      priority: "background",
    });
  } else if ("requestIdleCallback" in window) {
    requestIdleCallback(callback);
  } else {
    setTimeout(callback, 0);
  }
}
