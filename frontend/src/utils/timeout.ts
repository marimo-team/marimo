/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "./Logger";

/**
 * Retry a function with a timeout.
 * @param fn - The function to retry.
 * @param opts.retries - The number of times to retry.
 * @param opts.delay - The delay between retries.
 * @param opts.initialDelay - The initial delay before the first retry.
 */
export function retryWithTimeout(
  fn: () => boolean,
  opts: { retries: number; delay: number; initialDelay?: number },
) {
  const { retries, delay, initialDelay = 0 } = opts;

  let attempts = 0;
  const retry = () => {
    if (attempts < retries) {
      try {
        if (fn()) {
          return;
        }
      } catch (error) {
        Logger.error("Error executing function, retrying", {
          error,
          attempts,
        });
      }

      attempts++;
      setTimeout(retry, delay);
    }
  };

  if (initialDelay > 0) {
    setTimeout(retry, initialDelay);
  } else {
    retry();
  }
}
