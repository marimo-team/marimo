/* Copyright 2026 Marimo. All rights reserved. */

import { type Atom, useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { useMemo } from "react";

/**
 * Define at module scope to subscribe to one keyed slice of immutable state.
 *
 * The selector should return a primitive or a structurally shared value.
 * Each mounted hook owns its atom; no global key cache needs eviction.
 * This isolates renders, but selectors still run when the source changes:
 * reducers must preserve state identity for no-op actions.
 */
export function createKeyedSelectorHook<State, Key, Slice>(
  source: Atom<State>,
  select: (state: State, key: Key) => Slice,
) {
  return function useKeyedSelector(key: Key): Slice {
    const selected = useMemo(
      () => selectAtom(source, (state) => select(state, key)),
      [key],
    );
    return useAtomValue(selected);
  };
}
