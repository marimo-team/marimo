/* Copyright 2024 Marimo. All rights reserved. */
import { type Atom, atom, createStore, useStore } from "jotai";
import { isEqual } from "lodash-es";
import { useEffect } from "react";

/**
 * Global store allows getting and setting global state outside of React components.
 */
export const store = createStore();
export type JotaiStore = typeof store;

/**
 * Wait for an atom to satisfy a predicate.
 */
export async function waitFor<T>(
  atom: Atom<T>,
  predicate: (value: T) => boolean,
) {
  if (predicate(store.get(atom))) {
    return store.get(atom);
  }

  return new Promise<T>((resolve) => {
    const unsubscribe = store.sub(atom, () => {
      const value = store.get(atom);
      if (predicate(value)) {
        unsubscribe();
        resolve(value);
      }
    });
  });
}

/**
 * Create a Jotai effect that runs when an atom changes.
 */
export function useJotaiEffect<T>(
  atom: Atom<T>,
  effect: (value: T, prevValue: T) => void,
) {
  const store = useStore();
  useEffect(() => {
    let prevValue = store.get(atom);
    store.sub(atom, () => {
      const value = store.get(atom);
      effect(value, prevValue);
      prevValue = value;
    });
  }, [atom, effect, store]);
}

const sentinel = Symbol("sentinel");

export function createDeepEqualAtom<T>(
  baseAtom: Atom<T>,
  areEqual: (a: T, b: T) => boolean = isEqual,
) {
  let cachedValue: T | typeof sentinel = sentinel;

  return atom((get) => {
    const nextValue = get(baseAtom);

    if (cachedValue === sentinel || !areEqual(cachedValue, nextValue)) {
      cachedValue = nextValue;
    }

    return cachedValue;
  });
}
