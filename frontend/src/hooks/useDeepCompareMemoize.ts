/* Copyright 2026 Marimo. All rights reserved. */

import { dequal } from "dequal";
import React from "react";

/**
 * Deep compare memoize hook
 *
 * Useful when you want to memoize a react hook that has an object as a dependency
 * that you want to compare by value instead of reference.
 *
 * Useful when the re-render if more expensive than the deep compare.
 */
export function useDeepCompareMemoize<T>(value: T) {
  const [memoized, setMemoized] = React.useState(() => value);

  if (!dequal(value, memoized)) {
    setMemoized(() => value);
    return value;
  }

  return memoized;
}
