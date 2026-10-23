/* Copyright 2026 Marimo. All rights reserved. */
import { useState } from "react";

type EqualityFn<T> = (a: T, b: T) => boolean;

const defaultEqualityFn = <T>(a: T, b: T) => a === b;

/**
 * A hook that holds state that is synced with outside state.
 * If the outside state changes, the internal state is updated.
 */
export function useInternalStateWithSync<T>(
  initial: T,
  equalityFn: EqualityFn<T> = defaultEqualityFn,
) {
  const [state, setState] = useState(() => initial);
  const [previousInitial, setPreviousInitial] = useState(() => initial);

  // Whenever the outside state changes, update the internal state
  if (!equalityFn(previousInitial, initial)) {
    setState(() => initial);
    setPreviousInitial(() => initial);
  }

  return [state, setState] as const;
}
