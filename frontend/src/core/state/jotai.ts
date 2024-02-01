/* Copyright 2024 Marimo. All rights reserved. */
import { Atom, createStore } from "jotai";

/**
 * Global store allows getting and setting global state outside of React components.
 */
export const store = createStore();

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
