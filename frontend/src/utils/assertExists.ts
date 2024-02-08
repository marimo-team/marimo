/* Copyright 2024 Marimo. All rights reserved. */
export function assertExists<T>(
  x: T | null | undefined,
  message?: string,
): asserts x is T {
  if (x === undefined || x === null) {
    if (message) {
      throw new Error(message);
    }
    throw new Error(`Expected value but got ${x}`);
  }
}
