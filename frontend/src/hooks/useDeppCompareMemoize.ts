/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { dequal } from "dequal";

/**
 * Deep compare memoize hook
 *
 * Useful when you want to memoize a react hook that has an object as a dependency
 * that you want to compare by value instead of reference.
 *
 * Useful when the re-render if more expensive than the deep compare.
 */
export function useDeepCompareMemoize<T>(value: T) {
  const ref = React.useRef<T>(value);

  if (!dequal(value, ref.current)) {
    ref.current = value;
  }

  return ref.current;
}
