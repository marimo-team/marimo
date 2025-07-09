/* Copyright 2024 Marimo. All rights reserved. */
export function retryWithTimeout(
  fn: () => boolean,
  opts: { retries: number; delay: number },
) {
  const { retries, delay } = opts;

  let attempts = 0;
  const retry = () => {
    if (attempts < retries && !fn()) {
      attempts++;
      setTimeout(retry, delay);
    }
  };
  setTimeout(retry, delay);
}
