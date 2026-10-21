/* Copyright 2026 Marimo. All rights reserved. */
import { type SetStateAction, useCallback, useState } from "react";

/**
 * Local state that resets when its owner key changes (compared with Object.is).
 * The initializer runs on mount and key changes. Setters captured for another
 * key cannot update the current owner's state.
 */
export function useStateForKey<T>(key: unknown, initialize: () => T) {
  const [stored, setStored] = useState(() => ({ key, value: initialize() }));
  const current = Object.is(stored.key, key)
    ? stored
    : { key, value: initialize() };
  if (current !== stored) {
    setStored(current);
  }

  const setValue = useCallback(
    (update: SetStateAction<T>) => {
      setStored((previous) => {
        if (!Object.is(previous.key, key)) {
          return previous;
        }
        const value =
          typeof update === "function"
            ? (update as (previous: T) => T)(previous.value)
            : update;
        return Object.is(previous.value, value) ? previous : { key, value };
      });
    },
    [key],
  );

  return [current.value, setValue] as const;
}
