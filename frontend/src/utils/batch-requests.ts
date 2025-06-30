/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Debounces multiple calls to a loader function, returning the same promise for
 * all calls with the same key.
 */
export function batch<T, REQ extends unknown[]>(
  loader: (...args: REQ) => Promise<T>,
  toKey: (...args: REQ) => string,
) {
  const requestCache = new Map<string, Promise<T>>();

  return (...args: REQ): Promise<T> => {
    const key = toKey(...args);
    if (requestCache.has(key)) {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      return requestCache.get(key)!;
    }

    const requestPromise = loader(...args).finally(() => {
      requestCache.delete(key);
    });

    requestCache.set(key, requestPromise);
    return requestPromise;
  };
}
